[![Documentation Status](https://readthedocs.org/projects/whereabouts/badge/?version=latest)](http://whereabouts.readthedocs.io/en/latest/?badge=latest)
[![Downloads](https://pepy.tech/badge/whereabouts)](https://pepy.tech/project/whereabouts)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/ajl2718/whereabouts/issues)

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

As an example, to install the small size geocoder database for California:

```
python -m whereabouts download us_ca_sm
```

or for the small size geocoder database for all of Australia:

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

## License Disclaimer for Third-Party Data
Note that while the code from this package is licensed under the MIT license, the pre-built databases use data from data providers that may have restrictions for particular use cases:

- The Australian databases are built from the [Geocoded National Address File](https://https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf) with conditions of use based on the [End User License Agreemment](https://data.gov.au/dataset/ds-dga-e1a365fc-52f5-4798-8f0c-ed1d33d43b6d/distribution/dist-dga-0102be65-3781-42d9-9458-fdaf7170efed/details?q=previous%20gnaf)
- The US databases are still work-in-progress but are based on data from [OpenAddresses](https://openaddresses.io/) and so any work with whereabouts based on US address data should adhere to the [OpenAddresses license](https://github.com/openaddresses/openaddresses/blob/master/LICENSE).

Users of this software must comply with the terms and conditions of the respective data licenses, which may impose additional restrictions or requirements. By using this software, you agree to comply with the relevant licenses for any third-party data.

## Citing
To cite this repo, please use the following

```bibtext
@software{whereabouts_2024,
  author = {Alex Lee},
  doi = {[10.5281/zenodo.1234](https://doi.org/10.5281/zenodo.13627073)},
  month = {10},
  title = {{Whereabouts}},
  url = {https://github.com/ajl2718/whereabouts},
  version = {0.3.14},
  year = {2024}
}```

## To do:
- Additional countries (US, NZ, France, UK)
- Geocode street corners
- Geocode individual suburb, street name pairs (without house numbers)
