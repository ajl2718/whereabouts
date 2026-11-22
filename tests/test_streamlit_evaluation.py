from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd
import duckdb
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from whereabouts.evaluation import streamlit_app as app
from whereabouts.evaluation.dataset import AcceptableMatch, EvaluationCase, write_json
from whereabouts.evaluation.engine import RunConfig, score_case


def example_run() -> dict:
    cases = [
        EvaluationCase(str(index), address, [AcceptableMatch(address="CORRECT")])
        for index, address in enumerate(["FIRST", "DUPLICATE", "DUPLICATE"])
    ]
    return {
        "schema_version": 1,
        "run_id": "a" * 32,
        "experiment": "Baseline",
        "config": asdict(RunConfig("test")),
        "timing": {
            "measured_seconds": 1.25,
            "setup_seconds": 0.1,
            "warmup_seconds": 0.2,
            "wall_seconds": 2,
        },
        "rows": [
            score_case(
                cases[0],
                [{"address": "correct", "score": 0.9, "reference_id": "1"}],
                0.5,
            ),
            score_case(
                cases[1], [{"address": "WRONG", "score": 0.9, "reference_id": "2"}], 0.5
            ),
            score_case(cases[2], [], 0.5),
        ],
    }


def test_annotations_are_run_specific_and_clearable(tmp_path: Path) -> None:
    run = example_run()
    store = app.ErrorAnnotations(tmp_path / "errors.sqlite3")
    store.save(run["run_id"], "1", " Wrong house number ")
    store.save("other run", "1", "Different error")
    assert app.error_counts(run, store.latest(run["run_id"])) == {
        "Wrong house number": 1,
        "Unclassified": 1,
    }
    store.save(run["run_id"], "1", "")
    assert app.error_counts(run, store.latest(run["run_id"])) == {"Unclassified": 2}
    frame = app.result_frame(run)
    assert list(frame.columns) == [
        "input_address",
        "matched_address",
        "correct_address",
    ]
    assert frame.iloc[2]["matched_address"] == ""


def test_streamlit_loads_results_metrics_error_breakdown_and_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app, "RUNS", tmp_path)
    run = example_run()
    path = tmp_path / f"{run['run_id']}.json"
    write_json(path, run)
    app.ErrorAnnotations(tmp_path / "errors.sqlite3").save(
        run["run_id"], "1", "Wrong number"
    )
    test = AppTest.from_string(
        "from whereabouts.evaluation.streamlit_app import main\nmain()"
    )
    test.session_state["active_run"] = str(path)
    test.run()
    assert not test.exception
    assert [tab.label for tab in test.tabs] == [
        "Match addresses",
        "Error breakdown",
        "Compare saved runs",
        "Reference lookup",
    ]
    assert {metric.label: metric.value for metric in test.metric} == {
        "Total addresses": "3",
        "Correctly matched": "1 (33.3%)",
        "Unmatched / incorrect": "2 (66.7%)",
        "Error types": "1",
        "Geocoding time": "1.250 s",
    }
    pd.testing.assert_frame_equal(test.dataframe[0].value, app.result_frame(run))
    assert "#d4edda" in test.dataframe[0].proto.arrow_data.styler.styles
    assert "#f8d7da" in test.dataframe[0].proto.arrow_data.styler.styles
    assert set(test.dataframe[1].value["error_type"]) == {
        "Wrong number",
        "Unclassified",
    }
    test.session_state[f"results-{run['run_id']}"] = {
        "selection": {"rows": [1], "columns": []}
    }
    test.run()
    assert not test.exception
    field = next(
        element
        for element in test.text_input
        if element.label == "Error type (free text)"
    )
    field.set_value("Wrong street")
    next(button for button in test.button if button.label == "Save error type").click()
    test.run()
    assert not test.exception
    assert (
        app.ErrorAnnotations(tmp_path / "errors.sqlite3").latest(run["run_id"])["1"]
        == "Wrong street"
    )


def test_match_button_imports_csv_runs_selected_configuration_and_saves_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "example_data").mkdir()
    (tmp_path / "whereabouts/models").mkdir(parents=True)
    csv = tmp_path / "example_data/test_set_au.csv"
    csv.write_text(
        "input_address,best_match\nFIRST,CORRECT\nDUPLICATE,CORRECT\nDUPLICATE,CORRECT\n"
    )
    (tmp_path / "whereabouts/models/reference.db").write_bytes(b"snapshot")
    nested = tmp_path / "whereabouts/models/snapshots"
    nested.mkdir()
    alternate = nested / "reference.db"
    alternate.write_bytes(b"alternate")
    runs = tmp_path / "runs"
    monkeypatch.setattr(app, "ROOT", tmp_path)
    monkeypatch.setattr(app, "RUNS", runs)
    calls = []

    def match(
        root: Path,
        output: Path,
        dataset: Path,
        config: RunConfig,
        experiment: str,
        version: object,
    ) -> Path:
        from whereabouts.evaluation.dataset import EvaluationDataset

        imported = EvaluationDataset.load(dataset)
        assert [case.input_address for case in imported.cases] == [
            "FIRST",
            "DUPLICATE",
            "DUPLICATE",
        ]
        assert len({case.case_id for case in imported.cases}) == 3
        calls.append((config, experiment, version))
        path = output / ("a" * 32 + ".json")
        write_json(path, example_run())
        return path

    monkeypatch.setattr(app, "run_version", match)
    test = AppTest.from_string(
        "from whereabouts.evaluation.streamlit_app import main\nmain()"
    ).run()
    approved = app.approved_reference_databases()
    selected_id = next(key for key, path in approved.items() if path == alternate)
    selector = next(
        field
        for field in test.selectbox
        if field.label == "Reference database snapshot"
    )
    assert selector.options == ["reference.db", "snapshots/reference.db"]
    selector.set_value(selected_id)
    assert (
        next(
            field
            for field in test.selectbox
            if field.label == "Lookup reference database"
        ).options
        == selector.options
    )
    assert not any(
        "database path" in field.label.lower() or ".db path" in field.label
        for field in test.text_input
    )
    next(button for button in test.button if button.label == "Match addresses").click()
    test.run()
    assert not test.exception
    assert not test.error
    assert calls[0][0].reference_path == str(alternate)
    assert calls[0][1:] == ("Baseline", None)
    assert len(test.metric) == 5

    csv.write_text("wrong_header,best_match\nFIRST,CORRECT\n")
    next(button for button in test.button if button.label == "Match addresses").click()
    test.run()
    assert not test.exception
    assert "input_address and best_match" in test.error[0].value
    assert len(calls) == 1


def test_reference_lookup_tab_works_without_an_evaluation_and_reports_invalid_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(app, "ROOT", tmp_path)
    models = tmp_path / "whereabouts/models"
    (models / "nested").mkdir(parents=True)
    with duckdb.connect(str(models / "nested/reference.db")) as con:
        con.execute("""
            CREATE TABLE addrtext_with_detail AS
            SELECT i AS addr_id, 'LOT 15 TEST ST' AS address_label, 'BRUNSWICK' AS suburb
            FROM range(1, 102) AS t(i)
        """)
    test = AppTest.from_string(
        "from whereabouts.evaluation.streamlit_app import main\nmain()"
    ).run()
    next(
        field for field in test.text_input if field.label == "Lot number (after LOT)"
    ).set_value("15")
    next(
        field for field in test.text_input if field.label == "Suburb (exact)"
    ).set_value("brunswick")
    next(
        button for button in test.button if button.label == "Search reference database"
    ).click()
    test.run()
    assert not test.exception
    assert not test.error
    assert (
        test.metric[0].label == "Matching reference addresses"
        and test.metric[0].value == "101"
    )
    assert test.dataframe[0].value["reference_id"].tolist() == list(range(1, 101))
    next(button for button in test.button if button.label == "Next lookup page").click()
    test.run()
    assert not test.exception
    assert test.dataframe[0].value["reference_id"].tolist() == [101]
    next(
        button for button in test.button if button.label == "Previous lookup page"
    ).click()
    test.run()
    assert test.dataframe[0].value["reference_id"].tolist() == list(range(1, 101))
    for field in test.text_input:
        if field.label in ("Lot number (after LOT)", "Suburb (exact)"):
            field.set_value("")
    next(
        button for button in test.button if button.label == "Search reference database"
    ).click()
    test.run()
    assert not test.exception
    assert "at least one" in test.error[0].value
    assert not test.dataframe


def test_approved_registry_includes_nested_snapshots_and_excludes_escaping_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app, "ROOT", tmp_path)
    models = tmp_path / "whereabouts/models"
    nested = models / "snapshots"
    nested.mkdir(parents=True)
    reference = models / "reference.db"
    reference.write_bytes(b"snapshot")
    alternate = nested / "alternate.db"
    alternate.write_bytes(b"alternate")
    alias = models / "alias.db"
    alias.symlink_to(reference)
    external = tmp_path / "external.db"
    external.write_bytes(b"external snapshot")
    sibling = models.with_name("models-other")
    sibling.mkdir()
    (sibling / "reference.db").write_bytes(b"sibling snapshot")
    (models / "escape.db").symlink_to(external)
    (models / "dangling.db").symlink_to(tmp_path / "missing.db")
    (models / "external-directory").symlink_to(sibling, target_is_directory=True)
    (models / "wrong.txt").write_bytes(b"not a database")
    (models / "directory.db").mkdir()
    approved = app.approved_reference_databases()
    assert set(approved.values()) == {reference, alternate, alias}
    assert {app.resolve_reference(key, approved) for key in approved} == {
        reference,
        alternate,
    }
    for value in (str(external), str(reference), "../external.db", "unknown", [], 42):
        with pytest.raises(ValueError, match="Unknown"):
            app.resolve_reference(value, approved)
    with pytest.raises(ValueError, match="Select"):
        app.resolve_reference(None, approved)


@pytest.mark.parametrize("replacement", ["removed", "escaping_symlink"])
def test_registry_entry_is_revalidated_before_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    monkeypatch.setattr(app, "ROOT", tmp_path)
    models = tmp_path / "whereabouts/models"
    models.mkdir(parents=True)
    reference = models / "reference.db"
    reference.write_bytes(b"snapshot")
    approved = app.approved_reference_databases()
    reference.unlink()
    if replacement == "escaping_symlink":
        external = tmp_path / "external.db"
        external.write_bytes(b"external snapshot")
        reference.symlink_to(external)
    with pytest.raises((ValueError, OSError)):
        app.resolve_reference(next(iter(approved)), approved)


@pytest.mark.parametrize("cache_kind", ["legacy", "unknown", "removed", "remapped"])
def test_cached_lookup_rejects_stale_database_selections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cache_kind: str,
) -> None:
    monkeypatch.setattr(app, "ROOT", tmp_path)
    monkeypatch.setattr(app, "RUNS", tmp_path / "runs")
    models = tmp_path / "whereabouts/models"
    models.mkdir(parents=True)
    reference = models / "reference.db"
    with duckdb.connect(str(reference)) as con:
        con.execute("""
            CREATE TABLE addrtext_with_detail AS
            SELECT 1 AS addr_id, 'LOT 15 TEST ST' AS address_label, 'BRUNSWICK' AS suburb
        """)
    test = AppTest.from_string(
        "from whereabouts.evaluation.streamlit_app import main\nmain()"
    ).run()
    next(
        field for field in test.text_input if field.label == "Lot number (after LOT)"
    ).set_value("15")
    next(
        button for button in test.button if button.label == "Search reference database"
    ).click()
    test.run()
    assert not test.exception
    assert len(test.dataframe) == 1
    saved = test.session_state["reference_lookup"]
    if cache_kind == "legacy":
        test.session_state["reference_lookup"] = {"database": reference}
    elif cache_kind == "unknown":
        saved["database_id"] = "../external.db"
    elif cache_kind == "removed":
        reference.unlink()
    else:
        alternate = models / "alternate.db"
        alternate.write_bytes(b"replacement snapshot")
        reference.unlink()
        reference.symlink_to(alternate)
    test.run()
    assert not test.exception
    assert test.error
    assert not test.dataframe
    assert "reference_lookup" not in test.session_state


@pytest.mark.parametrize("lookup", [False, True])
def test_app_rejects_unknown_ids_before_evaluation_or_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lookup: bool,
) -> None:
    monkeypatch.setattr(app, "ROOT", tmp_path)
    monkeypatch.setattr(app, "RUNS", tmp_path / "runs")
    models = tmp_path / "whereabouts/models"
    models.mkdir(parents=True)
    (models / "reference.db").write_bytes(b"snapshot")
    examples = tmp_path / "example_data"
    examples.mkdir()
    (examples / "input.csv").write_text("input_address,best_match\nINPUT,CORRECT\n")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("An unapproved path reached database lookup or evaluation")

    monkeypatch.setattr(app, "lookup_reference", forbidden)
    monkeypatch.setattr(app, "run_version", forbidden)
    choose = app.choose_reference

    def unknown_selection(
        label: str, databases: dict[str, Path], key: str
    ) -> str | None:
        if key == ("lookup-database" if lookup else "match-database"):
            return "../external.db"
        return choose(label, databases, key)

    monkeypatch.setattr(app, "choose_reference", unknown_selection)
    test = AppTest.from_string(
        "from whereabouts.evaluation.streamlit_app import main\nmain()"
    ).run()
    button_label = "Search reference database" if lookup else "Match addresses"
    next(button for button in test.button if button.label == button_label).click()
    test.run()
    assert not test.exception
    assert "Unknown reference database selection" in test.error[0].value
