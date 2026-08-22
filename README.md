# Leave Impact Agent

Agentic leave-impact and coverage planning across organizational tools.

An AI agent that investigates what an employee's leave actually means operationally —
reading the HRMS, issue tracker, calendar, and chat — and drafts an evidence-backed
coverage plan for a human to approve. Deterministic rules handle the normal path; the
agent investigates the exceptions; the human decides.

[![CI](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml)

**Status: engineering baseline, no application code yet.** The vision is fixed
(VISION.md); DESIGN.md carries the rulings as they land — hosting and verification
so far. What exists is the floor the application will be built on: a typed, linted,
tested Python package (empty by design), CI with a real PostgreSQL service, a
multi-arch container published to GHCR on every green push to `main`, and the
Compose stack the instance will run. The probe days (`probes/README.md`) come next.
This README grows with the build and never claims ahead of it.

## Run the baseline

Needs `uv`, `just`, and Docker.

```
uv sync                 # locked environment, dev tools included
just hooks              # once per clone: pre-commit (secret scan + lint)
just check              # what CI runs: lint, types, unit tests + doctests, docs build
cp .env.example .env    # then set POSTGRES_PASSWORD and PGDATA_HOST
just db-up              # dev PostgreSQL on 127.0.0.1:5432
just test-integration   # the integration level against it
just db-down
```

`just --list` shows the rest (`coverage`, `test-all`, `docs`).

## Layout

- `src/leaveimpact/` — the package; `tests/{unit,integration,e2e}/` — the test levels
  (DESIGN, "Verification"); `probes/` — preregistered unknowns and their findings;
  `scripts/regen_docs.py` — the API reference, generated from docstrings, never edited.
- `Dockerfile`, `compose.yaml` — the deploy unit and the instance's stack;
  `compose.dev.yaml` — the laptop overlay.

## License

MIT — see LICENSE. Single-author portfolio project; issues welcome.
