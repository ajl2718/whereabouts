from time import time

import pandas as pd 

from whereabouts.Matcher import Matcher
from whereabouts.MatcherPipeline import MatcherPipeline

matcher1 = Matcher('au_all_sm')
matcher2 = Matcher('au_all_lg', how='trigram')
pipeline = MatcherPipeline([matcher1, matcher2])

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