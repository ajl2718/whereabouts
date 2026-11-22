from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import importlib.resources
import inspect
import json
import math
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter
from uuid import uuid4

import pandas as pd

from ..Matcher import Matcher, VALID_HOW_VALUES
from ..matching_queries import create_matching_pipeline
from ..QueryPipeline import QueryPipeline
from ..QueryStep import query_step
from .dataset import (
    AcceptableMatch,
    EvaluationCase,
    EvaluationDataset,
    file_hash,
    normalize,
    write_json,
)


@dataclass(frozen=True)
class RunConfig:
    database: str
    how: str = "standard"
    threshold: float = 0.5
    top_k: int = 5
    batch_size: int = 500
    pipeline: str | None = None
    reference_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.database, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", self.database
        ):
            raise ValueError("database must be an installed database name")
        if self.how not in VALID_HOW_VALUES:
            raise ValueError(f"Invalid algorithm: {self.how}")
        if isinstance(self.threshold, bool) or not isinstance(
            self.threshold, (int, float)
        ):
            raise ValueError("threshold must be a number")
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        if type(self.top_k) is not int or not 1 <= self.top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if self.pipeline is not None and (
            self.how != "standard" or ":" not in self.pipeline
        ):
            raise ValueError(
                "Custom pipelines require how=standard and module:function syntax"
            )
        if self.reference_path is not None:
            path = Path(self.reference_path)
            if not path.is_absolute() or path.suffix != ".db" or not path.is_file():
                raise ValueError(
                    "reference_path must identify an existing absolute .db snapshot"
                )


def _git(args: list[str], root: Path) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode:
        return None
    return result.stdout.strip()


def code_identity() -> dict:
    package = Path(str(importlib.resources.files("whereabouts")))
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".sql", ".html"):
            digest.update(str(path.relative_to(package)).encode())
            digest.update(path.read_bytes())
    status = _git(["status", "--porcelain"], package)
    lockfile = package.parent / "uv.lock"
    return {
        "package_version": importlib.metadata.version("whereabouts"),
        "package_sha256": digest.hexdigest(),
        "git_revision": _git(["rev-parse", "HEAD"], package),
        "git_dirty": bool(status) if status is not None else None,
        "git_status": status,
        "python_version": platform.python_version(),
        "duckdb_version": importlib.metadata.version("duckdb"),
        "pandas_version": importlib.metadata.version("pandas"),
        "numpy_version": importlib.metadata.version("numpy"),
        "lockfile_sha256": file_hash(lockfile) if lockfile.is_file() else None,
    }


class CandidateRunner:
    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.matcher = Matcher(config.reference_path or config.database, how=config.how)
        self.factory_source: dict | None = None
        with ExitStack() as cleanup:
            cleanup.callback(self.matcher.close)
            pipeline = create_matching_pipeline(self.matcher.con, config.how)
            if config.pipeline:
                module_name, function_name = config.pipeline.split(":", 1)
                factory = getattr(importlib.import_module(module_name), function_name)
                source = inspect.getsourcefile(factory)
                if source is None or not Path(source).is_file():
                    raise ValueError(
                        "Custom pipeline factories need a readable Python source file"
                    )
                self.factory_source = {
                    "path": str(Path(source).resolve()),
                    "sha256": file_hash(Path(source)),
                }
                pipeline = factory(self.matcher.con)
                if not isinstance(pipeline, QueryPipeline):
                    raise ValueError(
                        "Custom pipeline factory must return QueryPipeline"
                    )
                if pipeline.con is not self.matcher.con:
                    raise ValueError(
                        "Custom pipeline must use the supplied DuckDB connection"
                    )
            ranked = "matched_addresses_ranked_by_similarity"
            index = next(
                (
                    i
                    for i, step in enumerate(pipeline.steps)
                    if step.output_table_name == ranked
                ),
                None,
            )
            if index is None:
                raise ValueError(f"Pipeline must expose {ranked}")
            final = query_step(
                query_template=f"""
                    SELECT address_id1 AS address_id, address_id2, address_matched,
                           suburb, postcode, latitude, longitude, similarity
                    FROM {{ranked}} WHERE rank <= {config.top_k}
                    ORDER BY address_id1, rank
                """,
                output_table_name="evaluation_candidates",
                input_table_names={"ranked": ranked},
            )
            self.pipeline = QueryPipeline(
                self.matcher.con, [*pipeline.steps[: index + 1], final]
            )
            self.sql = "\n".join(
                step.render() for step in self.pipeline.steps if step.direct_execution
            )
            self.sql += self.pipeline.createCTEs()
            cleanup.pop_all()

    def close(self) -> None:
        self.matcher.close()

    def retrieve(self, cases: list[EvaluationCase]) -> list[list[dict]]:
        inputs = pd.DataFrame(
            {
                "address_id": range(1, len(cases) + 1),
                "address": [c.input_address for c in cases],
            }
        )
        inputs["address"] = inputs["address"].astype(object)
        con = self.matcher.con
        con.register("evaluation_input", inputs)
        try:
            con.execute(
                "CREATE OR REPLACE TEMP TABLE input_addresses AS SELECT * FROM evaluation_input"
            )
            frame = self.pipeline.execute()
            groups: list[list[dict]] = [[] for _ in cases]
            for row in frame.to_dict("records"):
                address_id = int(row["address_id"])
                if not 1 <= address_id <= len(cases):
                    raise ValueError(
                        f"Algorithm returned unexpected input ID: {address_id}"
                    )
                if pd.isna(row["address_matched"]):
                    continue
                score = float(row["similarity"])
                if not math.isfinite(score):
                    raise ValueError(
                        f"Algorithm returned a nonfinite score for input {address_id}"
                    )
                reference_id = str(int(row["address_id2"]))
                groups[address_id - 1].append(
                    {
                        "reference_id": reference_id,
                        "address": str(row["address_matched"]),
                        "locality": None
                        if pd.isna(row["suburb"])
                        else str(row["suburb"]),
                        "postcode": None
                        if pd.isna(row["postcode"])
                        else str(int(row["postcode"])),
                        "latitude": None
                        if pd.isna(row["latitude"])
                        else float(row["latitude"]),
                        "longitude": None
                        if pd.isna(row["longitude"])
                        else float(row["longitude"]),
                        "score": score,
                    }
                )
            for group in groups:
                group.sort(
                    key=lambda candidate: (
                        -candidate["score"],
                        int(candidate["reference_id"]),
                    )
                )
            return groups
        finally:
            con.execute("DROP TABLE IF EXISTS input_addresses")
            con.unregister("evaluation_input")


def _acceptable(
    case: EvaluationCase, candidate: dict, expected: AcceptableMatch
) -> bool:
    if case.precision == "locality":
        return normalize(candidate["locality"] or "") == normalize(
            expected.locality or ""
        ) and (expected.postcode is None or candidate["postcode"] == expected.postcode)
    if expected.reference_id is not None:
        return candidate["reference_id"] == expected.reference_id
    return normalize(candidate["address"]) == normalize(expected.address or "")


def score_case(case: EvaluationCase, candidates: list[dict], threshold: float) -> dict:
    selected = (
        candidates[0] if candidates and candidates[0]["score"] >= threshold else None
    )
    agreement = (
        selected is None
        if case.expect_abstention
        else (
            selected is not None
            and any(
                _acceptable(case, selected, expected) for expected in case.acceptable
            )
        )
    )
    ranks = [
        i
        for i, candidate in enumerate(candidates, 1)
        if any(_acceptable(case, candidate, expected) for expected in case.acceptable)
    ]
    rank = ranks[0] if ranks else None
    if case.label_status != "verified":
        outcome = "unscored"
    elif agreement:
        outcome = "correct"
    elif selected is None:
        outcome = "abstained"
    else:
        outcome = "wrong"
    if outcome in ("correct", "unscored"):
        mode = outcome
    elif case.expect_abstention:
        mode = "false_positive"
    elif rank == 1:
        mode = "threshold_rejection"
    elif rank is not None:
        mode = "ranking"
    else:
        mode = "not_in_top_k"
    return {
        "case": asdict(case),
        "candidates": candidates,
        "selected": selected,
        "agreement": agreement,
        "outcome": outcome,
        "diagnosis": mode,
        "acceptable_rank": rank,
    }


def summarize(rows: list[dict]) -> dict:
    scored = [row for row in rows if row["outcome"] != "unscored"]
    positive = [row for row in scored if not row["case"]["expect_abstention"]]
    returned = [row for row in scored if row["selected"] is not None]
    correct = sum(row["outcome"] == "correct" for row in scored)
    return {
        "total": len(rows),
        "scored": len(scored),
        "unscored": len(rows) - len(scored),
        "correct": correct,
        "wrong": sum(row["outcome"] == "wrong" for row in scored),
        "abstained": sum(row["outcome"] == "abstained" for row in scored),
        "accuracy": correct / len(scored) if scored else None,
        "coverage": len(returned) / len(scored) if scored else None,
        "accepted_accuracy": (
            sum(row["outcome"] == "correct" for row in returned) / len(returned)
            if returned
            else None
        ),
        "top_k_recall": (
            sum(row["acceptable_rank"] is not None for row in positive) / len(positive)
            if positive
            else None
        ),
        "label_agreement": sum(row["agreement"] for row in rows) / len(rows)
        if rows
        else None,
    }


def metrics(rows: list[dict]) -> dict:
    result = summarize(rows)
    result["by_error_mode"] = {
        mode: summarize([row for row in rows if row["case"]["error_mode"] == mode])
        for mode in sorted(
            {row["case"]["error_mode"] for row in rows if row["case"]["error_mode"]}
        )
    }
    result["by_precision"] = {
        precision: summarize(
            [row for row in rows if row["case"]["precision"] == precision]
        )
        for precision in sorted({row["case"]["precision"] for row in rows})
    }
    result["by_tag"] = {
        tag: summarize([row for row in rows if tag in row["case"]["tags"]])
        for tag in sorted({tag for row in rows for tag in row["case"]["tags"]})
    }
    result["diagnoses"] = {
        diagnosis: sum(row["diagnosis"] == diagnosis for row in rows)
        for diagnosis in sorted({row["diagnosis"] for row in rows})
    }
    return result


def run_evaluation(dataset_path: Path, config: RunConfig, output_dir: Path) -> Path:
    dataset_bytes = dataset_path.read_bytes()
    dataset = EvaluationDataset.from_dict(json.loads(dataset_bytes))
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    database_path = (
        Path(config.reference_path)
        if config.reference_path
        else (
            Path(str(importlib.resources.files("whereabouts.models")))
            / f"{config.database}.db"
        )
    )
    if not database_path.is_file():
        raise ValueError(
            "Evaluation requires an installed local database for checksum-based reproducibility"
        )
    database_hash = file_hash(database_path)
    identity = code_identity()
    started_at = datetime.now(timezone.utc).isoformat()
    setup_start = perf_counter()
    runner = CandidateRunner(config)
    try:
        setup_seconds = perf_counter() - setup_start
        warmup_start = perf_counter()
        runner.retrieve(dataset.cases[: min(config.batch_size, len(dataset.cases))])
        warmup_seconds = perf_counter() - warmup_start
        rows = []
        timings = []
        for offset in range(0, len(dataset.cases), config.batch_size):
            batch = dataset.cases[offset : offset + config.batch_size]
            start = perf_counter()
            candidates = runner.retrieve(batch)
            timings.append({"size": len(batch), "seconds": perf_counter() - start})
            rows.extend(
                score_case(case, group, config.threshold)
                for case, group in zip(batch, candidates, strict=True)
            )
        query_hash = hashlib.sha256(runner.sql.encode()).hexdigest()
        factory_source = runner.factory_source
    finally:
        runner.close()
    if (
        file_hash(dataset_path) != dataset_hash
        or file_hash(database_path) != database_hash
    ):
        raise ValueError(
            "Dataset or reference database changed during evaluation; run was not saved"
        )
    if code_identity()["package_sha256"] != identity["package_sha256"]:
        raise ValueError("Package source changed during evaluation; run was not saved")
    if (
        factory_source
        and file_hash(Path(factory_source["path"])) != factory_source["sha256"]
    ):
        raise ValueError(
            "Custom pipeline source changed during evaluation; run was not saved"
        )
    elapsed = sum(batch["seconds"] for batch in timings)
    run_id = uuid4().hex
    run = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": started_at,
        "config": asdict(config),
        "dataset": {
            "name": dataset.name,
            "version": dataset.version,
            "split": dataset.split,
            "sha256": dataset_hash,
            "path": str(dataset_path.resolve()),
        },
        "database": {"path": str(database_path.resolve()), "sha256": database_hash},
        "code": identity,
        "query_sha256": query_hash,
        "generated_sql": runner.sql,
        "factory_source": factory_source,
        "timing": {
            "setup_seconds": setup_seconds,
            "warmup_seconds": warmup_seconds,
            "measured_seconds": elapsed,
            "addresses_per_second": len(rows) / elapsed if elapsed else None,
            "batches": timings,
        },
        "metrics": metrics(rows),
        "rows": rows,
    }
    destination = output_dir / f"{run_id}.json"
    write_json(destination, run)
    return destination


def load_run(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or "rows" not in value
    ):
        raise ValueError(f"Not an evaluation run: {path}")
    if not isinstance(value["rows"], list) or len(
        {row["case"]["case_id"] for row in value["rows"]}
    ) != len(value["rows"]):
        raise ValueError(f"Invalid or duplicate run cases: {path}")
    return value


def compare_runs(baseline: dict, challenger: dict) -> dict:
    if baseline["dataset"]["sha256"] != challenger["dataset"]["sha256"]:
        raise ValueError(
            "Cannot compare runs with different datasets or label versions"
        )
    if baseline["database"]["sha256"] != challenger["database"]["sha256"]:
        raise ValueError("Cannot compare runs with different reference databases")
    left = {row["case"]["case_id"]: row for row in baseline["rows"]}
    right = {row["case"]["case_id"]: row for row in challenger["rows"]}
    if left.keys() != right.keys():
        raise ValueError("Cannot compare runs with different case IDs")
    rows = []
    for case_id, before in left.items():
        after = right[case_id]
        if before["case"] != after["case"]:
            raise ValueError(f"Case evidence differs between runs: {case_id}")
        if before["outcome"] == "unscored":
            category = "unscored"
        elif before["outcome"] == "correct" and after["outcome"] != "correct":
            category = "regression"
        elif before["outcome"] != "correct" and after["outcome"] == "correct":
            category = "improvement"
        elif before["outcome"] != "correct":
            category = "shared_failure"
        else:
            category = "shared_success"
        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "baseline": before,
                "challenger": after,
            }
        )
    return {
        "baseline": baseline["run_id"],
        "challenger": challenger["run_id"],
        "counts": {
            category: sum(row["category"] == category for row in rows)
            for category in (
                "regression",
                "improvement",
                "shared_failure",
                "shared_success",
                "unscored",
            )
        },
        "timing_comparable": baseline["config"]["batch_size"]
        == challenger["config"]["batch_size"]
        and baseline["config"]["top_k"] == challenger["config"]["top_k"],
        "rows": rows,
    }
