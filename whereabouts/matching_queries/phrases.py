from __future__ import annotations

from duckdb import DuckDBPyConnection

from ..constants import MAX_PHRASE_CHUNKS
from ..QueryPipeline import QueryPipeline
from ..QueryStep import query_step

_ALPHABET = (
    "A-Z0-9\u00c0\u00c2\u0100\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u014c\u0152"
    "\u00d9\u00db\u00dc\u0178\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b"
)


def build_phrase_pipeline(
    con: DuckDBPyConnection, kind: str = "standard", include_numeric_skip: bool = True
) -> QueryPipeline:
    if kind not in ("standard", "skipphrase"):
        raise ValueError(f"Unsupported phrase type: {kind}")
    gap = 1 if kind == "standard" else 2
    phrase_sql = f"""
        SELECT t1.addr_id, t1.token || ' ' || t2.token AS tokenphrase
        FROM {{tokens}} t1
        LEFT JOIN {{tokens}} t2 ON (t1.addr_id, t1.row_num) = (t2.addr_id, t2.row_num - {gap})
        WHERE tokenphrase IS NOT NULL
    """
    if kind == "standard" and include_numeric_skip:
        phrase_sql += """
            UNION ALL
            SELECT t1.addr_id, t1.token || ' ' || t2.token AS tokenphrase
            FROM {tokens} t1
            LEFT JOIN {tokens} t2 ON (t1.addr_id, t1.row_num) = (t2.addr_id, t2.row_num - 2)
            WHERE tokenphrase IS NOT NULL AND TRY_CAST(t1.token AS INTEGER) IS NOT NULL
        """
    return QueryPipeline(
        con,
        [
            query_step(
                query_template="SELECT addr_id, addr, row_number() OVER () AS row_num FROM {source}",
                output_table_name="addrtext_with_row_num",
                input_table_names={"source": "addrtext_with_detail"},
                step_name="Number source addresses",
            ),
            query_step(
                query_template=f"SELECT * FROM {{source}} WHERE row_num % {MAX_PHRASE_CHUNKS} = ?",
                output_table_name="addrtext_subset",
                input_table_names={"source": "addrtext_with_row_num"},
                step_name="Select address chunk",
            ),
            query_step(
                query_template=f"""
                SELECT addr_id,
                       unnest(string_to_array(regexp_replace(trim(addr), '[^{_ALPHABET}]+', ' ', 'g'), ' ')) AS token
                FROM {{source}}
            """,
                output_table_name="tokens_pre1",
                input_table_names={"source": "addrtext_subset"},
                step_name="Tokenize source addresses",
            ),
            query_step(
                query_template="SELECT addr_id, row_number() OVER () AS row_num, token FROM {source}",
                output_table_name="tokens_pre2",
                input_table_names={"source": "tokens_pre1"},
                step_name="Number source tokens",
            ),
            query_step(
                query_template="""
                SELECT addr_id, row_number() OVER (PARTITION BY addr_id ORDER BY row_num) AS row_num, token
                FROM {source}
            """,
                output_table_name="tokens",
                input_table_names={"source": "tokens_pre2"},
                step_name="Order tokens per address",
            ),
            query_step(
                query_template=phrase_sql,
                output_table_name="address_phrases",
                input_table_names={"tokens": "tokens"},
                step_name=f"Create {kind} phrases",
            ),
        ],
    )


def create_address_phrases(con: DuckDBPyConnection, filename: str) -> QueryPipeline:
    """Build adjacent phrases from the preloaded address table; filename is retained for compatibility."""
    return build_phrase_pipeline(con, include_numeric_skip=False)
