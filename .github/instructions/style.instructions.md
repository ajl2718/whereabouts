---
applyTo: "**"
---

# Style

- Follow **PEP 8** for all Python code.
- Use `ruff` as the linter and formatter. Run `uv run ruff check whereabouts/` before committing.
- Use **snake_case** for functions, methods, variables, and module-level constants (except `UPPER_SNAKE_CASE` for true constants).
- Use **PascalCase** for class names (e.g. `Matcher`, `AddressLoader`, `MatcherPipeline`).
- Keep lines to a maximum of **120 characters**.
- Prefer f-strings over `str.format()` or `%` formatting.
- Use type hints for function signatures in new or modified code.
