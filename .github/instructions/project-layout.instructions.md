---
applyTo: "**"
---

# Project layout

| Path | Purpose |
|------|---------|
| `whereabouts/` | Main package |
| `whereabouts/Matcher.py` | Core geocoding interface (`Matcher` class) |
| `whereabouts/AddressLoader.py` | Offline database builder |
| `whereabouts/MatcherPipeline.py` | Chains multiple matchers for improved recall |
| `whereabouts/QueryStep.py` | Composable SQL steps |
| `whereabouts/QueryPipeline.py` | Query pipeline |
| `whereabouts/utils.py` | Similarity functions (ngram_jaccard, list_overlap, etc.) |
| `whereabouts/models/` | Geocoder `.db` files (DuckDB databases) |
| `whereabouts/matching_queries/` | Implementations of matching algorithms |
| `examples/` | Example code demonstrating functionality of the package |
| `example_data/` | Data used for evaluation of the different algorithms |
| `tests/` | Test suite (stateful, order-dependent) |
| `docs/` | Sphinx documentation |
| `whereabouts/evaluation/` | Geocoder evaluation engine, CLI, and local review UI |
