from __future__ import annotations

import importlib.resources
import pickle
from typing import Any

import duckdb
from scipy.spatial import KDTree

from .QueryStep import QueryStep
from .matching_queries.addrtext_with_detail import build_address_detail_pipeline
from .matching_queries.phrases import insert_standard_phrases, insert_inverted_index, create_standard_indexes
from .constants import MAX_PHRASE_CHUNKS

DO_MATCH_BASIC = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_standard.sql').read_text(encoding='utf-8')
CREATE_GEOCODER_TABLES = importlib.resources.files('whereabouts.queries').joinpath('create_geocoder_tables.sql').read_text(encoding='utf-8')

CREATE_SKIPPHRASES = importlib.resources.files('whereabouts.queries').joinpath('create_skipphrases.sql').read_text(encoding='utf-8')
INVERTED_INDEX_SKIPPHRASE = importlib.resources.files('whereabouts.queries').joinpath('skipphrase_inverted.sql').read_text(encoding='utf-8')

CREATE_TRIGRAM_PHRASES = importlib.resources.files('whereabouts.queries').joinpath('create_trigramphrases.sql').read_text(encoding='utf-8')

TRIGRAM_STEP1 = importlib.resources.files('whereabouts.queries').joinpath('create_trigram_index_step1.sql').read_text(encoding='utf-8')
TRIGRAM_STEP2 = importlib.resources.files('whereabouts.queries').joinpath('create_trigram_index_step2b.sql').read_text(encoding='utf-8')
TRIGRAM_STEP3 = importlib.resources.files('whereabouts.queries').joinpath('create_trigram_index_step3.sql').read_text(encoding='utf-8')
TRIGRAM_STEP4 = importlib.resources.files('whereabouts.queries').joinpath('create_trigram_index_step4.sql').read_text(encoding='utf-8')


class AddressLoader:
    """
    A class for loading address data and creating a geocoding database.

    Attributes
    ----------
    db : str
        Name of the database.
    con : duckdb.DuckDBPyConnection
        A DuckDB database connection.
    """
    db: str
    con: duckdb.DuckDBPyConnection

    def __init__(self, db_name: str) -> None:
        self.db = db_name
        self.con = duckdb.connect(database=db_name)
        self.con.sql("INSTALL splink_udfs FROM community; LOAD splink_udfs;")

    def _execute_step(self, step: QueryStep, parameters: list | None = None) -> None:
        """Execute a QueryStep as a standalone SQL statement (not as a CTE)."""
        if isinstance(step.input_table_names, dict):
            sql = step.query_template.format(**step.input_table_names)
        else:
            sql = step.query_template
        if parameters is not None:
            self.con.execute(sql, parameters)
        else:
            self.con.execute(sql)

    def load_data(self, details: dict[str, Any], state_names: list[str] | None = None) -> None:
        id_value = details['schema']['addr_id']
        address_label_value = details['schema']['full_address']
        address_site_name_value = details['schema']['address_site_name']
        locality_name_value = details['schema']['locality_name']
        postcode_value = details['schema']['postcode']
        state_value = details['schema']['state']
        latitude_value = details['schema']['latitude']
        longitude_value = details['schema']['longitude']
        file_path = details['data']['filepath']
        sep = details['data']['sep']

        # check the extension of the file
        # either read_csv_auto or read_parquet
        filetype = file_path.split('.')[-1]
        if filetype == "parquet":
            load_function = f"read_parquet('{file_path}')"
        elif filetype == "csv":
            load_function = f"read_csv_auto('{file_path}', delim='{sep}')"

        if state_names is None:
            state_names = []

        if len(state_names) == 0:
            print("Loading data")
            query = f"""
            insert into addrtext 
            select 
            {id_value} addr_id, 
            {address_label_value} address_label,
            {address_site_name_value} address_site_name,
            {locality_name_value} locality_name,
            {postcode_value} postcode,
            {state_value} state,
            {latitude_value} latitude,
            {longitude_value} longitude
            from
            {load_function}
            """
            self.con.execute(query)
        else:
            for state_name in state_names:
                print(f"Loading data for {state_name}")
                query = f"""
                insert into addrtext 
                select 
                {id_value} addr_id, 
                {address_label_value} address_label,
                {address_site_name_value} address_site_name,
                {locality_name_value} locality_name,
                {postcode_value} postcode,
                {state_value} state,
                {latitude_value} latitude,
                {longitude_value} longitude
                from
                {load_function}
                where state=$1
                """
                self.con.execute(query, [state_name])
        
    def create_final_address_table(self) -> None:
        pipeline = build_address_detail_pipeline(self.con)
        cte_sql = pipeline.createCTEs()
        self.con.execute(f"CREATE TABLE addrtext_with_detail AS ({cte_sql})")

    def create_geocoder_tables(self) -> None:
        print("Creating geocoder tables...")
        self.con.execute(CREATE_GEOCODER_TABLES)
        
    def create_phrases(self, phrases: list[str] | None = None) -> None:
        if phrases is None:
            phrases = ['standard']
        if 'standard' in phrases:
            print('Creating phrases...')
            for n in range(MAX_PHRASE_CHUNKS):
                print(f'Creating phrases for chunk {n}...')
                self._execute_step(insert_standard_phrases, [n])
        if 'skipphrase' in phrases:
            print('Creating skipphrases...')
            for n in range(MAX_PHRASE_CHUNKS):
                print(f'Creating skipphrases for chunk {n}...')
                self.con.execute(CREATE_SKIPPHRASES, [n])
        if 'trigram' in phrases:
            print("Add row number to phrase inverted index...")
            self.con.execute(TRIGRAM_STEP1)
            print("Creating trigram inverted phrases. Step 1...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f'Creating trigram phrases for chunk {n}...')
                self.con.execute(TRIGRAM_STEP2, [n])
            print("Creating trigram inverted phrases. Step 2...")
            self.con.execute(TRIGRAM_STEP3)
            print("Creating trigram inverted phrases. Step 3...")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f'Creating trigram phrases for chunk {n}...')
                self.con.execute(TRIGRAM_STEP4, [n])

    def create_inverted_index(self, phrases: list[str] | None = None) -> None:
        """
        Create the inverted index for the database.

        Parameters
        ----------
        phrases : list of str, optional
            Types of phrases to create. Each str must be either 'standard', 'trigram', or 'skipphrase'.
            Defaults to ['standard'].
        """
        if phrases is None:
            phrases = ['standard']
        print('Creating inverted index...')
        if 'standard' in phrases:
            self._execute_step(insert_inverted_index)
            self._execute_step(create_standard_indexes)
        if 'skipphrase' in phrases:
            self.con.execute(INVERTED_INDEX_SKIPPHRASE)
          #  self.con.execute(CREATE_INDEXES_SKIPPHRASE)

    def clean_database(self, phrases: list[str]) -> None:
        """
        Once geocoder tables have been created, remove unnecessary tables from DB
        to clear up space. Note that DuckDB currently does not free up the space
        so the database has to be exported with tables and then loaded back again.

        Parameters
        ----------
        phrases : list of str
            The types of matching to use. Each str is either 'standard', 'trigram', or 'skipphrase'.
        """
        
        self.con.execute("""
        drop table addrtext;
        """)

        if 'standard' in phrases:
            self.con.execute("""
            drop table phrase;
            """)
        if 'skipphrase' in phrases:
            self.con.execute("""
            drop table skipphrase;
            """)
        if 'trigram' in phrases:
            self.con.execute("""
            drop table trigramphrase;
            drop table tg_distinct;
            drop table trigramphraseinverted;
            drop table trigramphraseinverted2;
            """)

    def export_database(self, db_path: str) -> None:
        """
        Export the database to the specified folder.

        Parameters
        ----------
        db_path : str
            Name of folder to export DB to.
        """
        self.con.execute(f"export database '{db_path}' (format parquet);")

    def import_database(self, db_path: str) -> None:
        """
        Import database from specified folder.

        Parameters
        ----------
        db_path : str
            Path where database files and queries are located.
        """
        self.con.execute(f"import database '{db_path}'")

    def create_kdtree(self, tree_path: str) -> None:
        """
        Create a KD-Tree data structure from the reference data.

        Parameters
        ----------
        tree_path : str
            Path to export computed KD-Tree.
        """
        
        print("Creating KD-Tree for reverse geocoding...")
        
        # extract address texts and lat, long coords from db
        self.reference_data = self.con.execute("""
        select 
        at.addr_id address_id,
        at.addr address,
        av.latitude latitude,
        av.longitude longitude
        from 
        addrtext at
        inner join
        address_view av
        on at.addr_id = av.address_detail_pid;
        """).df()

        # create kdtree
        tree = KDTree(self.reference_data[['latitude', 'longitude']].values)
        pickle.dump(tree, open(tree_path, 'wb'))