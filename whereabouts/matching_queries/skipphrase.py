from __future__ import annotations

from duckdb import DuckDBPyConnection

from ..QueryPipeline import QueryPipeline
from ..QueryStep import query_step
from .phrase_matching import candidate_steps, input_steps, result_step, token_steps

_ALPHABET = "A-Z\u00c0\u00c2\u0100\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u0152\u00d9\u00db\u00dc\u0178"


def create_matching_query(con: DuckDBPyConnection, top_n: int = 1) -> QueryPipeline:
    phrases = query_step(
        query_template="""
            SELECT t1.address_id, t1.token || ' ' || t2.token AS tokenphrase
            FROM {tokens} t1
            LEFT JOIN {tokens} t2 ON (t1.address_id, t1.row_num) = (t2.address_id, t2.row_num - 2)
            WHERE tokenphrase IS NOT NULL
        """,
        output_table_name="input_phrases",
        input_table_names={"tokens": "tokens"},
        step_name="Create skip-one phrases",
    )
    return QueryPipeline(
        con,
        [
            *input_steps(_ALPHABET, f"[0-9]+[{_ALPHABET}]{{0,1}}"),
            *token_steps(_ALPHABET),
            phrases,
            *candidate_steps(
                "input_phrases",
                "tokenphrase",
                "remote.skipphraseinverted",
                1000,
                "jaro_similarity",
            ),
            result_step(top_n),
        ],
    )
