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
    next(button for button in test.button if button.label == "Match addresses").click()
    test.run()
    assert not test.exception
    assert not test.error
    assert calls[0][0].reference_path == str(
        tmp_path / "whereabouts/models/reference.db"
    )
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
    models.mkdir(parents=True)
    with duckdb.connect(str(models / "reference.db")) as con:
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
