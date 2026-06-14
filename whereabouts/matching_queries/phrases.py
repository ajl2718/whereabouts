from duckdb import DuckDBPyConnection

from ..QueryStep import query_step
from ..QueryPipeline import QueryPipeline

def create_address_phrases(con: DuckDBPyConnection, filename: str) -> QueryPipeline:
    create_phrase_table = query_step(
        query_template="""
        CREATE TABLE IF NOT EXISTS {output_table_name} 
        (
            addr_id INTEGER NOT NULL,
            tokenphrase TEXT NOT NULL
        )""",
        output_table_name="phrase",
        direct_execution=True,
        step_name="Create table for 2-word phrases",
        step_description="Creates a table for 2-word phrases from the source address data.",
    )

    select_address_subset = query_step(
        query_template="""
        SELECT * from {input_table} where row_num % 100 == ?
        """,
        output_table_name="addrtext_subset",
        input_table_names={"input_table": "addrtext_with_detail"},
        step_name="Select address subset for phrase extraction",
        step_description="Selects a subset of addresses for phrase extraction from the addrtext_with_detail table.",
    )

    create_tokens = query_step(
        query_template="""
        SELECT
            addr_id,
            unnest(string_to_array(regexp_replace(trim(addr), '[^A-Z0-9]+', ' ', 'g'), ' ')) AS token
        FROM {input_table}
        """,
        output_table_name="tokens_pre1",
        input_table_names={"input_table": "addrtext_subset"},
        step_name="Select address subset for phrase extraction",
        step_description="Selects a subset of addresses for phrase extraction from the addrtext_with_detail table.",
    )

    add_row_numbers = query_step(
        query_template="""
        SELECT
            addr_id,
            row_number() OVER () row_num,
            token
        FROM {input_table}
        """,
        output_table_name="tokens_pre2",
        input_table_names={"input_table": "tokens_pre1"},
        step_name="Select address subset for phrase extraction",
        step_description="Selects a subset of addresses for phrase extraction from the addrtext_with_detail table.",
    )

    add_row_numbers_per_address = query_step(
        query_template="""
        SELECT
            addr_id,
            row_number() OVER (PARTITION BY addr_id ORDER BY row_num) row_num,
            token
        FROM {input_table}
        """,
        output_table_name="addresses_with_tokens_and_row_numbers",
        input_table_names={"input_table": "tokens_pre2"},
        step_name="Select address subset for phrase extraction",
        step_description="Selects a subset of addresses for phrase extraction from the addrtext_with_detail table.",
    )

    create_phrases = query_step(
        query_template="""
        SELECT
            t1.addr_id,
            t1.token || ' ' || t2.token AS tokenphrase
        FROM {input_table} t1
        LEFT JOIN {input_table} t2
        ON (t1.addr_id, t1.row_num) = (t2.addr_id, t2.row_num - 1)
        WHERE tokenphrase IS NOT NULL
        """,
        output_table_name="phrases",
        input_table_names={"input_table": "addresses_with_tokens_and_row_numbers"},
        step_name="Create phrases",
        step_description="Creates 2-word phrases from the addresses with tokens and row numbers.",
    )

    create_inverted_index = query_step(
        query_template="""
        INSERT INTO phraseinverted
        SELECT tokenphrase, array_agg(addr_id), count(1)
        FROM phrase
        GROUP BY tokenphrase""",
        output_table_name="phraseinverted_data",
        direct_execution=True,
        step_name="Create inverted index",
        step_description="Aggregates phrases into an inverted index with frequency counts.",
    )

    create_indexes = query_step(
        query_template="""
        CREATE UNIQUE INDEX IF NOT EXISTS addrtext_addr_id_idx ON addrtext_with_detail(addr_id);
        CREATE INDEX IF NOT EXISTS phraseinverted_tokenphrase_idx ON phraseinverted(tokenphrase)""",
        output_table_name="phrase_indexes",
        direct_execution=True,
        step_name="Create indexes",
        step_description="Creates database indexes on the address detail and inverted index tables.",
    )

    pipeline = QueryPipeline(
        con=con, 
        steps=[
            create_phrase_table, 
            select_address_subset, 
            create_tokens, 
            add_row_numbers, 
            add_row_numbers_per_address, 
            create_phrases,
            create_inverted_index,
            create_indexes,
            ])
    
    return pipeline


# ---------------------------------------------------------------------------
# Module-level QueryStep instances for use by AddressLoader and other callers
# ---------------------------------------------------------------------------

insert_standard_phrases = query_step(
    query_template="""
INSERT INTO phrase
WITH addrtext_with_row_num AS (
    SELECT
    addr_id,
    addr,
    row_number() OVER () row_num
    FROM addrtext_with_detail
),
addrtext_subset AS (
    SELECT * FROM addrtext_with_row_num
    WHERE row_num % 100 == ?
),
tokens_pre1 AS
(
SELECT addr_id, unnest(string_to_array(regexp_replace(trim(addr), '[^A-Z0-9\u00c0\u00c2\u0100\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u014c\u0152\u00d9\u00db\u00dc\u0178\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b]+', ' ', 'g'), ' ')) token
FROM addrtext_subset
),
tokens_pre2 AS
(
SELECT addr_id, row_number() OVER () row_num, token
FROM tokens_pre1
),
tokens AS
(
SELECT addr_id, row_number() OVER (PARTITION BY addr_id ORDER BY row_num) row_num, token FROM tokens_pre2
)
SELECT t1.addr_id, t1.token || ' ' || t2.token tokenphrase
FROM tokens t1
LEFT JOIN tokens t2
ON (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-1)
WHERE tokenphrase IS NOT NULL
UNION ALL
SELECT t1.addr_id, t1.token || ' ' || t2.token tokenphrase
FROM tokens t1
LEFT JOIN tokens t2
ON (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-2)
WHERE tokenphrase IS NOT NULL
AND TRY_CAST(t1.token AS INTEGER) IS NOT NULL""",
    output_table_name="phrase_chunk",
    step_name="Create standard phrases",
    step_description="Inserts bigram token-pair phrases (including skip-one numeric) for a single chunk.",
)

insert_inverted_index = query_step(
    query_template="""
INSERT INTO phraseinverted
SELECT tokenphrase, array_agg(addr_id), count(1)
FROM phrase
GROUP BY tokenphrase""",
    output_table_name="phraseinverted_data",
    step_name="Create standard inverted index",
    step_description="Aggregates phrases into an inverted index with frequency counts.",
)

create_standard_indexes = query_step(
    query_template="""
CREATE UNIQUE INDEX addrtext_addr_id_idx ON addrtext_with_detail(addr_id);
CREATE INDEX phraseinverted_tokenphrase_idx ON phraseinverted(tokenphrase)""",
    output_table_name="standard_indexes",
    step_name="Create standard indexes",
    step_description="Creates database indexes on the address detail and inverted index tables.",
)