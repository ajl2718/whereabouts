from __future__ import annotations

from collections import Counter

import duckdb
import numpy as np
import pandas as pd
import pytest
from duckdb import DuckDBPyConnection

from whereabouts.matching_queries import register_functions
from whereabouts.QueryPipeline import QueryPipeline
from whereabouts.matching_queries.standard_with_neighbours import (
    clean_addresses,
    create_address_numerics,
    create_address_alpha_tokens,
    create_input_phrases,
    first_matching_step,
    unnest_match_candidates,
    extract_match_candidate_details,
    filter_to_top50_candidates,
    neighbouring_suburb_match,
    compute_similarity,
    rank_by_similarity,
    select_current,
    rejoin_all_inputs,
)


@pytest.fixture(scope="module")
def pipeline_connection() -> DuckDBPyConnection:
    """Create one shared DuckDB connection used by all tests in this module."""
    con = duckdb.connect("whereabouts/models/db_test.db")
    # UDFs required by the pipeline components
    register_functions(con)
    # Keep tests independent of optional extension availability.
    con.execute("CREATE OR REPLACE MACRO unaccent(text_value) AS text_value;")
    yield con
    con.close()


@pytest.fixture()
def con(pipeline_connection: DuckDBPyConnection) -> DuckDBPyConnection:
    """Create a temporary input table with example addresses for each test."""
    pipeline_connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE input_addresses AS
        SELECT *
        FROM (
            VALUES
                (1, '115 sydney rd brunswick vic 3056'),
                (2, '504 Sydney Rd, Brunswick'),
                (3, '62 dawson st brunswick east')
        ) AS t(address_id, address);
        """
    )
    yield pipeline_connection
    pipeline_connection.execute("DROP TABLE IF EXISTS input_addresses;")


def test_template_non_empty() -> None:
    """Ensure that there are SQL queries defined for each of the pipeline components"""
    assert clean_addresses.query_template is not None
    assert create_address_numerics.query_template is not None
    assert create_address_alpha_tokens.query_template is not None
    assert create_input_phrases.query_template is not None
    assert first_matching_step.query_template is not None
    assert unnest_match_candidates.query_template is not None
    assert extract_match_candidate_details.query_template is not None
    assert filter_to_top50_candidates.query_template is not None
    assert neighbouring_suburb_match.query_template is not None
    assert compute_similarity.query_template is not None
    assert rank_by_similarity.query_template is not None
    assert select_current.query_template is not None
    assert rejoin_all_inputs.query_template is not None


def test_clean_addresses(con: DuckDBPyConnection) -> None:
    """Test that clean_addresses returns expected output on example data."""
    expected = pd.DataFrame(
        {
            "address_id": np.array([1, 2, 3], dtype="int32"),
            "address": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "504 SYDNEY RD BRUNSWICK",
                "62 DAWSON ST BRUNSWICK EAST",
            ],
        }
    )
    result = QueryPipeline(con=con, steps=[clean_addresses]).execute()
    pd.testing.assert_frame_equal(result, expected)


def test_create_address_numerics(con: DuckDBPyConnection) -> None:
    """Confirm create_address_numerics pipeline returns only numeric tokens"""
    result = QueryPipeline(
        con=con, steps=[clean_addresses, create_address_numerics]
    ).execute()
    result["numeric_tokens"] = result["numeric_tokens"].map(list)

    expected = pd.DataFrame(
        {
            "address_id": np.array([1, 2, 3], dtype="int32"),
            "address": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "504 SYDNEY RD BRUNSWICK",
                "62 DAWSON ST BRUNSWICK EAST",
            ],
            "numeric_tokens": [["115", "3056"], ["504"], ["62"]],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_create_address_alpha_tokens(con: DuckDBPyConnection) -> None:
    """create_address_alpha_tokens splits each address into alpha tokens"""
    result = QueryPipeline(
        con=con,
        steps=[clean_addresses, create_address_numerics, create_address_alpha_tokens],
    ).execute()
    result["numeric_tokens"] = result["numeric_tokens"].map(list)
    result["alpha_tokens"] = result["alpha_tokens"].map(list)

    expected = pd.DataFrame(
        {
            "address_id": pd.array([1, 2, 3], dtype="int32"),
            "address": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "504 SYDNEY RD BRUNSWICK",
                "62 DAWSON ST BRUNSWICK EAST",
            ],
            "numeric_tokens": [["115", "3056"], ["504"], ["62"]],
            "alpha_tokens": [
                ["SYDNEY", "RD", "BRUNSWICK", "VIC"],
                ["SYDNEY", "RD", "BRUNSWICK"],
                ["DAWSON", "ST", "BRUNSWICK", "EAST"],
            ],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_create_input_phrases(con: DuckDBPyConnection) -> None:
    """create_input_phrases generates token bigrams per address"""
    result = QueryPipeline(
        con=con,
        steps=[
            clean_addresses,
            create_address_numerics,
            create_address_alpha_tokens,
            create_input_phrases,
        ],
    ).execute()

    expected = {
        (1, "VIC 3056"),
        (1, "SYDNEY RD"),
        (1, "RD BRUNSWICK"),
        (1, "BRUNSWICK VIC"),
        (1, "115 SYDNEY"),
        (1, "115 RD"),
        (2, "504 SYDNEY"),
        (2, "504 RD"),
        (2, "SYDNEY RD"),
        (2, "RD BRUNSWICK"),
        (3, "62 DAWSON"),
        (3, "62 ST"),
        (3, "DAWSON ST"),
        (3, "ST BRUNSWICK"),
        (3, "BRUNSWICK EAST"),
    }
    assert set(zip(result["address_id"], result["tokenphrase"])) == expected


def test_first_matching_step(con: DuckDBPyConnection) -> None:
    """first_matching_step attaches candidate match IDs to each input phrase"""
    result = QueryPipeline(
        con=con,
        steps=[
            clean_addresses,
            create_address_numerics,
            create_address_alpha_tokens,
            create_input_phrases,
            first_matching_step,
        ],
    ).execute()

    assert set(result.columns) == {"address_id1", "address_ids2"}
    assert len(result) == 3
    # Each input address contributes its bigrams; order not guaranteed.
    assert Counter(result["address_id1"]) == {1: 1, 3: 2}
    # Candidate IDs should be populated (non-null) for every row.
    assert result["address_ids2"].notna().all()


def test_unnest_match_candidates(con: DuckDBPyConnection) -> None:
    """test unnesting step from initial matching step to individual candidate matches"""
    result = QueryPipeline(
        con=con,
        steps=[
            clean_addresses,
            create_address_numerics,
            create_address_alpha_tokens,
            create_input_phrases,
            first_matching_step,
            unnest_match_candidates,
        ],
    ).execute()

    assert list(result.columns) == ["address_id1", "address_id2"]
    assert set(result["address_id1"]) == {1, 3}
    assert result["address_id2"].nunique() == 112
    assert len(result) == 112


def test_extract_match_candidate_details(con: DuckDBPyConnection) -> None:
    """Test that extract_match_candidate_details returns expected output on example data."""
    result = (
        QueryPipeline(
            con=con,
            steps=[
                clean_addresses,
                create_address_numerics,
                create_address_alpha_tokens,
                create_input_phrases,
                first_matching_step,
                unnest_match_candidates,
                extract_match_candidate_details,
            ],
        )
        .execute()
        .sort_values("address_id1")
        .reset_index(drop=True)
    )

    expected = pd.DataFrame(
        {
            "address_id1": np.array([1, 3], dtype="int32"),
            "address_id2": np.array([7174666, 12721438], dtype="int32"),
            "address": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "62 DAWSON ST BRUNSWICK EAST",
            ],
            "input_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62"], dtype=object),
            ],
            "match_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62", "3056"], dtype=object),
            ],
            "input_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "EAST"], dtype=object),
            ],
            "match_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "VIC"], dtype=object),
            ],
            "address_matched": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "62 DAWSON ST BRUNSWICK VIC 3056",
            ],
            "suburb": ["BRUNSWICK", "BRUNSWICK"],
            "STATE": ["VIC", "VIC"],
            "postcode": np.array([3056, 3056], dtype="int32"),
            "latitude": np.array(
                [-37.774810791015625, -37.77077102661133], dtype="float32"
            ),
            "longitude": np.array(
                [144.9606170654297, 144.95619201660156], dtype="float32"
            ),
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_filter_to_top50_candidates(con: DuckDBPyConnection) -> None:
    """Test that filter_to_top50_candidates returns expected output on example data."""
    result = (
        QueryPipeline(
            con=con,
            steps=[
                clean_addresses,
                create_address_numerics,
                create_address_alpha_tokens,
                create_input_phrases,
                first_matching_step,
                unnest_match_candidates,
                extract_match_candidate_details,
                filter_to_top50_candidates,
            ],
        )
        .execute()
        .sort_values("address_id1")
        .reset_index(drop=True)
    )

    expected = pd.DataFrame(
        {
            "address_id1": np.array([1, 3], dtype="int32"),
            "address_id2": np.array([7174666, 12721438], dtype="int32"),
            "address": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "62 DAWSON ST BRUNSWICK EAST",
            ],
            "input_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62"], dtype=object),
            ],
            "match_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62", "3056"], dtype=object),
            ],
            "input_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "EAST"], dtype=object),
            ],
            "match_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "VIC"], dtype=object),
            ],
            "address_matched": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "62 DAWSON ST BRUNSWICK VIC 3056",
            ],
            "suburb": ["BRUNSWICK", "BRUNSWICK"],
            "STATE": ["VIC", "VIC"],
            "postcode": np.array([3056, 3056], dtype="int32"),
            "latitude": np.array(
                [-37.774810791015625, -37.77077102661133], dtype="float32"
            ),
            "longitude": np.array(
                [144.9606170654297, 144.95619201660156], dtype="float32"
            ),
            "pre_rank": np.array([1, 1], dtype="int64"),
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_neighbouring_suburb_match(con: DuckDBPyConnection) -> None:
    """Test that neighbouring suburb matches are being produced correctly"""
    result = (
        QueryPipeline(
            con=con,
            steps=[
                clean_addresses,
                create_address_numerics,
                create_address_alpha_tokens,
                create_input_phrases,
                first_matching_step,
                unnest_match_candidates,
                extract_match_candidate_details,
                filter_to_top50_candidates,
                neighbouring_suburb_match,
            ],
        )
        .execute()
        .sort_values("address_id1")
        .reset_index(drop=True)
    )

    assert result.shape == (18, 15)
    assert result.neighbouring_suburb_correction.value_counts().to_dict() == {
        True: 16,
        False: 2,
    }
    assert result.address.value_counts().to_dict() == {
        "115 SYDNEY RD BRUNSWICK VIC 3056": 9,
        "62 DAWSON ST BRUNSWICK EAST": 9,
    }
    assert result.address_matched_ns.unique().shape[0] == 18


def test_compute_similarity(con: DuckDBPyConnection) -> None:
    """Test that compute_similarity function for matches"""
    result = (
        QueryPipeline(
            con=con,
            steps=[
                clean_addresses,
                create_address_numerics,
                create_address_alpha_tokens,
                create_input_phrases,
                first_matching_step,
                unnest_match_candidates,
                extract_match_candidate_details,
                filter_to_top50_candidates,
                neighbouring_suburb_match,
                compute_similarity,
            ],
        )
        .execute()
        .sort_values("address_id1")
        .reset_index(drop=True)
    )

    assert result.shape == (18, 16)
    assert result.columns[-1] == "similarity"
    assert result.similarity.value_counts().to_dict() == {1.0: 9, 0.375: 9}


def test_rank_by_similarity(con: DuckDBPyConnection) -> None:
    """Test that rank_by_similarity function for matches"""
    result = (
        QueryPipeline(
            con=con,
            steps=[
                clean_addresses,
                create_address_numerics,
                create_address_alpha_tokens,
                create_input_phrases,
                first_matching_step,
                unnest_match_candidates,
                extract_match_candidate_details,
                filter_to_top50_candidates,
                neighbouring_suburb_match,
                compute_similarity,
                rank_by_similarity,
            ],
        )
        .execute()
        .sort_values("address_id1")
        .reset_index(drop=True)
    )

    assert result.shape == (18, 17)
    assert result["rank"].value_counts().to_dict() == {
        1: 2,
        8: 2,
        7: 2,
        6: 2,
        9: 2,
        4: 2,
        3: 2,
        2: 2,
        5: 2,
    }


def test_select_current(con: DuckDBPyConnection) -> None:
    """Test that select_current block for choosing best match"""
    result = QueryPipeline(
        con=con,
        steps=[
            clean_addresses,
            create_address_numerics,
            create_address_alpha_tokens,
            create_input_phrases,
            first_matching_step,
            unnest_match_candidates,
            extract_match_candidate_details,
            filter_to_top50_candidates,
            neighbouring_suburb_match,
            compute_similarity,
            rank_by_similarity,
            select_current,
        ],
    ).execute()

    expected = pd.DataFrame(
        {
            "address_id": np.array([1, 3], dtype="int32"),
            "input_address": np.array(
                ["115 SYDNEY RD BRUNSWICK VIC 3056", "62 DAWSON ST BRUNSWICK EAST"],
                dtype="object",
            ),
            "address_matched": [
                "115 SYDNEY RD BRUNSWICK VIC 3056",
                "62 DAWSON ST BRUNSWICK VIC 3056",
            ],
            "suburb": ["BRUNSWICK", "BRUNSWICK"],
            "postcode": np.array([3056, 3056], dtype="int32"),
            "latitude": np.array(
                [-37.774810791015625, -37.77077102661133], dtype="float32"
            ),
            "longitude": np.array(
                [144.9606170654297, 144.95619201660156], dtype="float32"
            ),
            "similarity": np.array([1.0, 0.375], dtype="float64"),
            "match_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62", "3056"], dtype=object),
            ],
            "match_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "VIC"], dtype=object),
            ],
            "input_numerics": [
                np.array(["115", "3056"], dtype=object),
                np.array(["62"], dtype=object),
            ],
            "input_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                np.array(["DAWSON", "ST", "BRUNSWICK", "EAST"], dtype=object),
            ],
            "neighbouring_suburb_correction": [False, False],
        }
    )

    pd.testing.assert_frame_equal(result, expected)


def test_rejoin_all_inputs(con: DuckDBPyConnection) -> None:
    """rejoin_all_inputs restores unmatched input rows while preserving match details.

    Row 1: exact match. Row 2: no match (all match columns null).
    Row 3: matched via a different candidate.
    """
    result = QueryPipeline(
        con=con,
        steps=[
            clean_addresses,
            create_address_numerics,
            create_address_alpha_tokens,
            create_input_phrases,
            first_matching_step,
            unnest_match_candidates,
            extract_match_candidate_details,
            filter_to_top50_candidates,
            neighbouring_suburb_match,
            compute_similarity,
            rank_by_similarity,
            select_current,
            rejoin_all_inputs,
        ],
    ).execute()

    expected = pd.DataFrame(
        {
            "address_id": np.array([1, 2, 3], dtype="int32"),
            "input_address": np.array(
                [
                    "115 SYDNEY RD BRUNSWICK VIC 3056",
                    "504 SYDNEY RD BRUNSWICK",
                    "62 DAWSON ST BRUNSWICK EAST",
                ],
                dtype=object,
            ),
            "address_matched": np.array(
                [
                    "115 SYDNEY RD BRUNSWICK VIC 3056",
                    np.nan,
                    "62 DAWSON ST BRUNSWICK VIC 3056",
                ],
                dtype=object,
            ),
            "suburb": np.array(["BRUNSWICK", np.nan, "BRUNSWICK"], dtype=object),
            "postcode": pd.array([3056, pd.NA, 3056], dtype="Int32"),
            "latitude": np.array(
                [-37.774810791015625, np.nan, -37.77077102661133], dtype="float32"
            ),
            "longitude": np.array(
                [144.9606170654297, np.nan, 144.95619201660156], dtype="float32"
            ),
            "similarity": np.array([1.0, np.nan, 0.375], dtype="float64"),
            "match_numerics": [
                np.array(["115", "3056"], dtype=object),
                pd.NA,
                np.array(["62", "3056"], dtype=object),
            ],
            "match_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                pd.NA,
                np.array(["DAWSON", "ST", "BRUNSWICK", "VIC"], dtype=object),
            ],
            "input_numerics": [
                np.array(["115", "3056"], dtype=object),
                pd.NA,
                np.array(["62"], dtype=object),
            ],
            "input_alpha_tokens": [
                np.array(["SYDNEY", "RD", "BRUNSWICK", "VIC"], dtype=object),
                pd.NA,
                np.array(["DAWSON", "ST", "BRUNSWICK", "EAST"], dtype=object),
            ],
            "neighbouring_suburb_correction": pd.Series(
                [False, pd.NA, False], dtype="boolean"
            ),
        }
    )

    pd.testing.assert_frame_equal(result, expected, check_exact=True)
