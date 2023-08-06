# Whereabouts
Fast, scalable geocoding for Python using an embedded database

## Description
Geocode addresses and reverse geocode coordinates with a simple, fast package. No additional database setup required. Currently only working for Australian data.

## Requirements
- Python 3.8+
- Poetry (for package management)

## Installation
Once Poetry is installed and you are in the project directory:

```
poetry shell
poetry install
```

Download the latest version of the GNAF
```
python download_gnaf.py
```

And setup the geocoder. This creates the required reference tables, etc.
```
python setup_geocoder.py
```

## Examples
