# Contributing to whereabouts

Thanks for your interest in contributing! Contributions are welcome from people working with geospatial data in and outside Australia.

## Development setup

Clone the repo and install dependencies (including dev tools):

    git clone https://github.com/ajl2718/whereabouts.git
    cd whereabouts
    uv sync

Install the pre-commit hooks so formatting and linting run automatically:

    uvx pre-commit install

## Before you open a pull request

Run the same checks CI runs:

    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

All three must pass. New features should come with tests.

## Submitting changes

Open a pull request against `main` with a clear description of what
changed and why. Keep commits focused — one logical change per commit,
with a descriptive message.

## Code style

Formatting and linting are handled by Ruff (configured in pyproject.toml),
so you don't need to format by hand — just run the commands above or let
pre-commit do it.
