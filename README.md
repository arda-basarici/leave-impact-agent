# Leave Impact Agent

Agentic leave-impact and coverage planning across organizational tools.

An AI agent that investigates what an employee's leave actually means operationally —
reading the HRMS, issue tracker, calendar, and chat — and drafts an evidence-backed
coverage plan for a human to approve. Deterministic rules handle the normal path; the
agent investigates the exceptions; the human decides.

[![CI](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml)

**Status: the world milestone closed on 2026-09-19; the investigator milestone's
measurement ran on 2026-10-16 and 17 and its result is recorded: on the measurement
world's thirty scenarios the investigator is correct in every part on 24 at both corpus
levels, against a full-context single call that is 30 of 30 at the base level and 14 of
30 at the padded level, where 24 of its 30 calls stop at the 8,192-token output maximum;
the registered primary difference is 0.20 to 0.47 at 95 percent
(`probes/FINDINGS.md`, `phase-c`).** What exists is the benchmark, the
evaluator that grades a run against it, the rules-only baseline, the investigator's
harness with its system content, the single-shot and full-context baselines over the
same harness, and the launch path that runs any of them on the instance from a
dispatched workflow and publishes the export. A generator builds a synthetic
organization and thirty scenarios in three difficulty tiers from a seed, materializes
the prose those scenarios need through gated model calls, projects the world into real
Frappe HR, Jira and Google Calendar instances, and seals the answer key where the
application cannot reach it. An independent validator re-reads the live systems and
approves a world only when every enumeration is exact and every record equals its
planting. A hand-audit protocol, under which the first golden world was read scenario
by scenario, sealed its audit beside the world. The evaluator takes a recorded run and
the sealed answer key and grades the run claim by claim, checks its plan, replays its
conclusions from what the run itself read, and computes the tables a committed
preregistration names; it runs under its own identity and never re-reads a vendor. The
rules-only baseline, the deterministic rules over structured reads with no model, is
built and graded end to end on a throwaway world. The investigator runs on LangGraph
over an event log that is the authority for recovery, audit and the run export: a
frozen prefetch of the structured records, reading turns through tools generated from
the read ports by a role-scoped registry (MCP was weighed and not chosen because one
in-process consumer of a small owned read surface gains nothing from a protocol, and
it returns with an external client that needs one), and one forced finalization in
which the model states facts with the words it read them from, the rules composing
every claim; full-text retrieval over sections is the core, and the vector arm,
declared as a supporting comparison, was decided not built at the freeze and is
exploratory on the measured world after it. The loop ran live on the first
development world under a draft registration, 105 runs across fifteen prompt rounds,
every one closing through a valid forced fact call, the prompt revised against named
failures and recorded with its digests; those runs are development runs, graded for
the plumbing and not reported as a result. The lifecycle then ran under production:
a workflow sends each step to the instance, the host runs the deployed image against
the live vendor systems and the real store, a human approves in a private session when
the policy asks for one, and the export is published where the evaluator reads it; the
investigator under both approval policies and the three baselines each ran once on one
scenario of a development world, every job green on its first dispatch after four
fixes the laptop's fakes could not have found, and one evaluation graded all five. The
procedure was then frozen before the measurement world existed, that world drawn from
a secret seed, validated and audited, the registration bound to it, and the 240
registered runs dispatched one at a time through the deployed lifecycle and graded in
one reported evaluation. The demo milestone's replay surface is public at
`https://leave-agent.ardabasarici.dev`: thirty replays of the golden world with their
reports, self-contained evidence, audit trails and narration timelines, and the results
page for the measurement; live runs stay behind an operator flag, off. This README grows
with the build and never claims ahead of it.

> **What this is and is not.** A benchmark with ground truth by construction, and the
> agent that will be graded on it. The organization is synthetic and small (about thirty
> people, thirty scenarios); the vendor systems are real. It is not a product, not a
> study of any real workforce, and its one claim about an agent's accuracy is the
> registered primary comparison above: thirty scenarios of one synthetic organization,
> one run each, intervals wide at that size, every development run excluded from the
> tables by the preregistration.

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

## What the investigator milestone established

- The primary comparison, registered before the measurement world existed: the
  investigator correct in every part on 24 of 30 scenarios at the padded corpus level
  against full context's 14, the difference 0.20 to 0.47 at 95 percent, ten scenarios
  the investigator alone passes and none the other way. The investigator is 24 of 30 at
  both levels; rules alone pass the structured ten and nothing else, so twenty scenarios
  are where any system can differ.
- Why the one-call reader loses: at the base level full context is 30 of 30 with every
  claim strictly correct, and at the padded level 24 of its 30 calls stop at the output
  maximum with the fact batch malformed. The freeze ruled that output saturation is
  reported as a mechanism and never as evidence of an input limit, and the report keeps
  to that. The investigator's six misses are all fragmented-tier scenarios at both
  levels; its mechanism measure shows every needed carrier returned and the facts not
  stated.
- The measurement discipline: the procedure frozen at a commit before the world was
  drawn, the world from a secret seed, validated and hand-audited, the registration
  bound to it, every run through the deployed lifecycle, the evaluation under its own
  identity with the harness inventory it was held to. One repeat a scenario, so the
  intervals are over scenarios and say nothing of run-to-run variability; four outage
  cells and four supporting comparisons were decided not run at the freeze and are
  reported as such; the 240 runs cost $9.96 of model spend.

## Run the checks

Needs `uv`, `just`, and Docker. No command here runs a system against a world: the
rules-only baseline runs inside the unit tests on a throwaway world, and an evaluation
of stored runs is a dispatched workflow (below).

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
verdict. `evaluate run` proves a sealed world and grades its stored runs under a third
role, in its own reviewer-gated `evaluation` environment; it reads the answer key and
writes one evaluation artifact. `probe bedrock` is the live check on the two prose
models. The application's
own role reads projected worlds and has no capability over the truth, which a boundary
probe proves on every deploy.

## Layout

- `src/leaveimpact/` — the package: `core` (the domain and its pure rules) · `world`
  (the benchmark: the organization, the scenarios, the truth, the sealed artifacts) ·
  `adapters` (one external boundary each: Frappe HR, Jira, Google Calendar, the document
  corpus, the prose models, the object store) · `generator`, `validator` and
  `evaluator` (the shells that build a world, check its projection and grade a run) ·
  `agent` (the investigator and the three baselines it is measured against). The layout
  and its import law are in ARCHITECTURE.md and enforced by
  `tests/unit/test_import_law.py`.
- `preregistration/` — `registration.json`, what the investigator milestone measures and
  how the result is read, frozen on 2026-10-14 before the measurement world exists and
  bound to it once the world is accepted; `prices.json`, the price table every
  run is priced from, with its sources in `PRICES.md`; `PROTOCOL.md` explains the files.
- `tests/{unit,integration,live,e2e}/` — the test levels (DESIGN, "Verification"); the
  vendor cassettes live under `tests/integration/cassettes/`.
- `AUDIT_METHODOLOGY.md` — how a generated world becomes a golden set;
  `scripts/audit_sheet.py` renders the sheet the audit reads and `scripts/audit_index.py`
  verifies and seals the audit's index. The first golden world, the one the demo serves,
  is released whole under `docs/golden-world/` (its three sealed objects, answer keys
  included, with an index); the measurement world's stay in the truth bucket until the
  last measurement on it. `docs/examples/audit_sheet_throwaway.md` shows the sheet's
  shape on a throwaway-seed world, and `scripts/audit_sheet.py --released
  docs/golden-world` renders it for the released one.
- `probes/` — the preregistered unknowns of the probe days, the build's probes (each
  written before it ran), the phase C dispatcher with its committed plan and ledger and
  the two scripts behind the reported numbers, and `FINDINGS.md`, every outcome;
  `scripts/regen_docs.py` — the API reference, generated from docstrings, never edited.
- `report/` — the milestone report: committed Markdown chapters, the pins that read
  every figure a chapter states from the committed results, the registration or a
  recorded FINDINGS row, the figure scripts, and the build (`just report`); the
  rendered PDF is committed at the freeze and served from the portfolio site.
- `Dockerfile`, `compose.yaml` — the deploy unit and the instance's stack;
  `compose.dev.yaml` — the laptop overlay; `deploy/` — the deployment entrypoint the
  CI deploy job runs on the host. The host itself (Terraform, the deploy role, the
  parameter names) is owned by the `platform` repository, stack `leave-impact-prod`.
- `.github/workflows/` — `ci` (check, image, deploy behind an approval), the three
  benchmark workflows (generate world, validate world, evaluate run), the prose probe,
  and the custom Frappe image build.

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
