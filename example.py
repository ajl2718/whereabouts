import pandas as pd 
from time import time
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='gnaf_sa')

# load a dataset
filename = '/home/alex/Desktop/Data/location_data/sa_propertydatabase.csv'

df = pd.read_csv(filename)

# clean the text fields
for col in df.columns[:-1]:
    df[col] = df[col].str.strip().str.replace('[ ]+', ' ', regex=True)

# create full address field
df['Full_Address'] = df['Address'] + ' ' + df['Suburb_PostCode']

addresslist = df.Full_Address.str.slice(0, -7).str.upper().str.replace('N', '')

# standard geocoding
t1 = time()
results = matcher.geocode(addresslist, how='standard')
t2 = time()
print(f'Geocoded {len(results)} addresses in {t2 - t1}s')

# trigram geocoding
df2 = pd.read_csv('adds_200823.csv')
addresslist = list(df2.address.values)
addresslist2 = list(df.Full_Address.str.slice(0, -7).str.upper().str.replace('N', '')[:256])
addresslist3 = addresslist + addresslist2
results = matcher.geocode(addresslist3, how='trigram')

# reverse geocode
df = pd.read_excel('/home/alex/Desktop/Data/location_data/current_victorian_licences_by_location_18.xlsx', skiprows=3)
points = df.loc[:, ['Latitude', 'Longitude']].dropna().values

matcher = Matcher('gnaf_vic')

t1 = time()
results = matcher.reverse_geocode(points)
t2 = time()
print(f'Reverse geocoded {len(results)} locations in {t2 - t1}s')