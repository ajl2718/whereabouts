from pathlib import Path

import duckdb
import pytest

from whereabouts.evaluation.dataset import file_hash
from whereabouts.evaluation.reference import ReferenceFilters, lookup_reference


@pytest.fixture
def reference_db(tmp_path: Path) -> Path:
    path = tmp_path / "reference.db"
    with duckdb.connect(str(path)) as con:
        con.execute("""
            CREATE TABLE addrtext_with_detail AS
            SELECT addr_id, address_label, address_label AS addr, suburb
            FROM (VALUES
                (1, 'UNIT 1/115 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (2, '115 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (3, 'LOT 115 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (4, 'LOT 15 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (5, '115A SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (6, '1115 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (7, '115 SYDNEY RD OTHER VIC 9999', 'OTHER'),
                (8, '115 SYDNEY ROAD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (9, '115 ST. JOHN''S RD BRUNSWICK VIC 3056', 'BRUNSWICK'),
                (10, '115-117 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK')
            ) AS t(addr_id, address_label, suburb)
        """)
    return path


def test_label_lookup_combines_filters_and_respects_token_boundaries(
    reference_db: Path,
) -> None:
    original = file_hash(reference_db)
    result = lookup_reference(
        reference_db,
        ReferenceFilters(
            street_number="115",
            street_name=" sydney   rd ",
            suburb=" brunswick ",
        ),
    )
    assert result.total == 4
    assert result.rows["reference_id"].tolist() == [1, 2, 3, 10]
    assert result.rows.iloc[0]["address"].startswith("UNIT 1/115")
    lot = lookup_reference(
        reference_db,
        ReferenceFilters(
            street_number="115",
            lot_number="115",
            street_name="SYDNEY RD",
            suburb="BRUNSWICK",
        ),
    )
    assert lot.rows["reference_id"].tolist() == [3]
    assert lookup_reference(reference_db, ReferenceFilters(lot_number="15")).rows[
        "reference_id"
    ].tolist() == [4]
    assert lookup_reference(reference_db, ReferenceFilters(street_number="115A")).rows[
        "reference_id"
    ].tolist() == [5]
    assert (
        lookup_reference(
            reference_db, ReferenceFilters(street_name="ST. JOHN'S RD")
        ).total
        == 1
    )
    assert (
        lookup_reference(reference_db, ReferenceFilters(street_name="SYDNEY.*")).total
        == 0
    )
    assert (
        lookup_reference(
            reference_db,
            ReferenceFilters(
                street_name="'; DROP TABLE addrtext_with_detail; --",
            ),
        ).total
        == 0
    )
    assert file_hash(reference_db) == original


def test_lookup_exposes_all_results_across_stable_pages(reference_db: Path) -> None:
    with duckdb.connect(str(reference_db)) as con:
        con.execute("""
            INSERT INTO addrtext_with_detail
            SELECT i, '1 TEST ST PAGED', '1 TEST ST PAGED', 'PAGED' FROM range(1000, 1205) AS t(i)
        """)
    pages = [
        lookup_reference(reference_db, ReferenceFilters(suburb="PAGED"), page=i)
        for i in range(3)
    ]
    assert [page.total for page in pages] == [205, 205, 205]
    assert [len(page.rows) for page in pages] == [100, 100, 5]
    assert [value for page in pages for value in page.rows["reference_id"]] == list(
        range(1000, 1205)
    )
    with pytest.raises(ValueError, match="page no longer exists"):
        lookup_reference(reference_db, ReferenceFilters(suburb="PAGED"), page=3)
    with pytest.raises(ValueError, match="at least one"):
        lookup_reference(reference_db, ReferenceFilters(suburb="  "))


def test_lookup_supports_legacy_labels_and_reports_unsupported_schema(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.db"
    with duckdb.connect(str(path)) as con:
        con.execute("""
            CREATE TABLE addrtext_with_detail AS
            SELECT 1 AS addr_id, 'LOT 15 TEST ST' AS addr, 'TEST TOWN' AS locality_name
        """)
    result = lookup_reference(
        path, ReferenceFilters(lot_number="15", suburb="test town")
    )
    assert result.total == 1 and result.rows.iloc[0]["address"] == "LOT 15 TEST ST"
    with duckdb.connect(str(path)) as con:
        con.execute("ALTER TABLE addrtext_with_detail DROP COLUMN locality_name")
    with pytest.raises(ValueError, match="suburb"):
        lookup_reference(path, ReferenceFilters(street_number="15"))
    with pytest.raises(ValueError, match="existing"):
        lookup_reference(tmp_path / "missing.db", ReferenceFilters(street_number="15"))
