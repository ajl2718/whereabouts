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
that uses trigram matching.

>>> from whereabouts.MatcherPipeline import MatcherPipeline
>>> from whereabouts.Matcher import Matcher 
>>> matcher1 = Matcher('au_all_sm')
>>> matcher2 = Matcher('au_all_lg', how='trigram')
>>> pipeline = MatcherPipeline([matcher1, matcher2])
>>> results = pipeline.geocode(addresses)