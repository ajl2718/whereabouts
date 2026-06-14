from __future__ import annotations

import importlib.resources
import os
import re
import urllib.parse

import duckdb
import numpy as np
import pandas as pd

from .matching_queries import create_matching_query, load_libraries, register_functions


from .utils import (
    list_overlap,
    numeric_overlap,
    numeric_overlap2,
    multiset_jaccard,
    ngram_jaccard,
    IOU,
    IOU_min
)
from .errors import InvalidDatabaseError

VALID_HOW_VALUES = frozenset({"standard", "skipphrase", "trigram"})

DO_MATCH_SKIPPHRASE = (
    importlib.resources.files("whereabouts.queries")
    .joinpath("geocoder_query_skipphrase2.sql")
    .read_text(encoding="utf-8")
)
DO_MATCH_TRIGRAM = (
    importlib.resources.files("whereabouts.queries")
    .joinpath("geocoder_query_trigramb3.sql")
    .read_text(encoding="utf-8")
)


class Matcher:
    """
    A class for geocoding and reverse geocoding addresses.

    Attributes
    ----------
    con : duckdb.DuckDBPyConnection
        A DuckDB database connection.
    how : str
        The geocoding algorithm to use, either 'standard', 'trigram', or 'skipphrase'.
        Defaults to 'standard'.
    threshold : float
        The threshold for considering a match valid. Defaults to 0.5.
    """

    con: duckdb.DuckDBPyConnection
    how: str
    threshold: float

    def __init__(
        self, db_name: str, how: str = "standard", threshold: float = 0.5
    ) -> None:
        """
        Initialize the Matcher object.

        Parameters
        ----------
        db_name : str
            The name of the database to use for geocoding.
        how : str, optional
            The geocoding algorithm to use. Defaults to 'standard'.
        threshold : float, optional
            The threshold for classifying a geocoded result as a match. Defaults to 0.5.
        """
        if how not in VALID_HOW_VALUES:
            raise ValueError(
                f"Invalid geocoding algorithm '{how}'. "
                f"Valid options: {', '.join(sorted(VALID_HOW_VALUES))}"
            )

        # create a working local DB
        self.con = duckdb.connect()

        # check if db_name is a local file path or a remote duckdb database
        parsed_url = urllib.parse.urlparse(db_name)
        if parsed_url.scheme in ("http", "https", "duckdb"):
            whereabouts_db = db_name
        elif parsed_url.scheme == "":
            # Check if the database is installed
            path_to_models = importlib.resources.files("whereabouts").joinpath("models")
            db_names = [
                name[:-3] for name in os.listdir(path_to_models) if name.endswith(".db")
            ]
            if db_name in db_names:
                whereabouts_db = f"{path_to_models}/{db_name}.db"
            else:
                raise InvalidDatabaseError(
                    f"Unknown database '{db_name}'. Valid options: {'\n'.join(db_names)}"
                )
        else:
            raise InvalidDatabaseError(f"Invalid database name or URL: {db_name}")

        # attach the whereabouts database — sanitize path to prevent SQL injection
        if not re.match(r"^[\w\s./:\-]+$", whereabouts_db) and parsed_url.scheme == "":
            raise InvalidDatabaseError(
                f"Database path contains invalid characters: {whereabouts_db}"
            )
        self.con.execute(f"ATTACH DATABASE '{whereabouts_db}' as remote;")

        # Register custom UDFs and extensions
        register_functions(self.con)
        load_libraries(self.con)

        # Build the standard matching pipeline
        self.pipeline = create_matching_query(self.con)

        self.how = how
        self.threshold = threshold

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        con = getattr(self, "con", None)
        if con is not None:
            con.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        self.close()

    def geocode(
        self,
        addresses: list[str] | str | np.ndarray | pd.Series,
        top_n: int = 1,
        address_ids: list[int] | None = None,
        how: str | None = None,
        verbose: bool = False,
    ) -> list[dict]:
        """
        Geocode a list of addresses.

        Parameters
        ----------
        addresses : list of str or str
            A list of strings representing addresses or a single address string.
        top_n : int, optional
            Max number of matches to return for each input address. Defaults to 1.
        address_ids : list of int, optional
            A list of integers representing the IDs of the addresses. Defaults to None.
        how : str, optional
            The geocoding algorithm to use. If not provided, the default 'how' attribute is used.
        verbose : bool, optional
            If True, print step-by-step details of the query pipeline. Defaults to False.

        Returns
        -------
        results : list of dict
            A list of dictionaries representing geocoded addresses.
        """
        if isinstance(addresses, str):
            addresses = [addresses]
        elif isinstance(addresses, np.ndarray):
            addresses = list(addresses)
        elif isinstance(addresses, pd.Series):
            if len(addresses.shape) > 1:
                raise ValueError(
                    f"Incorrect shape for input addresses: {addresses.shape}"
                )
            else:
                addresses = list(addresses)

        # Use default geocoding algorithm if not specified
        how = how or self.how
        if how not in VALID_HOW_VALUES:
            raise ValueError(
                f"Invalid geocoding algorithm '{how}'. "
                f"Valid options: {', '.join(sorted(VALID_HOW_VALUES))}"
            )

        if not addresses:
            raise ValueError("No addresses to match")

        if address_ids:
            df = pd.DataFrame({"address_id": address_ids, "address": addresses})
        else:
            df = pd.DataFrame(
                {"address_id": range(1, len(addresses) + 1), "address": addresses}
            )
        df["address"] = df["address"].astype(object)

        self.con.execute("DROP TABLE IF EXISTS input_addresses;")
        self.con.execute("DROP TABLE IF EXISTS input_addresses_with_tokens;")
        self.con.execute("""
        CREATE TABLE input_addresses (
            address_id INTEGER,
            address VARCHAR
        );""")
        self.con.execute("INSERT INTO input_addresses SELECT * FROM df")

        # Execute the appropriate matching algorithm
        if how == "trigram":
            answers = (
                self.con.execute(DO_MATCH_TRIGRAM, [top_n])
                .df()
                .sort_values(by="address_id")
                .reset_index(drop=True)
            )
        else:
            answers = (
                self.pipeline.execute(verbose=verbose)
                .sort_values(by="address_id")
                .reset_index(drop=True)
            )

        self.con.execute("DROP TABLE IF EXISTS input_addresses;")
        self.con.execute("DROP TABLE IF EXISTS input_addresses_with_tokens;")

        results = list(answers.T.to_dict().values())
        return results

    def reverse_geocode(self, points: list[tuple[float, float]]) -> list[dict]:
        """
        Find the nearest addresses for given latitude and longitude coordinates.

        Parameters
        ----------
        points : list of tuple
            A list of (latitude, longitude) tuples representing coordinates.

        Returns
        -------
        results : list of dict
            A list of dictionaries representing the nearest addresses.
        """
        if not hasattr(self, "tree") or not hasattr(self, "reference_data"):
            raise AttributeError(
                "reverse_geocode requires a KDTree and reference data. "
                "Use AddressLoader.create_kdtree() to build the tree first, "
                "then load it with Matcher.load_tree()."
            )
        query_indices = self.tree.query(points)[1]
        results = self.reference_data.iloc[query_indices, :]
        return [row._asdict() for row in results.itertuples(index=False)]

    def load_tree(self, tree_path: str) -> None:
        """
        Load a pre-built KDTree and its reference data for reverse geocoding.

        Parameters
        ----------
        tree_path : str
            Path to the pickled KDTree file created by AddressLoader.create_kdtree().

        .. warning::
            This uses ``pickle.load`` internally. Only load tree files from
            trusted sources, as deserializing untrusted pickle data can
            execute arbitrary code.
        """
        import pickle

        with open(tree_path, "rb") as f:  # noqa: S301
            self.tree = pickle.load(f)  # noqa: S301
        self.reference_data = self.con.execute("""
        SELECT addr_id AS address_id, addr AS address, latitude, longitude
        FROM remote.addresses
        """).df()

    def query(self, query: str) -> pd.DataFrame:
        """
        Execute a read-only SQL query using the matcher's database.

        Only SELECT statements are allowed. Mutations (INSERT, UPDATE,
        DELETE, DROP, ALTER, CREATE, ATTACH, DETACH, COPY, EXPORT) are
        rejected to prevent accidental or malicious data modification.

        Parameters
        ----------
        query : str
            The SQL query to execute (must be a SELECT statement).

        Returns
        -------
        results : pd.DataFrame
            The results of the query as a DataFrame.
        """
        _FORBIDDEN_PATTERN = re.compile(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|COPY|EXPORT)\b",
            re.IGNORECASE,
        )
        if _FORBIDDEN_PATTERN.search(query):
            raise ValueError(
                "Only read-only (SELECT) queries are allowed. "
                "Detected a forbidden keyword in the query."
            )
        results = self.con.execute(query).df()
        return results
