# Leave Impact Agent

Agentic leave-impact and coverage planning across organizational tools.

An AI agent that investigates what an employee's leave actually means operationally —
reading the HRMS, issue tracker, calendar, and chat — and drafts an evidence-backed
coverage plan for a human to approve. Deterministic rules handle the normal path; the
agent investigates the exceptions; the human decides.

[![CI](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/arda-basarici/leave-impact-agent/actions/workflows/ci.yml)

**Status: three milestones are closed, the last on 2026-11-09. The demo is public at
`https://leave-agent.ardabasarici.dev`: thirty replays of the investigator on the golden
world with their reports, evidence, audit trails and narration timelines, the results
page for the measurement, and capped live runs a visitor starts and then approves or
declines. The one registered result is the investigator milestone's: on the measurement
world's thirty scenarios the investigator is correct in every part on 24 at both corpus
levels, against a full-context single call that is 30 of 30 at the base level and 14 of
30 at the padded level; the registered primary difference, at the padded level, is 0.20
to 0.47 at 95 percent (`probes/FINDINGS.md`, `phase-c`).** The three sections below say
what each milestone built and what it established. This README grows with the build and
never claims ahead of it.

> **What this is and is not.** A benchmark with ground truth by construction, and the
> agent graded on it. The organization is synthetic and small (about thirty people,
> thirty scenarios); the vendor systems are real. It is not a product, not a study of
> any real workforce, and its one claim about an agent's accuracy is the registered
> primary comparison above: thirty scenarios of one synthetic organization, one run
> each, intervals wide at that size, every development run excluded from the tables by
> the preregistration. The golden world the demo serves is the world the investigator
> was developed against, so what the demo's pages and the demo section below say of it
> describes those runs and is no second claim.

## What the world milestone established

A generator builds a synthetic organization and thirty scenarios in three difficulty
tiers from a seed, materializes the prose those scenarios need through gated model
calls, projects the world into real Frappe HR, Jira and Google Calendar instances, and
seals the answer key where the application cannot reach it. An independent validator
re-reads the live systems and approves a world only when every enumeration is exact and
every record equals its planting. A hand-audit protocol, under which the first golden
world was read scenario by scenario, sealed its audit beside the world. Closed on
2026-09-19.

- The golden plan (thirty scenarios, three tiers, eleven classes) constructed on 199 of
  200 seeds against the default organization under the construction order the first
  golden world was built with, scarcest class first. Under the random order the
  generator has used since, which keeps a scenario's identifiers from following its
  tier, it constructs on 196 of the same 200 (`probes/FINDINGS.md`, `reservation-book`,
  runs 3 and 4). Every refusal is loud and named. That is feasibility evidence, not a
  proof of collision freedom: whole-world verification stays the oracle.
- The first golden world passed a hand audit of every scenario and seventeen deep
  traces with thirty accepts and no defect in the world. The audit verifies the key
  against the rules as coded and a human reading of the evidence, sharing the rules'
  dated view; thirteen scenarios rest on the pass and a recount rather than a trace.
- Model-written prose enters the world only under semantic containment (a lexical
  guard, an extraction check by a second model family, a human read of every
  answer-changing text); the stage costs well under a dollar per world, and its
  accepted texts converge on one sentence frame, a realism limitation on record.

## What the investigator milestone established

The evaluator takes a recorded run and the sealed answer key and grades the run claim
by claim, checks its plan, replays its conclusions from what the run itself read, and
computes the tables a committed preregistration names; it runs under its own identity
and never re-reads a vendor. The investigator is measured against three baselines:
the deterministic rules over structured reads with no model, built and graded end to
end on a throwaway world, and a single-shot and a full-context call over the
investigator's own harness.

The investigator runs on LangGraph over an event log that is the authority for
recovery, audit and the run export: a frozen prefetch of the structured records,
reading turns through tools generated from the read ports by a role-scoped registry
(MCP was weighed and not chosen because one in-process consumer of a small owned read
surface gains nothing from a protocol, and it returns with an external client that
needs one), and one forced finalization in which the model states facts with the words
it read them from, the rules composing every claim; full-text retrieval over sections
is the core, and the vector arm, declared as a supporting comparison, was decided not
built at the freeze and is exploratory on the measured world after it.

The loop ran live on the first development world under a draft registration, 105 runs
across fifteen prompt rounds, every one closing through a valid forced fact call, the
prompt revised against named failures and recorded with its digests; those runs are
development runs, graded for the plumbing and not reported as a result. The lifecycle
then ran under production: a workflow sends each step to the instance, the host runs
the deployed image against the live vendor systems and the real store, a human approves
in a private session when the policy asks for one, and the export is published where
the evaluator reads it; the investigator under both approval policies and the three
baselines each ran once on one scenario of a development world, every job green on its
first dispatch after four fixes the laptop's fakes could not have found, and one
evaluation graded all five. The procedure was then frozen before the measurement world
existed, that world drawn from a secret seed, validated and audited, the registration
bound to it, and the 240 registered runs dispatched one at a time through the deployed
lifecycle and graded in one reported evaluation. The measurement ran on 2026-10-16 and
17, and the milestone closed on the 17th.

- The primary comparison, registered before the measurement world existed: the
  investigator correct in every part on 24 of 30 scenarios at the padded corpus level
  against full context's 14, the difference 0.20 to 0.47 at 95 percent, ten scenarios
  the investigator alone passes and none the other way. The investigator is 24 of 30 at
  both levels; rules alone pass the structured ten and nothing else, so twenty scenarios
  are where any system can differ.
- Why the one-call reader loses: at the base level full context is 30 of 30 with every
  claim strictly correct, and at the padded level 24 of its 30 calls stop at the
  8,192-token output maximum with the fact batch malformed. The freeze ruled that output saturation is
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

## What the demo milestone established

The demo is a web surface on one small instance: the application (FastAPI, pages
rendered on the server), a worker service and PostgreSQL, three containers behind the
proxy. Every replay page is a read of what a run recorded. The report and the audit trail come
from the run's export, the evidence shown is what the run itself read and nothing is
fetched again for the page, and the narration is the run's event log replayed through
the transition the harness ran, as a timeline and as a stream of server-sent events. A
visitor's live run takes the same admission, the same work order and the same log as an
operator's dispatched one: the worker service runs one attempt at a time in a child
process it can terminate, and the plan waits for the visitor to approve or decline it.
Closed on 2026-11-09; the figures below are `probes/FINDINGS.md` entries, named beside
them.

- **The replays.** The registered investigator ran once on each of the golden world's
  thirty scenarios through the deployed lifecycle, for $2.0967 of model spend, and
  every run is public with its report, its evidence, its audit trail and its timeline.
  In the operator's offline grading 26 of the 30 are correct in every part (10, 7 and 9
  of ten in the structured, fragmented and adversarial tiers), and the four misses
  share one shape, a corpus clause's requirement left unstated, which is the mechanism
  the measurement found on its own world (`replay-set`).
- **What a public reader can reach.** Before the hostname served the application the
  tree was swept for anything of the embargoed measurement world and the golden world
  was released whole under `docs/golden-world/`, answer keys included. Once it served,
  a crawl of the 124 public pages through the hostname held in every form a reader
  receives them: the raw bodies, the HTML-decoded text and the JSON-decoded stream
  frames (`disclosure-sweep`, `golden-release`, `public-switch`). The milestone's exit was written as the URL used
  unassisted by a stranger. That test was skipped by a ruling on 2026-10-25, and the
  exit on record is the URL with the crawl held.
- **Backup and restore.** The database is dumped nightly by the platform's unit. The
  first dump was restored into a scratch database and the application's own
  `verify-restore` passed seven checks of seven over it, 214 closed attempts recharged
  (`backup-restore-drill`). A recovery loses up to a day, and the instance runbook says
  what is reconciled from the bill afterwards.
- **Live runs, capped.** A start is admitted against a ledger whose wall the operator
  sets by hand ($8 for the first public month), five runs a day and two an address, one
  attempt on the host at a time; a plan nobody decides within fifteen minutes is closed
  by the worker's sweeper, and a decline is an ending of its own in the log. The ledger
  page shows every charge, and an operator flag (`live_runs` in the demo configuration)
  stops new admissions and nothing else. The path was accepted on production on 2026-11-01 and again
  on 2026-11-09 with Cloudflare Access in front of the Frappe hostnames, and live runs
  have stayed on since: six runs settled on the visitors' ledger for $0.4088 in all;
  eight held streams on an open attempt cost the application 0.131 s of CPU a second
  above idle against a budget of 0.2; the worker peaked at 292.4 MiB under its 448 MiB
  limit (`live-acceptance`, `final-smoke`).
- **One criterion not met as written.** The final smoke asked that an open attempt's
  frames reach a subscriber within 2 s of their recorded instants at the 95th
  percentile. It read 2.00 and 2.09 s, on a measure that carries the offset between two
  clocks, bounded there only to 1.3 to 1.5 s, so it cannot resolve a two-second line.
  The intervals between the frames' arrivals, the measure the first acceptance's bound
  was held on, kept the recorded ones at 0.55 and 0.60 s. It stays recorded as not met.

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
models and `probe access` the check that a runner passes the Access application in
front of the Frappe hostnames. The application's
own role reads projected worlds and has no capability over the truth, which a boundary
probe proves on every deploy.

An operator's run is dispatched too: `investigate` sends a run to the instance one
lifecycle step at a time under the reviewer-gated `production` environment, and
`continue run` delivers a reviewer's approval to a waiting attempt or picks up one whose
job ended early. The 240 measured runs and the thirty
replays were made that way. A visitor's run on the demo needs no workflow.

## Layout

- `src/leaveimpact/` — the package, eleven subpackages by rank: `core` (the domain and
  its pure rules) · `world` (the benchmark: the organization, the scenarios, the truth,
  the sealed artifacts) · `results` (the public results schema) · `adapters` (one
  external boundary each: Frappe HR, Jira, Google Calendar, the document corpus, the
  prose models, the object store) · `generator`, `validator` and `evaluator` (the
  shells that build a world, check its projection and grade a run) · `cache` (the
  corpus cache job on the instance) · `agent` (the investigator, the three baselines it
  is measured against and the run log) · `launch` (admissions for an operator's run) ·
  `app` (the demo surface and its worker). ARCHITECTURE.md has the layout and the
  import rules; `tests/unit/test_import_law.py` holds the import rules listed there as
  tests, and the same document names what is held in review and the two separations
  that rest on the packages' contracts alone.
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
  `compose.dev.yaml` — the laptop overlay; `deploy/instance/` — the deployment
  entrypoint the CI deploy job runs on the host, the boundary probe that follows it, the
  run lifecycle's host side, and the runbook (its README); `deploy/runner/` — the driver
  the run workflows use; `deploy/frappe/` — the Frappe HR stack on the box. The host
  itself (Terraform, the deploy role, the parameter names, the proxy, the backup units)
  is owned by the `platform` repository, stack `leave-impact-prod`.
- `.github/workflows/` — `ci` (check, the slow sweeps, the crash matrix, image, deploy
  behind an approval), the three benchmark workflows (generate world, validate world,
  evaluate run), the two run workflows (investigate, continue run), the two probes
  (bedrock, access), the custom Frappe image build and the base-image mirror.

## Reading order

DESIGN.md holds the decisions and their reasoning, organized for the reader who has to
trust the ground truth: what a valid answer is, how the world and its prose are
constructed, the classes that leave the easy path, sealing and the audit, the boundaries
that keep the benchmark out of the product, and the deployment; ARCHITECTURE.md the
package shape as the tree stands, the life of a world and of a run, and the import law;
AUDIT_METHODOLOGY.md what "golden" means here; `probes/FINDINGS.md` every probe's and
every acceptance's outcome; `deploy/instance/README.md` how the host is deployed to and
operated; REPORT_NOTES.md the decision narratives, newest first; VISION.md the founding
snapshot, frozen.

## License

MIT — see LICENSE. Single-author portfolio project; issues welcome.
