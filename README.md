# Whereabouts
Fast, scalable geocoding for Python using DuckDB. The geocoding algorithms are based on the following papers:
- https://arxiv.org/abs/1708.01402
- https://arxiv.org/abs/1712.09691

## Description
Geocode addresses and reverse geocode coordinates directly from Python in your own environment. 
- No additional database setup required. Uses DuckDB to run all queries
- No need to send data to an external geocoding API
- Fast (Geocode 1000s / sec and reverse geocode 200,000s / sec)
- Robust to typographical errors


## Requirements
- Python 3.8+
- Poetry (for package management)

## Installation
Once Poetry is installed and you are in the project directory:

```
poetry shell
poetry install
```

## Create a geocoder database
To start geocoding, a geocoding database has to be created, which uses a reference dataset containing addresses and corresponding latitude, longitude values.

The reference file should be a single csv file with at least three fields: the complete address, latitude, longitude. These fields should be specified in a `setup.yml` file. An example is included.

Once the `setup.yml` is created and a reference dataset is available, the geocoding database can be created using the `setup_geocoder` function from whereabouts.utils.

The current process for using Australian data from the GNAF is as follows:
1) Download the latest version of GNAF core from https://geoscape.com.au/data/g-naf-core/
2) Update the `setup.yml` file to point to the location of the GNAF core file
3) Finally, setup the geocoder. This creates the required reference tables

```
python -m whereabouts setup_geocoder setup.yml
```

To use address data from another country, the file should have the following columns:

| Column name | Description |
| ----------- | ----------- |
| ADDRESS_DETAIL_PID | Unique identifier for address |
| ADDRESS_LABEL | The full address |
| ADDRESS_SITE_NAME | Name of the site. This is usually null |
| LOCALITY_NAME | Name of the suburb or locality |
| POSTCODE | Postcode of address |
| STATE | State 
| LATITUDE | Latitude of geocoded address |
| LONGITUDE | Longitude of geocoded address |

## Examples

Geocode a list of addresses 
```
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='gnaf_au')
matcher.geocode(addresslist, how='standard')
```

For more accurate geocoding you can use trigram phrases rather than token phrases (note that the trigram option has to have been specified in the setup.yml file as part of the setup)
```
matcher.geocode(addresslist, how='trigram')
```

Once a Matcher object is created, the KD-tree for fast geocoding will also be created. A list of latitude, longitude values can then be reverse geocoded as follows
```
matcher.reverse_geocode(coordinates)
```