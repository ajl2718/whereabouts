# Whereabouts
Fast, scalable geocoding for Python using DuckDB

## Description
Geocode addresses and reverse geocode coordinates directly from Python in your own environment. 
- No additional database setup required. Uses DuckDB to run all queries
- No need to send data to an external geocoding API
- Fast (Geocode 1000s / sec and reverse geocode 200,000s / sec)
- Robust to typographical errors

**Currently only working for Australian data.**

## Requirements
- Python 3.8+
- Poetry (for package management)

## Installation
Once Poetry is installed and you are in the project directory:

```
poetry shell
poetry install
```

1) Download the latest version of GNAF core from https://geoscape.com.au/data/g-naf-core/
2) Update the `setup.yml` file to point to the location of the GNAF core file
3) Finally, setup the geocoder. This creates the required reference tables

```
python setup_geocoder.py
```

## Examples

Geocode a list of addresses 
```
from whereabouts.Matcher import Matcher

matcher = Matcher(db_name='gnaf_au')
matcher.geocode(addresslist, how='standard')
```

For more accurate geocoding you can use trigram phrases rather than token phrases
```
matcher.geocode(addresslist, how='trigram')
```