Usage
=====

.. _installation:

Installation
------------

To use whereabouts, first install using your favourite package manager

.. code-block:: console

   (.venv) $ pip install whereabouts

You will then need to download a pre-built geocoding database or build your own

.. code-block:: console
   (.venv) $ python -m whereabouts download au_all_sm

Downloading a geocoding database
--------------------------------

whereabouts requires a geocoding database in order to match addresses correctly. The format of these
is (country_name)_(states)_(size)

Start geocoding
---------------

Now you're ready to start geocoding your own addresses:

>>> from whereabouts.Matcher import Matcher
>>> matcher = Matcher('au_all_sm')
>>> matcher.geocode(['34/121 exhibition st melbourne', '645 sydney rd brunswick'])
