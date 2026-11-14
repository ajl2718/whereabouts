from __future__ import annotations

from typing import Any

from duckdb import DuckDBPyConnection

from ..constants import MAX_PHRASE_CHUNKS
from ..QueryPipeline import QueryPipeline
from ..QueryStep import QueryStep, query_step


def direct_step(sql: str, name: str) -> QueryStep:
    return query_step(
        query_template=sql,
        output_table_name=name,
        direct_execution=True,
        step_name=name.replace("_", " "),
    )


def create_geocoder_tables(con: DuckDBPyConnection) -> QueryPipeline:
    schemas = {
        "addrtext": """addr_id INTEGER NOT NULL, ADDRESS_LABEL VARCHAR, ADDRESS_SITE_NAME VARCHAR,
                       LOCALITY_NAME VARCHAR, POSTCODE VARCHAR, STATE VARCHAR, LATITUDE FLOAT, LONGITUDE FLOAT""",
        "phrase": "addr_id INTEGER NOT NULL, tokenphrase TEXT NOT NULL",
        "phraseinverted": "tokenphrase TEXT NOT NULL, addr_ids INTEGER[] NOT NULL, frequency BIGINT NOT NULL",
        "skipphrase": "addr_id INTEGER NOT NULL, tokenphrase TEXT NOT NULL",
        "skipphraseinverted": "tokenphrase TEXT NOT NULL, addr_ids INTEGER[] NOT NULL, frequency BIGINT NOT NULL",
        "trigramphrase": "addr_id INTEGER NOT NULL, trigramphrase TEXT NOT NULL",
        "trigramphraseinverted": (
            "trigramphrase INTEGER NOT NULL, addr_ids INTEGER[] NOT NULL, frequency INTEGER NOT NULL"
        ),
    }
    steps = [
        direct_step(f"CREATE TABLE {name} ({schema})", f"create_{name}")
        for name, schema in schemas.items()
    ]
    steps.append(
        direct_step(
            "CREATE TABLE numbers AS (VALUES (1), (2), (3), (4), (5), (6), (7))",
            "create_numbers",
        )
    )
    return QueryPipeline(con, steps)


def load_data_pipeline(
    con: DuckDBPyConnection, details: dict[str, Any], filter_state: bool = False
) -> QueryPipeline:
    schema = details["schema"]
    source = details["data"]
    path = source["filepath"].replace("'", "''")
    filetype = source.get("format", path.rsplit(".", 1)[-1])
    if filetype == "parquet":
        reader = f"read_parquet('{path}')"
    elif filetype == "csv":
        separator = source["sep"].replace("'", "''")
        reader = f"read_csv_auto('{path}', delim='{separator}')"
    else:
        raise ValueError(f"Unsupported address data format: {filetype}")
    columns = ", ".join(
        schema[key]
        for key in (
            "addr_id",
            "full_address",
            "address_site_name",
            "locality_name",
            "postcode",
            "state",
            "latitude",
            "longitude",
        )
    )
    condition = f" WHERE {schema['state']} = ?" if filter_state else ""
    step = direct_step(
        f"INSERT INTO addrtext SELECT {columns} FROM {reader}{condition}",
        "load_address_data",
    )
    return QueryPipeline(con, [step])


def inverted_index_pipeline(con: DuckDBPyConnection, kind: str) -> QueryPipeline:
    if kind not in ("standard", "skipphrase"):
        raise ValueError(f"Unsupported inverted index: {kind}")
    source = "phrase" if kind == "standard" else "skipphrase"
    target = f"{source}inverted"
    steps = [
        direct_step(
            f"INSERT INTO {target} SELECT tokenphrase, array_agg(addr_id), count(1) FROM {source} GROUP BY tokenphrase",
            f"create_{target}",
        )
    ]
    if kind == "standard":
        steps.extend(
            [
                direct_step(
                    "CREATE UNIQUE INDEX addrtext_addr_id_idx ON addrtext_with_detail(addr_id)",
                    "index_addresses",
                ),
                direct_step(
                    "CREATE INDEX phraseinverted_tokenphrase_idx ON phraseinverted(tokenphrase)",
                    "index_phrases",
                ),
            ]
        )
    return QueryPipeline(con, steps)


def prepare_trigram_index(con: DuckDBPyConnection) -> QueryPipeline:
    return QueryPipeline(
        con,
        [
            direct_step(
                """
        CREATE TABLE phraseinverted_with_nums AS
        SELECT tokenphrase, addr_ids, frequency, row_number() OVER () AS row_num FROM phraseinverted
    """,
                "number_phrase_index",
            )
        ],
    )


def trigram_chunk_pipeline(con: DuckDBPyConnection) -> QueryPipeline:
    return QueryPipeline(
        con,
        [
            query_step(
                query_template=f"SELECT * FROM {{source}} WHERE row_num % {MAX_PHRASE_CHUNKS} = ?",
                output_table_name="phrase_index_chunk",
                input_table_names={"source": "phraseinverted_with_nums"},
                step_name="Select phrase-index chunk",
            ),
            query_step(
                query_template="""
                SELECT t1.addr_ids,
                       concat(str_split(t1.tokenphrase, ' ')[1][t2.col0:t2.col0+2], ' ',
                              str_split(t1.tokenphrase, ' ')[2][t3.col0:t3.col0+2]) AS trigramphrase,
                       t1.frequency
                FROM {source} t1, {numbers} t2, {numbers} t3
            """,
                output_table_name="trigramphrase_chunk",
                input_table_names={
                    "source": "phrase_index_chunk",
                    "numbers": "numbers",
                },
                step_name="Create trigram pairs",
            ),
            query_step(
                query_template="""
                SELECT cast(hash(trigramphrase) % 1000000000 AS INTEGER) AS trigramphrase, addr_ids, frequency
                FROM {source} WHERE length(trigramphrase) >= 5
            """,
                output_table_name="hashed_trigram_chunk",
                input_table_names={"source": "trigramphrase_chunk"},
                step_name="Hash trigram pairs",
            ),
        ],
    )


def prepare_trigram_merge(con: DuckDBPyConnection) -> QueryPipeline:
    return QueryPipeline(
        con,
        [
            direct_step(
                """
            CREATE TABLE tg_distinct AS
            SELECT trigramphrase, row_number() OVER () AS row_num
            FROM (SELECT DISTINCT trigramphrase FROM trigramphraseinverted)
        """,
                "number_distinct_trigrams",
            ),
            direct_step(
                """
            CREATE TABLE trigramphraseinverted2 AS
            SELECT t1.*, t2.row_num FROM trigramphraseinverted t1
            LEFT JOIN tg_distinct t2 ON t1.trigramphrase = t2.trigramphrase
        """,
                "attach_trigram_row_numbers",
            ),
            direct_step(
                """
            CREATE TABLE trigramphraseinverted3 (
                trigramphrase INTEGER NOT NULL, addr_ids INTEGER[] NOT NULL, frequency BIGINT NOT NULL
            )
        """,
                "create_final_trigram_index",
            ),
        ],
    )


def trigram_merge_pipeline(con: DuckDBPyConnection) -> QueryPipeline:
    return QueryPipeline(
        con,
        [
            query_step(
                query_template=(
                    "SELECT trigramphrase, addr_ids, frequency FROM {source} "
                    f"WHERE row_num % {MAX_PHRASE_CHUNKS} = ?"
                ),
                output_table_name="trigram_merge_chunk",
                input_table_names={"source": "trigramphraseinverted2"},
                step_name="Select trigram merge chunk",
            ),
            query_step(
                query_template="""
                SELECT trigramphrase, flatten(array_agg(addr_ids)) AS addr_ids, sum(frequency) AS frequency
                FROM {source} GROUP BY trigramphrase
            """,
                output_table_name="merged_trigrams",
                input_table_names={"source": "trigram_merge_chunk"},
                step_name="Merge trigram candidate lists",
            ),
        ],
    )


def cleanup_pipeline(
    con: DuckDBPyConnection, phrases: list[str], legacy: bool = False
) -> QueryPipeline:
    tables = ["addrtext"]
    if legacy:
        tables.extend(["skipphrase", "skipphraseinverted"])
    if "standard" in phrases:
        tables.append("phrase")
    if "skipphrase" in phrases and not legacy:
        tables.append("skipphrase")
    if "trigram" in phrases:
        tables.extend(
            [
                "trigramphrase",
                "tg_distinct",
                "trigramphraseinverted",
                "trigramphraseinverted2",
            ]
        )
    return QueryPipeline(
        con, [direct_step(f"DROP TABLE {table}", f"drop_{table}") for table in tables]
    )
