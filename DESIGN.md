# DESIGN — leave-impact-agent

What is being built and why — the decisions and their reasoning, as a narrative
snapshot of the current design. Edited in place; the journey lives in the session
log. Wins over VISION.md (the frozen founding snapshot) on disagreement. How it's
built → ARCHITECTURE (born with the scaffold); pitch → README.

*Design phase · last updated 2026-08-22.*

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

Mechanics: `tests/unit|integration|e2e/` with matching markers; `live` and `e2e`
excluded by default; a `justfile` makes the local gate the CI gate by one command.
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
broken docstring fails the push; a `justfile` replaces memorized `uv run` lines; the
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
