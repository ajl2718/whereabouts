from time import time
import pandas as pd 

from whereabouts import Matcher

matcher = Matcher('au_all_sm')

filename = '/Users/alexlee/Desktop/Data/test_data/nab_atms_080424.csv'
filename = '/Users/alexlee/Desktop/Data/test_data/rea_130824.csv'

df = pd.read_csv(filename, sep='\t')

addresses = df.address.unique()

t1 = time()
results = pipeline.geocode(addresses)
t2 = time()
print(f'Geocoded {addresses.shape[0]} addresses in {t2 - t1}s')

###
query = """
select unnest(string_to_array(regexp_replace(trim('BOLESŁAWIEC'), '[^A-Z0-9ÀÂĀÆÇÉÈÊËÎÏÔŌŒÙÛÜŸĄĆĘŁŃÓŚŹŻ]+', ' ', 'g'), ' ')) token
"""

addresses = ["WAŁOWA 2B BOLESŁAWIEC", "TADEUSZA KOŚCIUSZKI 56A BOLESŁAWIEC ", "ZIELONA 2 BOLESŁAWIEC "]

#
import duckdb
from whereabouts.utils import (
    list_overlap,
    numeric_overlap,
    numeric_overlap2,
    multiset_jaccard,
    ngram_jaccard,
    IOU,
    IOU_min
)

db = duckdb.connect('whereabouts/models/au_all_sm.db')

db.create_function("list_overlap", list_overlap)
db.create_function("numeric_overlap", numeric_overlap)
db.create_function("numeric_overlap2", numeric_overlap2)
db.create_function("multiset_jaccard", multiset_jaccard)
db.create_function("ngram_jaccard", ngram_jaccard)
db.create_function("IOU", IOU)
db.create_function("IOU_min", IOU_min)
db.execute(
    "INSTALL splink_udfs FROM community; LOAD splink_udfs;"
)

addresses = ['155 Charlotte St, Brisbane', '29 NAPIER ST ST ARNAUD']
addresses_numerics = [['155'], ['29']]
addresses_alphas = [['CHARLOTTE', 'ST', 'BRISBANE'], ['NAPIER', 'ST', 'ST', 'ARNAUD']]

addresses_correct = ['155 CHARLOTTE ST BRISBANE CITY QLD 4000']
addresses_correct_numerics = [['155', '4000']]
addresses_correct_alphas = [['CHARLOTTE', 'ST', 'BRISBANE', 'CITY', 'QLD']]

address_mismatched = [['UNIT 155 95 CHARLOTTE ST BRISBANE CITY QLD 4000', '155 CHARLOTTE BAY ST CHARLOTTE BAY NSW 2428']]

address_mismatched_numerics = [['155', '95', '4000'], ['155', '2428']]
addresses_mismatched_alphas = [['UNIT', 'CHARLOTTE', 'ST', 'BRISBANE', 'CITY', 'QLD'], ['CHARLOTTE', 'BAY', 'ST', 'CHARLOTTE', 'BAY', 'NSW']]

# comparing different similarities
db.sql("select IOU(['155'], ['155', '95']) * IOU_min(['CHARLOTTE', 'ST', 'BRISBANE', 'CITY', 'QLD'], ['UNIT', 'CHARLOTTE', 'ST', 'BRISBANE', 'CITY', 'QLD']) as similarity")

# for given pairs of addresses, compute different similarities

def compute_similarity(input_address: str, 
                       matched_address: str, 
                       similarity_func: callable) -> float:
    return similarity_func(input_address, matched_address)

def similarity1(input_address: str, 
                matched_address: str) -> float:
    input_numerics = [token for token in input_address.split(' ') if token.isdigit()]
    input_alpha_tokens = [token for token in input_address.split(' ') if not token.isdigit()]
    match_numerics = [token for token in matched_address.split(' ') if token.isdigit()]
    match_alpha_tokens = [token for token in matched_address.split(' ') if not token.isdigit()]
    return IOU_min(input_alpha_tokens, match_alpha_tokens) * IOU(input_numerics, match_numerics)    
)

prompt = """
I have a list of addresses in the file whereabouts/benchmark_results/benchmarking_results_010626_narrow.csv. This file contains columns: input_address, matched_address, expected_address and correct.

I want to create a string similarity function that ensures that the input address and the expected address has a higher similarity score than the input address and the matched address. The similarity function should extract features such as the numeric tokens, the non-numeric tokens, substrings and compute a similarity score. 

The objective is to maximise the number of rows where the similarity score between the input address and the expected address is higher than the similarity score between the input address and the matched address, for the rows where correct is True. 

Produce the final function in the the file sim_function.py. The function should take in two addresses and return a similarity score between 0 and 1.
"""