# AGENTS.md

Coding guidelines for AI agents working on this repository.

## Style

- Follow **PEP 8** for all Python code.
- Use `ruff` as the linter and formatter. Run `uv run ruff check whereabouts/` before committing.
- Use **snake_case** for functions, methods, variables, and module-level constants (except `UPPER_SNAKE_CASE` for true constants).
- Use **PascalCase** for class names (e.g. `Matcher`, `AddressLoader`, `MatcherPipeline`).
- Keep lines to a maximum of **120 characters**.
- Prefer f-strings over `str.format()` or `%` formatting.
- Use type hints for function signatures in new or modified code.

## Tooling

- **Package manager**: `uv`. All commands must be run via `uv run`.
- **Python version**: ≥ 3.12 (see `pyproject.toml`).
- **Build backend**: Hatchling.
- **Linter/formatter**: `ruff`.
- **Testing**: `pytest` with `pytest-order` (tests are stateful and must run in order).

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_addressbuilder.py

# Lint
uv run ruff check whereabouts/

# Format
uv run ruff format whereabouts/

# Build a geocoder database
uv run python -m whereabouts setup_geocoder setup.yml

# Download a pre-built database
uv run python -m whereabouts download au_all_sm

# List installed databases
uv run python -m whereabouts list_databases
```

## Project layout

| Path | Purpose |
|------|---------|
| `whereabouts/` | Main package |
| `whereabouts/Matcher.py` | Core geocoding interface (`Matcher` class) |
| `whereabouts/AddressLoader.py` | Offline database builder |
| `whereabouts/MatcherPipeline.py` | Chains multiple matchers for improved recall |
| `whereabouts/QueryStep.py` | SQL components and function registration |
| `whereabouts/QueryPipeline.py` | Query pipeline |
| `whereabouts/utils.py` | Similarity functions (ngram_jaccard, list_overlap, etc.) |
| `whereabouts/models/` | Geocoder `.db` files (DuckDB databases) |
| `whereabouts/matching_queries/` | Implementations of matching algorithms | 
| `examples/` | Example code demonstrating functionality of the package | 
| `example_data/` | Data used for evaluation of the different algorithms | 
| `tests/` | Test suite (stateful, order-dependent) |
| `docs/` | Sphinx documentation |
| `evaluation/` | Geocoder evaluation server and UI |

## Architecture notes

- Geocoder databases are DuckDB `.db` files containing inverted indexes of address token-pair phrases.
- The `Matcher` class attaches a DuckDB database and registers custom scalar functions (`list_overlap`, `numeric_overlap`, `ngram_jaccard`) for similarity scoring.
- Three matching algorithms exist: `standard`, `skipphrase`, and `trigram`. Each corresponds to a SQL file in `whereabouts/queries/`.
- SQL query files are versioned with numeric suffixes; the highest number is the active version.
- Database creation is driven by a `setup.yml` configuration file.

## Testing conventions

- Tests in `tests/test_addressbuilder.py` are **stateful and order-dependent** (enforced by `pytest-order`). They build a test database, run geocoding queries, then clean up.
- `conftest.py` removes stale test databases (`db_test.db`, `db_test_poland.db`) before the session starts.
- Always run the full test suite with `uv run pytest` to verify changes.
- Do not reorder or isolate tests that depend on prior test state.

## Git conventions

- Commit messages should be concise and descriptive.
- Do not commit generated `.db` files or large data files.
- The default branch is `main`.

## Benchmarking
The folder `example_data` contains benchmarking datasets to test the algorithm against. Each file in the folder is a `.csv` file with columns `input_address` and `best_match`, where the first of these columns is an address we want to geocode and the second column is what it should match to.

