from __future__ import annotations

from dataclasses import asdict, replace
import http.client
import json
from pathlib import Path
import re
from threading import Thread

import duckdb
import pytest

from whereabouts.evaluation import engine
from whereabouts.evaluation.app import create_server
from whereabouts.evaluation.cli import main
from whereabouts.evaluation.dataset import (
    AcceptableMatch,
    EvaluationCase,
    EvaluationDataset,
    ReviewStore,
    export_reviewed,
    file_hash,
    import_csv,
    write_json,
)
from whereabouts.evaluation.engine import (
    CandidateRunner,
    RunConfig,
    compare_runs,
    metrics,
    score_case,
)
from whereabouts.matching_queries import create_matching_query, register_functions


def gold(case_id: str = "one", **kwargs: object) -> EvaluationCase:
    values = {
        "case_id": case_id,
        "input_address": "115 Sydney Rd Brunswick",
        "acceptable": [AcceptableMatch(address="115 SYDNEY RD BRUNSWICK VIC 3056")],
        "label_status": "verified",
        "evidence": "Test reference",
        "tags": ["missing_postcode"],
    }
    return EvaluationCase(**{**values, **kwargs})


def candidate(
    address: str = "115 SYDNEY RD BRUNSWICK VIC 3056",
    score: float = 0.8,
    ref: str = "10",
) -> dict:
    return {
        "address": address,
        "score": score,
        "reference_id": ref,
        "locality": "BRUNSWICK",
        "postcode": "3056",
    }


def saved_run(rows: list[dict], run_id: str = "a" * 32) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "dataset": {
            "sha256": "dataset",
            "name": "test",
            "version": "1",
            "split": "development",
            "path": "unused",
        },
        "database": {"sha256": "reference"},
        "config": asdict(RunConfig("db_test")),
        "metrics": metrics(rows),
        "rows": rows,
    }


def test_import_preserves_unverified_labels_and_stable_duplicate_ids(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.csv"
    source.write_text(
        "input_address,best_match\n115 Sydney Rd,115 SYDNEY RD\n115 SYDNEY RD,115 SYDNEY RD\n"
    )
    dataset = import_csv(source, tmp_path / "v1.json")
    assert all(case.label_status == "needs_review" for case in dataset.cases)
    assert dataset.cases[0].case_id != dataset.cases[1].case_id
    assert import_csv(source, tmp_path / "copy.json").cases == dataset.cases
    assert EvaluationDataset.load(tmp_path / "v1.json") == dataset
    with pytest.raises(FileExistsError):
        dataset.save(tmp_path / "v1.json")
    source.write_text("input_address,best_match\n,\n")
    with pytest.raises(ValueError, match="nonempty"):
        import_csv(source, tmp_path / "invalid.json")


@pytest.mark.parametrize(
    "changes",
    [
        {"label_status": "verified", "evidence": ""},
        {"label_status": "bogus"},
        {"precision": "bogus"},
        {"expect_abstention": "false"},
        {"acceptable": []},
        {"precision": "street", "acceptable": [AcceptableMatch(locality="BRUNSWICK")]},
        {"precision": "locality"},
    ],
)
def test_invalid_gold_is_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        gold(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"threshold": float("nan")},
        {"threshold": 1.01},
        {"threshold": True},
        {"top_k": 0},
        {"top_k": 51},
        {"top_k": 1.5},
        {"batch_size": 0},
        {"how": "other"},
        {"pipeline": "invalid"},
    ],
)
def test_invalid_run_configuration_is_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        RunConfig("db_test", **changes)


def test_threshold_candidate_recall_abstentions_and_unverified_metrics() -> None:
    correct = score_case(gold(), [candidate(score=0.5)], 0.5)
    rejected = score_case(gold("reject"), [candidate(score=0.499)], 0.5)
    ranked = score_case(
        gold("rank"), [candidate("WRONG", ref="11"), candidate(score=0.7)], 0.5
    )
    missing = score_case(gold("missing"), [], 0.5)
    unverified = score_case(
        gold("review", label_status="needs_review"), [candidate()], 0.5
    )
    abstention = score_case(
        gold("none", acceptable=[], expect_abstention=True), [], 0.5
    )
    false_positive = score_case(
        gold("false", acceptable=[], expect_abstention=True), [candidate()], 0.5
    )
    assert correct["outcome"] == "correct"
    assert rejected["diagnosis"] == "threshold_rejection"
    assert rejected["selected"] is None and rejected["acceptable_rank"] == 1
    assert ranked["diagnosis"] == "ranking" and ranked["acceptable_rank"] == 2
    assert missing["diagnosis"] == "not_in_top_k"
    assert unverified["outcome"] == "unscored" and unverified["agreement"]
    assert abstention["outcome"] == "correct"
    assert false_positive["diagnosis"] == "false_positive"
    result = metrics(
        [correct, rejected, ranked, missing, unverified, abstention, false_positive]
    )
    assert result["scored"] == 6 and result["unscored"] == 1
    assert result["accuracy"] == pytest.approx(2 / 6)
    assert result["coverage"] == pytest.approx(3 / 6)
    assert result["top_k_recall"] == pytest.approx(3 / 4)
    assert result["accepted_accuracy"] == pytest.approx(1 / 3)
    assert result["by_tag"]["missing_postcode"]["total"] == 7
    assert metrics([unverified])["accuracy"] is None


def test_multiple_acceptable_ids_and_locality_precision() -> None:
    case = gold(
        precision="building",
        acceptable=[
            AcceptableMatch(reference_id="20"),
            AcceptableMatch(reference_id="10", address="DISPLAY LABEL"),
        ],
    )
    assert score_case(case, [candidate()], 0.5)["outcome"] == "correct"
    locality = gold(
        precision="locality",
        acceptable=[AcceptableMatch(locality="brunswick", postcode="3056")],
    )
    assert (
        score_case(locality, [candidate("A DIFFERENT BUILDING")], 0.5)["outcome"]
        == "correct"
    )
    assert (
        score_case(locality, [{**candidate(), "postcode": "9999"}], 0.5)["outcome"]
        == "wrong"
    )


def test_comparison_rejects_incompatible_runs_and_identifies_changes() -> None:
    cases = [
        gold("regression"),
        gold("improvement"),
        gold("failure"),
        gold("success"),
        gold("review", label_status="needs_review"),
    ]
    before = [
        score_case(case, [candidate()] if i in (0, 3) else [], 0.5)
        for i, case in enumerate(cases)
    ]
    after = [
        score_case(case, [candidate()] if i in (1, 3) else [], 0.5)
        for i, case in enumerate(cases)
    ]
    baseline, challenger = saved_run(before), saved_run(after, "b" * 32)
    assert compare_runs(baseline, challenger)["counts"] == {
        "regression": 1,
        "improvement": 1,
        "shared_failure": 1,
        "shared_success": 1,
        "unscored": 1,
    }
    for key in ("dataset", "database"):
        invalid = {**challenger, key: {**challenger[key], "sha256": "different"}}
        with pytest.raises(ValueError, match="different"):
            compare_runs(baseline, invalid)
    with pytest.raises(ValueError, match="case IDs"):
        compare_runs(baseline, {**challenger, "rows": after[:-1]})


class MemoryMatcher:
    def __init__(self, database: str, how: str = "standard") -> None:
        self.con = duckdb.connect()
        self.con.execute("ATTACH ':memory:' AS remote")
        self.con.execute("CREATE MACRO unaccent(value) AS value")
        register_functions(self.con)
        self.con.execute("""
            CREATE TABLE remote.addrtext_with_detail AS
            SELECT * FROM (VALUES
                (10, '115 SYDNEY RD BRUNSWICK VIC 3056', ['115', '3056'], 'BRUNSWICK', 'VIC', 3056, -37.0, 144.0),
                (11, 'UNIT 1 115 SYDNEY RD BRUNSWICK VIC 3056', ['1', '115', '3056'], 'BRUNSWICK', 'VIC', 3056, -37.0, 144.0)
            ) AS t(addr_id, addr, numeric_tokens, suburb, state, postcode, latitude, longitude);
            CREATE TABLE remote.phraseinverted AS
            SELECT * FROM (VALUES ('SYDNEY RD', [10, 11], 2), ('RD BRUNSWICK', [10, 11], 2))
            AS t(tokenphrase, addr_ids, frequency);
            CREATE TABLE remote.skipphraseinverted AS
            SELECT * FROM (VALUES ('SYDNEY BRUNSWICK', [10, 11], 2))
            AS t(tokenphrase, addr_ids, frequency);
        """)
        self.pipeline = create_matching_query(self.con)

    def close(self) -> None:
        self.con.close()


@pytest.mark.parametrize("how", ["standard", "skipphrase"])
def test_adapter_exports_ranked_candidates_without_mutating_public_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    how: str,
) -> None:
    monkeypatch.setattr(engine, "Matcher", MemoryMatcher)
    runner = CandidateRunner(RunConfig("test", how=how, top_k=2))
    try:
        groups = runner.retrieve(
            [gold(), gold("missing", input_address="NO SUCH STREET")]
        )
        assert len(groups[0]) == 2 and groups[1] == []
        assert [c["reference_id"] for c in groups[0]] == ["10", "11"]
        assert (
            runner.matcher.pipeline.steps[-1].output_table_name
            == "all_addresses_with_matches"
        )
        assert runner.retrieve([gold()]) == [groups[0]]
    finally:
        runner.close()


def test_run_records_provenance_and_warmup_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "dataset.json"
    EvaluationDataset("test", "1", "development", [gold(), gold("two")]).save(source)
    database = tmp_path / "test.db"
    database.write_bytes(b"reference snapshot")
    monkeypatch.setattr(engine.importlib.resources, "files", lambda package: tmp_path)
    monkeypatch.setattr(engine, "Matcher", MemoryMatcher)
    identity = {
        "package_sha256": "source",
        "git_revision": "revision",
        "git_dirty": True,
    }
    monkeypatch.setattr(engine, "code_identity", lambda: identity)
    path = engine.run_evaluation(
        source, RunConfig("test", top_k=2, batch_size=1), tmp_path / "runs"
    )
    run = engine.load_run(path)
    assert run["dataset"]["sha256"] == file_hash(source)
    assert run["database"]["sha256"] == file_hash(database)
    assert run["code"] == identity and run["query_sha256"]
    assert len(run["timing"]["batches"]) == 2 and run["timing"]["warmup_seconds"] > 0
    assert run["metrics"]["correct"] == 2 and len(run["rows"][0]["candidates"]) == 2
    second = engine.run_evaluation(
        source, RunConfig("test", threshold=1, top_k=2), tmp_path / "runs"
    )
    assert second != path and path.exists()

    retrieve = CandidateRunner.retrieve

    def change_reference(
        self: CandidateRunner, cases: list[EvaluationCase]
    ) -> list[list[dict]]:
        groups = retrieve(self, cases)
        database.write_bytes(b"changed reference")
        return groups

    monkeypatch.setattr(CandidateRunner, "retrieve", change_reference)
    saved_paths = set((tmp_path / "runs").glob("*.json"))
    with pytest.raises(ValueError, match="changed during evaluation"):
        engine.run_evaluation(source, RunConfig("test"), tmp_path / "runs")
    assert set((tmp_path / "runs").glob("*.json")) == saved_paths


def test_reviews_are_append_only_and_exports_do_not_mutate_runs_or_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "v1.json"
    case = gold(label_status="needs_review")
    EvaluationDataset("test", "1", "development", [case]).save(source)
    digest = file_hash(source)
    store = ReviewStore(tmp_path / "reviews.sqlite3")
    store.save(digest, gold(notes="first"))
    store.save(digest, gold(notes="latest"))
    store.save("another dataset", gold(notes="different"))
    reviewed = export_reviewed(source, tmp_path / "v2.json", store, "2")
    assert (
        reviewed.cases[0].notes == "latest"
        and reviewed.cases[0].label_status == "verified"
    )
    assert file_hash(source) == digest
    with pytest.raises(ValueError, match="new dataset version"):
        export_reviewed(source, tmp_path / "invalid.json", store, "1")


def test_cli_import_and_compare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv = tmp_path / "input.csv"
    csv.write_text("input_address,best_match\n115 Sydney Rd,115 SYDNEY RD\n")
    main(["import-csv", str(csv), "--output", str(tmp_path / "dataset.json")])
    assert "1 unverified cases" in capsys.readouterr().out
    for run_id in ("a" * 32, "b" * 32):
        write_json(
            tmp_path / f"{run_id}.json",
            saved_run([score_case(gold(), [candidate()], 0.5)], run_id),
        )
    main(
        [
            "compare",
            str(tmp_path / ("a" * 32 + ".json")),
            str(tmp_path / ("b" * 32 + ".json")),
        ]
    )
    assert '"shared_success": 1' in capsys.readouterr().out

    regressed = saved_run([score_case(gold(), [], 0.5)], "c" * 32)
    write_json(tmp_path / ("c" * 32 + ".json"), regressed)
    with pytest.raises(SystemExit) as failure:
        main(
            [
                "compare",
                str(tmp_path / ("a" * 32 + ".json")),
                str(tmp_path / ("c" * 32 + ".json")),
                "--fail-on-regression",
            ]
        )
    assert failure.value.code == 1


def test_local_ui_reviews_escape_data_and_reject_cross_origin_writes(
    tmp_path: Path,
) -> None:
    case = gold(input_address="<script>alert(1)</script>")
    run = saved_run([score_case(case, [candidate()], 0.5)])
    source = tmp_path / "dataset.json"
    EvaluationDataset("test", "1", "development", [case]).save(source)
    run["dataset"].update({"sha256": file_hash(source), "path": str(source)})
    database = tmp_path / "reference.db"
    database.write_bytes(b"new snapshot")
    run["database"].update({"path": str(database)})
    path = tmp_path / (run["run_id"] + ".json")
    write_json(path, run)
    original_hash = file_hash(path)
    server = create_server(tmp_path, 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        page = response.read().decode()
        policy = response.getheader("Content-Security-Policy")
        assert response.status == 200 and policy is not None
        assert "frame-ancestors 'none'" in policy
        assert "<script>alert(1)</script>" not in page and ".textContent" in page
        token_match = re.search(r'const token = "([a-f0-9]+)"', page)
        assert token_match is not None
        payload = {
            "run_id": run["run_id"],
            "case_id": case.case_id,
            "proposal": asdict(replace(case, notes="Reviewed")),
        }
        connection.request(
            "POST",
            "/api/reviews",
            json.dumps(payload),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        headers = {
            "Content-Type": "application/json",
            "X-Evaluation-Token": token_match[1],
        }
        connection.request(
            "POST",
            "/api/reviews",
            json.dumps(payload),
            {**headers, "Origin": "https://example.invalid"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("POST", "/api/reviews", json.dumps(payload), headers)
        response = connection.getresponse()
        assert response.status == 200
        response.read()
        assert file_hash(path) == original_hash
        assert (
            ReviewStore(tmp_path / "reviews.sqlite3").latest(run["dataset"]["sha256"])[
                case.case_id
            ]["notes"]
            == "Reviewed"
        )
        connection.request(
            "POST",
            "/api/run",
            json.dumps(
                {
                    "run_id": run["run_id"],
                    "how": "standard",
                    "threshold": 0.5,
                    "top_k": 5,
                }
            ),
            headers,
        )
        response = connection.getresponse()
        assert response.status == 400
        assert "Reference database has changed" in json.loads(response.read())["error"]
        connection.request(
            "GET", f"/api/compare?baseline={run['run_id']}&challenger={run['run_id']}"
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["counts"]["shared_success"] == 1
        connection.request("GET", "/api/runs", headers={"Host": "attacker.invalid"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join()
