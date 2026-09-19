# `just check` is the fast local subset of the CI gate in .github/workflows/ci.yml: lint,
# types, the default test levels and the docs build. CI runs two gates beyond it that this
# file does not reproduce, the integration level against a PostgreSQL service (locally
# `just db-up` then `just test-integration`) and a Gitleaks scan over the full history, so
# a green `just check` predicts those two only as far as the change stays clear of them.
# Recipes stay thin wrappers over `uv run …` — the tools own their configuration in
# pyproject.toml.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
# POSTGRES_PASSWORD and PGDATA_HOST come from the user's environment — no .env file
# in the tree (secrets live in env or the secret store, never in the project).

default: check

# The fast subset of the CI gate: lint, types, tests (default levels), docs build.
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

# The live level alone: the two prose models reached for real. The ini's addopts are
# replaced, not extended, because the network block cannot admit an endpoint by name —
# the guard sees the resolved IP the socket connects to (found 2026-09-14) — and a level
# defined by reaching the network runs without the block. Needs AWS credentials in the
# shell (`$env:AWS_PROFILE`), skips itself without; the probe workflow is authoritative.
test-live:
    uv run pytest -q -o addopts="" --doctest-modules --strict-markers -m live

# Integration level alone, against the dev PostgreSQL (`just db-up` first).
# The loopback address, not `localhost`: the name resolves to IPv6 first, the
# container publishes on IPv4 only, and every connection would wait out the timeout.
[windows]
test-integration:
    $env:DATABASE_URL = "postgresql://leaveimpact:$env:POSTGRES_PASSWORD@127.0.0.1:5432/leaveimpact"; uv run pytest -q -m integration

[unix]
test-integration:
    DATABASE_URL="postgresql://leaveimpact:$POSTGRES_PASSWORD@127.0.0.1:5432/leaveimpact" uv run pytest -q -m integration

# Re-record the adapter cassettes against the real sandboxes (their sites and
# credentials come from the user's environment; tests/recording.py names the
# variables). The same integration tests, run under a record mode instead of replay;
# a green run rewrites the cassettes, and the cassette-safety unit test gates them.
test-record:
    uv run pytest -q -m integration --record-mode=rewrite

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
