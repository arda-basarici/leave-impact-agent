# Leave Impact Agent

Agentic leave-impact and coverage planning across organizational tools.

An AI agent that investigates what an employee's leave actually means operationally —
reading the HRMS, issue tracker, calendar, and chat — and drafts an evidence-backed
coverage plan for a human to approve. Deterministic rules handle the normal path; the
agent investigates the exceptions; the human decides.

[![CI](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml)

**Status: the world milestone closed on 2026-09-19; the investigator milestone opens
with its own design session.** What exists is the benchmark and the machinery that
makes it trustworthy. A generator builds a synthetic organization and thirty scenarios
in three difficulty tiers from a seed, materializes the prose those scenarios need
through gated model calls, projects the world into real Frappe HR, Jira and Google
Calendar instances, and seals the answer key where the application cannot reach it. An
independent validator re-reads the live systems and approves a world only when every
enumeration is exact and every record equals its planting. A hand-audit protocol, under
which the first golden world was read scenario by scenario, sealed its audit beside the
world. No agent exists yet: its harness, framework and evaluator are the next
milestone's design, made on this milestone's evidence. This README grows with the build
and never claims ahead of it.

> **What this is and is not.** A benchmark with ground truth by construction, and the
> agent that will be graded on it. The organization is synthetic and small (about
> thirty people, thirty scenarios); the vendor systems are real. It is not a product,
> not a study of any real workforce, and it makes no claim about an agent's accuracy
> yet, since no agent has run.

## What the world milestone established

- The golden plan (thirty scenarios, three tiers, eleven classes) constructs on 199 of
  200 seeds against the default organization; the one refusal is loud and named. That
  is feasibility evidence, not a proof of collision freedom: whole-world verification
  stays the oracle.
- The first golden world passed a hand audit of every scenario and seventeen deep
  traces with thirty accepts and no defect in the world. The audit verifies the key
  against the rules as coded and a human reading of the evidence, sharing the rules'
  dated view; thirteen scenarios rest on the pass and a recount rather than a trace.
- Model-written prose enters the world only under semantic containment (a lexical
  guard, an extraction check by a second model family, a human read of every
  answer-changing text); the stage costs well under a dollar per world, and its
  accepted texts converge on one sentence frame, a realism limitation on record.

## Run the baseline

Needs `uv`, `just`, and Docker.

```
uv sync                 # locked environment, dev tools included
just hooks              # once per clone: pre-commit (secret scan + lint)
just check              # the fast subset of CI: lint, types, unit tests + doctests, docs build
# set POSTGRES_PASSWORD (letters+digits) and PGDATA_HOST (absolute path) as user env vars — no .env
docker network create web   # once per machine: the proxy network the stack joins
just db-up              # dev PostgreSQL on 127.0.0.1:5432
just test-integration   # the integration level: recorded vendor cassettes + the real PostgreSQL
just db-down
```

`just --list` shows the rest (`coverage`, `test-all`, `test-live`, `test-record`,
`docs`). The integration level replays recorded HTTP cassettes of the three vendor
sandboxes, so it needs no credentials; re-recording them does, and the `live` level
reaches the two prose models for real.

## The benchmark workflows

A world is never generated from a workstation or from the application's host. `generate
world` and `validate world` are dispatched GitHub workflows under the reviewer-gated
`benchmark` environment, each assuming its own OIDC-trusted AWS role: the generator
writes the world and its truth, the validator reads the world and writes nothing but its
verdict. `probe bedrock` is the live check on the two prose models. The application's
own role reads projected worlds and has no capability over the truth, which a boundary
probe proves on every deploy.

## Layout

- `src/leaveimpact/` — the package: `core` (the domain and its pure rules) · `world`
  (the benchmark: the organization, the scenarios, the truth, the sealed artifacts) ·
  `adapters` (one external boundary each: Frappe HR, Jira, Google Calendar, the document
  corpus, the prose models, the object store) · `generator` and `validator` (the
  shells). The layout and its import law are in ARCHITECTURE.md and enforced by
  `tests/unit/test_import_law.py`.
- `tests/{unit,integration,live,e2e}/` — the test levels (DESIGN, "Verification"); the
  vendor cassettes live under `tests/integration/cassettes/`.
- `AUDIT_METHODOLOGY.md` — how a generated world becomes a golden set;
  `scripts/audit_sheet.py` renders the sheet the audit reads and `scripts/audit_index.py`
  verifies and seals the audit's index. The audit's output on a golden world holds its
  answer keys and stays in the truth bucket, never in this tree;
  `docs/examples/audit_sheet_throwaway.md` shows the sheet's shape, keys included, on a
  throwaway-seed world that is never sealed or scored.
- `probes/` — the preregistered unknowns of the probe days and their findings;
  `scripts/regen_docs.py` — the API reference, generated from docstrings, never edited.
- `Dockerfile`, `compose.yaml` — the deploy unit and the instance's stack;
  `compose.dev.yaml` — the laptop overlay; `deploy/` — the deployment entrypoint the
  CI deploy job runs on the host. The host itself (Terraform, the deploy role, the
  parameter names) is owned by the `platform` repository, stack `leave-impact-prod`.
- `.github/workflows/` — `ci` (check, image, deploy behind an approval), the two
  benchmark workflows, the prose probe, and the custom Frappe image build.

## Reading order

DESIGN.md holds the decisions and their reasoning, organized for the reader who has to
trust the ground truth: what a valid answer is, how the world and its prose are
constructed, the classes that leave the easy path, sealing and the audit, the boundaries
that keep the benchmark out of the product, and the deployment; ARCHITECTURE.md the
package shape and the import law; AUDIT_METHODOLOGY.md what "golden" means here;
`probes/FINDINGS.md` what the probe days established; REPORT_NOTES.md the decision
narratives, newest first; VISION.md the founding snapshot, frozen.

## License

MIT — see LICENSE. Single-author portfolio project; issues welcome.
