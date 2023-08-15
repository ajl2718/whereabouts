import pandas as pd 
from time import time
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='gnaf_au')

# load a dataset
filename = 'datasets/apartments_210223.csv'

df = pd.read_csv(filename)
addresslist = df.address.values

t1 = time()
results = matcher.geocode(addresslist, how='trigram')
t2 = time()
print(f'Geocoded {len(results)} addresses in {t2 - t1}s')