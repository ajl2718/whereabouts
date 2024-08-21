# Whereabouts
A light-weight, fast geocoder for Python using DuckDB. Try it out online at [Huggingface](https://huggingface.co/spaces/saunteringcat/whereabouts-geocoding)


## Description
Whereabouts is an open-source geocoding library for Python, allowing you to geocode and standardize address data all within your own environment:

Features:
- Two line installation
- No additional database setup required. Uses DuckDB to run all queries
- No need to send data to an external geocoding API
- Fast (Geocode 1000s / sec depending on your setup)
- Robust to typographical errors

## Requirements
- Python 3.8+
- requirements.txt (found in repo)

## Installation: via PIP

whereabouts can be installed either from this repo using pip / uv / conda

```
pip install whereabouts
```

## Download a geocoder database or create your own

You will need a geocoding database to match addresses against. You can either download a pre-built database or create your own using a dataset of high quality reference addresses for a given country, state or other geographic region.

### Option 1: Download a geocoder database

Pre-built geocoding database are available from [Huggingface](https://www.huggingface.co). The list of available databases can be found [here](https://huggingface.co/saunteringcat/whereabouts-db/tree/main)

As an example, to install the small size geocoder database for all of Australia:

```
python -m whereabouts download au_all_sm
```

### Option 2: Create a geocoder database

Rather than using a pre-built database, you can create your own geocoder database if you have your own address file. This file should be a single csv or parquet file with the following columns:

| Column name | Description | Data type |
| ----------- | ----------- | --------- |
| ADDRESS_DETAIL_PID | Unique identifier for address | int |
| ADDRESS_LABEL | The full address | str |
| ADDRESS_SITE_NAME | Name of the site. This is usually null | str |
| LOCALITY_NAME | Name of the suburb or locality | str |
| POSTCODE | Postcode of address | int |
| STATE | State | str |
| LATITUDE | Latitude of geocoded address | float |
| LONGITUDE | Longitude of geocoded address | float |

These fields should be specified in a `setup.yml` file. Once the `setup.yml` is created and a reference dataset is available, the geocoding database can be created:

```
python -m whereabouts setup_geocoder setup.yml
```
## Geocoding examples

Geocode a list of addresses 
```
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='au_all_sm')
matcher.geocode(addresslist, how='standard')
```

For more accurate geocoding you can use trigram phrases rather than token phrases. Note you will need one of the large databases to use trigram geocoding.
```
matcher.geocode(addresslist, how='trigram')
```

## How it works
The algorithm employs simple record linkage techniques, making it suitable for implementation in around 10 lines of SQL. It is based on the following papers
- https://arxiv.org/abs/1708.01402
- https://arxiv.org/abs/1712.09691

## Documentation
Work in progress: https://whereabouts.readthedocs.io/en/latest/

## To do:
- Additional countries (US, NZ, France, UK)
- Geocode street corners
- Geocode individual suburb, street name pairs (without house numbers)
