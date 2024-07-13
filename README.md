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
- requirements.txt (found in repo)

## Installation: via PIP

whereabouts can be installed either from this repo using pip / uv / conda

```
pip install whereabouts
```

### 1. Install depedencies
Install all the dependencies:

```
pip install -r requirements.txt
```

## Download a geocoder database or create your own

You will need a geocoding database to match addresses against. You can either download a pre-built database or create your own using a dataset of high quality reference addresses for a given country, state or other geographic region.

### 1. Download a geocoder database

Pre-built geocoding database are available from [Huggingface](https://www.huggingface.co). The list of available databases can be found [here](https://huggingface.co/saunteringcat/whereabouts-db/tree/main)

As an example, to install the small size geocoder database for all of Australia:

```
python -m whereabouts download au_all_sm
```


### 2. Create a geocoder database

You can create your own geocoder database if you have your own address file. This file should be a single csv or parquet file with the following columns:

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

matcher = Matcher(db_name='gnaf_au')
matcher.geocode(addresslist, how='standard')
```

For more accurate geocoding you can use trigram phrases rather than token phrases (note that the trigram option has to have been specified in the setup.yml file as part of the setup)
```
matcher.geocode(addresslist, how='trigram')
```