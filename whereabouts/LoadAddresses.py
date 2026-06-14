"""
LoadAddresses — builds a geocoder database using QueryStep / QueryPipeline.

This module provides the same functionality as AddressLoader but organises
all SQL operations around the QueryStep and QueryPipeline abstractions,
following the same pattern used by Matcher.py and matching_queries/standard.py.
"""
from __future__ import annotations

import pickle
from typing import Any

import duckdb
from scipy.spatial import KDTree

from .QueryStep import QueryStep, query_step
from .QueryPipeline import QueryPipeline
from .constants import MAX_PHRASE_CHUNKS


# ---------------------------------------------------------------------------
# Step definitions — static, module-level QueryStep instances
# ---------------------------------------------------------------------------

# ---- Table creation -------------------------------------------------------

_create_geocoder_tables = query_step(
    query_template="""
CREATE TABLE addrtext(
    addr_id integer not null,
    ADDRESS_LABEL varchar,
    ADDRESS_SITE_NAME varchar,
    LOCALITY_NAME varchar,
    POSTCODE varchar,
    STATE varchar,
    LATITUDE float,
    LONGITUDE float
);

CREATE TABLE phrase
(addr_id integer not null,
tokenphrase text not null);

CREATE TABLE phraseinverted
(tokenphrase text not null,
addr_ids integer[] not null,
frequency bigint not null);

CREATE TABLE skipphrase
(addr_id integer not null,
tokenphrase text not null);

CREATE TABLE skipphraseinverted
(tokenphrase text not null,
addr_ids integer[] not null,
frequency bigint not null);

CREATE TABLE trigramphrase
(addr_id integer not null,
trigramphrase text not null
);

CREATE TABLE trigramphraseinverted
(trigramphrase integer not null,
addr_ids integer[] not null,
frequency integer not null);

CREATE TABLE numbers AS (
VALUES
(1),
(2),
(3),
(4),
(5),
(6),
(7)
)""",
    output_table_name="geocoder_tables_ddl",
    step_name="Create geocoder tables",
    step_description="Creates all base tables needed for the geocoder database.",
)


# ---- Standard phrase creation ---------------------------------------------

_create_standard_phrases = query_step(
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
    step_description="Inserts bigram token-pair phrases for a single chunk of addresses.",
)


# ---- Skip-phrase creation -------------------------------------------------

_create_skip_phrases = query_step(
    query_template="""
INSERT INTO skipphrase
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
SELECT addr_id, unnest(string_to_array(regexp_replace(trim(addr), '[^A-Z\u00c0\u00c2\u0100\u00c6\u00c7\u00c9\u00c8\u00ca\u00cb\u00ce\u00cf\u00d4\u014c\u0152\u00d9\u00db\u00dc\u0178\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b0-9]+', ' ', 'g'), ' ')) token
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
ON (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-2)
WHERE tokenphrase IS NOT NULL""",
    output_table_name="skipphrase_chunk",
    step_name="Create skip-phrases",
    step_description="Inserts skip-one-word token-pair phrases for a single chunk of addresses.",
)


# ---- Standard inverted index ----------------------------------------------

_create_standard_inverted_index = query_step(
    query_template="""
INSERT INTO phraseinverted
SELECT tokenphrase, array_agg(addr_id), count(1)
FROM phrase
GROUP BY tokenphrase""",
    output_table_name="phraseinverted_data",
    step_name="Create standard inverted index",
    step_description="Aggregates phrases into an inverted index with frequency counts.",
)


_create_standard_indexes = query_step(
    query_template="""
CREATE UNIQUE INDEX addrtext_addr_id_idx ON addrtext_with_detail(addr_id);
CREATE INDEX phraseinverted_tokenphrase_idx ON phraseinverted(tokenphrase)""",
    output_table_name="standard_indexes",
    step_name="Create standard indexes",
    step_description="Creates database indexes on the address detail and inverted index tables.",
)


# ---- Skip-phrase inverted index -------------------------------------------

_create_skipphrase_inverted_index = query_step(
    query_template="""
INSERT INTO skipphraseinverted
SELECT tokenphrase, array_agg(addr_id), count(1)
FROM skipphrase
GROUP BY tokenphrase""",
    output_table_name="skipphraseinverted_data",
    step_name="Create skip-phrase inverted index",
    step_description="Aggregates skip-phrases into an inverted index with frequency counts.",
)


# ---- Trigram index steps --------------------------------------------------

_trigram_step1 = query_step(
    query_template="""
CREATE TABLE phraseinverted_with_nums AS
SELECT tokenphrase, addr_ids, frequency, row_number() OVER () row_num
FROM phraseinverted""",
    output_table_name="phraseinverted_with_nums_table",
    step_name="Trigram step 1 — add row numbers",
    step_description="Creates phraseinverted_with_nums table with row numbers for chunked trigram processing.",
)


_trigram_step2 = query_step(
    query_template="""
INSERT INTO trigramphraseinverted
WITH trigramphrase_chunk AS (
    SELECT addr_ids,
    concat(str_split(t1.tokenphrase, ' ')[1][t2.col0:t2.col0+2], ' ', str_split(t1.tokenphrase, ' ')[2][t3.col0:t3.col0+2]) trigramphrase,
    frequency
    FROM phraseinverted_with_nums t1, numbers t2, numbers t3
    WHERE row_num % 100 = ?
)
SELECT cast(hash(trigramphrase) % 1000000000 AS integer) trigramphrase, addr_ids, frequency
FROM trigramphrase_chunk
WHERE length(trigramphrase) >= 5""",
    output_table_name="trigram_inverted_chunk",
    step_name="Trigram step 2 — build trigram inverted phrases",
    step_description="Inserts hashed trigram phrases for a single chunk into the inverted index.",
)


_trigram_step3 = query_step(
    query_template="""
CREATE TABLE tg_distinct AS (
    WITH tg_distinct_pre AS (
        SELECT DISTINCT(trigramphrase) trigramphrase FROM
        trigramphraseinverted
    )
    SELECT trigramphrase, row_number() OVER () row_num
    FROM tg_distinct_pre
);

CREATE TABLE trigramphraseinverted2 AS (
    SELECT t1.*, t2.row_num
    FROM trigramphraseinverted t1
    LEFT JOIN tg_distinct t2
    ON t1.trigramphrase=t2.trigramphrase
);

CREATE TABLE trigramphraseinverted3(
    trigramphrase integer not null,
    addr_ids integer[] not null,
    frequency bigint not null
)""",
    output_table_name="trigram_distinct_tables",
    step_name="Trigram step 3 — distinct trigrams and secondary inverted table",
    step_description="Creates distinct trigram lookup and a secondary inverted index table.",
)


_trigram_step4 = query_step(
    query_template="""
INSERT INTO trigramphraseinverted3
WITH trigramphrase_chunk AS (
    SELECT trigramphrase, addr_ids, frequency
    FROM trigramphraseinverted2
    WHERE row_num % 100 = ?
)
SELECT trigramphrase, flatten(array_agg(addr_ids)), sum(frequency) frequency
FROM trigramphrase_chunk
GROUP BY trigramphrase""",
    output_table_name="trigram_final_chunk",
    step_name="Trigram step 4 — flatten trigram inverted index",
    step_description="Flattens and aggregates a chunk of the trigram inverted index.",
)


# ---- Cleanup steps --------------------------------------------------------

_drop_addrtext = query_step(
    query_template="DROP TABLE addrtext",
    output_table_name="drop_addrtext",
    step_name="Drop addrtext",
    step_description="Removes the raw addrtext table to reclaim space.",
)


_drop_phrase = query_step(
    query_template="DROP TABLE phrase",
    output_table_name="drop_phrase",
    step_name="Drop phrase table",
    step_description="Removes the standard phrase table after inverted index is built.",
)


_drop_skipphrase = query_step(
    query_template="DROP TABLE skipphrase",
    output_table_name="drop_skipphrase",
    step_name="Drop skipphrase table",
    step_description="Removes the skipphrase table after inverted index is built.",
)


_drop_trigram_tables = query_step(
    query_template="""
DROP TABLE trigramphrase;
DROP TABLE tg_distinct;
DROP TABLE trigramphraseinverted;
DROP TABLE trigramphraseinverted2""",
    output_table_name="drop_trigram_tables",
    step_name="Drop trigram intermediate tables",
    step_description="Removes all intermediate trigram tables.",
)


# ---------------------------------------------------------------------------
# Address detail pipeline — a genuine QueryPipeline (CTE chain)
# ---------------------------------------------------------------------------

def _build_address_detail_pipeline(con: duckdb.DuckDBPyConnection) -> QueryPipeline:
    """Build a QueryPipeline that generates the addrtext_with_detail CTE chain.

    The pipeline cleans raw address labels, extracts numeric tokens, and
    joins them back with the original metadata — mirroring the logic in
    ``create_addrtext2.sql`` but expressed as composable QuerySteps.
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


# ---------------------------------------------------------------------------
# LoadAddresses class
# ---------------------------------------------------------------------------

class LoadAddresses:
    """
    A class for loading address data and creating a geocoding database,
    using QueryStep and QueryPipeline for SQL organisation.

    This is a drop-in replacement for ``AddressLoader`` with the same
    public interface but with all SQL operations expressed as named,
    documented QueryStep instances.

    Attributes
    ----------
    db : str
        Name of the database file.
    con : duckdb.DuckDBPyConnection
        A DuckDB database connection.
    """
    db: str
    con: duckdb.DuckDBPyConnection

    def __init__(self, db_name: str) -> None:
        self.db = db_name
        self.con = duckdb.connect(database=db_name)
        self.con.sql("INSTALL splink_udfs FROM community; LOAD splink_udfs;")

    # ---- internal helpers -------------------------------------------------

    @staticmethod
    def _execute_step(
        con: duckdb.DuckDBPyConnection,
        step: QueryStep,
        parameters: list | None = None,
    ) -> None:
        """Execute a QueryStep as a standalone SQL statement (not as a CTE)."""
        if isinstance(step.input_table_names, dict):
            sql = step.query_template.format(**step.input_table_names)
        else:
            sql = step.query_template
        if parameters is not None:
            con.execute(sql, parameters)
        else:
            con.execute(sql)

    # ---- public API (same interface as AddressLoader) ---------------------

    def create_geocoder_tables(self) -> None:
        """Create all base tables required by the geocoder."""
        print("Creating geocoder tables...")
        self._execute_step(self.con, _create_geocoder_tables)

    def load_data(self, details: dict[str, Any], state_names: list[str] | None = None) -> None:
        """Load address data from a file (CSV or Parquet) into the addrtext table.

        Parameters
        ----------
        details : dict
            Configuration dictionary with ``schema`` and ``data`` sections.
        state_names : list of str, optional
            If provided, load only rows matching these state values.
        """
        id_value = details["schema"]["addr_id"]
        address_label_value = details["schema"]["full_address"]
        address_site_name_value = details["schema"]["address_site_name"]
        locality_name_value = details["schema"]["locality_name"]
        postcode_value = details["schema"]["postcode"]
        state_value = details["schema"]["state"]
        latitude_value = details["schema"]["latitude"]
        longitude_value = details["schema"]["longitude"]
        file_path = details["data"]["filepath"]
        sep = details["data"]["sep"]

        filetype = file_path.split(".")[-1]
        if filetype == "parquet":
            load_function = f"read_parquet('{file_path}')"
        elif filetype == "csv":
            load_function = f"read_csv_auto('{file_path}', delim='{sep}')"

        table_mappings: dict[str, str] = {
            "id_col": id_value,
            "label_col": address_label_value,
            "site_name_col": address_site_name_value,
            "locality_col": locality_name_value,
            "postcode_col": postcode_value,
            "state_col": state_value,
            "lat_col": latitude_value,
            "lon_col": longitude_value,
            "source": load_function,
        }

        if state_names is None:
            state_names = []

        if len(state_names) == 0:
            print("Loading data")
            step = QueryStep(
                query_template="""
                INSERT INTO addrtext
                SELECT
                {id_col} addr_id,
                {label_col} address_label,
                {site_name_col} address_site_name,
                {locality_col} locality_name,
                {postcode_col} postcode,
                {state_col} state,
                {lat_col} latitude,
                {lon_col} longitude
                FROM {source}""",
                output_table_name="addrtext_loaded",
                input_table_names=table_mappings,
                step_name="Load data",
                step_description="Loads address data from file into the addrtext table.",
            )
            self._execute_step(self.con, step)
        else:
            for state_name in state_names:
                print(f"Loading data for {state_name}")
                step = QueryStep(
                    query_template="""
                    INSERT INTO addrtext
                    SELECT
                    {id_col} addr_id,
                    {label_col} address_label,
                    {site_name_col} address_site_name,
                    {locality_col} locality_name,
                    {postcode_col} postcode,
                    {state_col} state,
                    {lat_col} latitude,
                    {lon_col} longitude
                    FROM {source}
                    WHERE state=$1""",
                    output_table_name="addrtext_loaded_state",
                    input_table_names=table_mappings,
                    step_name=f"Load data for {state_name}",
                    step_description=f"Loads address data for state {state_name}.",
                )
                self._execute_step(self.con, step, parameters=[state_name])

    def create_final_address_table(self) -> None:
        """Create the ``addrtext_with_detail`` table using a QueryPipeline.

        The pipeline tokenises addresses, extracts numeric tokens, and
        joins the results with the original metadata — expressed as a
        composable CTE chain.
        """
        print("Creating final address table...")
        pipeline = _build_address_detail_pipeline(self.con)
        cte_sql = pipeline.createCTEs()
        self.con.execute(f"CREATE TABLE addrtext_with_detail AS ({cte_sql})")

    def create_phrases(self, phrases: list[str] | None = None) -> None:
        """Create phrase tokens for the specified matching algorithms.

        Parameters
        ----------
        phrases : list of str, optional
            Types of phrases to create.  Each element must be ``'standard'``,
            ``'skipphrase'``, or ``'trigram'``.  Defaults to ``['standard']``.
        """
        if phrases is None:
            phrases = ["standard"]

        if "standard" in phrases:
            print("Creating phrases...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating phrases for chunk {n}...")
                self._execute_step(self.con, _create_standard_phrases, parameters=[n])

        if "skipphrase" in phrases:
            print("Creating skipphrases...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating skipphrases for chunk {n}...")
                self._execute_step(self.con, _create_skip_phrases, parameters=[n])

        if "trigram" in phrases:
            print("Add row number to phrase inverted index...")
            self._execute_step(self.con, _trigram_step1)
            print("Creating trigram inverted phrases. Step 1...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating trigram phrases for chunk {n}...")
                self._execute_step(self.con, _trigram_step2, parameters=[n])
            print("Creating trigram inverted phrases. Step 2...")
            self._execute_step(self.con, _trigram_step3)
            print("Creating trigram inverted phrases. Step 3...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating trigram phrases for chunk {n}...")
                self._execute_step(self.con, _trigram_step4, parameters=[n])

    def create_inverted_index(self, phrases: list[str] | None = None) -> None:
        """Create the inverted index for the specified phrase types.

        Parameters
        ----------
        phrases : list of str, optional
            Types of phrases to index.  Defaults to ``['standard']``.
        """
        if phrases is None:
            phrases = ["standard"]

        print("Creating inverted index...")
        if "standard" in phrases:
            self._execute_step(self.con, _create_standard_inverted_index)
            self._execute_step(self.con, _create_standard_indexes)

        if "skipphrase" in phrases:
            self._execute_step(self.con, _create_skipphrase_inverted_index)

    def clean_database(self, phrases: list[str]) -> None:
        """Remove intermediate tables to reclaim space.

        Parameters
        ----------
        phrases : list of str
            The phrase types that were built (``'standard'``, ``'skipphrase'``,
            ``'trigram'``).
        """
        self._execute_step(self.con, _drop_addrtext)

        if "standard" in phrases:
            self._execute_step(self.con, _drop_phrase)

        if "skipphrase" in phrases:
            self._execute_step(self.con, _drop_skipphrase)

        if "trigram" in phrases:
            self._execute_step(self.con, _drop_trigram_tables)

    def export_database(self, db_path: str) -> None:
        """Export the database to the specified folder.

        Parameters
        ----------
        db_path : str
            Name of folder to export DB to.
        """
        self.con.execute(f"EXPORT DATABASE '{db_path}' (FORMAT PARQUET);")

    def import_database(self, db_path: str) -> None:
        """Import database from specified folder.

        Parameters
        ----------
        db_path : str
            Path where database files and queries are located.
        """
        self.con.execute(f"IMPORT DATABASE '{db_path}'")

    def create_kdtree(self, tree_path: str) -> None:
        """Create a KD-Tree for reverse geocoding.

        Parameters
        ----------
        tree_path : str
            Path to export the computed KD-Tree pickle file.
        """
        print("Creating KD-Tree for reverse geocoding...")

        self.reference_data = self.con.execute("""
        SELECT
        at.addr_id address_id,
        at.addr address,
        av.latitude latitude,
        av.longitude longitude
        FROM
        addrtext at
        INNER JOIN
        address_view av
        ON at.addr_id = av.address_detail_pid;
        """).df()

        tree = KDTree(self.reference_data[["latitude", "longitude"]].values)
        pickle.dump(tree, open(tree_path, "wb"))
