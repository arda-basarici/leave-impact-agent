# The local gate is the CI gate: `just check` runs exactly what .github/workflows/ci.yml
# runs, so a green local run predicts a green push. Recipes stay thin wrappers over
# `uv run …` — the tools own their configuration in pyproject.toml.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

default: check

# Everything CI runs on a push: lint, types, tests (default levels), docs build.
check: lint typecheck test docs

lint:
    uv run ruff check

typecheck:
    uv run pyright

# Default levels only — `live` and `e2e` stay excluded (pyproject addopts).
test:
    uv run pytest -q

# Every level, including the ones that need a deployment or spend quota.
test-all:
    uv run pytest -q -m ""

# Integration level alone — needs the PostgreSQL service (`just db-up`).
test-integration:
    uv run pytest -q -m integration

# The API reference is generated from docstrings; a broken docstring breaks this.
docs:
    uv run python scripts/regen_docs.py

# One-time per clone: installs the pre-commit hooks (secret scan + lint).
hooks:
    uv run pre-commit install
