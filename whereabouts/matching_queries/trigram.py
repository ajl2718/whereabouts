from __future__ import annotations

from duckdb import DuckDBPyConnection

from ..QueryPipeline import QueryPipeline
from ..QueryStep import query_step
from .phrase_matching import candidate_steps, input_steps, result_step, token_steps

_ALPHABET = (
    "A-Z\u00c0\u00c2\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u0152\u00d9\u00db\u00dc\u0178"
    "\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b"
)


def create_matching_query(con: DuckDBPyConnection, top_n: int = 1) -> QueryPipeline:
    trigrams = query_step(
        query_template="""
            SELECT t1.address_id, t1.row_num, t1.token,
                   substr(t1.token, t2.col0, 3) AS trigram
            FROM {tokens} t1, {numbers} t2
            WHERE trigram != '' AND strlen(trigram) >= 2
            ORDER BY address_id, row_num
        """,
        output_table_name="trigrams",
        input_table_names={"tokens": "tokens", "numbers": "remote.numbers"},
        step_name="Extract character trigrams",
    )
    phrases = query_step(
        query_template="""
            SELECT t1.address_id,
                   cast(hash(t1.trigram || ' ' || t2.trigram) % 1000000000 AS INTEGER) AS trigramphrase
            FROM {trigrams} t1
            LEFT JOIN {trigrams} t2 ON (t1.address_id, t1.row_num) = (t2.address_id, t2.row_num - 1)
            WHERE trigramphrase IS NOT NULL
        """,
        output_table_name="input_trigramphrases",
        input_table_names={"trigrams": "trigrams"},
        step_name="Hash adjacent trigram pairs",
    )
    return QueryPipeline(
        con,
        [
            *input_steps(_ALPHABET, "[0-9]+"),
            *token_steps(_ALPHABET),
            trigrams,
            phrases,
            *candidate_steps(
                "input_trigramphrases",
                "trigramphrase",
                "remote.trigramphraseinverted3",
                10000,
                "ngram_jaccard",
            ),
            result_step(top_n),
        ],
    )
