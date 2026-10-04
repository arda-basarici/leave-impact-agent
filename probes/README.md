# Probes — the preregistered plan

Each probe states its pass criterion *before* it runs (DESIGN's "Probes preceded the remaining design"
names why). Outcomes go to `FINDINGS.md`; raw evidence (JSON, `free -m` output,
screenshots, API responses) goes to `captures/<probe>/`. A probe is done when its
capture exists and FINDINGS records pass/fail against the criterion written here —
never edited after the fact.

Timebox: 3–5 days. Order is dependency order; Calendar goes first on day one because
its auth model is the least certain unknown.

## Day 0 — floors

| probe | pass criterion | capture |
|---|---|---|
| **box-upgrade** — netcup Lite 1 → Lite 3 in place | 16 GB visible; SteamLens healthy after reboot | `captures/box-upgrade/free-before.txt`, `free-after.txt` |
| **aws-bootstrap** — root MFA, Identity Center + CLI SSO, Budgets ($30) + anomaly monitor, Terraform state bucket, Bedrock model access requested for the shortlist in `eu-central-1` | `aws sts get-caller-identity` answers under an SSO profile; budget visible | `captures/aws-bootstrap/caller-identity.json`, budget screenshot |

## Day 1 — the fatal unknowns

| probe | pass criterion | capture |
|---|---|---|
| **calendar** — Google Calendar API; the auth model is the unknown (service account + domain-wide delegation needs Workspace; consumer OAuth does not). Ruled before running (2026-08-22): one consumer OAuth principal owning one secondary calendar per synthetic person — real Calendar behavior, simulated identity | events created on ≥ 3 synthetic people's calendars and overlaps listed back via `freeBusy.query`; the refresh-token lifetime ruled and recorded (an *External + Testing* consent screen expires refresh tokens after 7 days — the publishing status that survives must be chosen); the `calendar.app.created` scope tried, result recorded | `captures/calendar/` auth path chosen + consent-screen status + event listings |
| **frappe-up** — Frappe HR in Compose on the box behind Caddy + Cloudflare, memory-limited | HTTPS login from outside; resident footprint under the target org measured with ≥ 1.5 GB box headroom | `captures/frappe-up/` compose file hash, `docker stats`, `free -m` |
| **frappe-rest** — employee, leave allocation, leave application created and read back via API token from outside the box; the `leave_approver` wart. Ruled before running (2026-08-23): same person model as Jira — employees are `Employee` records only, one service `User` is everyone's approver | all three doctypes round-trip; a documented working path for `leave_approver` (`frappe.client.set_value`, server script, or fixture import) | `captures/frappe-rest/` request/response pairs |
| **jira** — Jira Cloud free tier. Ruled before running (2026-08-23, DESIGN "One organization, many scenarios"): synthetic employees are a single-select custom field keyed by employee id, `assignee` unassigned; the probe tests that model, not bare CRUD | (a) a single-select custom field `Synthetic Owner` created over REST on Free with ≥ 3 options (`emp_001 — Probe Alice` …) and shown on the project's create screen; (b) issues created with an option set, `assignee` empty, a `scenario:<id>` label; (c) JQL `"Synthetic Owner" = "emp_001 — Probe Alice"` returns exactly that person's issues; (d) a comment naming a synthetic person round-trips; (e) CSV import (UI wizard — no REST importer) with backdated `created`/`resolved` on 3 issues, read back over REST, dates recorded as-is — pass or fail is a finding, it gates the history ruling's scope; (f) a second run creates no duplicates (issue keys remembered in a manifest outside captures). The 10-user ceiling is no longer a criterion — it does not bind under the ruled model | `captures/jira/` field definition, options, issue payloads, JQL results, CSV read-back |
| **seed-spike** — one command lands 5 people / 1 project / a week of meetings / 2 leaves into all three systems. Extended before running (2026-08-24, per the world-shape rulings): fresh containers (Frappe site `hr-w1`, Jira project `W1`, world-prefixed calendars — ruled over scrubbing), world dates as custom date fields, `now` as declared world state | (a) same org visible in all three, keyed by the same employee ids; (b) a second run creates no duplicates in any system (manifest outside captures); (c) `Opened On`/`Resolved On` date custom fields created + set over REST on Free and JQL date arithmetic on them returns the right issues; (d) stable-now: `answer(now)` — on-leave set, open issues per person, busy blocks — identical at two instants inside the declared stable interval | `captures/seed-spike/` run logs ×2 + the stable-now pair |

## Day 2 — the AWS floor, and the cuttable one

| probe | pass criterion | capture |
|---|---|---|
| **instance** — Terraform: VPC, SG (443 from Cloudflare ranges), `t4g.small`, data volume, instance role; SSM session; hello-world container | HTTPS 200 through the public hostname; SSM session opened; no port 22 open from outside (`nmap`) | `captures/instance/` plan output, nmap |
| **oidc-deploy** — Actions job assumes the deploy role, pushes an arm64 image to ECR, `ssm send-command` pulls it | a commit to `main` changes the hello-world response; the token's `sub` format recorded (post-2026-07 repos emit an ID-based subject) | `captures/oidc-deploy/` job log, `sub` claim |
| **bedrock** — Converse API from the instance role for each shortlisted model (Anthropic + ≥ 1 cheaper non-Anthropic) | one round-trip per model; per-model Frankfurt availability, tool-use support, and catalogue price per M tokens recorded | `captures/bedrock/models.md` |
| **slack** — developer sandbox: bot token, post + read a channel. **Non-blocking** | post/read round-trip; a failure is noted and the milestone exits anyway | `captures/slack/` |

## Exit

The five day-one unknowns pass and the two day-two floors (**instance**,
**oidc-deploy**) pass. **bedrock** and **slack** may trail into the world milestone.

## The LangGraph acceptance spike (written 2026-10-04, before any of it runs)

The framework choice is provisional on this spike (DESIGN, "The loop runs on LangGraph").
It has
two halves. The provider probes run live against the `eu.` Haiku 4.5 and Nova Pro
inference profiles with no persistence. The persistence checks run a minimal graph
(prefetch, a model and tool loop, the approval interrupt, the terminal state) on a
scripted model against real PostgreSQL, with an event log beside the framework's
checkpoints. The code lives under `probes/`; what is accepted is rewritten into the
package afterwards.

**What a pass accepts.** The locked versions and the recorded configuration, nothing
wider: `langgraph` 1.2.12, `langgraph-checkpoint-postgres` 3.1.2, `langchain-aws` 1.8.0,
`langchain-core` 1.6.6, `botocore` 1.43.93, `psycopg` 3.3.4; the synchronous saver on
its own autocommit connection; `durability="sync"`; no node retry policy; client retries
set explicitly with `total_max_attempts`; temperature 0 and an explicit output limit on
every request. The provider probes run from a workstation under an administrative
principal, so they prove nothing about the deployed role's grant.

**Captures.** Unlike the probes above, this spike's captures are held outside the tree:
they contain model requests and responses. A FINDINGS row carries an opaque capture
identifier, the capture's digest, the script's commit and the dependency versions. The
scripts reproduce the procedure, not the responses.

**Must pass.** Each is a criterion; a failure is attributed (below) before anything is
changed.

| check | pass criterion |
|---|---|
| **capture** | for every live call the request body is recorded as sent and the stream as parsed events, in order, partial streams and exceptions included, while the client consumes the response normally; tracing to any third party is asserted off before the first send |
| **forced choice** | all eight cells (two model families × forced by `any` and by a named tool × streamed and not): the response carries a tool call whose arguments reconstruct and pass the tool's own validation. The generated tool definitions are sent unchanged first and compared for equality with the definitions in the captured request; where a family rejects them, the smallest translation that passes is used, captured and named, and the cell is judged on it |
| **tool result** | a result rendered by the canonical serializer is returned in one exchange, and the captured request body, JSON-decoded, holds that exact string |
| **crash matrix** | the run executes in a child process that is killed, not interrupted by an exception, at every seam crossing a scripted run makes; seams sit around every event append, both saver write methods and the approval handoff's three points. At each crash boundary, before recovery, every result in a durable checkpoint (pending writes included) already exists in the event log with identical content. After recovery runs to completion the log holds each logical operation exactly once, the final checkpoint's results equal the logged ones by identifier, and the export is byte-equal to an uninterrupted run's with the duration field masked. Per crossing, intents ≥ observed model requests ≥ confirmed responses, with the expected values asserted |
| **approval** | one approval event per run; a kill at each of the handoff's three points recovers with no second approval event |
| **same seam twice** | the kill repeated at the same crossing in the recovering process ends recovered or not reached again, never failed |
| **export from the log** | a completed run's export is built with the checkpoint tables dropped, then encoded, decoded and compared equal through the package's export codec |
| **invalid tool calls** | an unknown tool name, unparseable arguments and schema-violating arguments each end in an observable disposition, and the injector's dispatch record shows no port was called for any of them |
| **live path** | one bounded live run (one scenario of a throwaway world, Haiku 4.5, a small call cap) goes through the graph, a tool-result round trip, the approval and persistence, and completes. Nothing about claim quality is read from it |

**Measured.** Any result is a finding, none is a pass or a fail: cache counter states
per call (present, absent, zero) and hits in a bounded number of repeats; request digest
stability across two sends of one logical request; whether Nova Pro takes the generated
schema unchanged; the serving identity a response returns; every usage field the raw
response carries; tool dispatch duplicates per crossing; the failure-site catalogue
(what each store holds and what recovery can establish at each site); the shapes of four
provoked provider faults (a read timeout, a request refused before sending, a request
AWS rejects, a denial, the last recorded as not run if no restricted principal is
reachable); how a disposed invalid call is represented; streamed and non-streamed input
counts side by side; text beside a tool call and several tool calls in one response.

**Attribution.** A failed must-pass check is assigned to one of three layers: this
project's persistence design, the chat client, the graph framework. Where a failure
appears does not settle its cause, so a minimal reproduction substitutes one layer with
the rest held fixed, and the layer whose substitution removes the fault is the one
reopened. A design fault is fixed here and the check rerun; a client fault reopens the
client with the framework standing; a framework fault reopens the framework choice
before any further harness code. A workaround is accepted only on public API, in one
module, with its own check, and FINDINGS names what it supplies and what it costs to
maintain; a private attribute, a patched internal or a fork is a fault at its level.

**Guards.** Against a loop bug, not a budget: 150 sends per execution with retries
counted, a request-size ceiling and an output limit at the send hook, and a cumulative
stop at 1,000 sends across executions unless deliberately overridden. Every send's raw
usage is recorded; an unresolved outcome stays unknown and is never counted as zero.
