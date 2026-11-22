from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import ReviewStore, export_reviewed, import_csv, write_json
from .engine import RunConfig, compare_runs, load_run, run_evaluation


def main(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m whereabouts evaluate")
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser(
        "import-csv", help="Import legacy labels as needs_review"
    )
    convert.add_argument("source", type=Path)
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument("--version", default="1")
    convert.add_argument(
        "--split", choices=("development", "held_out"), default="development"
    )
    run = commands.add_parser("run", help="Run one or more threshold configurations")
    run.add_argument("dataset", type=Path)
    run.add_argument("--database", required=True)
    run.add_argument(
        "--how", choices=("standard", "skipphrase", "trigram"), default="standard"
    )
    run.add_argument("--threshold", type=float, nargs="+", default=[0.5])
    run.add_argument("--top-k", type=int, default=5)
    run.add_argument("--batch-size", type=int, default=500)
    run.add_argument(
        "--pipeline",
        help="Trusted Python pipeline factory, module:function (standard only)",
    )
    run.add_argument("--output-dir", type=Path, default=Path("evaluation_runs"))
    compare = commands.add_parser(
        "compare", help="Compare identical datasets and reference databases"
    )
    compare.add_argument("baseline", type=Path)
    compare.add_argument("challenger", type=Path)
    compare.add_argument("--output", type=Path)
    compare.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit nonzero if verified cases regress",
    )
    review = commands.add_parser("review", help="Start a loopback-only review UI")
    review.add_argument("--runs", type=Path, default=Path("evaluation_runs"))
    review.add_argument("--port", type=int, default=8765)
    export = commands.add_parser(
        "export-reviewed", help="Create a new dataset version from label proposals"
    )
    export.add_argument("dataset", type=Path)
    export.add_argument(
        "--reviews", type=Path, default=Path("evaluation_runs/reviews.sqlite3")
    )
    export.add_argument("--version", required=True)
    export.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(args)
    try:
        if options.command == "import-csv":
            dataset = import_csv(
                options.source,
                options.output,
                version=options.version,
                split=options.split,
            )
            print(f"Imported {len(dataset.cases)} unverified cases to {options.output}")
        elif options.command == "run":
            configs = [
                RunConfig(
                    options.database,
                    options.how,
                    threshold,
                    options.top_k,
                    options.batch_size,
                    options.pipeline,
                )
                for threshold in options.threshold
            ]
            for config in configs:
                path = run_evaluation(options.dataset, config, options.output_dir)
                print(f"Run saved: {path}")
                print(json.dumps(load_run(path)["metrics"], indent=2))
        elif options.command == "compare":
            result = compare_runs(
                load_run(options.baseline), load_run(options.challenger)
            )
            print(
                json.dumps(
                    {key: value for key, value in result.items() if key != "rows"},
                    indent=2,
                )
            )
            if options.output:
                write_json(options.output, result)
                print(f"Comparison saved: {options.output}")
            if options.fail_on_regression and result["counts"]["regression"]:
                parser.exit(
                    1, f"{result['counts']['regression']} verified cases regressed\n"
                )
        elif options.command == "review":
            from .app import serve

            serve(options.runs, options.port)
        else:
            dataset = export_reviewed(
                options.dataset,
                options.output,
                ReviewStore(options.reviews),
                options.version,
            )
            print(
                f"Exported {len(dataset.cases)} cases as version {dataset.version}: {options.output}"
            )
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Evaluation failed: {exc}\n")
