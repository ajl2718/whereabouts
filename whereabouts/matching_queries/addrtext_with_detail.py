from duckdb import DuckDBPyConnection

from ..QueryStep import query_step
from ..QueryPipeline import QueryPipeline


def create_addrtext_with_detail(con: DuckDBPyConnection, filename: str) -> QueryPipeline:
    """
    Creates a query pipeline to process the input address data and create a detailed address table.

    Parameters
    ----------
    con : DuckDBPyConnection
        A connection to the DuckDB database where the queries will be executed.
    filename : str
        The path to the input CSV file containing the address data.

    Returns
    -------
    QueryPipeline
        A QueryPipeline instance containing the steps to process the address data and create the addrtext_with_detail table.    
    """
    load_data = query_step(
        query_template="""
        CREATE TABLE IF NOT EXISTS addrtext AS (
            SELECT
                ADDRESS_LABEL address,
                LOCALITY_NAME,
                STATE,
                POSTCODE,
                LATITUDE,
                LONGITUDE
            FROM
                {source}
        )""",
        output_table_name="addrtext",
        input_table_names={"source": f"read_csv_auto('{filename}')"},
        direct_execution=True,
        step_name="Load data",
        step_description="Loads source address data into the addrtext table.",
    )

    insert_address_id = query_step(
        query_template="""
        ALTER TABLE addrtext ADD COLUMN addr_id INTEGER;
        UPDATE addrtext
        SET addr_id = subquery.rn
            FROM (
                SELECT rowid, row_number() OVER (ORDER BY rowid) AS rn
                FROM addrtext
                ) subquery
            WHERE addrtext.rowid = subquery.rowid""",
        output_table_name="addrtext_with_id",
        direct_execution=True,
        step_name="Insert address ID",
        step_description="Adds an auto-incrementing addr_id column to the addrtext table.",
    )

    clean_addresses = query_step(
        query_template="""
        SELECT 
        addr_id addr_id,
        trim(regexp_replace(regexp_replace(unaccent(upper(address)), '[^A-Z0-9]+', ' ', 'g'), '[ ]+', ' ')) AS addr
        FROM {input_addresses}
        """,
        output_table_name="addresses_cleaned",
        input_table_names={"input_addresses": "addrtext"},
        step_name="Clean addresses",
        step_description="Cleans the input addresses by removing special characters and converting to uppercase.",
    )

    create_tokens = query_step(
        query_template="""
        SELECT 
        addr_id addr_id,
        addr,
        unnest(string_to_array(addr, ' ')) AS token
        FROM {input_table}
        """,
        output_table_name="address_tokens",
        input_table_names={"input_table": "addresses_cleaned"},
        step_name="Create address tokens",
        step_description="Creates tokens from the cleaned addresses.",
    )

    create_numeric_tokens = query_step(
        query_template="""
        SELECT 
        addr_id,
        addr,
        array_agg(token) numeric_tokens
        FROM {input_table}
        WHERE regexp_matches(token, '[0-9]+[A-Z]{{0,1}}')
        GROUP BY addr_id, addr
        """,
        output_table_name="address_tokens_with_numerics",
        input_table_names={"input_table": "address_tokens"},
        step_name="Filter numeric tokens",
        step_description="Filters tokens to keep only those that are numeric or alphanumeric with a numeric prefix.",
    )

    create_addrtext_with_detail = query_step(
        query_template="""
        SELECT 
        t1.addr_id,
        t1.addr,
        t1.numeric_tokens,
        t2.LOCALITY_NAME,
        t2.STATE,
        t2.POSTCODE,
        t2.LATITUDE,
        t2.LONGITUDE
        FROM {tokens} t1
        LEFT JOIN {addrtext} t2 ON t1.addr_id = t2.addr_id
        """,
        output_table_name="addrtext_with_detail",
        input_table_names={"tokens": "address_tokens_with_numerics", "addrtext": "addrtext"},
        step_name="Aggregate address tokens and join with original data",
        step_description="Aggregates numeric tokens and joins with original address data.",
    )

    pipeline = QueryPipeline(
        con=con, 
        steps=[
            load_data,
            insert_address_id,
            clean_addresses,
            create_tokens,
            create_numeric_tokens,
            create_addrtext_with_detail
        ])
    
    return pipeline


def build_address_detail_pipeline(con: DuckDBPyConnection) -> QueryPipeline:
    """
    Creates a query pipeline to build the addrtext_with_detail table from an
    existing ``addrtext`` table.

    This assumes that the ``addrtext`` table already exists and contains
    columns: ``addr_id``, ``address_label``, ``locality_name``, ``postcode``,
    ``state``, ``latitude``, ``longitude``.

    Parameters
    ----------
    con : DuckDBPyConnection
        A connection to the DuckDB database.

    Returns
    -------
    QueryPipeline
        A QueryPipeline whose CTE chain can be materialised as the
        ``addrtext_with_detail`` table.
    """
    tokenize = query_step(
        query_template=r"""
        SELECT
        addr_id,
        trim(regexp_replace(regexp_replace(upper(address_label), '[\-\.\,\;\:\_\(\)\!]+', ' ', 'g'), '  ', ' ')) addr,
        unnest(string_to_array(trim(regexp_replace(regexp_replace(upper(address_label), '[\-\.\,\;\:\_\(\)\!]+', ' ', 'g'), '  ', ' ')), ' ')) AS token
        FROM {source}""",
        output_table_name="tokens",
        input_table_names={"source": "addrtext"},
        step_name="Tokenize addresses",
        step_description="Cleans address labels and splits into individual word tokens.",
    )

    extract_numerics = query_step(
        query_template="""
        SELECT addr_id, addr, array_agg(token) numeric_tokens
        FROM {tokens}
        WHERE regexp_matches(token, '[0-9]+[A-Z\u00c0\u00c2\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u0152\u00d9\u00db\u00dc\u0178\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b]{{0,1}}')
        GROUP BY addr_id, addr""",
        output_table_name="addrtext_with_detail_pre",
        input_table_names={"tokens": "tokens"},
        step_name="Extract numeric tokens",
        step_description="Aggregates numeric tokens per address for downstream matching.",
    )

    join_detail = query_step(
        query_template="""
        SELECT t1.*, t2.address_label, t2.locality_name suburb, t2.postcode, t2.latitude, t2.longitude, t2.state
        FROM {pre} t1
        LEFT JOIN {source} t2 ON t1.addr_id = t2.addr_id""",
        output_table_name="address_detail_final",
        input_table_names={"pre": "addrtext_with_detail_pre", "source": "addrtext"},
        step_name="Join with original metadata",
        step_description="Joins numeric tokens with original address metadata (suburb, postcode, coords).",
    )

    return QueryPipeline(
        con=con,
        steps=[tokenize, extract_numerics, join_detail],
    )
