from json import loads
import os
import importlib.resources

import duckdb
import pandas as pd

from .utils import list_overlap, numeric_overlap, ngram_jaccard

# change files to files
DO_MATCH_BASIC = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_standard2.sql').read_text()
DO_MATCH_SKIPPHRASE = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_skipphrase.sql').read_text()
DO_MATCH_TRIGRAM = importlib.resources.files('whereabouts.queries').joinpath('geocoder_query_trigramb2.sql').read_text()
CREATE_GEOCODER_TABLES = importlib.resources.files('whereabouts.queries').joinpath('create_geocoder_tables.sql').read_text()
    
class Matcher(object):
    """
    A class for geocoding addresses.

    Attributes
    ----------
    con : duckdb.connect
        Reference to a DuckDB database connection.
    how : str
        Algorithm for matching, either 'standard' or 'trigram'. Defaults to 'standard'.
    threshold : float
        The threshold at which to consider a match valid. Defaults to 0.5.

    Methods
    -------
    geocode(addresses):
        Geocodes a list of addresses.
    """
    def __init__(self, db_name, how='standard', threshold=0.5):
        """
        Initialize the matcher object.

        Uses the `setup.yml` file for the geocoder database name.

        :param str db_name: Name of the database.
        :param str how: Geocoding type to use.
        :param float threshold: Threshold for classifying a geocoded result as a match.
        """
        # check that model is in folder
        path_to_models = importlib.resources.files('whereabouts').joinpath('models')

        db_names = os.listdir(path_to_models)
        db_names = [db_name[:-3] for db_name in db_names if db_name[-3:] == '.db']
        if db_name in db_names:
            self.con = duckdb.connect(database=f'{path_to_models}/{db_name}.db')
        else:
            print(f"Could not find database {db_name}")
            print("The following geocoding databases are installed:")
            for db_name in db_names:
                print(f'{db_name}')
        try:    
            self.con.create_function('list_overlap', list_overlap)
            self.con.create_function('numeric_overlap', numeric_overlap)
            self.con.create_function('ngram_jaccard', ngram_jaccard)
        except:
            pass
      #  self.tree = KDTree(self.reference_data[['latitude', 'longitude']].values)
        self.how = how
        self.threshold = threshold

    def geocode(self, addresses, address_ids=None, how=None):
        """
        Geocodes a list of addresses

        Args:
            addresses (list or str): list or string representing addresses
        
        Returns:
            results (list): list of dicts representing geocoded addresses
        """
        if isinstance(addresses, str):
            addresses = [addresses]

        # use default geocoding algorithm if not specified
        if how:
            how = how 
        else:
            how = self.how

        # check if there is actually a list of addresses to match
        if len(addresses) == 0:
            raise Exception("No addresses to match")
        else:   
            if address_ids:
                df = pd.DataFrame(data={'address_id': address_ids, 'address': addresses})
            else:
                df = pd.DataFrame(data={'address_id': range(1, len(addresses)+1), 'address': addresses})
            self.con.execute("drop table if exists input_addresses;")
            self.con.execute("drop table if exists input_addresses_with_tokens;")
            self.con.execute("""
            create table input_addresses (
            address_id integer,
            address varchar);"""
            )
            self.con.execute("INSERT INTO input_addresses SELECT * FROM df")

            if how == 'skipphrase':
                answers = self.con.execute(DO_MATCH_SKIPPHRASE).df().sort_values(by='address_id').reset_index().iloc[:, 1:]
            elif how == 'trigram':
                answers = self.con.execute(DO_MATCH_TRIGRAM).df().sort_values(by='address_id').reset_index().iloc[:, 1:]
            else:
                answers = self.con.execute(DO_MATCH_BASIC).df().sort_values(by='address_id').reset_index().iloc[:, 1:]
            
            self.con.execute("drop table if exists input_addresses;")
            self.con.execute("drop table if exists input_addresses_with_tokens;")

            results = list(answers.T.to_dict().values())
            return results
                
        
    # to do: extract all address components for each point rather than full address
    def reverse_geocode(self, points):
        """
        Given a list of latitude longitude tuples, find the corresponding nearest
        addresses

        Args:
            points (list of tuples): the latitude, longitude coordinates to reverse geocode

        Returns:
            results (list of dicts): addresses
        """
        tree = self.tree
        
        query_indices = tree.query(points)[1]
        results = self.reference_data.iloc[query_indices, :]
        results = loads(results.to_json(orient='table'))['data']
        return results

    def query(self, query):
        """
        Execute a generic SQL query using the database of the matcher
        """
        results = self.con.execute(query).df()
        return results