from pathlib import Path
import duckdb
import pandas as pd
from json import loads
import os
import importlib.resources

DO_MATCH_BASIC = importlib.resources.read_text('whereabouts.queries', 'geocoder_query_standard2.sql')
DO_MATCH_SKIPPHRASE = importlib.resources.read_text('whereabouts.queries', 'geocoder_query_skipphrase.sql')
DO_MATCH_TRIGRAM = importlib.resources.read_text('whereabouts.queries', 'geocoder_query_trigramb2.sql')
CREATE_GEOCODER_TABLES = importlib.resources.read_text('whereabouts.queries', 'create_geocoder_tables.sql')

# UDF for comparing overlap in numeric tokens between input and candidate addresses
def list_overlap(list1: list[str], 
                 list2: list[str], 
                 threshold: float) -> bool:
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

def ngram_jaccard(input_address: str, candidate_address: str) -> float:
    # bigrams
    bigrams_input = [input_address[n:n+2] for n in range(0, len(input_address) - 1)]
    bigrams_candidate = [candidate_address[n:n+2] for n in range(0, len(candidate_address) - 1)]
    # unigrams
    unigrams_input = [input_address[n:n+1] for n in range(0, len(input_address))]
    unigrams_candidate = [candidate_address[n:n+1] for n in range(0, len(candidate_address))]
    ngrams_input_set = set(bigrams_input).union(unigrams_input)
    ngrams_candidate_set = set(bigrams_candidate).union(unigrams_candidate)
    return len(ngrams_input_set.intersection(ngrams_candidate_set)) / len(ngrams_input_set.union(ngrams_candidate_set))

    
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
        # check that model is in folder
        with importlib.resources.path('whereabouts', '') as whereabouts_path:
            path_to_models = Path(whereabouts_path) / 'models'

        db_names = os.listdir(path_to_models)
        db_names = [db_name[:-3] for db_name in db_names if db_name[-3:] == '.db']
        if db_name in db_names:
            self.con = duckdb.connect(database=f'{path_to_models}/{db_name}.db')
        else:
            print(f"Could not find database {db_name}")
            print(f"The following geocoding databases are installed:")
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