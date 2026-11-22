from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.resources
import json
import logging
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qs, urlparse

import duckdb

from .dataset import EvaluationCase, ReviewStore, file_hash
from .engine import RunConfig, compare_runs, load_run, run_evaluation

logger = logging.getLogger(__name__)


def create_server(runs_dir: Path, port: int = 8765) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    runs_dir.mkdir(parents=True, exist_ok=True)
    store = ReviewStore(runs_dir / "reviews.sqlite3")
    token = secrets.token_hex(32)
    template = (
        importlib.resources.files(__package__)
        .joinpath("review.html")
        .read_text(encoding="utf-8")
    )

    def read_run(run_id: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run ID")
        return load_run(runs_dir / f"{run_id}.json")

    class Handler(BaseHTTPRequestHandler):
        def reply(
            self, status: HTTPStatus, value: object, *, html: bool = False
        ) -> None:
            data = (
                str(value).encode()
                if html
                else json.dumps(value, allow_nan=False).encode()
            )
            self.send_response(status)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8" if html else "application/json",
            )
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'nonce-{token}'; style-src 'nonce-{token}'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def allowed(self, *, write: bool = False) -> bool:
            host = f"127.0.0.1:{server.server_port}"
            if self.headers.get("Host") != host:
                self.reply(
                    HTTPStatus.FORBIDDEN, {"error": "Use the printed 127.0.0.1 URL"}
                )
                return False
            if write and not secrets.compare_digest(
                self.headers.get("X-Evaluation-Token", ""), token
            ):
                self.reply(HTTPStatus.FORBIDDEN, {"error": "Invalid review token"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{host}":
                self.reply(
                    HTTPStatus.FORBIDDEN,
                    {"error": "Cross-origin requests are not allowed"},
                )
                return False
            return True

        def do_GET(self) -> None:
            if not self.allowed():
                return
            url = urlparse(self.path)
            try:
                if url.path == "/":
                    self.reply(
                        HTTPStatus.OK, template.replace("__TOKEN__", token), html=True
                    )
                elif url.path == "/api/runs":
                    runs = [
                        read_run(path.stem)
                        for path in sorted(runs_dir.glob("*.json"))
                        if re.fullmatch(r"[a-f0-9]{32}", path.stem)
                    ]
                    self.reply(
                        HTTPStatus.OK,
                        [
                            {key: value for key, value in run.items() if key != "rows"}
                            for run in runs
                        ],
                    )
                elif url.path == "/api/compare":
                    query = parse_qs(url.query)
                    baseline = read_run(query["baseline"][0])
                    challenger = read_run(query["challenger"][0])
                    comparison = compare_runs(baseline, challenger)
                    comparison["reviews"] = store.latest(baseline["dataset"]["sha256"])
                    self.reply(HTTPStatus.OK, comparison)
                else:
                    self.reply(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except (ValueError, KeyError, OSError) as exc:
                logger.warning("Evaluation request failed: %s", exc)
                self.reply(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_POST(self) -> None:
            if not self.allowed(write=True):
                return
            try:
                if (
                    self.headers.get("Content-Type", "").split(";")[0]
                    != "application/json"
                ):
                    raise ValueError("Expected application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError("Request must be between 1 byte and 1 MiB")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Expected a JSON object")
                run = read_run(value["run_id"])
                if self.path == "/api/reviews":
                    original = next(
                        (
                            row["case"]
                            for row in run["rows"]
                            if row["case"]["case_id"] == value["case_id"]
                        ),
                        None,
                    )
                    if original is None:
                        raise ValueError("Unknown case ID")
                    proposal = EvaluationCase.from_dict(value["proposal"])
                    if (
                        proposal.case_id != original["case_id"]
                        or proposal.input_address != original["input_address"]
                    ):
                        raise ValueError(
                            "Reviews cannot change case IDs or input addresses"
                        )
                    store.save(run["dataset"]["sha256"], proposal)
                    self.reply(HTTPStatus.OK, {"saved": True})
                elif self.path == "/api/run":
                    if run["dataset"]["split"] == "held_out":
                        raise ValueError(
                            "Use the CLI for held-out evaluations; do not tune against held-out labels"
                        )
                    source = Path(run["dataset"]["path"])
                    if file_hash(source) != run["dataset"]["sha256"]:
                        raise ValueError(
                            "Source dataset has changed; launch a new CLI run"
                        )
                    if (
                        file_hash(Path(run["database"]["path"]))
                        != run["database"]["sha256"]
                    ):
                        raise ValueError(
                            "Reference database has changed; launch a new CLI baseline"
                        )
                    config = RunConfig(
                        database=run["config"]["database"],
                        how=value["how"],
                        threshold=value["threshold"],
                        top_k=value["top_k"],
                        batch_size=run["config"]["batch_size"],
                    )
                    path = run_evaluation(source, config, runs_dir)
                    self.reply(HTTPStatus.OK, {"run_id": path.stem})
                else:
                    self.reply(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except (ValueError, KeyError, TypeError, OSError) as exc:
                logger.warning("Evaluation request failed: %s", exc)
                self.reply(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except (duckdb.Error, RuntimeError, ImportError, AttributeError):
                logger.exception("Evaluation execution failed")
                self.reply(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "Evaluation failed; see server log"},
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


def serve(runs_dir: Path, port: int) -> None:
    with create_server(runs_dir, port) as server:
        print(f"Evaluation UI: http://127.0.0.1:{server.server_port}", flush=True)
        print(
            "Press Ctrl+C to stop. Label proposals are saved separately from runs.",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nEvaluation UI stopped.")
