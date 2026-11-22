"""Launch with uv run --extra evaluation streamlit run whereabouts/evaluation/streamlit_app.py."""

from __future__ import annotations

from collections import Counter
import json
import logging
from pathlib import Path
import re
import sqlite3

import duckdb
import pandas as pd
import streamlit as st

from whereabouts.evaluation.dataset import file_hash, import_csv
from whereabouts.evaluation.engine import RunConfig, compare_runs, load_run
from whereabouts.evaluation.reference import ReferenceFilters, lookup_reference
from whereabouts.evaluation.versions import (
    AlgorithmVersion,
    load_versions,
    register_version,
    run_version,
)

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "evaluation_runs"


class ErrorAnnotations:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, error_type TEXT NOT NULL
                )
            """)

    def save(self, run_id: str, case_id: str, error_type: str) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO errors(run_id, case_id, error_type) VALUES (?, ?, ?)",
                (run_id, case_id, error_type.strip()),
            )

    def latest(self, run_id: str) -> dict[str, str]:
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """
                SELECT case_id, error_type FROM errors WHERE id IN (
                    SELECT max(id) FROM errors WHERE run_id = ? GROUP BY case_id
                )
            """,
                (run_id,),
            ).fetchall()
        return dict(rows)


def result_frame(run: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "input_address": row["case"]["input_address"],
                "matched_address": row["selected"]["address"]
                if row["selected"]
                else "",
                "correct_address": " | ".join(
                    match["address"] or match["reference_id"] or match["locality"]
                    for match in row["case"]["acceptable"]
                ),
            }
            for row in run["rows"]
        ]
    )


def error_counts(run: dict, annotations: dict[str, str]) -> Counter[str]:
    return Counter(
        annotations.get(row["case"]["case_id"], "").strip() or "Unclassified"
        for row in run["rows"]
        if not row["agreement"]
    )


def show_error(exc: Exception) -> None:
    logger.exception("Streamlit evaluation operation failed")
    st.error(str(exc))


def choose_run(label: str, paths: list[Path], key: str) -> Path | None:
    return st.selectbox(
        label,
        [None, *paths],
        format_func=lambda p: p.stem if p else "Select a saved run",
        key=key,
    )


def resolve_reference(database: Path | None, custom_database: str) -> Path:
    reference = Path(custom_database).expanduser() if custom_database else database
    if reference is None:
        raise ValueError("Select a reference database snapshot")
    if custom_database and not reference.is_absolute():
        raise ValueError("Reference database path must be absolute")
    return reference.resolve()


def reference_lookup_tab(models: list[Path]) -> None:
    st.subheader("Reference address lookup")
    st.caption(
        "Street number and street name search whole tokens/phrases in the address label; "
        "lot number searches LOT followed by that number. Suburb is an exact, case-insensitive filter. "
        "All supplied filters must match."
    )
    st.warning(
        "These databases do not retain structured street/lot components. A street-number token can also "
        "be a unit, lot, postcode, or range endpoint. Use the spelling/abbreviations shown in the database; "
        "this is label searching, not address parsing or fuzzy matching."
    )
    database = (
        st.selectbox("Lookup reference database", models, format_func=lambda p: p.name)
        if models
        else None
    )
    custom = st.text_input("Lookup database path (absolute .db path)")
    with st.form("reference-lookup"):
        left, right = st.columns(2)
        street_number = left.text_input("Street number (label token)")
        lot_number = right.text_input("Lot number (after LOT)")
        street_name = left.text_input("Street name (label phrase)")
        suburb = right.text_input("Suburb (exact)")
        search = st.form_submit_button("Search reference database")
    if search:
        st.session_state.pop("reference_lookup", None)
        try:
            reference = resolve_reference(database, custom)
            filters = ReferenceFilters(street_number, lot_number, street_name, suburb)
            with st.spinner("Searching reference address labels..."):
                result = lookup_reference(reference, filters)
            st.session_state["reference_lookup"] = {
                "database": reference,
                "filters": filters,
                "page": 0,
                "result": result,
            }
        except (ValueError, OSError, duckdb.Error) as exc:
            show_error(exc)
    saved = st.session_state.get("reference_lookup")
    if not saved:
        return
    result, page = saved["result"], saved["page"]
    st.caption(f"Results from {saved['database']} using {saved['filters']}")
    st.metric("Matching reference addresses", result.total)
    if not result.total:
        st.info("No reference addresses agree with these filters.")
        return
    previous, following = st.columns(2)
    back = previous.button("Previous lookup page", disabled=page == 0)
    forward = following.button(
        "Next lookup page", disabled=(page + 1) * 100 >= result.total
    )
    if back or forward:
        try:
            next_page = page + (1 if forward else -1)
            with st.spinner("Loading reference results..."):
                result = lookup_reference(
                    saved["database"], saved["filters"], page=next_page
                )
            saved.update({"page": next_page, "result": result})
            st.rerun()
        except (ValueError, OSError, duckdb.Error) as exc:
            show_error(exc)
    st.caption(
        f"Showing {page * 100 + 1}-{page * 100 + len(result.rows)} of {result.total}. "
        "All results are available in pages of 100."
    )
    st.dataframe(result.rows, hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(page_title="Whereabouts evaluation", layout="wide")
    st.title("Address matching experiments")
    st.caption(
        "Trusted local code only. Pinned revisions execute in separate worktrees and environments."
    )
    RUNS.mkdir(parents=True, exist_ok=True)
    store = ErrorAnnotations(RUNS / "errors.sqlite3")
    registry = RUNS / "versions.json"
    try:
        versions = load_versions(registry)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        show_error(exc)
        st.stop()

    with st.sidebar:
        st.header("Algorithm versions")
        selected_version = st.selectbox(
            "Implementation version",
            [None, *versions],
            format_func=lambda v: (
                f"{v.name} ({v.commit[:10]})" if v else "Working copy"
            ),
        )
        with st.expander("Register a pinned revision"):
            st.caption(
                "The revision must already exist locally and contain the worker contract and uv.lock."
            )
            with st.form("register-version"):
                version_name = st.text_input("Version name")
                revision = st.text_input("Full Git commit SHA")
                add = st.form_submit_button("Register version")
            if add:
                try:
                    register_version(
                        ROOT, registry, AlgorithmVersion(version_name, revision)
                    )
                except (ValueError, RuntimeError, OSError) as exc:
                    show_error(exc)
                else:
                    st.rerun()
        if selected_version is None:
            st.caption(
                "Each run preserves a source snapshot, including uncommitted algorithm changes."
            )
        st.caption(
            "Historical environments may need dependency downloads on their first run."
        )

    matching, errors, comparison, lookup = st.tabs(
        ["Match addresses", "Error breakdown", "Compare saved runs", "Reference lookup"]
    )
    with matching:
        options = sorted((ROOT / "example_data").glob("*.csv"))
        default = next(
            (i for i, path in enumerate(options) if path.name == "test_set_au.csv"), 0
        )
        local_csv = (
            st.selectbox(
                "Repository CSV", options, index=default, format_func=lambda p: p.name
            )
            if options
            else None
        )
        upload = st.file_uploader("Or select an input CSV", type=["csv"])
        st.caption(
            "Required columns: input_address and best_match. An uploaded CSV takes precedence."
        )
        models = sorted((ROOT / "whereabouts/models").glob("*.db"))
        database = (
            st.selectbox(
                "Reference database snapshot", models, format_func=lambda p: p.name
            )
            if models
            else None
        )
        custom_database = st.text_input("Or an absolute path to another .db snapshot")
        algorithm = st.selectbox(
            "Matching algorithm", ["standard", "skipphrase", "trigram"]
        )
        experiment = st.text_input("Experiment name", value="Baseline")
        settings = st.columns(3)
        threshold = settings[0].number_input(
            "Acceptance threshold", min_value=0.0, max_value=1.0, value=0.5
        )
        top_k = settings[1].number_input(
            "Retained candidates", min_value=1, max_value=50, value=5
        )
        batch_size = settings[2].number_input("Batch size", min_value=1, value=500)
        if st.button("Match addresses", type="primary"):
            try:
                source = local_csv
                if upload is not None:
                    import hashlib

                    content = upload.getvalue()
                    source = (
                        RUNS / "inputs" / f"{hashlib.sha256(content).hexdigest()}.csv"
                    )
                    source.parent.mkdir(parents=True, exist_ok=True)
                    if not source.exists():
                        source.write_bytes(content)
                if source is None:
                    raise ValueError("Select an input CSV")
                reference = resolve_reference(database, custom_database)
                config = RunConfig(
                    "snapshot",
                    how=algorithm,
                    threshold=threshold,
                    top_k=int(top_k),
                    batch_size=int(batch_size),
                    reference_path=str(reference.resolve()),
                )
                dataset = RUNS / "datasets" / f"{file_hash(source)}.json"
                if not dataset.exists():
                    import_csv(source, dataset)
                with st.spinner("Preparing implementation and matching addresses…"):
                    path = run_version(
                        ROOT, RUNS, dataset, config, experiment, selected_version
                    )
                st.session_state["active_run"] = str(path)
            except (
                ValueError,
                RuntimeError,
                OSError,
                KeyError,
                TypeError,
                UnicodeError,
            ) as exc:
                show_error(exc)

        paths = sorted(
            path
            for path in RUNS.glob("*.json")
            if re.fullmatch(r"[a-f0-9]{32}", path.stem)
        )
        saved = choose_run("Open a saved run", paths, "open-run")
        if st.button("Load saved run", disabled=saved is None) and saved is not None:
            st.session_state["active_run"] = str(saved)
        active = st.session_state.get("active_run")
        if active:
            try:
                run = load_run(Path(active))
                annotations = store.latest(run["run_id"])
                st.session_state["displayed_run"] = run
                st.subheader(run.get("experiment", run["run_id"]))
                st.caption(f"Algorithm: {run['config']['how']} · Run: {run['run_id']}")
                total = len(run["rows"])
                correct = sum(row["agreement"] for row in run["rows"])
                counts = error_counts(run, annotations)
                distinct = len({label for label in counts if label != "Unclassified"})
                summary = st.columns(5)
                summary[0].metric("Total addresses", total)
                summary[1].metric(
                    "Correctly matched", f"{correct} ({correct / total:.1%})"
                )
                summary[2].metric(
                    "Unmatched / incorrect",
                    f"{total - correct} ({(total - correct) / total:.1%})",
                )
                summary[3].metric("Error types", distinct)
                summary[4].metric(
                    "Geocoding time", f"{run['timing']['measured_seconds']:.3f} s"
                )
                st.caption(
                    "Correct means agreement with the CSV label (case/whitespace normalized), not independently "
                    "verified accuracy. Incorrect includes missing and below-threshold results. "
                    f"Setup: {run['timing']['setup_seconds']:.3f} s; warm-up: "
                    f"{run['timing']['warmup_seconds']:.3f} s; total wall time: "
                    f"{run['timing'].get('wall_seconds', 0):.3f} s."
                )
                frame = result_frame(run)

                def shade(row: pd.Series) -> list[str]:
                    color = (
                        "#d4edda" if run["rows"][row.name]["agreement"] else "#f8d7da"
                    )
                    return [f"background-color: {color}; color: #111111"] * len(row)

                selection = st.dataframe(
                    frame.style.apply(shade, axis=1),
                    hide_index=True,
                    width="stretch",
                    on_select="rerun",
                    selection_mode="single-row",
                    key=f"results-{run['run_id']}",
                )
                if selection.selection.rows:
                    index = selection.selection.rows[0]
                    row = run["rows"][index]
                    case_id = row["case"]["case_id"]
                    st.caption(f"Selected input: {row['case']['input_address']}")
                    if not row["agreement"]:
                        with st.form(f"annotation-{run['run_id']}-{case_id}"):
                            error_type = st.text_input(
                                "Error type (free text)",
                                value=annotations.get(case_id, ""),
                                help="Leave empty to clear the classification.",
                            )
                            annotate = st.form_submit_button("Save error type")
                        if annotate:
                            store.save(run["run_id"], case_id, error_type)
                            st.rerun()
                    else:
                        st.info("This row agrees with its supplied label.")
                export = {
                    "schema_version": 1,
                    "run": run,
                    "error_annotations": annotations,
                }
                st.download_button(
                    "Save results (JSON)",
                    json.dumps(export, indent=2, allow_nan=False),
                    file_name=f"{run['run_id']}.json",
                    mime="application/json",
                )
                csv_frame = frame.assign(
                    correct=[row["agreement"] for row in run["rows"]],
                    error_type=[
                        annotations.get(row["case"]["case_id"], "")
                        for row in run["rows"]
                    ],
                )
                st.download_button(
                    "Save results (CSV)",
                    csv_frame.to_csv(index=False),
                    file_name=f"{run['run_id']}.csv",
                    mime="text/csv",
                )
                st.caption(
                    f"Run evidence and error annotations are also saved locally under {RUNS}."
                )
            except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
                show_error(exc)

    with errors:
        displayed = st.session_state.get("displayed_run")
        if displayed:
            counts = error_counts(displayed, store.latest(displayed["run_id"]))
            breakdown = pd.DataFrame(
                [
                    {
                        "error_type": label,
                        "count": count,
                        "percent_of_errors": count / sum(counts.values()) * 100,
                    }
                    for label, count in counts.most_common()
                ],
                columns=["error_type", "count", "percent_of_errors"],
            )
            st.dataframe(breakdown, hide_index=True)
            if counts:
                st.bar_chart(breakdown.set_index("error_type")["count"])
            else:
                st.success("All rows agree with their supplied labels.")
        else:
            st.info("Run or load an evaluation first.")

    with comparison:
        baseline = choose_run("Baseline", paths, "baseline")
        challenger = choose_run("Challenger", paths, "challenger")
        if baseline is not None and challenger is not None:
            try:
                before, after = load_run(baseline), load_run(challenger)
                result = compare_runs(before, after)
                changes = []
                for row in result["rows"]:
                    left, right = row["baseline"], row["challenger"]
                    changes.append(
                        {
                            "input_address": left["case"]["input_address"],
                            "baseline_address": left["selected"]["address"]
                            if left["selected"]
                            else "",
                            "challenger_address": right["selected"]["address"]
                            if right["selected"]
                            else "",
                            "baseline_correct": left["agreement"],
                            "challenger_correct": right["agreement"],
                        }
                    )
                regressions = sum(
                    row["baseline_correct"] and not row["challenger_correct"]
                    for row in changes
                )
                improvements = sum(
                    not row["baseline_correct"] and row["challenger_correct"]
                    for row in changes
                )
                st.write(
                    f"Label-agreement improvements: {improvements}; regressions: {regressions}."
                )
                if not result["timing_comparable"]:
                    st.warning(
                        "Timing settings differ: batch size or retained candidate count."
                    )
                st.dataframe(pd.DataFrame(changes), hide_index=True)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                show_error(exc)

    with lookup:
        reference_lookup_tab(models)


if __name__ == "__main__":
    main()
