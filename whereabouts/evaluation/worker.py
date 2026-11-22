"""Versioned subprocess contract for trusted, local algorithm implementations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from .dataset import file_hash, write_json
from .engine import RunConfig, run_evaluation

PROTOCOL_VERSION = 1
REQUIRED_TABLES = {
    "standard": {"addrtext_with_detail", "phraseinverted"},
    "skipphrase": {"addrtext_with_detail", "skipphraseinverted"},
    "trigram": {"addrtext_with_detail", "trigramphraseinverted3", "numbers"},
}


def check_reference(path: Path, how: str) -> None:
    with duckdb.connect(str(path), read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    missing = REQUIRED_TABLES[how] - tables
    if missing:
        raise ValueError(
            f"Reference snapshot lacks {how} capabilities: {', '.join(sorted(missing))}"
        )


def execute(request: dict) -> Path:
    if request.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("Unsupported evaluation worker protocol")
    config = RunConfig(**request["config"])
    if config.reference_path is None:
        raise ValueError("Worker requires an explicit reference snapshot")
    reference = Path(config.reference_path)
    dataset = Path(request["dataset"])
    if file_hash(reference) != request["reference_sha256"]:
        raise ValueError("Reference snapshot differs from the requested checksum")
    if file_hash(dataset) != request["dataset_sha256"]:
        raise ValueError("Dataset differs from the requested checksum")
    check_reference(reference, config.how)
    return run_evaluation(dataset, config, Path(request["output_dir"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    options = parser.parse_args()
    try:
        run = execute(json.loads(options.request.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, OSError, duckdb.Error) as exc:
        parser.exit(1, f"Evaluation worker failed: {exc}\n")
    write_json(
        options.response,
        {"protocol_version": PROTOCOL_VERSION, "run": str(run.resolve())},
    )


if __name__ == "__main__":
    main()
