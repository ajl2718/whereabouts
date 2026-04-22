# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands should be run with `uv`:

```bash
# Run all tests (tests must run in order — use pytest-order)
uv run pytest

# Run a single test file
uv run pytest tests/test_addressbuilder.py

# Run a single test by name
uv run pytest tests/test_addressbuilder.py::test_geocoding_standard

# Lint
uv run ruff check whereabouts/

# Download a pre-built geocoder database
uv run python -m whereabouts download au_all_sm

# Build a geocoder database from a reference dataset
uv run python -m whereabouts setup_geocoder setup.yml

# List installed databases
uv run python -m whereabouts list_databases
```

## Architecture

Whereabouts is a Python geocoding library backed by DuckDB. The core idea: address strings are broken into token-pair "phrases", which are indexed in an inverted index stored in a DuckDB `.db` file. At query time, input phrases are looked up in the inverted index to find candidate addresses, then a similarity score (n-gram Jaccard × numeric token overlap) ranks and filters them.

### Key classes

- **`Matcher`** ([whereabouts/Matcher.py](whereabouts/Matcher.py)) — The main geocoding interface. On init, attaches a DuckDB database (`remote`) and registers three custom scalar functions (`list_overlap`, `numeric_overlap`, `ngram_jaccard`) into the DuckDB connection. `geocode()` loads input addresses into a temporary DuckDB table and dispatches to one of three SQL query files depending on `how`.

- **`AddressLoader`** ([whereabouts/AddressLoader.py](whereabouts/AddressLoader.py)) — Used offline to build geocoder databases from raw CSV/Parquet address files. Runs a sequence of SQL steps: create tables → load raw data → create phrase/skipphrase/trigram tables → build inverted index → clean up intermediate tables → export/import the final `.db`.

- **`MatcherPipeline`** ([whereabouts/MatcherPipeline.py](whereabouts/MatcherPipeline.py)) — Chains multiple `Matcher` objects sequentially: addresses below the first matcher's similarity threshold are passed to the next matcher, improving recall.

### Three matching algorithms

Each corresponds to a SQL file loaded at module import time:

| `how=` | SQL file | Index table | Notes |
|--------|----------|-------------|-------|
| `standard` | `geocoder_query_standard3.sql` | `phraseinverted` | Token-pair phrases; fastest |
| `skipphrase` | `geocoder_query_skipphrase2.sql` | `skipphraseinverted` | Token-pairs with one token skipped; handles word-order variation |
| `trigram` | `geocoder_query_trigramb3.sql` | trigram tables | Character-level; most typo-tolerant; requires large DB |

### Database structure

Geocoder databases are DuckDB `.db` files stored in `whereabouts/models/`. The key tables are:

- `addrtext` — raw address records (addr_id, addr, numeric_tokens, ADDRESS_LABEL, suburb, POSTCODE, LATITUDE, LONGITUDE)
- `addrtext_with_detail` — final address table joined with spatial attributes
- `phraseinverted` — inverted index mapping token-pair phrases → list of matching addr_ids
- `skipphraseinverted` — same for skip-phrases
- Trigram tables (built in four SQL steps)

The `Matcher` connects to the database as `remote` (attached DuckDB), while input addresses are loaded into a temporary in-memory `input_addresses` table for each `geocode()` call.

### SQL queries

All SQL is in `whereabouts/queries/` and loaded via `importlib.resources` at import time. The numbered variants (e.g., `geocoder_query_standard3.sql`) are successive iterations — the highest-numbered file is the one actually used. `geocoder_query_standard5.sql` in the project root is an in-progress query, not yet wired in.

### Similarity functions
The matching algorithm depends on a user-defined similarity function. This is important for ranking candidate matches; different choices of similarity function have significant impacts on precision and recall of the matching algorithm.

### Configuration / setup

Database creation is driven by a `setup.yml` file (see [setup.yml](setup.yml) for an example). The `geocoder.matchers` key controls which phrase types are built (`standard`, `skipphrase`, `trigram`). State filtering is optional. Depending on the country `State` may refer to `Region`, `Province` or some other sub-national geographic area.

### Tests

Tests in `tests/test_addressbuilder.py` are stateful and must run in order (enforced via `pytest-order`): they build a `db_test.db` database from `tests/test_data3056.parquet`, geocode against it, then delete it. `conftest.py` cleans up stale databases before the session starts.