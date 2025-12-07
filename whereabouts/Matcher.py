from json import loads
import urllib.parse
import os
import importlib.resources

import duckdb
import numpy as np
import pandas as pd

from .utils import list_overlap, numeric_overlap, ngram_jaccard
from .errors import InvalidDatabaseError

# change files to files
DO_MATCH_BASIC = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_standard3.sql').read_text(encoding='utf-8')
DO_MATCH_SKIPPHRASE = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_skipphrase2.sql').read_text(encoding='utf-8')
DO_MATCH_TRIGRAM = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_trigramb3.sql').read_text(encoding='utf-8')
CREATE_GEOCODER_TABLES = importlib.resources.files('whereabouts.queries').joinpath('create_geocoder_tables.sql').read_text(encoding='utf-8')

class Matcher:
    """
    A class for geocoding and reverse geocoding addresses.

    Attributes
    ----------
    con : duckdb.DuckDBPyConnection
        A DuckDB database connection
    how : str, optional
        The geocoding algorithm to use, either 'standard', 'trigram', or 'skipphrase'
        Defaults to 'standard'
    threshold : float, optional
        The threshold for considering a match valid. Defaults to 0.5

    Methods
    -------
    geocode(addresses, address_ids=None, how=None):
        Geocodes a list of addresses
    reverse_geocode(points):
        Finds the nearest addresses for given latitude and longitude coordinates
    query(query):
        Executes a generic SQL query on the database
    """
    
    def __init__(self, db_name, how='standard', threshold=0.5):
        """
        Initialize the Matcher object.

        Parameters
        ----------
        db_name : str
            The name of the database to use for geocoding
        how : str, optional
            The geocoding algorithm to use. Defaults to 'standard'
        threshold : float, optional
            The threshold for classifying a geocoded result as a match. Defaults to 0.5
        """
        # create a working local DB
        self.con = duckdb.connect()

        # check if db_name is a local file path or a remote duckdb database
        parsed_url = urllib.parse.urlparse(db_name)
        if parsed_url.scheme in ('http', 'https', 'duckdb'):
            whereabouts_db = db_name
        elif parsed_url.scheme == '':
            # Check if the database is installed
            path_to_models = importlib.resources.files('whereabouts').joinpath('models')
            db_names = [name[:-3] for name in os.listdir(path_to_models) if name.endswith('.db')]
            if db_name in db_names:
                whereabouts_db = f"{path_to_models}/{db_name}.db"
            else:
                raise InvalidDatabaseError(f"Unknown database '{db_name}'. Valid options: {'\n'.join(db_names)}") 
        else:
            raise InvalidDatabaseError(f"Invalid database name or URL: {db_name}")

        # attach the whereabouts database
        if whereabouts_db:
            self.con.execute(f"ATTACH DATABASE '{whereabouts_db}' as remote;")
            # Create custom functions in DuckDB connection
            try:
                self.con.create_function('list_overlap', list_overlap)
                self.con.create_function('numeric_overlap', numeric_overlap)
                self.con.create_function('ngram_jaccard', ngram_jaccard)
            except Exception:
                pass
        
        self.how = how
        self.threshold = threshold

    def geocode(self, addresses, top_n=1, address_ids=None, how=None):
        """
        Geocodes a list of addresses.

        Parameters
        ----------
        addresses : list of str or str
            A list of strings representing addresses or a single address string
        top_n : int, default = 1
            Specify max number of matches to return for each input address
        address_ids : list of int, optional
            A list of integers representing the IDs of the addresses (default is None)
        how : str, optional
            The geocoding algorithm to use. If not provided, the default 'how' attribute is used

        Returns
        -------
        results : list
            A list of dictionaries representing geocoded addresses
        """
        if isinstance(addresses, str):
            addresses = [addresses]
        elif isinstance(addresses, np.ndarray):
            addresses = list(addresses)
        elif isinstance(addresses, pd.Series):
            if len(addresses.shape) > 1:
                raise ValueError(f"Incorrect shape for input addresses: {addresses.shape}")
            else:
                addresses = list(addresses)

        # Use default geocoding algorithm if not specified
        how = how if how else self.how

        if not addresses:
            raise ValueError("No addresses to match")
        
        if address_ids:
            df = pd.DataFrame({'address_id': address_ids, 'address': addresses})
        else:
            df = pd.DataFrame({'address_id': range(1, len(addresses) + 1), 'address': addresses})
        
        self.con.execute("DROP TABLE IF EXISTS input_addresses;")
        self.con.execute("DROP TABLE IF EXISTS input_addresses_with_tokens;")
        self.con.execute("""
        CREATE TABLE input_addresses (
            address_id INTEGER,
            address VARCHAR
        );""")
        self.con.execute("INSERT INTO input_addresses SELECT * FROM df")

        # Execute the appropriate matching algorithm
        if how == 'skipphrase':
            answers = self.con.execute(DO_MATCH_SKIPPHRASE, [top_n]).df().sort_values(by='address_id').reset_index(drop=True)
        elif how == 'trigram':
            answers = self.con.execute(DO_MATCH_TRIGRAM, [top_n]).df().sort_values(by='address_id').reset_index(drop=True)
        else:
            answers = self.con.execute(DO_MATCH_BASIC, [top_n]).df().sort_values(by='address_id').reset_index(drop=True)
        
        self.con.execute("DROP TABLE IF EXISTS input_addresses;")
        self.con.execute("DROP TABLE IF EXISTS input_addresses_with_tokens;")

        results = list(answers.T.to_dict().values())
        return results

    def reverse_geocode(self, points):
        """
        Finds the nearest addresses for given latitude and longitude coordinates

        Parameters
        ----------
        points : list of tuple
            A list of (latitude, longitude) tuples representing coordinates

        Returns
        -------
        results : list of dict
            A list of dictionaries representing the nearest addresses
        """
        query_indices = self.tree.query(points)[1]
        results = self.reference_data.iloc[query_indices, :]
        results = loads(results.to_json(orient='table'))['data']
        return results

    def query(self, query):
        """
        Executes a generic SQL query using the matcher's database.

        Parameters
        ----------
        query : str
            The SQL query to execute.

        Returns
        -------
        results : pd.DataFrame
            The results of the query as a DataFrame.
        """
        results = self.con.execute(query).df()
        return results