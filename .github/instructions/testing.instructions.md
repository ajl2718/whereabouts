---
applyTo: "**"
---

# Testing conventions

- Tests in `tests/test_addressbuilder.py` are **stateful and order-dependent** (enforced by `pytest-order`). They build a test database, run geocoding queries, then clean up.
- `conftest.py` removes stale test databases (`db_test.db`, `db_test_poland.db`) before the session starts.
- Run the full test suite with `uv run pytest` after any code change that modifies behaviour.
- Do not reorder or isolate tests that depend on prior test state.
