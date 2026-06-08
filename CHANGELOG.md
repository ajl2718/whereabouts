# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Benchmarking CLI command (`python -m whereabouts benchmark`) for evaluating geocoder accuracy against test sets.
- Benchmarking dataset (`example_data/test_set_au.csv`) for Australian addresses.
- `multiset_jaccard` similarity function for improved string matching.
- New SQL matching query using `multiset_jaccard` for string similarity.
- New standard geocoder query using intersection/union numeric overlap.
- `AGENTS.md` and `CLAUDE.md` for agentic coding guidelines.
- Type hints across the codebase.
- Custom error classes for better error handling.
- Evaluation server and UI for interactive geocoder testing.
- 12 new test sets for filtering and string similarity.

### Changed
- Refactored `matching_queries.py` into a `matching_queries/` package with separate modules (`standard.py`, `common.py`).
- Tidied similarity functions.
- Improved docstring style, import ordering, and control flow.
- `setup_geocoder` now removes any existing database with the given name before creating a new one.
- Databases are now recreated fresh if they already exist.
- Better handling of edge cases in similarity functions.

### Fixed
- Upgraded `urllib3` to fix security vulnerability.
- Upgraded `requests` to fix security vulnerability.
- Bumped `lxml` from 5.3.1 to 6.1.0.
- Fixed string type issue failing `db_test` matching test.
- Reverted `numeric_overlap` function to previous version to fix regression.

### Removed
- Evaluation tool temporarily removed until security issue is addressed.

## [0.4.3] - 2025-12-30

### Added
- Custom error type classes (`InvalidDatabaseError`, etc.).

### Fixed
- Ensured trigram phrases are stored as integers.
- Fixed error handling when loading databases.

## [0.4.2] - 2025-12-06

### Added
- Support for remote DuckDB databases (contributed by [@luipir](https://github.com/luipir)).
- `filter_to_single_response` utility function for extracting the best match per address ID.
- New SQL queries supporting multiple ranked candidate matches per input address.
- `full_address` schema label in setup configuration.
- README documentation for `setup.yml` structure.

### Changed
- Matcher can now transparently use remote or local whereabouts databases.
- `order_matches` updated to include similarity in descending order for multi-response matches.

### Fixed
- Fixed bug in `urllib` import.
- Updated `urllib3` to 2.6.0 to fix security vulnerability.

## [0.4.1] - 2025-08-17

### Added
- Support for returning multiple candidate matches per input address via `top_n` parameter.
- `matcher.geocode` now accepts `pd.Series` and `np.ndarray` inputs.
- Additional tests for multi-response geocoding.
- Accuracy comparison charts in README (vs Google, Mapbox, Nominatim).
- Project links added to `pyproject.toml`.
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
- Issue templates.

### Changed
- Migrated from Hugging Face Hub to direct `requests` downloads for database files.
- Migrated build system to `uv`.
- Updated `convert_db` function to output to current working directory.
- Updated ReadTheDocs configuration.

### Fixed
- Fixed indentation error.
- Fixed error with `os.remove` after database creation.
- Fixed `utf-8` encoding when loading `.sql` files.
- Updated `jinja2`, `numpy`, and other dependencies for security and compatibility.
- Fixed GitHub Actions workflow permissions for code scanning.

## [0.3.15] - 2024-12-23

### Added
- SQL query support for Polish addresses with Unicode character handling.
- Polish address test data and tests.
- JOSS paper draft submission.
- License disclaimer for third-party data in README.
- Citation information in README.

### Changed
- Updated documentation with database creation instructions.

## [0.3.14] - 2024-08-29

### Changed
- Updated contributions file.

## [0.3.13] - 2024-08-28

### Added
- Initial tagged release.
- Core geocoding engine using DuckDB with inverted indexes of address token-pair phrases.
- `Matcher` class for geocoding and reverse geocoding.
- `AddressLoader` for building geocoder databases from CSV/Parquet files.
- Three matching algorithms: `standard`, `skipphrase`, and `trigram`.
- SQL-based query pipeline for address matching.
- Support for Australian GNAF data via `GNAFLoader`.
- Database export/import functionality.
- KD-tree creation for reverse geocoding.
- `setup.yml`-driven database creation.
- Pre-built database downloads from Hugging Face.
- Command-line interface (`python -m whereabouts`).

[Unreleased]: https://github.com/ajl2718/whereabouts/compare/0.4.3...HEAD
[0.4.3]: https://github.com/ajl2718/whereabouts/compare/0.4.2...0.4.3
[0.4.2]: https://github.com/ajl2718/whereabouts/compare/0.4.1...0.4.2
[0.4.1]: https://github.com/ajl2718/whereabouts/compare/0.3.15...0.4.1
[0.3.15]: https://github.com/ajl2718/whereabouts/compare/0.3.14...0.3.15
[0.3.14]: https://github.com/ajl2718/whereabouts/compare/0.3.13...0.3.14
[0.3.13]: https://github.com/ajl2718/whereabouts/releases/tag/0.3.13
