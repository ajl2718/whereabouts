from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

PRECISIONS = ("exact", "unit", "building", "street", "locality")
LABEL_STATUSES = ("verified", "needs_review", "ambiguous")


def normalize(value: str) -> str:
    return " ".join(value.upper().split())


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Create a new file, never overwrite an existing dataset or run."""
    content = json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)


@dataclass(frozen=True)
class AcceptableMatch:
    address: str | None = None
    reference_id: str | None = None
    locality: str | None = None
    postcode: str | None = None

    def __post_init__(self) -> None:
        for value in (self.address, self.reference_id, self.locality, self.postcode):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(
                    "Acceptable-match fields must be nonempty strings or null"
                )
        if not any((self.address, self.reference_id, self.locality)):
            raise ValueError(
                "An acceptable match needs an address, reference_id, or locality"
            )


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    input_address: str
    acceptable: list[AcceptableMatch]
    precision: str = "exact"
    label_status: str = "needs_review"
    expect_abstention: bool = False
    tags: list[str] = field(default_factory=list)
    evidence: str = ""
    notes: str = ""
    error_mode: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("case_id must be a nonempty string")
        if not isinstance(self.input_address, str) or not self.input_address.strip():
            raise ValueError(f"{self.case_id}: input_address must be a nonempty string")
        if self.precision not in PRECISIONS or self.label_status not in LABEL_STATUSES:
            raise ValueError(f"{self.case_id}: invalid precision or label_status")
        if not isinstance(self.expect_abstention, bool):
            raise ValueError(f"{self.case_id}: expect_abstention must be boolean")
        if not isinstance(self.tags, list) or any(
            not isinstance(tag, str) or not tag.strip() for tag in self.tags
        ):
            raise ValueError(f"{self.case_id}: tags must be a list of nonempty strings")
        if any(
            not isinstance(value, str)
            for value in (self.evidence, self.notes, self.error_mode)
        ):
            raise ValueError(
                f"{self.case_id}: evidence, notes, and error_mode must be strings"
            )
        if not isinstance(self.acceptable, list) or any(
            not isinstance(match, AcceptableMatch) for match in self.acceptable
        ):
            raise ValueError(f"{self.case_id}: acceptable must be a list of matches")
        if self.expect_abstention and self.acceptable:
            raise ValueError(
                f"{self.case_id}: abstention cases cannot also have acceptable matches"
            )
        if self.label_status == "verified" and (
            not self.evidence.strip() or not (self.acceptable or self.expect_abstention)
        ):
            raise ValueError(
                f"{self.case_id}: verified labels need evidence and an answer or expected abstention"
            )
        for match in self.acceptable:
            if self.precision == "locality":
                if match.locality is None:
                    raise ValueError(
                        f"{self.case_id}: locality precision requires a locality"
                    )
            elif match.address is None and match.reference_id is None:
                raise ValueError(
                    f"{self.case_id}: {self.precision} precision needs explicit candidate identities"
                )

    @classmethod
    def from_dict(cls, value: dict) -> EvaluationCase:
        if not isinstance(value, dict) or not isinstance(value.get("acceptable"), list):
            raise ValueError("Each case needs an acceptable list")
        try:
            return cls(
                **{
                    **value,
                    "acceptable": [
                        AcceptableMatch(**match) for match in value["acceptable"]
                    ],
                }
            )
        except TypeError as exc:
            raise ValueError(f"Invalid case fields: {exc}") from exc


@dataclass(frozen=True)
class EvaluationDataset:
    name: str
    version: str
    split: str
    cases: list[EvaluationCase]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported dataset schema_version")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.name, self.version)
        ):
            raise ValueError("Dataset name and version must be nonempty strings")
        if self.split not in ("development", "held_out"):
            raise ValueError("Dataset split must be development or held_out")
        if not self.cases or any(
            not isinstance(case, EvaluationCase) for case in self.cases
        ):
            raise ValueError("Dataset must contain evaluation cases")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate case_id")

    @classmethod
    def load(cls, path: Path) -> EvaluationDataset:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, value: dict) -> EvaluationDataset:
        if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
            raise ValueError("Dataset must be an object with a cases list")
        try:
            return cls(
                **{
                    **value,
                    "cases": [
                        EvaluationCase.from_dict(case) for case in value["cases"]
                    ],
                }
            )
        except TypeError as exc:
            raise ValueError(f"Invalid dataset fields: {exc}") from exc

    def save(self, path: Path) -> None:
        write_json(path, asdict(self))


def import_csv(
    source: Path, destination: Path, *, version: str = "1", split: str = "development"
) -> EvaluationDataset:
    cases = []
    occurrences: dict[str, int] = {}
    with source.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"input_address", "best_match"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires input_address and best_match columns")
        for line, row in enumerate(reader, 2):
            address = row["input_address"]
            expected = row["best_match"]
            if not address or not expected:
                raise ValueError(
                    f"CSV line {line}: input_address and best_match must be nonempty"
                )
            key = hashlib.sha256(normalize(address).encode()).hexdigest()[:16]
            occurrences[key] = occurrences.get(key, 0) + 1
            cases.append(
                EvaluationCase(
                    case_id=f"{key}-{occurrences[key]}",
                    input_address=address,
                    acceptable=[AcceptableMatch(address=expected)],
                    notes=f"Imported from {source.name}, CSV line {line}; label not independently verified.",
                )
            )
    dataset = EvaluationDataset(source.stem, version, split, cases)
    dataset.save(destination)
    return dataset


class ReviewStore:
    """Append-only label proposals, kept separately from immutable run evidence."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY, dataset_hash TEXT NOT NULL,
                    case_id TEXT NOT NULL, created_at TEXT NOT NULL, proposal TEXT NOT NULL
                )
            """)

    def save(self, dataset_hash: str, case: EvaluationCase) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO reviews(dataset_hash, case_id, created_at, proposal) VALUES (?, ?, ?, ?)",
                (
                    dataset_hash,
                    case.case_id,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(asdict(case)),
                ),
            )

    def latest(self, dataset_hash: str) -> dict[str, dict]:
        with sqlite3.connect(self.path) as con:
            rows = con.execute(
                """SELECT case_id, proposal FROM reviews WHERE id IN (
                       SELECT max(id) FROM reviews WHERE dataset_hash = ? GROUP BY case_id
                   )""",
                (dataset_hash,),
            ).fetchall()
        return {case_id: json.loads(proposal) for case_id, proposal in rows}


def export_reviewed(
    source: Path, destination: Path, store: ReviewStore, version: str
) -> EvaluationDataset:
    dataset = EvaluationDataset.load(source)
    if dataset.version == version:
        raise ValueError("Reviewed labels require a new dataset version")
    proposals = store.latest(file_hash(source))
    cases = [
        EvaluationCase.from_dict(proposals[case.case_id])
        if case.case_id in proposals
        else case
        for case in dataset.cases
    ]
    reviewed = EvaluationDataset(dataset.name, version, dataset.split, cases)
    reviewed.save(destination)
    return reviewed
