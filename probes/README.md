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

> **Since export format 2 (2026-10-04) the scripts under `langgraph-spike/` no longer run at HEAD.** They build and assert format 1 exports through `core`'s format 1 types, which format 2 replaced. They are left as they ran: every execution FINDINGS cites is reproducible at `f2d1f28`, the commit it names, and the event log step rewrites this code against format 2 and reruns the crash, resume and export checks through it.

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

## The event log step's three probes (written 2026-10-05, before any of them runs)

The event log's store appends under a lock, and its ledger authorizes a model call only on
a bound of that call's input tokens. Both shapes rest on a mechanism nobody here had
watched: what PostgreSQL does to a guarded insert that overlaps a takeover, and what can
be said about a request's token count before it is sent. A probe can falsify a bound and
measure what it costs; it cannot prove one. None of the three is a pass or a fail of the
project, each decides a shape, and the forecast written here is what the result is read
against.

| probe | what it decides | forecast | rests on |
|---|---|---|---|
| **input-bound, bytes** (`input-bound/bytes_against_input.py`, offline) — over the acceptance spike's captured sends that reported usage: the request body's bytes against the reported total input (input, cache read and cache write summed), by family and by streamed or whole | whether a request's byte length is a usable upper bound of its input tokens | bytes are never under the reported input; the ratio lies between 2 and 6 bytes a token. The first send's ratio (5,152 bytes, 2,049 tokens) was seen before this was written | the captured requests are small (161 to 36,651 bytes) and mostly tool definitions and JSON records; nothing here says how prose at a hundred thousand tokens behaves |
| **lock-race** (`lock-race/probe.py`, local PostgreSQL, two connections, barriers on the server's own lock table and no sleeps) — a worker's append guarded by the attempt's generation, against a takeover that increments it | whether a guard read without a lock keeps a displaced worker out, and whether a row lock does | plain, read then insert: the displaced worker's event commits after the takeover. Plain, one guarded statement held mid-execution: the same, the guard having read the statement's snapshot. Locked, worker first: the takeover waits and the append stands before it. Locked, takeover first: the worker's locking read waits, wakes on the committed row, reads the new generation and appends nothing | the default isolation level (read committed) on PostgreSQL 16; the last row is the one the store relies on and was reasoned, never observed |
| **input-bound, the counting call** (`input-bound/count_tokens.py`, live, from a workstation under an administrative principal) — captured request bodies replayed through the provider's `CountTokens` on the `eu.` Haiku 4.5 and Nova Pro profiles and on their base model ids, each count beside the input the same bytes reported at inference; one request near a hundred thousand tokens counted and then sent once to Haiku 4.5 | whether the call exists for the models and profiles the harness uses, and whether its count bounds what inference reports | a guess, marked as one: Haiku 4.5 answers under at least one of the two identifiers with a count equal to the reported input or a little above; Nova Pro may not be served at all | the captured requests carry tools and a forced choice, and the counting call takes no inference configuration; a request that hit a cache at inference is compared on its summed input |

The byte probe also answers one question by arithmetic, done by hand on the corpus-shape
probe's recorded numbers and not by any script here: the full-context request at the
padded corpus level held 530,154 characters of filler text for a reported input of
107,858 tokens, so its body is longer than 530,154 bytes, and a bound of one token a byte
puts it above a 400,000-token cap. The counting probe cannot show that the call is free;
that is read from the bill afterwards or stays a cited claim. It runs under an
administrative principal, so it says nothing of the deployed role's grant.

## The worker group's parse probe (written 2026-10-06, before it runs)

The parse protocol (`agent/answer_parse.py`) reads a model's answer by shape: a `toolUse`
block is a tool call, the fact tool's call is handled as the batch its input holds, a text
block opening with `{` is a fact payload in the answer's own content. It was built against
hand-written fixtures; the acceptance spike's two captured responses cover the read-call
shape and the text-only shape (replayed in `tests/unit/test_agent_answer_parse_captures.py`)
and no capture holds the two fact shapes. The probe asks for both in one answer and records
which arrived; it confirms or amends the protocol before any prompt is written to it.

| probe | what it decides | forecast | rests on |
|---|---|---|---|
| **parse-protocol** (`parse_protocol/live_probe.py`, live, one send to Haiku 4.5 on the `eu.` profile from a workstation under an administrative principal) — a system prompt asking for one `state_facts` call carrying a given entry and, beside it, the same payload as plain text opening with `{`; the response scrubbed (`parse_protocol/scrub.py`) into `tests/fixtures/converse/` and parsed through `parse_answer` | whether a real response carries the fact tool's call and the `{` text block as the protocol reads them, and whether both shapes can arrive in one answer | a guess, marked as one: the tool call arrives with an object input the fact parser reads; the text payload arrives less reliably, since a model given a tool tends to use it and skip the prose. Whichever arrives is parsed as a batch of one stated fact; a shape that does not arrive is reported as a gap and the protocol is not amended on its absence | one send, one model, temperature 0; the probe's prompt is not the investigator's and transfers nothing to it (the contract step's ruling on prompts earning their own checks) |

**Result (2026-10-06, one send, 962 input and 99 output tokens, 867 ms).** The tool call
arrived and the text payload did not: the model used the tool and wrote no prose, the
likelier of the two outcomes the forecast named. The call's `facts` held the one entry
nested one list deeper than the declared schema (`[[{...}]]`), so the protocol read a batch
of one refused input (undecodable: an entry is an object, got list) and no stated fact. The
outer shape is confirmed: a `state_facts` call is handled as the batch its input holds and
nothing raised. The entry's shape is not evidence against the parser on one send under a
stand-in prompt that asked for the same payload twice, once in the tool and once as text;
it goes to the investigator graph's prompt (step 11), whose own check on real output the
contract step already requires, with the flattening of a singly nested list as the cheapest
candidate amendment if a prompt written to the schema still gets it. The scrubbed response
is `tests/fixtures/converse/parse-probe-20261006T205828Z.json`, replayed by the capture
test with the reading above.

## The investigator step's prompt check (written 2026-10-10, before it runs)

The investigator's three prompt assets (`agent/prompts/`) were written from the span probe's
accepted second-pass configuration, revised for a loop that reads through tools instead of
being shown everything, and no real model has run the loop under them. The check is the
step's live probe (the step-11 forks file, fork 15 with amendment 6): the real worker over
the real store and the real turns, the live clients, the first development world read from
the local store through the planted readers and the corpus cache, the automatic approval,
publishing nothing; the forecast is the first section of the FINDINGS entry, computed
model-free by `prompt-check/forecast.py` before any call.

| probe | what it decides | forecast | rests on |
|---|---|---|---|
| **prompt-check** (`prompt-check/live_probe.py`, live, the six live-iteration scenarios of the first development world under the normal condition at the base level, Haiku 4.5 on the `eu.` profile at temperature 0 from a workstation under the administrative profile, the real evaluator in process over each export) — per scenario the calls, tokens and cost from the log; the fact-stage measures (stated against planted, admitted, refused by reason); the span outcome of every requirement stated; the nesting rate of the fact tool's input; the chain check against a clause asking for two; whether max-tokens-with-tool-use occurs. Then one comparison round per prompt sentence beyond the accepted configuration, the sentence removed whole, the same six | whether the loop runs to a valid forced finalization under the shipped prompts, what each sentence beyond the accepted configuration does to the model, and whether the entry schema is registered as the parser declares it or amended by one-level flattening | the FINDINGS entry's forecast section: no abstention, three to four logical calls a scenario, about 11,000 tokens a first request (bounded 5,500 to 13,500 by bytes), about three dollars for the whole programme; the nesting rate a guess, below one batch in four; max-tokens-with-tool-use not expected | six scenarios at temperature 0 on one development world whose corpus a single call could hold; no rate is claimed from six runs, the raw shapes are recorded beside every count, and a sentence stays only where its removal shows the named failure on the same six |

**Result (2026-10-10, fifteen rounds with one repeat, 105 runs, $8.10).** The loop, the forced finalization,
the account and the parse protocol held on every run (nested 0 of every batch, no
`max_tokens` stop, every plumbing check empty, the two-person clause through the chain
check). The forecast's reading sentence sent the model to search for words the corpus
never holds; it was rewritten four times against named failures until every needed section
target was reached, then stated accurately; the seven other sentences beyond the accepted
configuration were each removed for a round, one stayed on its failure showing and six
were dropped, the final set confirmed at the base's level, and a repeat under the
identical prompt reproduced its seven runs exactly. The entry schema is registered
unamended. The correct-whole verdict of every run was read back from the captured
exports at the close (`prompt-check/results/verdicts.md`): the final set 6 of 7, the
miss the shortened-span scenario, round 0 at 3 of 7. The FINDINGS entry `prompt-check`
holds the forecast, every round and the raw shapes; `prompt-check/results/summary.md`
the cross-round table from the result files.
