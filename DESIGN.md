# DESIGN — leave-impact-agent

What is being built and why — the decisions and their reasoning, as a narrative
snapshot of the current design. Edited in place; the journey lives in the session
log. Wins over VISION.md (the frozen founding snapshot) on disagreement. How it's
built → ARCHITECTURE (born with the scaffold); pitch → README.

*Design phase · last updated 2026-09-10.*

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
the shape before any option was weighed: the existing netcup box (then 2 vCPU /
4 GB) already hosts SteamLens and sat at ~0.65 GB used, measured idle and in-job;
and Frappe's recommended footprint is 8 GB. The probe days replaced the
recommendation with a measurement: the box was upgraded in place to 8 vCPU / 16 GB
on 2026-08-22, and Frappe HR with a site installed idles at ~0.9 GB on it
(`probes/FINDINGS.md`, box-upgrade and frappe-up). The "bigger host" premise was
vendor sizing, not a measured need; the split below stands on its other reasons.
The question is where the application itself runs.

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
able to read the write credentials in Parameter Store, and with no model-invocation
permission at all. The investigator's identity cannot retrieve those secrets; they
do not exist on its host. Input is the human-approved action manifest, output is the
exact approved writes plus an audit artifact. Two principals on one host would be
two configurations, not a boundary; a separate execution identity is what makes the
least-privilege claim provable rather than intended.

**The surrounding AWS set, and nothing more.** All of it under Terraform, owned by
the `platform` repository since 2026-08-27 (its stack `leave-impact-prod`; this
repository consumes the contract values its `projects/leave-impact/README.md`
publishes — the deploy role ARN, the instance tag, the `/leave-agent/` parameter
prefix — and owns only its deployment entrypoint, `deploy/`): IAM roles
and policies; GitHub Actions deploys through OIDC federation (temporary credentials,
trust policy pinned to the repository and the `production` environment through the
ID-based subject GitHub emits — no stored keys); SSM Parameter Store SecureString for
secrets (free tier; Secrets Manager's per-secret fee buys rotation nothing here needs);
CloudWatch for logs and alarms; S3 for golden datasets, evaluation reports, shipped
audit trails, and precomputed demo replays; AWS Budgets with a cost alert; Bedrock as
**the sole model provider behind a model seam** — the Converse API gives one
request shape across model families, so the seam's question is *which model per
role* (investigator, extraction sub-tasks, grading), answered by the evaluation on
the golden set rather than fixed up front — from the models the instance role can
*call*, not the catalogue: Nova opens with no request, Anthropic's 4.x needs a
use-case form (opens per model within ~20 min), the 5-series is account-gated with
no resolution path as of 2026-08-26 (`probes/captures/bedrock/models.md`); `eu.`
inference profiles cost `global.` + 10 %; the seam also checks a model's feature
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
later. The upgrade was a probe-day step, not a design-time action: done 2026-08-22
with `free` captured before and after (15 Gi visible), and Frappe's footprint is
now a measured number — ~0.9 GB idle with the site installed, so the 8 GB bought
headroom rather than met a need. Box rules that arrive with the new tenant: Compose memory
limits on the Frappe stack and a swapfile, so the heaviest tenant cannot starve
SteamLens. Rejected: a second box (two proxies, two firewalls, two backup paths for
no benefit once the in-place upgrade proved reboot-only).

**Cost envelopes, stated and tracked.** Persistent, excluding model tokens: the box
delta (+€7.57) plus roughly $21 on AWS always-on (instance ~$14, EBS ~$3, public
IPv4 ~$3.65, Parameter Store / S3 / CloudWatch / Budgets ~$0–1) — Frankfurt list
prices from the Pricing API for the provisioned shape (`probes/captures/instance/
pricing.md`, 2026-08-26); stopping the instance between working days takes the
instance line out for those hours; the account holds no free-tier allowance, so
these are the real rates. Model tokens are
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

**Three rulings at the world milestone's entry (2026-09-09), all cheap to
reverse.** *The model shortlist* the instance may invoke is re-cut to what the
account can call: Haiku 4.5, Sonnet 4.6, Nova Lite, Nova Pro, Nova 2 Lite; the
gated Sonnet 5 and Opus 5 rows leave the list and return the day the account
review passes. The prose stage's two families are Haiku 4.5 writing and Nova Pro
checking — configuration, not architecture. *Residency:* `eu.` inference profiles
throughout, at their ten-percent premium over `global.`; the data is synthetic,
so this is a story ruling — Frankfurt end to end is a sentence the deployment can
carry — and the cross-region cache misses the probe observed are an `eu.` fact
that `global.` would only widen. *Hostname gating:* the Frappe hostnames go
behind one Cloudflare Access application now — the generator's first write from
the instance is the cross-host call over the public edge that the platform's
trigger names, the service token joins the secrets ceremony, and the Frappe login
stops being scannable; the agent's own hostname stays ungated, since it serves a
hello page until the demo milestone and that demo must be public, so the
question returns at that milestone's entry rather than being decided twice. The
Access application is platform work; this document rules only which hostnames.

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
cross-scenario contamination is caught rather than assumed away. Which entities a
scenario owns is recorded in the sealed world spec's owned-entities table, not
planted in the systems: the adapters carry no scenario id (ruled at the close of
the adapter step, replacing the earlier plan of a Jira label, a calendar property
and a Frappe custom field, which nothing would have read), so a slice is
enumerable from the spec and could be reset from it if anything ever writes to the
world; the reset itself is not built until something does. Org-per-scenario was rejected: it simplifies ground truth by
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
`now`); scenarios take disjoint windows — fourteen-day slices since the first
golden set's ruling below — which is the cheapest write-isolation mechanism and
gives the shared calendars a believable spread — a rule that may relax once
entity ownership is proven. Temporal
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
are plantable and their content is a world fact ("[2026-09-12, emp_023 — Bob Kaya]
blocked on the vendor API"), while the comment's own timestamp and author are vendor
operational facts (every write is the service account's). The bracketed prefix is
the physical home of the comment's world date and speaker: a fixed shape the
generator writes, exactly as the owner field carries `emp_017 — Alice Demir`, so the
adapter reads it into the comment's structured date and author the way it reads a
custom field — a format translation, not an interpretation of the prose, which stays
whole, prefix included — and fails loudly on a comment without it; the validator
checks every projected comment parses (ruled 2026-09-10, at the step 2 review). The
free-text synthesis the fragmented tier measures is the comment's content, never
who said it when. Frappe leave records and calendar events take the dates the seed sets, so
past leave and past meetings are real history where history is needed. The Jira
probe (2026-08-23) found the CSV importer backdates `created` but not
`resolutiondate`, is UI-only and targets team-managed projects — and that the
question was mis-posed: ticket dates are world facts like ownership, so they live
in generator-controlled custom date fields (`Opened On`, `Resolved On`) set over
REST, exposed by the adapter as `opened_on` / `resolved_on`, while Jira's own
timestamps stay hidden as vendor time. Date-level history ("opened in March,
resolved in May") is therefore plantable without a manual step; actor-level
history ("who handled this before") remains outside the first truth model.

### The answer-key contract (2026-09-09)

**The report and the key speak one typed vocabulary, frozen at the world
milestone.** Everything downstream grades on it and the generator emits truth in
the same words, so the types, their grading keys and the four semantic rules below
are lasting; field names and enum members can still grow. Six claim types:

```text
impact                key (leave_id, subtype, artifact)   subtype: deadline | meeting | responsibility
constraint            key (clause_id, applies_to)
candidate_assessment  key (impact_key, employee_id)       verdict: viable | non_viable | unknown, reasons[]
source_conflict       key (entity, predicate)             observations[], resolved_value, authority_rule
unknown               key (subject, required_fact)        reason: absent | inaccessible | ambiguous | conflicting | insufficient
coverage_action       key (impact_key)                    action: assign | uncovered | unknown, assignee_ids[], rationale?

shared, serialized: claim_id, type, evidence_refs[], derived_from_claim_ids[]
computed from the payload, never serialized: the grading key, entity_refs[]
```

*(Keys as ruled at the claim-vocabulary step, 2026-09-10; the 2026-09-09 draft keyed
an impact by `(subtype, artifact_id)`, a constraint by a `rule_id`, an assessment by a
`need_id`, and gave the coverage action its own `basis_claim_ids`.)*

Impacts describe what the leave affects; constraints what a valid response must
obey; candidate assessments who could satisfy a need; coverage actions what the
proposed plan does; conflicts and unknowns where the evidence chain could not be
established. A responsibility is an existing obligation attached to the leaver — an
open ticket, a named client contact in a document — and is an impact; "a release
needs two qualified engineers" is normative and is a constraint, cited from its
clause, never an impact of the leave. Every type has its own grading identity
because a universal `(type, entity_id)` fails as soon as a claim is relational (an
assessment is a person *for* a need, a conflict is an entity *and* a predicate).
Evidence refs are plural from the first schema: a single non-viability can rest on
Calendar, Frappe and a clause at once, and a single-source field would tempt the
agent to cite one fragment of a multi-source inference. Not added, deliberately:
`violation` (the constraint checker emits those), `evidence` (that is provenance),
`risk` (an impact already is one), `reasoning` (report layer, not benchmark
ontology); a `dependency` impact subtype waits for a scenario class that needs it.

**The vocabulary in code (ruled 2026-09-10, step 3 of the M1 build).** A
constraint's rule is its clause: `clause_id` is the key, so a constraint the agent
cannot trace to a clause cannot be expressed, which is the grounding rule made a type.
Clause-backed requirements become constraint claims; deterministic domain rules (the
cover may not itself be on leave) constrain validity inside the viability rule
without becoming claims. There is no need apart from an impact: an impact *is* the
coverage need, cardinality and eligibility come from constraints and rules, so the
assessment and the coverage action key on the impact's key. That key carries the
leave: a run investigates one leave, but the truth manifest holds every scenario's
impacts side by side and an impact's identity is world-wide, "this leave affects
this artifact". Grading identity is never a claim id: claim ids are minted by
whichever emitter wrote the report, so the same world fact carries different ids in
the agent's report and the answer key; a claim's grading key is computed from its own
fields and identifies the fact across emitters, while `derived_from_claim_ids` links
claims inside one report (the coverage action's former `basis_claim_ids` was the same
relation under a second name and is folded in). References are typed at run time:
an `EntityRef` pairs an entity kind with an id and validates the id's namespace at
construction, because a union of `NewType` strings is invisible once the type checker
leaves; an impact key validates its subtype against the kind (deadline → work item,
meeting → event, responsibility → work item or clause, since an obligation may be a
ticket or a runbook paragraph). `entity_refs` say what a claim is about,
`evidence_refs` (source, target, field) say where it was read. A conflict's
observations carry typed values (`FactValue`: an entity reference, text, or a date,
tagged in JSON; the fact base owns and may extend the union from step 4), never text
flattened for convenience, because resolution compares them. A coverage action names
its assignees in the plural (the cardinality clause needs two) and carries an
optional rationale, the only text the LLM judge reads. The assessment's reason
vocabulary is seeded from what this document already names (skill, component,
availability, load, hard rule) and closed by the viability rule at step 4.
Serialization is a stdlib codec in one module, canonical (fixed field order, compact,
tagged by claim type), decoding through the same constructors the code path uses so
validation has one home; pydantic stays out of `core`, and may enter at the agent's
structured-output edge in the investigator milestone without the domain knowing.
A claim set is well-formed when claim ids are unique, every claim-id reference
resolves to another claim, the provenance graph is acyclic, and no two claims of one
type share a grading key; the semantic chain checks (an unknown assessment rests on
an unknown claim) belong to the rules.

**The rules in code (ruled 2026-09-10, step 4 of the M1 build).** The fact base is
the rules' only world: a fact is a subject, a predicate, a typed value, the evidence
reference it was read from and the world date at which it became observable, and a
rule that has to reach back into an entity is not reading the fact base, which is why
two rows joined the registry (`scheduled_at`, an event's half-open instant span;
`in_component`, a work item's component). Each registry row now declares its value
spec — an entity reference of a kind, a closed enum vocabulary `core` owns, a skill
slug whose seeded set only `world` knows, a date, a date span, an instant span, or a
requirement — a fact validates against the spec at construction, and the JSON tag is
the spec's kind rather than a second declaration. Multi-valued predicates are one
fact per value. `on_leave` stores the inclusive date span with the leave record as
provenance; `requires` stores a requirement, a minimum count and a tuple of typed
criteria (skill, employment type; grade and country join with their predicates when
a clause plants them), tagged in JSON so a sealed key survives a later criterion.
Country, timezone and grade have no predicate until a rule reads one. Absence is a
record of its own: a `Gap` says the record was observed and this field held no
value, planted where a scenario class plants a missing fact, never a failed read —
a failed read is the run condition, a separate `RunCondition` (the reachable
sources) passed beside `RunContext` because one scenario runs under several. The
closure rule reads facts and gaps visible at `now` from reachable sources and
answers in order: a positive fact → known true, with the facts that established
it; a source of the predicate's declared domain unreachable → unknown /
inaccessible; a gap → unknown / absent; an open domain → unknown / insufficient;
otherwise known false. Zero facts mean false only after the evidence domain has been
fully observed, and a gap blocks that inference. Closure derives three unknown
reasons and the claim vocabulary keeps five: `ambiguous` and `conflicting` are the
agent's to emit, never the rule's. The entity's `None`-versus-empty distinction maps
to gap-versus-no-facts in `core`'s derivation (the ports ruling, below; step 4 had
placed the per-field table in `world`), and a ticket without a due date is an
observed negative, not a gap. Viability evaluates
every criterion through closure and combines: any known false → non-viable with
every failing reason, otherwise any unknown → unknown deriving from one unknown
claim per unresolved fact, otherwise viable. The criteria and their sources of
truth: the required skill from the clause-backed requirements that apply to the
impact's artifact or its component (`skill`); membership of a work item's component,
a domain rule (`component`); not on leave over the need's window, the investigated
leave's span for a deadline or responsibility and the event's own span for a
meeting, read in the run's reference timezone, and not attending another event
overlapping a meeting (`availability`); the requirement's policy criteria
(`hard_rule`). The investigated leave's span is a parameter of the rule, never a fact the rule
establishes; who supplies it differs — the evaluator from the scenario spec, the
investigator from the leave record it read through the people port (the ports
ruling, below). An unreadable work-item component is one unresolved criterion, not an
unresolved need, so a known failure still settles a candidate; an unreadable meeting
schedule leaves no window to ask about and is an unresolved need for everyone. `load` is pruned: no first-set
class names it, and a threshold would be either a domain constant the agent can
only be told or a clause no scenario uses; it returns when a class establishes its
semantics. The leaver fails through `on_leave` like anyone. A requirement's count
never touches individual viability: criteria assess a candidate, count judges a
plan, so one viable person against a two-person clause is a viable candidate and an
invalid plan. Three record-returning functions carry the plan side, because a
defective plan is a graded outcome: the plan check resolves each constraint claim's
clause to its `requires` fact — the agent establishes which clause applies and never
transcribes its content — and reports `insufficient_cardinality` (per requirement,
count a minimum, an implicit minimum of one without a clause; under the conjunctive
model this reduces to the largest count, a property of the current semantics, not
a theorem), `missing_assessment` and `non_viable_assignee` (an unknown assignee is
not viable for an assign); the truth outcome over an explicit candidate universe,
never the `must_assess` set, with `V` viable and `U` unknown against count `n`: `V
≥ n` assign, `V + U < n` uncovered, otherwise unknown — the expected action is
truth, an expected assignee set is not; and the chain checks, report-internal and
named for what they know (an unknown assessment derives from unknown claims shaped
as the rule emits them — about the candidate, the impact's artifact, or a clause the
report's own constraints cite for something that could apply to the impact, on a
predicate the rule reads for that subject — an unknown action from an unknown
assessment, an assign action's assignees each hold a viable assessment, an
uncovered action holds no viable one, a conflict resolves to the system of
record's observation under the rule it cites, every impact has exactly one
coverage action and every action an impact), with a separate completeness check
that takes the universe and lists every member without an assessment, so
`uncovered` is never inferred from a report that simply stopped assessing.

**Four semantic rules travel with the vocabulary.** *Viability is relational and
preference is never truth:* the key states whether `(need, employee)` is viable and
why; "the best person" has no exact truth unless an optimization rule is declared,
and none is, which keeps candidate grading from smuggling a reference plan back in.
*Extra candidates are judged from the truth fact base, never from re-reading the
world:* the scenario plants a bounded `must_assess` set with authored verdicts (the
deliberate near-misses that make "why not Deniz?" objectively gradable), and any
further candidate the agent proposes is recomputed by the evaluator's pure viability
rule over evaluator-only normalized facts — every planted atomic fact in structured
form with its provenance, wherever it physically landed, so a skill that lives only
in a ticket comment is a fact the evaluator holds without solving the agent's
extraction problem. The evaluator and the deterministic core share those pure rules,
which is not the generator-echo problem but does admit a shared rule bug; the
generator invariant that closes it: for every `must_assess` candidate the authored
verdict must equal the rule's verdict over the fact base, and a mismatch fails
scenario generation rather than grading an agent wrong. *Conflicting observations
resolve through a deterministic authority table:* "live wins" is the design intent,
`system_of_record_wins` is the rule — each normalized predicate has exactly one
system of record (employment and location facts → Frappe, ticket owner and status →
Jira, meeting participation → Calendar, procedure requirements → the corpus) and a
document is never the record for an operational fact about a person or a work item,
while the corpus is the record for what a procedure requires, a normative fact that
exists nowhere else; conflicts are keyed by `(entity,
predicate)`, not by field names that happen to look alike (an office location and
a calendar timezone are not a contradiction), and the conflict claim cites the rule
id so precedence is testable instead of intuited. *Closed-world reasoning applies
per declared evidence domain:* each predicate declares the sources that
collectively hold all admissible evidence for it in this synthetic world and whether
that domain is closed; positive evidence → known true; no positive evidence with a
closed domain and every required source available → known false; no positive
evidence with an open or incomplete domain, or a required source absent or
inaccessible → unknown. So a skills list without Kafka is `non_viable / skill`, an
explicitly empty list is the same, a missing skills field is `unknown / absent`,
and a closed domain whose Jira half is unreachable in this run is `unknown /
inaccessible` even when the HR half shows nothing — which is why expected verdicts
are derived per run condition from facts plus closure declarations rather than
stored: a tool-failure run against the same scenario legitimately turns a
`non_viable` into an `unknown`, and that difference is the tool-failure metric.

**Three coverage outcomes, and the unknowns chain.** `assign` is a positive
conclusion, `uncovered` a negative one (the evidence suffices and nobody qualifies —
the vision's own "no qualified coverage exists for the migration" case), `unknown`
an epistemic limit. Keeping the second apart from the third is what stops the
benchmark rewarding caution: "I don't know whether anyone can cover this" against a
complete world that establishes nobody can is wrong, and so is "nobody can" when a
required source was unreachable. The word `unknown` appears at three levels with
one relation between them: an `unknown` claim records the missing fact and its
reason, an assessment whose verdict is `unknown` derives from that claim, a coverage
action whose action is `unknown` rests on the assessments — missing evidence →
unknown fact → unknown assessment → unknown coverage, one chain, not three unrelated
uses of a word. The completeness condition reads over this: every planted impact
gets a coverage action, `unknown` included, or the plan is incomplete.

**Grading falls out of the vocabulary, with the judge kept away from facts.**
Impact and constraint discovery: precision/recall over grading keys. Candidate
assessments: verdict plus reason class against authored or derived truth.
Distractors: false positives bucketed by the planted reason class (wrong window,
other team, already resolved, stale document, timezone), so a near-miss reads as a
sentence. Source conflicts: detected, and resolved to the authority table's value.
Unknowns: the expected gaps of a missing-information scenario found, and no gap
claimed where the world is complete. Grounding: evidence refs re-verified against
the world. The plan: completeness plus deterministic constraint satisfaction over
coverage actions. Only the rationale text behind an action goes to an LLM judge,
calibrated on a hand-graded set with its cost budgeted. The ontology is frozen
whole and exercised gradually: the first golden set covers the three or four types
its scenario classes need, and no scenario is authored to give a type coverage.

### The first golden set (2026-09-09)

**Thirty scenarios, ten per tier; a tier is a capability level, a class is what a
scenario is about, and modifiers ride on top.** The tiers name how far the
reasoning has to reach. Tier 1, structured: every answer-relevant fact sits in a
structured field — dated tickets the leaver owns, meetings in the slice, skills on
the HR record, free/busy, open-ticket load; the capability under test is tool use,
temporal filtering, joins across systems and the deterministic candidate check.
Tier 2, fragmented: at least one answer-changing fact needs synthesis beyond
structured fields — a qualification that exists only in a ticket comment, a
responsibility that exists only in a runbook — and/or the single supported clause
type ("a release needs two qualified engineers"), which turns a one-person answer
into two or makes a planted candidate non-viable by `hard_rule`. Tier 3,
adversarial: the correct output depends on reasoning about the evidence itself —
a stale runbook naming an outdated owner against Jira (`source_conflict`, resolved
to the system of record), a genuinely missing fact (`unknown / absent`), or a
complete world in which nobody qualifies (`uncovered`). Underneath the tiers,
scenario classes (`structured_deadline`, `structured_meeting`, `structured_mixed`;
`free_text_qualification`, `free_text_responsibility`,
`release_cardinality_constraint`, `fragmented_composite`; `stale_source_conflict`,
`missing_information`, `uncovered`, `adversarial_composite`) give results a second
reporting axis, so a tier that scores badly decomposes into which mechanism broke.
Distractors (`wrong_team`, `already_resolved`, `outside_window`,
`timezone_boundary`) and candidate pressure (`concurrent_leave`) are orthogonal
modifiers tagged on a scenario, never classes of their own, so the tier
definitions stop growing as features arrive; every modifier occurs on several
scenarios, Tier 1 included, so distractor rejection is measured on structured
evidence before free text enters. Tool failure is a run condition applied over any
scenario — the same truth, run once normally and once with Calendar unreachable —
never a scenario class, so degradation is measured against an unchanged key.

**Primitive failure modes repeat independently before any composite.** The
stratification (counts cheap to change, the rule lasting): Tier 1 — four deadline,
four meeting, two mixed; Tier 2 — three free-text qualification, three free-text
responsibility, two release-cardinality, two combinations; Tier 3 — three source
conflict, three missing information, three uncovered, one controlled composite.
Three clean `unknown` cases and three clean `uncovered` cases are worth more than
six in which both occur, because the distinction the vocabulary encodes is only
measurable when the cases are separate. The set is sized for engineering
evaluation and failure localization, not fine-grained model ranking: at ten
scenarios per tier a score of eight in ten carries a Wilson interval near 49–94 %,
so two tiers a few points apart are not distinguishable, while the failure classes
behind them are. Claim-level counts are larger but not independent within a
scenario; uncertainty is reported at scenario level, bootstrapped over scenarios.
The set grows after the first evaluator shows which classes need more cover, not
before, and not to narrow an error bar.

**A scenario owns a disjoint fourteen-day slice; the leave sits inside it.** The
slice is the world state the scenario owns; the leave interval is placed within
it independently and is usually shorter, and `now` sits inside the slice before
the leave begins, with the `stable_now_interval` around it. Room before and after
the leave is what makes "a meeting the day before", "a meeting during", "a
meeting the day after" plantable without a two-week absence. Thirty slices are
about fourteen months of organizational history, which the calendars and the
ticket dates carry believably; the first cut, one window per month, was the cost
of the same isolation at twice the span.

**Org-level facts are static across the world; scenarios select, never mutate.**
Several classes rest on facts that no scenario owns — a skills field, a team
membership, a manager link. A missing-information scenario wants the only
plausible candidate to have no skills record, and blanking that field for one
slice would leak into every other slice that touches the person. So a person
whose skills field is blank is blank for all fourteen months, and a scenario
produces its class by choosing the leaver, the need and the `must_assess` set so
that the static facts yield the intended outcome; the generator asserts that the
class emerged (a class invariant beside the `must_assess` invariant) instead of
editing shared state. Verdicts derive from the fact base, so the same person is
consistently `unknown` wherever they are a candidate. With roughly twenty-eight
people and thirty scenarios, leavers repeat, as they would.

**The fact base is world-level and time-filtered by `now`.** A qualification
evidenced in a ticket comment from month three is admissible in month nine and
not in month one. Every fact in the truth base therefore carries the world date at
which its provenance became observable (static HR facts carry world start), and
the evaluator admits only facts dated at or before the scenario's `now` — the
"time is world state" rule applied to truth. The truth manifest thus has two
layers: one world-level fact base with dated provenance, and per-scenario keys
that own the impacts, the distractors, the `must_assess` set, the slice and `now`.
It also settles what an evidence domain spans: "relevant Jira history" means the
whole organization's history up to `now`, not the scenario's slice.

**Two audit depths make "golden" an honest word.** All thirty scenarios receive
deterministic validation and a human acceptance pass — the scenario, its truth,
the expected claims, obvious consistency — so every scenario in the set has been
looked at. Ten of them, stratified three / three / four across the tiers so that
conflict, missing information, uncovered, free-text qualification and the
cardinality clause are all represented, receive the full trace: every expected
claim followed back through its evidence, the candidate facts, the distractors,
the authority resolution and the coverage outcome. Thirty scenarios inspected only
ten deep would be a generated evaluation set with an audited subset, and would be
named that.

### The generator: pure specification, materialized prose, frozen world (2026-09-09)

**Semantic generation is deterministic and pure; surface prose is materialized
once and frozen; projection reads the frozen world.** Three stages, and the
reproducibility claim is exact at each. Seed, parameters and generator version go
into the pure generator and the complete structured world comes out as plain data:
people, teams, skills, tickets, meetings, leaves, the scenario definitions, the
truth fact base, the keys, and *briefs* for every piece of prose the world needs.
A second stage materializes the briefs into text — deterministic templates for
structured-shaped text (ticket titles and summaries, meeting titles, leave
descriptions, routine fields; nothing is learned from paying a model to write
"Release planning — Payments API"), an LLM for the language-bearing artifacts that
free-text reasoning is meant to exercise (runbooks, client notes, ticket comments,
procedure prose). Accepted prose joins the specification as immutable canonical
world data, and the projectors read that bundle; re-projection never invokes a
model. The seed identifies the semantic specification; the frozen artifact bundle
identifies the realized world, and the world version is the bundle's content hash,
not the seed — two construction runs from one seed may differ in prose, and that
is fine because the seed never claimed to identify the text. Saying "the same seed
produces the whole world" would have been false the moment a model wrote a
sentence; the boundary above makes the strong statement true.

**A brief carries facts, never sentences, and the model does surface realization
only.** A brief lists the planted facts as predicates (`emp_023 has_skill kafka`,
role `answer_changing`), the context facts the text may mention, and what is
forbidden (additional qualification claims, additional responsibilities,
cardinalities); "must include the sentence 'Deniz has Kafka experience'" would turn
the benchmark into paraphrase detection. Generated text is accepted only under
**semantic containment**: every required planted fact is present and no additional
benchmark-relevant fact is introduced — `required(brief) ⊆ claims(text) ⊆
allowed(brief)`, harmless prose permitted. A lexicon check alone is not that
guarantee: "Deniz led the Kafka migration" and "Deniz has never worked with Kafka"
pass the same vocabulary test as "Deniz observed a Kafka migration", and "three
engineers must attend" adds an answer-changing cardinality without one forbidden
word. Four guards enforce containment. A namespace check — every employee, client,
ticket key, skill, project, date and number in the text belongs to the brief's
vocabulary — catches cheap invention. A required-fact check catches a planted fact
that vanished in the writing. An independent extraction check recovers the text's
propositions, negations included (a negated planted fact is an added fact, not a
missing one), with a different model family and prompt than the writer, and
compares them to the brief; it is a generation-time gate and never becomes truth,
which stays the structured brief. And for the first golden set, a human reads every
generated artifact that carries an answer-changing fact and asks whether the text
added, reversed, weakened or implied anything the brief did not say — folded into
the acceptance pass all thirty scenarios receive, not a third ritual. The
extraction check's agreement with that human pass is recorded, which is the
evidence for retiring the human pass later and costs nothing now.

**Failed generations are discarded and retried, never patched.** A patched
artifact has the provenance "model output plus generator fix plus perhaps a human
edit" and needs edit histories and altered truth assumptions; a discarded one
needs nothing. Draft → validate → freeze on pass, discard whole on fail, retry.
After acceptance an artifact is immutable. Materialization runs inside the
generator job, so the generator role gains invoke rights on the writer and checker
models (a role-policy edit in the platform stack); the models are cheap ones and
cheap to change; the materializer sits behind a renderer seam so the unit level
uses a fake renderer and the real one runs under the `live` marker. At thirty
scenarios the whole stage costs well under a dollar per world.

**Projection is the effectful, idempotent shell; the validator is separate and
read-only.** One projector per system — Frappe, Jira, Calendar, and the corpus,
which is the fourth target: the project's own document system with PostgreSQL
behind it, so the agent's `search_policy` is an adapter like the other three and
whether the table gets full-text search or pgvector stays the investigator
milestone's question, while the documents' canonical form lives in the world
bucket beside the manifest. Projectors are adapter-bound and find-or-create by
the semantic key each system stores (the domain id planted on every entity), so a
rerun adds nothing (the seed spike's contract; the one exception is a secondary
calendar, whose id Google chooses and the app-created scope cannot rediscover, so
a create whose response was lost leaves an empty orphan only a human sees — the
composition root's persistence of the map is what keeps that narrow); they hold no
scenario reasoning. The identity map — semantic id to vendor id — is what
projection writes back, not what it reads: the frozen bundle is sealed before any
vendor has minted an id, and the world manifest that carries the map is
projection's receipt, recording the world version it realized. The validator is a
distinct module that only reads: it re-reads the live systems the way the
investigator reads them and compares what they hold with the sealed world spec,
the manifest supplying configuration and provenance — every closed enumeration
exact, every record equal to its planting, and each scenario's derived view, read
once at its declared run day, equal to the plantings' under the runtime rule. One
read per scenario, not two instants: a run's view does not change inside the
stable interval, because the systems hold every projected record at once and the
harness dates every returned record to the run's day, so the interval is the
evaluator's alone and the assembly's whole-world re-verification proves the key
across it under both the dated and the runtime views (the runtime-view ruling at
the validator step). It validates the projected systems rather than the
generator's intermediate objects on purpose, so the projection seam is under test
too, and a shared generation bug cannot produce an evaluation that agrees with a
wrong world.

**The organization in code (ruled 2026-09-11, step 6 of the M1 build).** Semantic
generation identifies an organization by three separate inputs — the seed is the
stochastic realization, `OrgParams` the shape (every dial that can change the org lives
there or does not exist), the generator version the algorithm — and the version is
stamped by the code, never passed, because a version a caller could pass is provenance a
caller could forge. The interpreter's minor version is recorded beside the generator
version and checked by a test: Python guarantees only the raw `random()` stream across
releases, and the higher-level draws the generator uses may change, so an upgrade fails
the suite until the version is bumped and worlds re-cut. The vocabulary is curated,
closed and versioned rather than drawn from a faker library — the tables are generator
semantics and the namespace guard on prose needs a finite set of words — and a recorded
digest makes an unbumped edit visible in the same diff, without proving the bump (the
frozen bundle's hash for a reference seed will). One `random.Random` from the seed is
passed to every helper; ids are minted after the seats are shuffled so an id reveals no
structure. The organization guarantees *shapes*, never coverage: at least one unheld
skill, one singleton, one broadly held; exactly the parameterized number of absent
skills records; every component crossing team lines; one contractor when the share is
above zero. A first draft promised every skill two holders "so coverage is a search",
and would have made `uncovered` and `missing_information` unplantable, since both select
static org facts that scenarios never mutate; coverage as a search is the scenario's
class invariant. Members are dealt round-robin with at most two moves between teams,
because independent placement gave ten against three at twenty-eight people. Runtime
scalar types are the typed API's and the configuration boundary's, not the parameter
record's; the record owns the generator's ranges and cross-field constraints.

**The scenario framework in code (ruled 2026-09-11, step 7 of the M1 build).**
Constructive selection, never rejection sampling. A scenario class states what it needs
from the static organization as a query and returns every admissible construction in a
canonical order; the RNG chooses among them; the chosen construction plants the owned
entities and authors the expectations; `core`'s rules then run over the truth base as an
independent check — every authored verdict must equal the rule's, every declared
outcome the truth outcome over the whole organization — and a mismatch is a named
construction error, never a retry and never a reclassification. The query is
deliberately weaker than the rule: it filters affordances, the rule judges the planted
scenario, and a query that mirrored the rule in reverse would make the invariant's
independence a fiction. Modifiers are planters with a class's shape minus an outcome,
composed by the framework after the class; a modifier may amend a candidate's verdict
through a declarative effect and may never change the class's declared outcome, which
is what makes "orthogonal" testable. A scenario plants only entities it owns; policies
and procedures are world-owned and selected, runbooks and client notes scenario-owned.
Slices are dealt in order with a random gap of up to three days; the leave starts on
day six to nine so that `now`, two to four days before it, always has slice history
behind it; the stable interval is derived from planted observability and never
authored — the latest fact the key needs bounds it below, the earliest later
answer-changing fact above, capped at the day before the leave — and construction stays
independent of the rule implementation there too, the whole-world re-verification at
assembly, every stable day under the dated and the runtime views, being the independent
verification. Three records serve three audiences: the
agent-visible spec, the evaluator-only key (an outcome per impact and never a reference
plan, `must_assess` per impact, constraint keys, distractors unique by entity and never
an expected impact's artifact, the stable interval, the required sources), and the
construction record that binds them and refuses records that cannot describe one
scenario. Truth is `core`'s derivation over every planted record from its planted date
plus the facts only a world can plant, each stated once as the fact and once in the brief
that will carry it, on purpose. Required sources are found by asking the rules under each
single-source outage rather than from evidence provenance: a negative conclusion carries
no evidence fact yet depends on every source of the predicate's domain, and an unknown
for absence and an unknown for an unreachable source are different conclusions with one
verdict. The first Tier 1 class, `structured_deadline`, and the first modifier,
`already_resolved`, were built as the framework's proof: the cover is a fellow component
member, the near-miss the leaver's own teammate outside the component, and the look-alike
enters the world on its resolution date, never before.

**The assembled world in code (ruled 2026-09-11, step 8 of the M1 build).** A scenario
is correct locally against its key; a world is correct globally over the history
observable at each scenario's `now`. The golden set is therefore valid only after every
scenario has been re-verified against the complete assembled world, at its `now` and
across its declared stable interval: the fact base is world-level and time-filtered, so a
record one scenario plants can change a verdict in another slice months later, which
per-scenario verification cannot see. The re-check is the same verification over the
union of every planted record — authored verdicts, declared outcomes, and the required
sources through the one pure rule construction uses, since the interval promises the
same key and the key includes them: a foreign fact can change what a conclusion
depends on without moving it (review ruling). Global contamination is a construction error that names
the scenario, the verdict or outcome that changed, expected against actual, the foreign
record with its owning scenario and its observable-from date — and never triggers a
repair or a redraw, since a world that needs re-draws is a class whose affordance is
under-specified. Attribution costs nothing because planted records are only ever added:
a verdict can only flip toward more established facts, and the flipped verdict's own
evidence names the foreign record. Preventing contamination by construction was rejected
as rejection sampling by another name, and it cannot hold once a Tier 2 comment is meant
to be admissible months after its slice. The world plan is data: a seeded table of tier,
class and modifiers per scenario, recorded in the world manifest and produced by one
compatibility-aware planner under a stated rule — the golden set's Tier 1 counts, every
modifier on at least two scenarios, at most two modifiers on any scenario, at least two
scenarios with none. Compatibility is a static class-by-modifier matrix declared in code
and proven over every admissible construction, since no draft exists when the plan is
made. The planner is a small deterministic backtracking search in which the RNG orders
the legal alternatives and the first complete assignment wins — randomness chooses
among valid plans and never decides whether one exists, the rule the organization's
guarantees already follow; a greedy draw raised on thirty-seven of two hundred seeds
for a rule every one could satisfy (review ruling). A plan the rule cannot satisfy
therefore fails by name and means it, rather than relaxing a constraint. Independent draws
per scenario were rejected because at ten rows a modifier can land zero times, and
"measured on structured evidence" would then have no rows behind it. The clean rows are
a baseline, not a causal isolation: ten rows on different scenarios compare low against
higher distractor pressure and do not measure one modifier's effect. Two is the cap
because the collision rules were tested on pairs and the composite classes own "several
things at once". The same planner serves Tiers 2 and 3 with more rows; the plan rules
are generator semantics and bump the version. The timezone affordance is guaranteed by
the organization, on the contractor precedent: at least one employee whose zone differs
from the reference zone by a fixed minimum of hours (a cheap dial) at every instant of a
full calendar year — DST-aware and date-free, so the invariant is checkable by the org
generator alone, which never knows what scenarios plan; the reference zone becomes an
org parameter under the dial rule. The modifier chooses that far attendee independently
of the leaver, who still attends: the far colleague makes the instant plausible working
time, and the event sits at the leave's edge so that its instant is outside the leave in
reference-zone truth and inside it under a wrong-zone or UTC reading. Offsets are
computed at the planted instant, never as city constants. Truth stays exclusively
reference-zone based. Leaving the affordance to seed luck was rejected as rejection
sampling at world level; deferring the modifier to Tier 3 contradicts the golden set.

**The world bundle and its version (ruled 2026-09-11, step 8 of the M1 build; the
artifact names settled at the step's review).** `WorldSpec` is the pure composed bundle:
the organization, the plan, the scenarios, the world-level fact base derived after
assembly, and the provenance (seed, org parameters, generator version, interpreter minor
version, vocabulary digest). Three sealed artifacts serve three readers. The *world
spec* — organization, plan, slices, provenance, and the content hashes of the other two
files, so a swapped file is visible — is benchmark-private: read by the projectors and
the validator, never by the application, since the plan alone names which traps were
planted. The *scenario specs* hold the agent-visible rows only, legitimate run inputs
and no evaluator-only truth. The *truth manifest* is evaluator-only: the keys, the
construction and observability records the audit reads, and the dated fact base. The
*world manifest* of the benchmark-state ruling above is a fourth, different object: the
projection's receipt — adapter configuration, the identity map from semantic to vendor
ids, org parameters, the world version and digests — written after the vendors mint
ids, application-readable, outside the hash, holding no fact that can change an answer;
its test stays "delete it after identity resolution and lose nothing answer-relevant".
The step's first cut reused its name for the world spec and put the organization and
the plan in an application-readable file; the collision was caught at review and the
identity-map write-back alone proves the two cannot be one file. Storage follows
access, not names: the truth bucket holds the world spec and the truth manifest under
separate prefixes, the validator's role reading the spec prefix only and the
evaluator's both, the application's neither; the world bucket holds the scenario specs
and the world manifest. Canonical serialization and digests are pure and live in
`world`; writing, sealing and the assumed role belong to the generator entry point. The world version is the digest of the realized bundle — the three canonical byte
sequences in a fixed order — never of the recipe, because the interpreter finding is
exactly a case where the recipe holds and the realization drifts; the version is
external metadata of the bundle and is never serialized into a hashed artifact, which
would define it circularly. A reference seed's hash is recorded beside the generator
version as a pair, so a changed hash with an unchanged version fails the suite, and
re-cutting the pair is the deliberate act that accompanies a bump. The interpreter's
minor version is recorded as provenance; the patch version is not independently part of
the identity recipe, and any runtime difference that changes the canonical realized
bundle is reflected in the hash regardless — which is why the realization is hashed and
not the recipe.

---

## Package boundaries and the import law (2026-09-09)

**Ranks give the default dependency direction; denied edges enforce the trust
boundaries.** A rank law alone ("import only lower ranks") would have let the
investigator import the fact base, the keys and the briefs at source level while
credentials kept it from the truth bucket at run time — a boundary the whole
answer-key design depends on, left to convention. So the law has two parts.

| Rank | Package | Purity | Holds |
|---|---|---|---|
| 0 | `core` | pure | domain types (employee, work item, event, document, leave), the predicate registry, the claim vocabulary, `RunContext` and world time, the pure rules (viability, the authority table, closure, constraint checks), and vendor-neutral ports where two consumers need one |
| 1 | `world` | pure | the benchmark: world spec, scenarios, truth facts, keys, briefs, templates, the semantic generator, the construction invariants |
| 2 | `adapters` | shell | `frappe`, `jira`, `calendar`, `corpus`, `prose` — one external boundary each: vendor shape and identity translated to `core` types and back; credentials, HTTP, pagination, connection-fault retries |
| 3 | `generator` | shell | prose materialization and its guards, the projectors, sealing, the generation entry point |
| 3 | `validator` | shell | read-only verification of the live systems against the declared world |
| 3 | `evaluator`, `agent` | shell | the investigator milestone's; named now so the law has their place |
| 4 | `app` | shell | the demo milestone's surface |

The laws, all of them pytest tests shipped with the scaffold: imports point
strictly downward; no lateral imports among the rank-3 shells (the generator never
reaches the validator or the evaluator, so read-only and non-echo are architectural
rather than aspirational, and the entry point composes generation then validation
without either importing the other); `agent` never imports `world`, `generator`,
`validator` or `evaluator`; `app` never imports a benchmark package; `core` never
imports `world` — the domain does not know synthetic worlds exist, and the
production investigator depends on the domain without depending on the benchmark
that grades it, which is why `world` stays a separate package however small it
remains; `core` and `world` perform no I/O, guarded by a forbidden-import list
(`httpx`, `psycopg`, `boto3`, `googleapiclient`) that is a cheap guard and not a
proof of purity (an allowlist can replace it if the guard ever proves thin);
sibling adapters never import one another, since cross-system orchestration lives
above them and a tangled shell can obey the top-level law; external identity is
supplied at composition — one `JiraAdapter` taking a credential, never a
`GeneratorJiraAdapter` beside an `AgentJiraAdapter`, so the generator's principal
and the agent's future read principal differ in authority and share transport, and
no credential or configuration enters `core`; world time comes only from an
explicit `RunContext`, and wall-clock time is read only at a composition root
(a CLI, a job runner, an HTTP startup) and converted into context at once —
retries and timeouts use monotonic elapsed time, an infrastructure concern that
never touches scenario time.

**Placements that decide who shares what.** The pure rules live in `core`, not in
the evaluator: the evaluator's viability and the agent's deterministic core are
the same functions, and putting them in one place makes the sharing visible where
duplication would hide it. Sharing rules is not the generator-echo problem; the
edges that would be are `evaluator → agent` and `agent → evaluator`, both denied.
Two independent sources check the shared implementation: the generated
`must_assess` verdicts, authored independently of the rule, and a set of
hand-written rule cases kept as unit fixtures. Domain-facing ports (`core/ports`:
work items, people, calendar, document search) sit below their implementations
because both the generator and the investigator consume them; an abstraction that
describes what the domain needs belongs below the adapter, one that describes how
Jira works belongs inside the Jira adapter, and no interface is manufactured to
make the architecture look hexagonal — the prose renderer has one consumer and
stays a seam inside its adapter. Two verification points, two packages: the truth-level
checks (the `must_assess` invariant, the class invariant) are construction
invariants in `world`, pure, run by the generator before sealing; the validator
verifies that projection realized the declared world by reading the world spec
and the live systems, and never reads truth.

**The ports in code (ruled 2026-09-10, step 5 of the M1 build).** A port returns
observed domain entities — an entity with the source it was read from — and never
facts: `core` derives facts and gaps from an observed entity in one deterministic
derivation, so an adapter translates vendor shape and identity and never decides what
is true, and the gap logic closure depends on lives beside closure rather than in four
vendor modules. The same derivation serves every consumer: the investigator's harness
derives from live reads, and the world builds its truth base by deriving from the
entities it generated and adding the facts only a world can plant — a skill evidenced
in a comment, an owner a runbook asserts, what a clause requires — so the two bases
agree on what every field means by construction. The per-field meaning of absence is
therefore stated once: a missing skills field is a gap, an empty one is zero facts; a
missing due date or manager is an observed negative; a requested leave, a comment, a
team and a document derive nothing. When a fact became observable is the caller's
knowledge and a parameter of the derivation, since the entities keep vendor
timestamps out. The wrapper carries only the source; the record's reference is
computed from the entity's own id, and the source is explicit rather than inferred
from the type because the registry keys conflicts by source and a second system
claiming the same kind of record is a designed-for case. The corpus is the exception
and not a reason to return facts: a document section is an id and text, `requires` is
a normative fact the world's structured brief supplies to the truth fact base, and the
extraction check at generation time never becomes truth, so the document port searches
and returns text and derives nothing; the investigator establishes which clause
applies and cites it, never transcribing content, the plan check resolves the citation
to the truth's `requires` fact, and no extraction seam exists anywhere. Reading and
writing are two modules, `core/ports/read` and `core/ports/write`, so read-only is a
property of the module graph: the import law lets only `adapters` and `generator`
import `core.ports.write` — an allowlist over every module that names it, since a
re-export from `core/__init__` would put a writer behind an import the law reads as
`core` — and the validator and the investigator are readers by construction, the
investigator milestone's role-scoped principle landing at the type level before the
investigator exists. The writers have one production consumer and are a port anyway,
for the least-privilege type and for the in-memory implementation of both sides that
lives under `tests` as shared infrastructure (an `adapters/memory` package would call
memory an external system); hexagonal symmetry is not the reason. A writer adds and
never finds — find-or-create is the projector's, reading by domain id and adding what
is missing — and returns the record's locator in the source, an opaque receipt the
world manifest records; vendor ids otherwise stay inside the adapter's identity map.
A fact-bearing reader enumerates its domain, selects by identity, or narrows by a
natural window — a leave or an event over a span, the queries the systems answer by
range — and never filters by a relationship the domain derives; document search is
content retrieval and derives no facts (found at the step's review: the first cut let the tracker answer "owned
by" and "in component", two registered predicates). The registry declares a
predicate's domain closed and closure turns zero facts from a reachable source into
known false; that declaration can be honoured only when the run read the universe to
completion before the rules ran and the adapter translated every record, so a
malformed one raised instead of being dropped by a vendor-side filter the domain
never saw, and a fault halfway marks the source unreachable rather than leaving a
partial read to be graded as absence. Reachability is not completeness — the run
condition records the first and the ingestion lifecycle owns the second, a contract
the derivation states and the investigator's harness will have to keep; it becomes
an explicit record only if reads ever turn incremental. "What Alice owns" is a
filter over facts derived from every work item: retrieval efficiency spent for the
benchmark's evidence semantics, negligible at this world size, and pagination stays
the adapter's without reintroducing a relationship filter.
`RunContext` carries the leave under investigation as `leave_id` and nothing more:
run inputs identify what to investigate, ports establish the facts about it, so the
leave record, its employee and its span are read through the people port as evidence
a scenario can contradict, and the investigator, which may not import `world`, learns
the leave from the context. If the authoritative leave record cannot be read, the run
continues degraded and surfaces the resulting unknowns rather than inventing the span
— with no interval, everything downstream is unknown, not only `on_leave` — and how
that grades is the evaluator's design. A port reports three outcomes three ways,
because closure treats them differently: a record that is not there is a `None` or an
empty tuple — missing data is evidence, what its absence means is closure's, and it is
never a gap, which says an observed record lacked a field; a source that cannot answer
after the adapter's retries raises `SourceUnreachable` — an epistemic limit the run
condition records; a record the adapter cannot translate raises `MalformedRecord`,
with an opaque source-side locator because translation can fail before a domain
identity exists — a defect, never an unknown. The two exceptions share no base so one
clause cannot catch both, a vendor exception never leaves its adapter, and the fault is
per call: the first `SourceUnreachable` marks the source unreachable for the rest of
the run and stops the calls, facts already read stay facts because closure checks a
positive fact before reachability, and `RunCondition` describes the run as it ended.
In the world milestone `MalformedRecord` crashes the generator and the validator,
whose job catching a malformed projection is; whether the investigator degrades
instead is its milestone's runtime policy.

**Only the packages the world milestone needs are created at its scaffold** —
`core`, `world`, `adapters`, `generator`, `validator`. The structural test carries
the full graph, future names included, and skips a package that does not exist
yet; empty placeholder packages would be structure for its own sake. Each later
milestone scaffolds its own package after its own design session.

## Verification: five automated questions, and the eval kept apart

**The test suite answers five distinct questions; each level owns one.** SteamLens's
suite was unit-dominant with an unlabeled integration layer and nothing end-to-end;
this project names the levels and gives each a home, because it has two things
SteamLens did not — real external systems and a real PostgreSQL.

| Level | Question | What runs | When |
|---|---|---|---|
| unit | is the pure core right? | rules, constraint checks, evaluator arithmetic, parsers — doctests + pytest, no I/O | every push, default |
| integration | do the seams hold against real dependencies? | the event-log/checkpoint store against a real PostgreSQL service (never a SQLite stand-in — the store is evaluated on the terms it runs on); tool adapters against recorded HTTP cassettes of Frappe / Jira / Calendar | every push, `-m integration` |
| live contract | has an external API drifted from the cassettes? | the same adapter tests re-run against the real sandboxes under a record mode (`just test-record`); a pass re-records. The `live` marker is narrower: a test that can only run live, with no cassette possible | gated by env, on demand |
| agent smoke | does the loop's plumbing work end to end without model spend? | one scenario through the real loop with a scripted fake model (a fixed tool-call trace), cassettes, PostgreSQL; asserts the event log and the plan's shape | every push |
| e2e | does the deployed thing work? | after deploy, through the public hostname: health, a replayed scenario, the audit trail rendering | the deploy job, post-approval |

Mechanics: `tests/unit|integration|e2e/` with matching markers; the default run is
the unit level; agent-smoke tests carry the `integration` marker (spend-free, but
they write the real event log); `integration`, `live`, and `e2e` are selected
deliberately; a `justfile` makes the local gate the CI gate by one command. Network
access is blocked for every test by default, so only a vcr-marked test under a record
mode reaches a sandbox; a cassette is scrubbed by hook before it is written (hosts to
placeholders, credentials and token bodies redacted) and a unit test walks every
committed cassette for a surviving secret, so the discipline is a gate and not a review
habit. Cassettes are the honest fake — real payload shapes — and the gated live replay is
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
