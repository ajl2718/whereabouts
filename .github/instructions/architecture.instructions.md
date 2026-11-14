---
applyTo: "**"
---

# Architecture notes

- Geocoder databases are DuckDB `.db` files containing inverted indexes of address token-pair phrases.
- The `Matcher` class attaches a DuckDB database and registers custom scalar functions (`list_overlap`, `numeric_overlap`, `ngram_jaccard`) for similarity scoring.
- All matching algorithms use `QueryStep`/`QueryPipeline` factories in `whereabouts/matching_queries/`. `create_matching_pipeline` selects standard, skipphrase, or trigram for both the matcher and evaluator.
- Database table creation, data loading, phrases, indexes, and cleanup use shared pipelines in `matching_queries/database.py`, `phrases.py`, and `addrtext_with_detail.py`. `LoadAddresses` reuses `AddressLoader`; `GNAFLoader` retains its legacy interface.
- There are no bundled `.sql` resources. CTE pipelines use `execute`, `execute_as_table`, or `execute_into_table`; standalone DDL/DML pipelines use `execute_direct`.
- Database creation is driven by a `setup.yml` configuration file.
