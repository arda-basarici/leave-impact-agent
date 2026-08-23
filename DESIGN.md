# DESIGN — leave-impact-agent

What is being built and why — the decisions and their reasoning, as a narrative
snapshot of the current design. Edited in place; the journey lives in the session
log. Wins over VISION.md (the frozen founding snapshot) on disagreement. How it's
built → ARCHITECTURE (born with the scaffold); pitch → README.

*Design phase · last updated 2026-08-23.*

## Objective

An agent that investigates what an employee's leave means operationally — reading the
HRMS, issue tracker, calendar, and chat through their real APIs — and drafts an
evidence-backed coverage plan for a human to approve. Deterministic rules own the
normal path; the agent investigates exceptions; the human decides. The org is
generated into real systems by a generator that also emits the sealed answer key, so
every claim the agent makes can be graded against constructed truth. A valid answer
is a report whose facts trace to org data, whose plan satisfies the scenario's
planted constraints, and whose unknowns are stated rather than invented — measured
across the evaluation spine by difficulty tier, served from a deployment that exists
from the first milestone on.

---

## Hosting and the cloud line

The vision fixed *deployed from day one* and deferred the target. Two facts settled
the shape before any option was weighed: the existing netcup box (2 vCPU / 4 GB)
already hosts SteamLens and sits at ~0.65 GB used, measured idle and in-job; and
Frappe HR alone wants 8 GB. So the simulated org's HR system needs a bigger host
whatever else is decided, and the question becomes where the application itself
runs.

**The hybrid split.** The application runs on AWS; Frappe HR stays on the netcup
box. Frappe is a heavy, stateful, multi-process system used *as* a realistic HRIS —
nothing about hosting it on a hyperscaler adds to the product, while cheap persistent
compute for it already exists. The application is the engineering that matters, and
a cloud deployment with the same operating discipline as the box is itself a
deliverable of this project. The split also makes the boundary honest: the
application reaches Frappe as a remote system behind an **`HRProvider` adapter**
over an authenticated API, exactly as it would reach a customer's BambooHR or
Personio, rather than pretending a local container is an enterprise integration. A
side effect feeds the evaluation spine — *HRIS unavailable* becomes a real failure
mode the system must degrade through, not a mock-only one. Rejected: everything on
the box (no cloud deployment at all), the box plus peripheral AWS services (an app
that "uses S3 and Bedrock" is not a cloud deployment), and everything on AWS (paying
to host the simulation for no product reason).

**Hosts consume artifacts; they never manufacture them** (ruled 2026-08-23, when
Frappe HR turned out to need a custom image — no official one carries the `hrms`
app). The box's rule from SteamLens holds for every deployable in this project:
`source → CI build → registry → host`, the host references an immutable digest
and pulls. CI rebuilds an image only when its *inputs* change (`apps.json`, the
build recipe), never when deployment settings do — image definition and
deployment definition are different artifacts. Rejected: a one-time build on the
box (a special-case path for fifteen minutes' gain) and builds from the
workstation (a release step in an undocumented environment). What the rule buys
is the claim that the production machine is replaceable.

**The application host: one EC2 instance, one Compose stack.** A `t4g.small`
(2 vCPU / 2 GB, arm) runs the application and its PostgreSQL in Docker Compose, the
database on a gp3 EBS volume, Cloudflare in front as the only ingress (no load
balancer), inbound restricted to Cloudflare's ranges, administrative access through
SSM Session Manager with no public SSH port. It is the cheapest always-on shape that
keeps PostgreSQL local; the managed alternatives were priced and rejected — an
always-on Fargate service plus ALB plus RDS lands near 2.5× the cost for no
architectural benefit at one-process scale (RDS is a cost floor; the ALB is pure
overhead behind Cloudflare), and a serverless agent (Lambda / Step Functions) would
deform multi-minute narrated runs around a 15-minute ceiling. Self-managed
PostgreSQL carries its own obligation: a nightly backup shipped off-host (the
SteamLens pattern with `pg_dump` in place of the SQLite snapshot) and **one
demonstrated restore** as an exit criterion, since owning recovery is the price of
not paying for RDS.

**PostgreSQL as the application's truth.** The application store is PostgreSQL, not
SQLite: agent runs, run events, tool calls, evidence references, coverage plans,
manager decisions, evaluation runs, and scenario metadata form a genuinely relational
model, and the framework's checkpoints land in the same database so a run survives
its worker. Frappe keeps its own MariaDB — Frappe-on-PostgreSQL is the less-trodden
path and the vision's first-named risk is week-one infrastructure eating the
schedule. Ownership is clean: Frappe's MariaDB holds HR truth, PostgreSQL holds
application and orchestration truth, S3 holds immutable exported artifacts.
Rejected: PostgreSQL on the netcup box reached remotely, like Frappe — the
application store is chatty (a checkpoint per framework node, an event per narrated
line) where Frappe is coarse, so every run would pay hundreds of cross-provider
round trips; it would also put the production write path on a public link and
confound the HRIS-unavailable evaluation case with the app's own outage. It buys
~$6/mo and unlocks no better AWS shape — the ephemeral tier it would cheapen is the
one where a remote store hurts most. The box's headroom serves instead as an
off-host backup destination and, if useful, a development PostgreSQL.

**The job seam: runs write an event log, surfaces read it.** An investigation is a
job that appends narrated events and checkpoints to PostgreSQL; the UI streams by
reading that log, never by holding the worker's socket. The seam is justified on its
own — it is what makes runs resumable, auditable, and replayable — and it is also
what makes the worker's location a deployment detail: in-process on the instance
today, an ephemeral task later, with the database swapped by a connection string. No
generic compute abstraction is built on top of it; the seam is the event log and
nothing more.

**The executor trust boundary.** If post-approval execution survives its own design
fork (an open question below), the writes run in a **deterministic executor
Lambda** — not a second agent — with its own IAM role that is the sole principal
able to read the write credentials in Secrets Manager, and with no model-invocation
permission at all. The investigator's identity cannot retrieve those secrets; they
do not exist on its host. Input is the human-approved action manifest, output is the
exact approved writes plus an audit artifact. Two principals on one host would be
two configurations, not a boundary; a separate execution identity is what makes the
least-privilege claim provable rather than intended.

**The surrounding AWS set, and nothing more.** All of it under Terraform: IAM roles
and policies; GitHub Actions deploys through OIDC federation (temporary credentials,
trust policy pinned to repository and branch — no stored keys); Secrets Manager;
CloudWatch for logs and alarms; S3 for golden datasets, evaluation reports, shipped
audit trails, and precomputed demo replays; AWS Budgets with a cost alert; Bedrock as
**the sole model provider behind a model seam** — the Converse API gives one
request shape across model families, so the seam's question is *which model per
role* (investigator, extraction sub-tasks, grading), answered by the evaluation on
the golden set rather than fixed up front; the seam also checks a model's feature
support (tool use, structured output, caching) at startup so a mismatch fails loudly.
A direct Anthropic API path is deliberately not committed to — the seam admits it
later if a reason appears. Bedrock stays one supporting component rather than the
centrepiece. Not added until a
requirement names it: ECS services, EKS, RDS, DynamoDB, SQS, EventBridge, CloudFront,
ElastiCache, OpenSearch, a managed vector store. One bootstrap exception is
recorded deliberately: the Budgets alert was created by hand before any
infrastructure existed, so the guardrail predates the resources; it is imported
under Terraform once the infrastructure code exists.

**The netcup box: in-place upgrade to VPS Lite 3 G12s.** The provider's panel
confirms an in-place upgrade within the product generation — reboot-only, no setup
fee, the old tariff refunded pro rata, a new six-month term. Lite 3 (8 vCPU / 16 GB /
320 GB, €11.67/mo net, +€7.57 over the current tariff) over Lite 2 (4 vCPU / 8 GB,
+€2.55): 8 GB is Frappe's recommended footprint *alone*, the box's own design is one
VPS running every project, downgrades do not exist while each upgrade resets the
term — so headroom is bought once, at box level, rather than in a second upgrade
later. The upgrade is a probe-day step, not a design-time action: it happens the day
Frappe goes up, with `free -m` captured before and after, so Frappe's footprint
becomes a measured number. Box rules that arrive with the new tenant: Compose memory
limits on the Frappe stack and a swapfile, so the heaviest tenant cannot starve
SteamLens. Rejected: a second box (two proxies, two firewalls, two backup paths for
no benefit once the in-place upgrade proved reboot-only).

**Cost envelopes, stated and tracked.** Persistent, excluding model tokens: the box
delta (+€7.57) plus roughly $21 on AWS (instance ~$12, EBS ~$3, public IPv4 ~$3.65,
Secrets Manager, S3, CloudWatch, Budgets ~$2–3; the Lambda executor inside the
permanent free tier) — list-price estimates pending a pricing-calculator pass; the
account holds no free-tier allowance, so these are the real rates. Model tokens are
the larger line: an agentic loop re-sends a growing context every turn, so a single
investigation is estimated at ~$0.75 on Sonnet-class pricing *with prompt caching*
(~3× more without), and an evaluation pass scales with scenario count. The budget is
preregistered in three numbers — **expected $150 for the investigator milestone,
hard ceiling $300, mandatory reforecast after the first ten representative runs** —
and the levers are design-level: a tiered scenario subset for iteration with the full
set only for reported numbers; the deterministic core pre-fetching structured facts
so the agent starts with evidence instead of discovering it turn by turn; a cheaper
model for sub-tasks such as extraction over chat text; the Batch API for any
non-interactive step. Per-run cost is a hypothesis until measured.

**The ephemeral-compute probe, preregistered for the demo milestone's entry.** The
strongest cloud shape for this workload is ephemeral: a Fargate task per
investigation, Aurora Serverless v2 PostgreSQL scaling to zero between runs, an API
Gateway + Lambda control plane, narration relayed from the event log. Its idle cost
would undercut the instance, and bursty agentic work is what that shape exists for.
It is not the starting point because it is a different application topology —
control plane, worker, and streaming relay — with VPC networking, a cold start of
roughly 45–75 s (task provisioning plus image pull plus database resume), and a
week of plumbing that would come out of evaluation depth. The job seam makes it a
migration rather than a rewrite, so it is earned by measurement at the demo
milestone's entry, criteria fixed now: control-plane acknowledgement ≤ 2 s *with the
wait narrated in the UI*; p95 cold-to-first-substantive-narration ≤ 45 s; migration
≤ 2 days; idle AWS baseline ≤ $5/mo; no NAT Gateway (tasks in a public subnet with
public IPs). Pass → the demo ships on it; fail → the instance stays and the measured
numbers are the tombstone. Either outcome is a complete story.

### The hosting-options matrix

The options weighed, in the order the reasoning produced them. Costs are monthly
and persistent, excluding model tokens; "box Δ" is the netcup upgrade delta.

| | **All on netcup** | **Netcup + AWS components** | **All on AWS** | **Hybrid, EC2 monolith** | **Fargate service + ALB + RDS** | **Ephemeral Fargate + Aurora** | **Serverless agent** |
|---|---|---|---|---|---|---|---|
| **Frappe** | box | box | EC2, 8 GB class | box, remote HRIS via adapter | box | box | box |
| **App compute** | box | box | EC2 | EC2 `t4g.small`, Compose | Fargate service, always-on | Fargate RunTask per job + API GW/Lambda control plane | Lambda / Step Functions |
| **PostgreSQL** | box container | box container | EC2 container | EC2 container on EBS | RDS `db.t4g.micro` | Aurora Serverless v2, scale-to-zero | RDS or Aurora |
| **Ingress** | Caddy / Cloudflare | Caddy / Cloudflare | Cloudflare | Cloudflare → instance, no ALB | ALB | static UI + API GW WebSocket relay | API GW |
| **Persistent cost / mo** | box Δ | box Δ + ~$3 | ~$60–80, box idle | box Δ + ~$21 | box Δ + ~$45–50 | box Δ + ~$5–10 | box Δ + ~$3–5 |
| **Cold start to first narration** | seconds | seconds | seconds | seconds | seconds | ~45–75 s | per step; streaming awkward |
| **A cloud deployment with the box's discipline** | no | weakly | yes, wastefully | yes | yes | yes, strongest | nominally |
| **Effort** | lowest | low | medium | medium | medium-high | highest (three-part app + VPC) | high, deforms the product |
| **Main risk** | no cloud evidence | reads as peripheral | paying to host a simulation | "a VPS with a logo" — answered by the surrounding discipline | cost floor, no benefit | week-one infrastructure; demo UX | 15-min ceiling vs multi-minute runs |
| **Standing** | rejected | rejected | rejected | **baseline** | rejected | **preregistered probe** | rejected |

Invariant across every surviving column: Frappe on the box behind the `HRProvider`
adapter · the executor as its own execution identity · the PostgreSQL event log and
checkpoints as the job seam · Bedrock as the sole provider behind the model seam ·
S3 for artifacts · the Budgets alert from day one.

---

## The probe days

The vision's first milestone is two to three days that kill the fatal unknowns
before anything is designed on them; the hosting ruling adds the deploy-from-day-one
floor to the same days. **Probes precede the remaining design.** The framework,
tool-layer, and post-approval questions are decided at a session held after the
probe days, on their evidence — not before. Each probe's pass criterion is fixed
before it runs and recorded with the plan in `probes/README.md`; outcomes land in
`probes/FINDINGS.md` with captures beside them, and later rulings cite those
findings by name. The milestone exits when the five unknowns (Frappe standing at
its real footprint, Frappe REST including the `leave_approver` wart, Jira, Google
Calendar, the generator seed spike) and the two floors (the instance via Terraform,
the OIDC deploy) pass; the Bedrock model shortlist and Slack may trail into the
world milestone without blocking it. Honest timebox: three to five days — the
vision's estimate plus roughly a day for the AWS floor, then the usual 1.5–2× on
first estimates.

---

## The world's shape

Rulings made before the Jira and seed probes, because the probes test a model
rather than bare CRUD. Each is a short decision with its reasoning; the generator
implements them at the world milestone.

**One generated organization, read-shared, write-isolated, truth-isolated.** The
org is a single synthetic company of roughly 25–30 people in about five teams,
both generator parameters (`ORG_SIZE`, `TEAM_COUNT`) rather than fixed numbers.
The agent sees the whole org: other teams' people, tickets, meetings and policies
are the plausible-wrong candidates that make coverage a real search, which a
six-person sandbox cannot produce. Scenarios are slices of that org, not orgs of
their own: each owns its mutable entities (the leave, its tickets, its events) and
a time window, never writes into another scenario's entities, and carries its own
sealed answer key, which the validator re-derives against the full live org so
cross-scenario contamination is caught rather than assumed away. Every
scenario-owned entity carries the scenario id in each system (Jira label, calendar
`extendedProperties`, a Frappe custom field), so a slice is enumerable and can
later be reset if anything ever writes to the world; the reset itself is not built
until something does. Org-per-scenario was rejected: it simplifies ground truth by
removing exactly the irrelevant-but-plausible evidence the evaluation exists to
test, and multiplies the seed and validation runs for no gain.

People are cheap and scenarios are expensive: a person is a handful of generated
records per system, a scenario is planted facts, named distractors, a relevant
policy clause, a defensible key and a hand audit. The golden set therefore grows by
adding scenarios in new time windows, not by adding employees. Three constraints
keep the construction honest: a team does not determine its scenario's type (the
generator assigns type independently, the manifest records both, so structure
cannot stand in for reasoning); distractors are planted and named in the key with
the reason each is wrong, so a near-miss is gradable and background filler stays
bounded rather than "hundreds of tickets"; and policy clauses have real-world scope
only (contractors, a country, a grade), with scenarios chosen so a clause becomes
relevant, never clauses written to make one scenario's answer come out.

**Synthetic employees are domain entities, not Atlassian users** — the Calendar
ruling applied to Jira. Work ownership lives in a dedicated single-select custom
field keyed by stable employee id (`emp_017 — Alice Demir`); `assignee` stays
unassigned so the board never claims the service account is responsible for the
work. Issues, workflows, sprints, components, comments, changelog and JQL remain
real Jira behaviour. Actor identity is outside the first truth model: every write
comes from one service account, so changelog and comment authors carry no world
fact, and the same holds for Calendar's organizer. Rejected: real accounts (Free
caps at 10 users, the developer instance at 5 and for app development only); a
hybrid of real and synthetic people (two identity paths in every tool and grader,
and licensing shaping which people a scenario may involve); Jira Service
Management customer accounts (free and unlimited, but their appearance in user
pickers is a documented gap Atlassian is asked to close). The Jira probe tests
this model: a select field and its options created over REST on Free, exact JQL on
it, comments naming synthetic people.

**Three layers, and adapters that translate but never launder.** The synthetic
world (an employee id, a team, skills, a manager) exists independently of any
vendor; each external system holds a representation of it (a Jira field option, a
secondary calendar id, a Frappe Employee record); the agent sees a domain-shaped
tool surface (`search_work_items(employee_id=…)`, `get_free_busy(…)`,
`get_employee(…)`, `search_policy(…)`) and never a vendor's identity system or
query syntax. The adapters own credentials, HTTP, pagination, retries and the
identity mapping — the world manifest is adapter configuration, not agent
context — and they stay thin: shape and identity are translated, every world fact
passes through as the system reports it, contradictions included. A planted
inconsistency (the HRMS says Berlin, the calendar says Istanbul; Jira says In
Progress, the last comment says blocked) is the agent's to reconcile, and an
adapter that normalized it away would destroy the evidence the evaluation grades.
Tools are domain-facing rather than vendor-facing because the question is whether
an agent can gather evidence across organizational systems, not whether it knows
JQL; tools answer questions about the world and make no decisions (no
`get_best_substitute`, no workload judgement). Real-API behaviour — a 403, a rate
limit, a stale read — surfaces as a tool failure, which is itself an evaluated
condition. Swapping a vendor (Outlook for Google Calendar) touches one adapter.

**Time is world state, never the machine's clock.** Every run receives a
`RunContext` — scenario id, world (seed) version, a canonical `now` as an instant
with a reference timezone, and that's the reproducibility boundary: same
scenario, same world version, same `now` → same evidence, on any machine, months
later. `now` is injected into the deterministic core, the agent's context and the
tools; no core, adapter or evaluator code reads the wall clock for world
semantics, and a test enforces it. Telling the agent "today is 2026-10-01" is not
cheating — a deployed assistant knows the date too; only its source is fixed.
Seeded data carries absolute world dates; human dates are interpreted in the
employee's or organization's timezone (the calendar probe's own "13:00 UTC on an
Istanbul calendar" slip is why the instant carries a zone). Three clocks exist and
only the first is truth: world time (`now`, leave and event dates, deadlines,
policy-effective dates); vendor operational time (when Jira physically stored the
issue, API timestamps); run time (when the evaluation executed). The tool surface
exposes exactly the fields the generator controls, which settles vendor
timestamps without per-field judgement: Jira's `created` is absent from
`search_work_items` today because the seed cannot set it, and becomes a world
fact the moment it can. Tools take explicit date ranges the agent reasons to;
defaults derived from `now` exist for convenience but the harness handles time
mechanics and never decides which period is relevant — that relevance is part of
what is evaluated. A scenario carries two time fields: its reference `now`, and
its evidence `window` (the span of world state it owns, reaching before and after
`now`); scenarios take disjoint windows, roughly one per month, which is the
cheapest write-isolation mechanism and gives the shared calendars a believable
spread — a rule that may relax once entity ownership is proven. Temporal
robustness is a metamorphic check over a declared `stable_now_interval`, not a
universal "advance three days, same answer": within the interval the key must
hold for any `now`; outside it a scenario may legitimately flip (a notice-period
clause), and such flips are a temporal-reasoning test of their own. The seed
spike's criterion gains this check. No attempt is made to alter the vendors'
clocks.

**Benchmark state is split by audience and authority, and "sealed" is enforced,
not promised.** Three artifacts: the *world manifest* — adapter configuration and
cross-system identity routing (`emp_017` → Jira option id, calendar id, Frappe
record; document locations; org parameters; world version), read by the
adapters and holding no fact that can change a scenario's answer — the test is
that deleting it after the vendor ids are resolved loses nothing answer-relevant;
the *scenario spec* — what the run is asked: scenario id, `now`, the owned
window, the request under investigation, visible to harness and agent; and the
*truth manifest* — evaluator-only: planted impacts, named distractors with the
reason each is wrong, the relevant clauses, required plan constraints, the
stable-now interval, scoring facts. Distractors carry their reasons so grading
can separate final-answer correctness, evidence correctness, constraint coverage
and distractor rejection, and so a failure reads as a sentence ("found the skill
match, never retrieved the release meeting") rather than a zero. World and truth
live in separate S3 buckets; the application's IAM role can read world and
scenario artifacts and has no read capability over truth; the evaluator runs
under its own role; a CI test assumes the application role, attempts a read on
the truth bucket and passes only on `AccessDenied` — that public test and its log
are the evidence a reader can check, since the policy itself cannot be verified
from outside. The generator knows both halves, so it is never part of the
deployed runtime: it runs as a separate job under a generator role obtained
through STS assume-role (an EC2 instance profile is one role, so "the generator
runs from the instance" means a short-lived role the application process never
holds), writes its artifacts and terminates. Integrity is the guarantee
underneath secrecy: the truth artifact is serialized once, hashed as exact bytes,
versioned in S3, and every world records its truth digest; every evaluation run
records world version, scenario id, seed, truth digest and S3 version id, harness
commit and model, recorded before grading — so a result months later is the same
question about the same world against the same key. Hand auditing produces a
separately versioned provenance artifact; held-out truth and its audit notes stay
in the truth bucket, never in the public repository; the repository publishes the
audit methodology and fully released example scenarios, and a retired evaluation
set can be published whole.

**History is planted only where it can be planted honestly; qualification is
derived from atomic facts, never stored as a conclusion.** Jira's REST API cannot
set `created`, `updated` or `resolutiondate` (the request has been open since
2014), so "Bob resolved twelve payments tickets last year" is not a plantable
world fact over REST. Coverage qualification is therefore expressed as atomic,
world-observable facts spread across the systems — an employee's skills on the
Frappe record, a Jira component with its named synthetic members, a policy
clause stating what coverage requires ("component experience and the required
skill"), the calendar's free/busy, the active tickets a person owns — and the
agent derives "Bob is a valid candidate" from them; no system stores that
conclusion, which is the same rule that keeps decisions out of tools. Comments
are plantable and their content is a world fact ("[2026-09-12, Bob Kaya] blocked
on the vendor API"), while the comment's own timestamp is vendor operational
time. Frappe leave records and calendar events take the dates the seed sets, so
past leave and past meetings are real history where history is needed. The Jira
probe (2026-08-23) found the CSV importer backdates `created` but not
`resolutiondate`, is UI-only and targets team-managed projects — and that the
question was mis-posed: ticket dates are world facts like ownership, so they live
in generator-controlled custom date fields (`Opened On`, `Resolved On`) set over
REST, exposed by the adapter as `opened_on` / `resolved_on`, while Jira's own
timestamps stay hidden as vendor time. Date-level history ("opened in March,
resolved in May") is therefore plantable without a manual step; actor-level
history ("who handled this before") remains outside the first truth model.

---

## Verification: five automated questions, and the eval kept apart

**The test suite answers five distinct questions; each level owns one.** SteamLens's
suite was unit-dominant with an unlabeled integration layer and nothing end-to-end;
this project names the levels and gives each a home, because it has two things
SteamLens did not — real external systems and a real PostgreSQL.

| Level | Question | What runs | When |
|---|---|---|---|
| unit | is the pure core right? | rules, constraint checks, evaluator arithmetic, parsers — doctests + pytest, no I/O | every push, default |
| integration | do the seams hold against real dependencies? | the event-log/checkpoint store against a real PostgreSQL service (never a SQLite stand-in — the store is evaluated on the terms it runs on); tool adapters against recorded HTTP cassettes of Frappe / Jira / Calendar | every push, `-m integration` |
| live contract | has an external API drifted from the cassettes? | the same adapter tests replayed against the real sandboxes; a pass re-records | gated by env, nightly or on demand |
| agent smoke | does the loop's plumbing work end to end without model spend? | one scenario through the real loop with a scripted fake model (a fixed tool-call trace), cassettes, PostgreSQL; asserts the event log and the plan's shape | every push |
| e2e | does the deployed thing work? | after deploy, through the public hostname: health, a replayed scenario, the audit trail rendering | the deploy job, post-approval |

Mechanics: `tests/unit|integration|e2e/` with matching markers; the default run is
the unit level; agent-smoke tests carry the `integration` marker (spend-free, but
they write the real event log); `integration`, `live`, and `e2e` are selected
deliberately; a `justfile` makes the local gate the CI gate by one command.
Cassettes are the honest fake — real payload shapes — and the gated live replay is
what keeps them from drifting silently; hand-written fakes were rejected because
they drift without a signal. Coverage is measured, never gated: the number shows
where the unit layer is thin, a threshold only invites theater. PostgreSQL runs as a
CI service from the first commit, before any code needs it, so the pattern exists
when the code arrives.

**The eval is not a test.** The golden-set harness with real models is the project's
end-to-end evidence, and it is an experiment: preregistered design, a budget,
baselines, uncertainty reported, its output a finding rather than a green check.
It lives in its own section and its own tooling (harness, run manifests, results
persisted to S3), and the suite's only contact with it is the agent-smoke level —
plumbing verified with a fake model so an eval run never fails for a non-eval
reason. Listing the eval beside pytest markers would blur exactly the distinction
the project exists to demonstrate.

**Structural laws are tests.** The core/shell import law and whatever the second
design session rules about module rank ship as pytest tests with the scaffold (the
SteamLens `test_import_graph` precedent) — deferred to that session, not past it.

**The baseline inherits SteamLens where it proved out and improves where it was
thin.** Inherited: `uv_build` backend, src layout, PEP 735 dev group, locked sync in
CI, ruff lint at 100 columns, pyright strict over `src` and `tests`, doctests via
`--doctest-modules`, the two-stage Dockerfile with the provenance-or-refuse
`CODE_VERSION` guard and a non-root runtime, the allowlist `.dockerignore`, a
production Compose with no `build:`, and the `check → image → deploy` pipeline
behind an approval environment. Improved: images are built for `linux/arm64` (the
Graviton instance) and `amd64` (the workstation); the pdoc build runs in CI so a
module that fails to import fails the push (doctests catch broken examples); a `justfile` replaces memorized `uv run` lines; the
pre-commit framework replaces the opt-in hooks path so a fresh clone is scanned;
Compose declares health checks and `service_healthy` dependencies, which SteamLens
never needed because its store was a file; the deploy transport is SSM, not SSH.
Ansible for the application host is deferred to the shared infra side-quest — the
instance's first-boot configuration is cloud-init until then.

---

## Scope & non-goals

- In: the hosting shape above, from the first probe day; the deployment itself is
  continuous from the first application slice.
- Deliberately out: any AWS service beyond the named set until a requirement names
  it — service count does not add to the design.
- **The organizational tools cost nothing.** Jira, Frappe, Google Calendar (and
  Slack, if it stays) run on free tiers; spend is AWS and model tokens only. This
  rules out paid Atlassian seats and Atlassian's official MCP server (paid plans
  only, verified 2026-08-23), so Jira access is the project's own REST adapter.
- **Schedule cuts, 2026-08-23** (four of the envelope's six weeks were gone at the
  probe days; six holds only with the cuts made now): post-approval execution is
  out — no executor Lambda, no IAM split — but a run still ends in an
  *approved-plan* state in the event log that nothing consumes yet, so an executor
  later is a new consumer rather than a reworked seam; Slack is out for the world
  and investigator milestones, the adapter seam kept; the conversation milestone
  moves to backlog and is not part of the six-week claim; the first corpus is one
  answer-changing clause type (real-world scope, per the world rulings) and one
  staleness pattern; the ephemeral-compute probe moves to future work with its
  criteria intact. Each returns as an addition; none changes the shape of what
  is built now.

## Future work (curated)

- **Ephemeral compute on AWS** — preregistered probe at the demo milestone's entry
  (criteria above); the thread lives in this document until the probe fires.
- **Lite 2 as the box tariff** — sufficient for Frappe alone; rejected for box-level
  headroom and a single term reset. Revisit never; the upgrade is one-way.
- **A direct Anthropic API path beside Bedrock** — not committed to; one provider
  keeps credentials, billing, and audit in one place. Revisit if Bedrock lacks a
  model or feature the evaluation shows the product needs.

## Open questions

Pinned to the milestone whose evidence decides each; the agenda inherited from the
vision's deferred list.

- **Framework** (LangGraph the default candidate) — decided at the design session
  that follows the probe days, judged on narrated streaming, tool orchestration, a
  human-approval step, an audit trail, resumable runs against the PostgreSQL job
  seam.
- **MCP versus plain function tools** — same session; learning value against
  plumbing cost.
- **Post-approval execution** — same session; whether the product ends at the
  approved report or executes the approved plan. The executor trust boundary above
  is the candidate architecture if execution is in; if it is out, the Lambda and its
  secrets namespace are not built.
- **Retrieval detail** — chunking and retrieval for the policy corpus, and whether
  Slack and issue-comment history share the index or stay tool-call-only; decided at
  the investigator milestone's design, once the generator's corpus exists.
- **Conversational-surface mechanics** — grounding method, refusal behaviour,
  evaluation reuse; decided at the conversation milestone's entry, strictly after
  the demo ships.
- **Per-run token cost** — the ~$0.75 estimate is re-derived from the first ten
  representative runs at the investigator milestone; the budget reforecast is
  mandatory, not optional.
