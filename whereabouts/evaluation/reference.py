from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import duckdb
import pandas as pd

from .dataset import normalize


@dataclass(frozen=True)
class ReferenceFilters:
    street_number: str = ""
    lot_number: str = ""
    street_name: str = ""
    suburb: str = ""


@dataclass(frozen=True)
class ReferencePage:
    rows: pd.DataFrame
    total: int


def label_pattern(value: str) -> str:
    phrase = r"\s+".join(re.escape(token) for token in normalize(value).split())
    return rf"(^|[^\p{{L}}\p{{N}}]){phrase}([^\p{{L}}\p{{N}}]|$)"


def lookup_reference(
    database: Path,
    filters: ReferenceFilters,
    page: int = 0,
    page_size: int = 100,
) -> ReferencePage:
    if database.suffix != ".db" or not database.is_file():
        raise ValueError("Select an existing local .db reference snapshot")
    if type(page) is not int or page < 0 or type(page_size) is not int or page_size < 1:
        raise ValueError(
            "Lookup page must be nonnegative and page size must be positive"
        )
    values = {
        name: normalize(getattr(filters, name))
        for name in ("street_number", "lot_number", "street_name", "suburb")
    }
    if not any(values.values()):
        raise ValueError("Enter at least one reference lookup filter")
    with duckdb.connect(str(database.resolve()), read_only=True) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "addrtext_with_detail" not in tables:
            raise ValueError("Reference snapshot does not contain addrtext_with_detail")
        columns = {
            row[0].lower()
            for row in con.execute("DESCRIBE addrtext_with_detail").fetchall()
        }
        if "addr_id" not in columns or not columns.intersection(
            {"address_label", "addr"}
        ):
            raise ValueError("Reference lookup requires address IDs and address labels")
        label = "address_label" if "address_label" in columns else "addr"
        suburb = "suburb" if "suburb" in columns else "locality_name"
        if suburb not in columns:
            raise ValueError("Reference lookup requires suburb or locality_name")
        conditions, parameters = [], []
        for name in ("street_number", "lot_number", "street_name"):
            if values[name]:
                term = f"LOT {values[name]}" if name == "lot_number" else values[name]
                conditions.append(f"regexp_matches(upper({label}), ?)")
                parameters.append(label_pattern(term))
        if values["suburb"]:
            conditions.append(
                rf"regexp_replace(trim(upper({suburb})), '\s+', ' ', 'g') = ?"
            )
            parameters.append(values["suburb"])
        where = " AND ".join(conditions)
        total = con.execute(
            f"SELECT count(*) FROM addrtext_with_detail WHERE {where}", parameters
        ).fetchone()[0]
        offset = page * page_size
        if page and offset >= total:
            raise ValueError(
                "This result page no longer exists; search the reference database again"
            )
        details = [
            name if name in columns else f"NULL AS {name}"
            for name in ("state", "postcode", "latitude", "longitude")
        ]
        rows = con.execute(
            f"""
                SELECT addr_id AS reference_id, {label} AS address, {suburb} AS suburb,
                       {", ".join(details)}
                FROM addrtext_with_detail WHERE {where}
                ORDER BY addr_id LIMIT ? OFFSET ?
            """,
            [*parameters, page_size, offset],
        ).fetchdf()
    return ReferencePage(rows, total)
