Usage
=====

.. _installation:

License Disclaimer for Third-Party Data
---------------------------------------

Note that while the code from this package is licensed under the MIT license, the pre-built databases use data from data providers that may have restrictions for particular use cases:

- The Australian databases are built from the `Geocoded National Address File <https://data.gov.au/data/dataset/geocoded-national-address-file-g-naf>`_ with conditions of use based on the `End User License Agreement <https://data.gov.au/dataset/ds-dga-e1a365fc-52f5-4798-8f0c-ed1d33d43b6d/distribution/dist-dga-0102be65-3781-42d9-9458-fdaf7170efed/details?q=previous%20gnaf>`_.
- The US databases are still work-in-progress but are based on data from `OpenAddresses <https://openaddresses.io/>`_ and so any work with whereabouts based on US address data should adhere to the `OpenAddresses license <https://github.com/openaddresses/openaddresses/blob/master/LICENSE>`_.

Users of this software must comply with the terms and conditions of the respective data licenses, which may impose additional restrictions or requirements. By using this software, you agree to comply with the relevant licenses for any third-party data.

Installation
------------

To use whereabouts, first install using your favourite package manager

.. code-block:: console

   $ pip install whereabouts

You will then need to download a pre-built geocoding database or build your own

.. code-block:: console

   $ python -m whereabouts download au_all_sm

The current pre-built databases are available on `Huggingface <https://huggingface.co/saunteringcat/whereabouts-db>`_.
These come in two sizes, with the larger databases able to handle a greater range of data quality issues for improved 
recall.

Start geocoding: standard matching
---------------

Now you're ready to start geocoding your own addresses:

>>> from whereabouts.Matcher import Matcher
>>> matcher = Matcher('au_all_sm')
>>> matcher.geocode(['34/121 exhibition st melbourne', '645 sydney rd brunswick'])

This is the standard matcher that is faster but can be less accurate, depending on the quality of the input data.

Trigram matching
----------------
For improved matching accuracy you can use a larger database with `trigram` matching. This comes at the expense of speed.

>>> matcher = Matcher('au_all_lg')
>>> matcher.geocode(['121 exhibitn st melburne'], how='trigram')

Matching pipelines: the best of both worlds
-------------------------------------------
You can also chain matcher objects together so that addresses that fail to match with standard matching are sent to a second matcher
that uses trigram matching. Note that the larger databases allow for both standard and trigram matching.

>>> from whereabouts.MatcherPipeline import MatcherPipeline
>>> from whereabouts.Matcher import Matcher 
>>> matcher1 = Matcher('au_all_lg', how='standard')
>>> matcher2 = Matcher('au_all_lg', how='trigram')
>>> pipeline = MatcherPipeline([matcher1, matcher2])
>>> results = pipeline.geocode(addresses)

Building your own address database
----------------------------------

Rather than using a pre-built database, you can create your own geocoder database if you have your own address file. This file should be a single csv or parquet file with the following columns:

.. list-table:: 
   :header-rows: 1

   * - Column name
     - Description
     - Data type
   * - ADDRESS_DETAIL_PID
     - Unique identifier for address
     - int
   * - ADDRESS_LABEL
     - The full address
     - str
   * - ADDRESS_SITE_NAME
     - Name of the site. This is usually null
     - str
   * - LOCALITY_NAME
     - Name of the suburb or locality
     - str
   * - POSTCODE
     - Postcode of address
     - int
   * - STATE
     - State
     - str
   * - LATITUDE
     - Latitude of geocoded address
     - float
   * - LONGITUDE
     - Longitude of geocoded address
     - float

These fields should be specified in a ``setup.yml`` file, which is structured as follows::

    data:
        db_name: au_vic_lg
        folder: geodb
        filepath: 'address_file.parquet'
        sep: ","
    geocoder:
        matchers: [standard, trigram]
        states: [VIC]
    schema:
        addr_id: ADDRESS_DETAIL_PID
        full_address: ADDRESS_LABEL
        address_site_name: ADDRESS_SITE_NAME
        locality_name: LOCALITY_NAME
        postcode: POSTCODE
        state: STATE
        latitude: LATITUDE
        longitude: LONGITUDE

``addr_id`` is a unique integer, ``full_address`` contains the full address string while ``locality_name``, ``postcode`` and ``state`` are components of the address.


Once the ``setup.yml`` is created and a reference dataset is available, the geocoding database can be created:

.. code-block:: bash

   python -m whereabouts setup_geocoder setup.yml
