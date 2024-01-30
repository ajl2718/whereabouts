from pathlib import Path
import duckdb
import pandas as pd
from json import loads

DO_MATCH_BASIC = Path("whereabouts/queries/geocoder_query_standard2.sql").read_text() # threshold 500 - for fast matching
DO_MATCH_SKIPPHRASE = Path("whereabouts/queries/geocoder_query_skipphrase.sql").read_text()
DO_MATCH_TRIGRAM = Path("whereabouts/queries/geocoder_query_trigramb2.sql").read_text()
CREATE_GEOCODER_TABLES = Path("whereabouts/queries/create_geocoder_tables.sql").read_text()

# UDF for comparing overlap in numeric tokens between input and candidate addresses
def list_overlap(list1: list[str], list2: list[str], threshold: float) -> bool:
    if list2:
        overlap = len(set(list1).intersection(set(list2))) / len(list1)
        if overlap >= threshold:
            return True
        else:
            return False
    else:
        return False
    
def numeric_overlap(input_numerics: list[str], 
                    candidate_numerics: list[str]) -> float:
    num_overlap = len(set(input_numerics).intersection(set(candidate_numerics)))
    fraction_overlap = num_overlap / len(set(input_numerics))
    return fraction_overlap
    
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
        self.con = duckdb.connect(database=f'whereabouts/models/{db_name}.db')

        try:    
            self.con.create_function('list_overlap', list_overlap)
            self.con.create_function('numeric_overlap', numeric_overlap)
        except:
            pass
      #  self.tree = KDTree(self.reference_data[['latitude', 'longitude']].values)
        self.how = how
        self.threshold = threshold

    def geocode(self, addresses, address_ids=None, how=None):
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

            return list(answers.T.to_dict().values())
                
        
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