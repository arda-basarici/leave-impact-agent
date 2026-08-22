# The local gate is the CI gate: `just check` runs exactly what .github/workflows/ci.yml
# runs, so a green local run predicts a green push. Recipes stay thin wrappers over
# `uv run …` — the tools own their configuration in pyproject.toml.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
# POSTGRES_PASSWORD and PGDATA_HOST come from the user's environment — no .env file
# in the tree (secrets live in env or the secret store, never in the project).

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

# Integration level alone, against the dev PostgreSQL (`just db-up` first).
[windows]
test-integration:
    $env:DATABASE_URL = "postgresql://leaveimpact:$env:POSTGRES_PASSWORD@localhost:5432/leaveimpact"; uv run pytest -q -m integration

[unix]
test-integration:
    DATABASE_URL="postgresql://leaveimpact:$POSTGRES_PASSWORD@localhost:5432/leaveimpact" uv run pytest -q -m integration

# The dev PostgreSQL on 127.0.0.1:5432 for the integration level. (CODE_VERSION
# is interpolated by every compose command, build or not — the placeholder
# satisfies the overlay's guard; nothing here builds the app image. Two forms
# because the shell differs per OS: PowerShell here, sh on the instance.)
[windows]
db-up:
    $env:CODE_VERSION = "not-a-build"; docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres

[unix]
db-up:
    CODE_VERSION=not-a-build docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres

[windows]
db-down:
    $env:CODE_VERSION = "not-a-build"; docker compose -f compose.yaml -f compose.dev.yaml down

[unix]
db-down:
    CODE_VERSION=not-a-build docker compose -f compose.yaml -f compose.dev.yaml down

# Coverage as a number to read, never a gate (DESIGN: "Verification").
coverage:
    uv run pytest -q --cov=leaveimpact --cov-report=term-missing

# The API reference is generated from docstrings; an import error breaks this.
docs:
    uv run python scripts/regen_docs.py

# One-time per clone: installs the pre-commit hooks (secret scan + lint).
hooks:
    uv run pre-commit install
