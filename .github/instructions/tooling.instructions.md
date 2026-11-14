---
applyTo: "**"
---

# Tooling

- **Package manager**: `uv`. All commands must be run via `uv run`.
- **Python version**: >= 3.12 (see `pyproject.toml`).
- **Build backend**: Hatchling.
- **Linter/formatter**: `ruff`.
- **Testing**: `pytest` with `pytest-order` (tests are stateful and must run in order).
