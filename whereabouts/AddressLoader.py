from __future__ import annotations

import pickle
from typing import Any

import duckdb
from scipy.spatial import KDTree

from .QueryStep import QueryStep
from .matching_queries.addrtext_with_detail import build_address_detail_pipeline
from .matching_queries.database import (
    cleanup_pipeline,
    create_geocoder_tables,
    inverted_index_pipeline,
    load_data_pipeline,
    prepare_trigram_index,
    prepare_trigram_merge,
    trigram_chunk_pipeline,
    trigram_merge_pipeline,
)
from .matching_queries.phrases import build_phrase_pipeline
from .constants import MAX_PHRASE_CHUNKS


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
        step.execute(self.con, parameters)

    def load_data(
        self, details: dict[str, Any], state_names: list[str] | None = None
    ) -> None:
        if state_names is None:
            state_names = []
        if len(state_names) == 0:
            print("Loading data")
            load_data_pipeline(self.con, details).execute_direct()
        else:
            for state_name in state_names:
                print(f"Loading data for {state_name}")
                load_data_pipeline(self.con, details, filter_state=True).execute_direct(
                    [state_name]
                )

    def create_final_address_table(self) -> None:
        pipeline = build_address_detail_pipeline(self.con)
        pipeline.execute_as_table("addrtext_with_detail")

    def create_geocoder_tables(self) -> None:
        print("Creating geocoder tables...")
        create_geocoder_tables(self.con).execute_direct()

    def create_phrases(self, phrases: list[str] | None = None) -> None:
        if phrases is None:
            phrases = ["standard"]
        if "standard" in phrases:
            print("Creating phrases...")
            pipeline = build_phrase_pipeline(self.con)
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating phrases for chunk {n}...")
                pipeline.execute_into_table("phrase", [n])
        if "skipphrase" in phrases:
            print("Creating skipphrases...")
            pipeline = build_phrase_pipeline(self.con, "skipphrase")
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating skipphrases for chunk {n}...")
                pipeline.execute_into_table("skipphrase", [n])
        if "trigram" in phrases:
            print("Add row number to phrase inverted index...")
            prepare_trigram_index(self.con).execute_direct()
            print("Creating trigram inverted phrases. Step 1...")
            pipeline = trigram_chunk_pipeline(self.con)
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating trigram phrases for chunk {n}...")
                pipeline.execute_into_table("trigramphraseinverted", [n])
            print("Creating trigram inverted phrases. Step 2...")
            prepare_trigram_merge(self.con).execute_direct()
            print("Creating trigram inverted phrases. Step 3...")
            pipeline = trigram_merge_pipeline(self.con)
            for n in range(MAX_PHRASE_CHUNKS):
                print(f"Creating trigram phrases for chunk {n}...")
                pipeline.execute_into_table("trigramphraseinverted3", [n])

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
            phrases = ["standard"]
        print("Creating inverted index...")
        if "standard" in phrases:
            inverted_index_pipeline(self.con, "standard").execute_direct()
        if "skipphrase" in phrases:
            inverted_index_pipeline(self.con, "skipphrase").execute_direct()

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

        cleanup_pipeline(self.con, phrases).execute_direct()

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
        tree = KDTree(self.reference_data[["latitude", "longitude"]].values)
        pickle.dump(tree, open(tree_path, "wb"))
