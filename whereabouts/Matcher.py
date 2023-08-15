from pathlib import Path
import duckdb
import pandas as pd
from scipy.spatial import KDTree
from json import loads

DO_MATCH_BASIC = Path("queries/geocoder_query_standard.sql").read_text() # threshold 500 - for fast matching
DO_MATCH_TRIGRAM = Path("queries/geocoder_query_trigram.sql").read_text()
CREATE_GEOCODER_TABLES = Path("queries/create_geocoder_tables.sql").read_text()

class Matcher(object):
    def __init__(self, db_name, how='standard', threshold=0.5):
        """
        Initialize the matcher object. Uses setup.yml file for the geocoder
        database name

        Args
        ----
        db_name (str): name of database
        how (str): geocoding type to use
        threshold (float): when to classify geocoded result as a match 
        """
        self.con = duckdb.connect(database=db_name)

        # for reverse geocoding, require reference data
        self.reference_data = self.con.execute("""
        select 
        addr_id address_id,
        addr address,
        latitude latitude,
        longitude longitude
        from 
        addrtext_with_detail at
        """).df()

        self.tree = KDTree(self.reference_data[['latitude', 'longitude']].values)
        self.how = how
        self.threshold = threshold


    def geocode(self, addresses, how='standard'):
        if isinstance(addresses, str):
            addresses = [addresses]

        # check if there is actually a list of addresses to match
        if len(addresses) == 0:
            raise Exception("No addresses to match")
        else:   
            if how == 'standard':
                df = pd.DataFrame(data={'address_id': range(1, len(addresses)+1), 'address': addresses})
                self.con.execute("drop table if exists input_addresses;")
                self.con.execute("drop table if exists input_addresses_with_tokens;")
                
                # create a table with the address info
                self.con.execute("""
                create table input_addresses (
                address_id integer,
                address varchar);"""
                )

                self.con.execute("INSERT INTO input_addresses SELECT * FROM df")
                
                answers = self.con.execute(DO_MATCH_BASIC).df().sort_values(by='address_id').reset_index().iloc[:, 1:]

                self.con.execute("drop table if exists input_addresses;")
                self.con.execute("drop table if exists input_addresses_with_tokens;")

                return answers.T.to_dict()
            elif how == 'trigram':
                df = pd.DataFrame(data={'address_id': range(1, len(addresses)+1), 'address': addresses})
                self.con.execute("drop table if exists input_addresses;")
                self.con.execute("drop table if exists input_addresses_with_tokens;")
                
                # create a table with the address info
                self.con.execute("""
                create table input_addresses (
                address_id integer,
                address varchar);"""
                )

                self.con.execute("INSERT INTO input_addresses SELECT * FROM df")
                
                answers = self.con.execute(DO_MATCH_TRIGRAM).df().sort_values(by='address_id').reset_index().iloc[:, 1:]

                self.con.execute("drop table if exists input_addresses;")
                self.con.execute("drop table if exists input_addresses_with_tokens;")

                return answers.T.to_dict()
            else:
                raise Exception("No recognised query type")
        
    # to do: extract all address components for each point rather than full address
    def reverse_geocode(self, points):
        """
        Given a list of latitude longitude tuples, find the corresponding nearest
        addresses

        Args
        ----
        points (list of tuples): the latitude, longitude coordinates to reverse geocode

        Return
        -------
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