---
applyTo: "**"
---

# Commands

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
