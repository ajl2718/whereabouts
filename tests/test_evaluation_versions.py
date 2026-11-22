from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from whereabouts.evaluation import worker
from whereabouts.evaluation.dataset import EvaluationDataset, file_hash, import_csv
from whereabouts.evaluation.engine import RunConfig, load_run
from whereabouts.evaluation.versions import (
    AlgorithmVersion,
    command,
    load_versions,
    prepare_worktree,
    register_version,
    run_version,
)


STUB_WORKER = """
import argparse, hashlib, json, pathlib, subprocess, uuid
parser = argparse.ArgumentParser()
parser.add_argument("--request")
parser.add_argument("--response")
args = parser.parse_args()
request = json.loads(pathlib.Path(args.request).read_text())
run_id = uuid.uuid4().hex
dataset = json.loads(pathlib.Path(request["dataset"]).read_text())
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
run = {
    "schema_version": 1, "run_id": run_id,
    "dataset": {"sha256": request["dataset_sha256"]},
    "database": {"sha256": request["reference_sha256"]},
    "config": request["config"],
    "code": {"git_revision": revision, "git_dirty": False},
    "timing": {"measured_seconds": 0.1},
    "rows": [{"case": case, "selected": {"address": ADDRESS}} for case in dataset["cases"]],
}
output = pathlib.Path(request["output_dir"]) / (run_id + ".json")
output.parent.mkdir(parents=True)
output.write_text(json.dumps(run))
pathlib.Path(args.response).write_text(json.dumps({"protocol_version": 1, "run": str(output)}))
"""


def git_commit(root: Path, message: str) -> str:
    command(["git", "add", "."], root)
    command(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            f"{message}\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
        ],
        root,
    )
    return command(["git", "rev-parse", "HEAD"], root)


def test_pinned_revisions_execute_independently_and_reject_dirty_worktrees(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    command(["git", "init"], root)
    (root / "pyproject.toml").write_text(
        '[project]\nname="worker-test"\nversion="1"\nrequires-python=">=3.12"\n'
    )
    (root / ".gitignore").write_text(".venv/\n__pycache__/\n")
    subprocess.run(
        ["uv", "lock", "--offline", "--python", sys.executable],
        cwd=root,
        check=True,
        capture_output=True,
    )
    package = root / "whereabouts/evaluation"
    package.mkdir(parents=True)
    (root / "whereabouts/__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    script = package / "worker.py"
    script.write_text('ADDRESS = "BASELINE"\n' + STUB_WORKER)
    baseline = AlgorithmVersion("Baseline", git_commit(root, "Baseline worker"))
    script.write_text('ADDRESS = "CHALLENGER"\n' + STUB_WORKER)
    challenger = AlgorithmVersion("Challenger", git_commit(root, "Challenger worker"))
    runs = tmp_path / "runs"
    registry = runs / "versions.json"
    for version in (baseline, challenger):
        register_version(root, registry, version)
    assert load_versions(registry) == [baseline, challenger]
    with pytest.raises(ValueError, match="already registered"):
        register_version(root, registry, baseline)
    csv = tmp_path / "input.csv"
    csv.write_text("input_address,best_match\nINPUT,CORRECT\n")
    dataset = tmp_path / "dataset.json"
    import_csv(csv, dataset)
    reference = tmp_path / "reference.db"
    reference.write_bytes(b"snapshot")
    config = RunConfig("snapshot", reference_path=str(reference))
    paths = [
        run_version(root, runs, dataset, config, version.name, version)
        for version in (baseline, challenger)
    ]
    assert [load_run(path)["rows"][0]["selected"]["address"] for path in paths] == [
        "BASELINE",
        "CHALLENGER",
    ]
    assert command(["git", "rev-parse", "HEAD"], root) == challenger.commit
    assert not command(["git", "status", "--porcelain"], root)
    assert reference.read_bytes() == b"snapshot"
    worktree = prepare_worktree(root, runs / "implementations", baseline)
    (worktree / "whereabouts/evaluation/worker.py").write_text("changed")
    with pytest.raises(ValueError, match="has changes"):
        run_version(root, runs, dataset, config, "Dirty baseline", baseline)
    (worktree / "whereabouts/evaluation/worker.py").write_text(
        'ADDRESS = "BASELINE"\n' + STUB_WORKER
    )
    for version in (baseline, challenger):
        command(
            [
                "git",
                "worktree",
                "remove",
                str(runs / "implementations/worktrees" / version.commit),
            ],
            root,
        )


def test_revision_without_contract_is_explicitly_unsupported(tmp_path: Path) -> None:
    command(["git", "init"], tmp_path)
    (tmp_path / "file.txt").write_text("legacy implementation")
    revision = git_commit(tmp_path, "Legacy")
    with pytest.raises(ValueError, match="Unsupported revision"):
        register_version(
            tmp_path, tmp_path / "versions.json", AlgorithmVersion("Legacy", revision)
        )
    with pytest.raises(ValueError, match="40-character"):
        AlgorithmVersion("Short SHA", revision[:8])


def test_worker_rejects_snapshot_mismatch_and_missing_capabilities(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference.db"
    with duckdb.connect(str(reference)) as con:
        con.execute("CREATE TABLE addrtext_with_detail(addr VARCHAR)")
    csv = tmp_path / "input.csv"
    csv.write_text("input_address,best_match\nINPUT,CORRECT\n")
    dataset = tmp_path / "dataset.json"
    import_csv(csv, dataset)
    request = {
        "protocol_version": 1,
        "config": {"database": "snapshot", "reference_path": str(reference)},
        "dataset": str(dataset),
        "dataset_sha256": file_hash(dataset),
        "reference_sha256": "incorrect",
        "output_dir": str(tmp_path / "runs"),
    }
    with pytest.raises(ValueError, match="checksum"):
        worker.execute(request)
    request["reference_sha256"] = file_hash(reference)
    with pytest.raises(ValueError, match="phraseinverted"):
        worker.execute(request)
    request["protocol_version"] = 2
    with pytest.raises(ValueError, match="protocol"):
        worker.execute(request)
    assert EvaluationDataset.load(dataset).cases[0].label_status == "needs_review"
