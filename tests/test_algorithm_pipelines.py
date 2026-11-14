from __future__ import annotations

import csv
from importlib import import_module
from pathlib import Path

import duckdb
from duckdb import DuckDBPyConnection
import pandas as pd
import pytest

from whereabouts import Matcher
from whereabouts.AddressLoader import AddressLoader
from whereabouts.GNAFLoader import GNAFLoader
from whereabouts.LoadAddresses import LoadAddresses
from whereabouts.QueryPipeline import QueryPipeline
from whereabouts.matching_queries.addrtext_with_detail import (
    build_address_detail_pipeline,
)
from whereabouts.matching_queries.database import (
    create_geocoder_tables,
    inverted_index_pipeline,
    prepare_trigram_index,
    prepare_trigram_merge,
    trigram_chunk_pipeline,
    trigram_merge_pipeline,
)
from whereabouts.matching_queries.phrases import build_phrase_pipeline


def _count(connection: DuckDBPyConnection, sql: str) -> int:
    row = connection.execute(sql).fetchone()
    assert row is not None and isinstance(row[0], int)
    return row[0]


@pytest.fixture
def reference_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    models = tmp_path / "models"
    models.mkdir()
    with duckdb.connect(str(models / "sample.db")) as connection:
        create_geocoder_tables(connection).execute_direct()
        connection.execute("""
            INSERT INTO addrtext VALUES
            (1, '115 SYDNEY RD, BRUNSWICK VIC 3056', NULL, 'BRUNSWICK', '3056', 'VIC', -37.7, 144.9),
            (2, 'UNIT 1 115 SYDNEY RD, BRUNSWICK VIC 3056', NULL, 'BRUNSWICK', '3056', 'VIC', -37.7, 144.9)
        """)
        build_address_detail_pipeline(connection).execute_as_table(
            "addrtext_with_detail"
        )
        for kind in ("standard", "skipphrase"):
            pipeline = build_phrase_pipeline(connection, kind)
            for chunk in (1, 2):
                pipeline.execute_into_table(
                    "phrase" if kind == "standard" else "skipphrase", [chunk]
                )
            inverted_index_pipeline(connection, kind).execute_direct()
        prepare_trigram_index(connection).execute_direct()
        for chunk in range(100):
            trigram_chunk_pipeline(connection).execute_into_table(
                "trigramphraseinverted", [chunk]
            )
        prepare_trigram_merge(connection).execute_direct()
        for chunk in range(100):
            trigram_merge_pipeline(connection).execute_into_table(
                "trigramphraseinverted3", [chunk]
            )
    module = import_module("whereabouts.Matcher")
    monkeypatch.setattr(module.importlib.resources, "files", lambda package: tmp_path)
    monkeypatch.setattr(
        module,
        "load_libraries",
        lambda con: con.execute("CREATE MACRO unaccent(value) AS strip_accents(value)"),
    )
    return tmp_path


@pytest.mark.parametrize(
    ("address", "normalized", "matched", "score"),
    [
        (
            "115 Sydney Rd, Brunswick VIC 3056",
            "115 SYDNEY RD BRUNSWICK VIC 3056",
            "115 SYDNEY RD BRUNSWICK VIC 3056",
            1.0,
        ),
        (
            "  115, S\u00fddney RD. (Br\u00fan\u015bwick) VIC-3056!!  ",
            "115 SYDNEY RD BRUNSWICK VIC 3056",
            "115 SYDNEY RD BRUNSWICK VIC 3056",
            1.0,
        ),
        (
            "Unit 1 / 115 Sydney Rd Brunswick VIC 3056",
            "UNIT 1 115 SYDNEY RD BRUNSWICK VIC 3056",
            "UNIT 1 115 SYDNEY RD BRUNSWICK VIC 3056",
            1.0,
        ),
        (
            "115 Sydney Rd Brunswick",
            "115 SYDNEY RD BRUNSWICK",
            "115 SYDNEY RD BRUNSWICK VIC 3056",
            0.5,
        ),
    ],
)
def test_standard_normalizes_inputs_and_ranks_building_or_unit(
    reference_database: Path, address: str, normalized: str, matched: str, score: float
) -> None:
    with Matcher("sample", how="standard") as matcher:
        results = matcher.geocode([address])
    assert len(results) == 1
    result = results[0]
    assert result["input_address"] == normalized
    assert result["address_matched"] == matched
    assert result["similarity"] == pytest.approx(score)
    assert result["suburb"] == "BRUNSWICK"
    assert result["postcode"] == "3056"
    assert result["latitude"] == pytest.approx(-37.7)
    assert result["longitude"] == pytest.approx(144.9)
    assert set(result) == {
        "address_id",
        "input_address",
        "address_matched",
        "suburb",
        "postcode",
        "latitude",
        "longitude",
        "similarity",
        "match_numerics",
        "match_alpha_tokens",
        "input_numerics",
        "input_alpha_tokens",
    }


@pytest.mark.parametrize(
    ("address", "accepted"),
    [
        ("999 Sydney Rd Brunswick", False),
        ("115 9 8 7 6 Sydney Rd Brunswick", True),
        ("115 9 8 7 6 5 Sydney Rd Brunswick", False),
    ],
)
def test_standard_numeric_filter_rejects_conflicts_and_accepts_boundary(
    reference_database: Path, address: str, accepted: bool
) -> None:
    with Matcher("sample", how="standard") as matcher:
        result = matcher.geocode([address])[0]
    if accepted:
        assert result["address_matched"] == "115 SYDNEY RD BRUNSWICK VIC 3056"
        assert result["similarity"] == pytest.approx(1 / 6)
    else:
        assert pd.isna(result["address_matched"])
        assert pd.isna(result["similarity"])


@pytest.mark.parametrize(("frequency", "accepted"), [(999, True), (1000, False)])
def test_standard_excludes_phrases_at_frequency_cutoff(
    reference_database: Path, frequency: int, accepted: bool
) -> None:
    with Matcher("sample", how="standard") as matcher:
        matcher.con.execute(
            "UPDATE remote.phraseinverted SET frequency = ?", [frequency]
        )
        result = matcher.geocode(["115 Sydney Rd Brunswick VIC 3056"])[0]
    if accepted:
        assert result["address_matched"] == "115 SYDNEY RD BRUNSWICK VIC 3056"
    else:
        assert pd.isna(result["address_matched"])


def test_standard_preserves_sparse_ids_duplicate_inputs_and_unmatched_rows(
    reference_database: Path,
) -> None:
    addresses = [
        "115 Sydney Rd Brunswick",
        "999 Sydney Rd Brunswick",
        "115 Sydney Rd Brunswick",
        "",
        "Sydney Rd Brunswick",
        "321 Unknown Street",
    ]
    with Matcher("sample", how="standard") as matcher:
        results = matcher.geocode(addresses, address_ids=[40, 5, 20, 60, 70, 80])
    assert [row["address_id"] for row in results] == [5, 20, 40, 60, 70, 80]
    by_id = {row["address_id"]: row for row in results}
    for address_id in (20, 40):
        assert (
            by_id[address_id]["address_matched"] == "115 SYDNEY RD BRUNSWICK VIC 3056"
        )
    for address_id in (5, 60, 70, 80):
        assert pd.isna(by_id[address_id]["address_matched"])
    assert by_id[60]["input_address"] == ""
    assert by_id[70]["input_address"] == "SYDNEY RD BRUNSWICK"


@pytest.mark.parametrize("candidate_count", [49, 50, 51])
def test_standard_candidate_budget_and_reference_id_tie_break(
    reference_database: Path, candidate_count: int
) -> None:
    with Matcher("sample", how="standard") as matcher:
        matcher.con.execute(
            "DELETE FROM remote.phraseinverted; DELETE FROM remote.addrtext_with_detail"
        )
        # Coordinates identify the winning reference when candidate addresses and scores are identical.
        matcher.con.execute(
            """
            INSERT INTO remote.addrtext_with_detail
            SELECT reference_id, '115 SYDNEY RD BRUNSWICK VIC 3056', ['115', '3056'],
                   '115 SYDNEY RD BRUNSWICK VIC 3056', 'BRUNSWICK', '3056',
                   cast(reference_id AS FLOAT), 144.9, 'VIC'
            FROM range(1, ?) AS refs(reference_id)
        """,
            [candidate_count + 1],
        )
        matcher.con.execute("""
            INSERT INTO remote.phraseinverted
            SELECT 'SYDNEY RD', list(addr_id ORDER BY addr_id DESC), count(*)
            FROM remote.addrtext_with_detail
        """)
        matcher.con.execute("""
            CREATE TABLE input_addresses AS
            SELECT 1 AS address_id, '115 SYDNEY RD BRUNSWICK VIC 3056' AS address
        """)
        steps = matcher.pipeline.steps
        pruning = next(
            index
            for index, step in enumerate(steps)
            if step.output_table_name == "top_50_candidates"
        )
        candidates = QueryPipeline(matcher.con, steps[: pruning + 1]).execute()
        expected_count = min(candidate_count, 50)
        assert len(candidates) == expected_count
        assert set(candidates["address_id2"]) == set(range(1, expected_count + 1))
        result = matcher.pipeline.execute()
        assert len(result) == 1
        assert result.iloc[0]["latitude"] == 1.0
        assert result.iloc[0]["similarity"] == 1.0


@pytest.mark.parametrize("how", ["skipphrase", "trigram"])
def test_public_matcher_returns_ranked_candidates(
    reference_database: Path, how: str
) -> None:
    with Matcher("sample", how=how) as matcher:
        results = matcher.geocode(
            ["115 sydney rd brunswick", "no such road"], top_n=2, address_ids=[10, 20]
        )
        matches = [row for row in results if row["address_id"] == 10]
        assert len(matches) == 2
        assert {row["address_id2"] for row in matches} == {1, 2}
        assert results[-1]["address_id"] == 20 and pd.isna(
            results[-1]["address_matched"]
        )
        assert set(results[0]) == {
            "address_id",
            "address",
            "address_id2",
            "address_matched",
            "suburb",
            "postcode",
            "latitude",
            "longitude",
            "similarity",
        }
        standard = matcher.geocode(["115 sydney rd brunswick"], how="standard")
        assert standard[0]["address_matched"] == "115 SYDNEY RD BRUNSWICK VIC 3056"
        assert "input_address" in standard[0]


@pytest.mark.parametrize("loader_class", [AddressLoader, LoadAddresses])
def test_loaders_share_pipelines_and_bind_mapped_state_column(
    tmp_path: Path, loader_class: type[AddressLoader]
) -> None:
    source = tmp_path / "addresses' sample.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["id", "label", "site", "locality", "postal", "region", "lat", "lon"]
        )
        writer.writerow(
            [
                1,
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "",
                "BRUNSWICK",
                "3056",
                "VIC",
                -37.7,
                144.9,
            ]
        )
        writer.writerow(
            [2, "1 OTHER ST OTHER QLD 4000", "", "OTHER", "4000", "QLD", -27.0, 153.0]
        )
    details = {
        "schema": dict(
            zip(
                [
                    "addr_id",
                    "full_address",
                    "address_site_name",
                    "locality_name",
                    "postcode",
                    "state",
                    "latitude",
                    "longitude",
                ],
                ["id", "label", "site", "locality", "postal", "region", "lat", "lon"],
                strict=True,
            )
        ),
        "data": {"filepath": str(source), "sep": ","},
    }
    loader = loader_class(str(tmp_path / "builder.db"))
    try:
        loader.create_geocoder_tables()
        loader.load_data(details, ["VIC"])
        loader.create_final_address_table()
        assert loader.con.execute(
            "SELECT addr_id, STATE FROM addrtext_with_detail"
        ).fetchall() == [(1, "VIC")]
        loader.create_phrases(["standard", "skipphrase"])
        loader.create_inverted_index(["standard", "skipphrase"])
        assert _count(loader.con, "SELECT count(*) FROM skipphraseinverted") > 0
        assert (
            _count(
                loader.con, "SELECT count(*) FROM phrase WHERE tokenphrase = '115 RD'"
            )
            == 1
        )
        loader.clean_database(["standard", "skipphrase"])
        assert "addrtext" not in {
            row[0] for row in loader.con.execute("SHOW TABLES").fetchall()
        }
    finally:
        loader.con.close()


def test_legacy_gnaf_preserves_address_shape_and_builds_compatible_trigram_index(
    tmp_path: Path,
) -> None:
    source = tmp_path / "gnaf.psv"
    source.write_text(
        "ADDRESS_DETAIL_PID|ADDRESS_LABEL|ADDRESS_SITE_NAME|LOCALITY_NAME|POSTCODE|STATE|LATITUDE|LONGITUDE\n"
        "1|115 SYDNEY RD BRUNSWICK VIC 3056||BRUNSWICK|3056|VIC|-37.7|144.9\n"
        "2|1 OTHER ST OTHER NSW 2000||OTHER|2000|NSW|-33.0|151.0\n"
    )
    loader = GNAFLoader(str(tmp_path / "gnaf.db"))
    try:
        loader.create_geocoder_tables()
        loader.load_gnaf_data(str(source), [])
        assert _count(loader.con, "SELECT count(*) FROM addrtext") == 0
        loader.load_gnaf_data(str(source))
        loader.create_final_address_table()
        columns = [
            row[0]
            for row in loader.con.execute("DESCRIBE addrtext_with_detail").fetchall()
        ]
        assert columns == [
            "addr_id",
            "addr",
            "numeric_tokens",
            "ADDRESS_LABEL",
            "suburb",
            "POSTCODE",
            "LATITUDE",
            "LONGITUDE",
        ]
        assert _count(loader.con, "SELECT count(*) FROM addrtext_with_detail") == 1
        loader.create_phrases()
        assert (
            _count(
                loader.con, "SELECT count(*) FROM phrase WHERE tokenphrase = '115 RD'"
            )
            == 0
        )
        loader.create_inverted_index()
        loader.create_phrases(["trigram"])
        assert _count(loader.con, "SELECT count(*) FROM trigramphraseinverted3") > 0
        kind = loader.con.execute(
            "SELECT typeof(trigramphrase) FROM trigramphraseinverted3 LIMIT 1"
        ).fetchone()
        assert kind is not None and kind[0] == "INTEGER"
        loader.clean_database(["standard", "trigram"])
        assert {row[0] for row in loader.con.execute("SHOW TABLES").fetchall()} == {
            "addrtext_with_detail",
            "phraseinverted",
            "phraseinverted_with_nums",
            "numbers",
            "trigramphraseinverted3",
        }
    finally:
        loader.con.close()
