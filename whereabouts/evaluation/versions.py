from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

from .dataset import file_hash, write_json
from .engine import RunConfig, code_identity, load_run

PROTOCOL_VERSION = 1


def command(args: list[str], cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({args[0]}):\n{result.stderr or result.stdout}"
        )
    return result.stdout.strip()


@dataclass(frozen=True)
class AlgorithmVersion:
    name: str
    commit: str

    def __post_init__(self) -> None:
        if not self.name.strip() or self.name == "Working copy":
            raise ValueError("Choose a nonempty version name other than Working copy")
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError(
                "Algorithm versions require a full 40-character Git commit SHA"
            )


def load_versions(path: Path) -> list[AlgorithmVersion]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("versions"), list)
    ):
        raise ValueError("Unsupported version registry")
    versions = [AlgorithmVersion(**entry) for entry in value["versions"]]
    if len({version.name for version in versions}) != len(versions):
        raise ValueError("Duplicate algorithm version names")
    return versions


def register_version(root: Path, registry: Path, version: AlgorithmVersion) -> None:
    command(["git", "cat-file", "-e", f"{version.commit}^{{commit}}"], root)
    for file in ("whereabouts/evaluation/worker.py", "pyproject.toml", "uv.lock"):
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{version.commit}:{file}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError(
                f"Unsupported revision: missing {file}. Commit the worker contract before registering it."
            )
    versions = load_versions(registry)
    if version.name in {entry.name for entry in versions}:
        raise ValueError("This version name is already registered")
    registry.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry.with_name(f"{registry.name}.{uuid4().hex}.tmp")
    try:
        write_json(
            temporary,
            {
                "schema_version": 1,
                "versions": [asdict(v) for v in [*versions, version]],
            },
        )
        temporary.replace(registry)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_worktree(root: Path, cache: Path, version: AlgorithmVersion) -> Path:
    path = cache.resolve() / "worktrees" / version.commit
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        command(["git", "worktree", "add", "--detach", str(path), version.commit], root)
    if command(["git", "rev-parse", "HEAD"], path) != version.commit:
        raise ValueError("Cached worktree does not match its pinned revision")
    if command(["git", "status", "--porcelain", "--untracked-files=all"], path):
        raise ValueError(
            "Cached historical worktree has changes; restore it before running"
        )
    if not (path / "whereabouts/evaluation/worker.py").is_file():
        raise ValueError("Revision does not support the evaluation worker contract")
    return path


def snapshot_source(root: Path, cache: Path) -> Path:
    """Preserve working-copy code without importing it into the UI process."""
    destination = cache.resolve() / "sources" / uuid4().hex
    for path in (root / "whereabouts").rglob("*"):
        if path.is_file() and path.suffix in (".py", ".sql", ".html"):
            target = destination / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy2(root / name, destination / name)
    return destination


def run_version(
    root: Path,
    runs_dir: Path,
    dataset: Path,
    config: RunConfig,
    experiment: str,
    version: AlgorithmVersion | None = None,
) -> Path:
    if not experiment.strip():
        raise ValueError("An experiment name is required")
    if config.reference_path is None:
        raise ValueError("Select an explicit reference database snapshot")
    root, runs_dir, dataset = root.resolve(), runs_dir.resolve(), dataset.resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    origin = code_identity()
    cache = runs_dir / "implementations"
    implementation = (
        prepare_worktree(root, cache, version)
        if version
        else snapshot_source(root, cache)
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)
    if version:
        launcher = ["uv", "run", "--locked", "--project", str(implementation), "python"]
    else:
        launcher = [sys.executable]
    with TemporaryDirectory(prefix="evaluation-", dir=runs_dir) as temporary:
        scratch = Path(temporary)
        request, response = scratch / "request.json", scratch / "response.json"
        write_json(
            request,
            {
                "protocol_version": PROTOCOL_VERSION,
                "dataset": str(dataset),
                "dataset_sha256": file_hash(dataset),
                "reference_sha256": file_hash(Path(config.reference_path)),
                "config": asdict(config),
                "output_dir": str(scratch / "runs"),
            },
        )
        result = subprocess.run(
            [
                *launcher,
                "-m",
                "whereabouts.evaluation.worker",
                "--request",
                str(request),
                "--response",
                str(response),
            ],
            cwd=implementation,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                f"Algorithm execution failed:\n{result.stderr or result.stdout}"
            )
        payload = json.loads(response.read_text(encoding="utf-8"))
        if payload.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Algorithm returned an unsupported worker protocol")
        output = Path(payload["run"]).resolve()
        if not output.is_relative_to(scratch):
            raise ValueError("Worker returned a result outside its output directory")
        run = load_run(output)
        request_data = json.loads(request.read_text(encoding="utf-8"))
        if (
            run["dataset"]["sha256"] != request_data["dataset_sha256"]
            or run["database"]["sha256"] != request_data["reference_sha256"]
            or run["config"] != asdict(config)
        ):
            raise ValueError("Worker result does not match the requested experiment")
        if version and (
            run["code"]["git_revision"] != version.commit or run["code"]["git_dirty"]
        ):
            raise ValueError("Worker did not execute the clean pinned revision")
        if not version:
            if run["code"]["package_sha256"] != origin["package_sha256"]:
                raise ValueError(
                    "Working-copy source changed while its snapshot was being prepared"
                )
            run["code"].update(
                {
                    key: origin[key]
                    for key in ("git_revision", "git_dirty", "git_status")
                }
            )
        run["experiment"] = experiment.strip()
        run["implementation"] = {
            "version": asdict(version) if version else None,
            "source_path": str(implementation),
            "protocol_version": PROTOCOL_VERSION,
        }
        run["timing"]["wall_seconds"] = perf_counter() - started
        destination = runs_dir / f"{run['run_id']}.json"
        write_json(destination, run)
        return destination
