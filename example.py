import pandas as pd 
from time import time
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='gnaf_au')

# load a dataset
filename = '/home/alex/Desktop/Data/location_data/current_victorian_licences_by_location_18.xlsx'
df = pd.read_excel(filename, skiprows=3)
df = (
    df
    .assign(address_full = df.Address + ' ' + df.Suburb)
    .query('address_full.isnull() == False')
    .query('Latitude.isnull() == False')
    .query('Longitude.isnull() == False')
    .loc[:, ['address_full', 'Latitude', 'Longitude']]
    .rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'})
)

addresslist = df.address_full.values

t1 = time()
results = matcher.geocode(addresslist)
t2 = time()
print(f'Geocoded {len(results)} addresses in {t2 - t1}s')

# reverse geocoding
points = (df
          .query('latitude.isnull() == False')
          .query('longitude.isnull() == False')
          .loc[:, ['latitude', 'longitude']]
).values

t1 = time()
results = matcher.reverse_geocode(points)
t2 = time()
print(f'Reverse geocoded {len(results)} addresses in {t2 - t1}s')

# Geocoding fixes:
# don't use building name in comparison
# address spans
# incorrect suburb or postcode
# street corners

# for reverse geocoding:
# how to match to closest polygon rather than point, e.g., when location takes up substantial space 
# point may be within the polygon but closer to another address's centroid.