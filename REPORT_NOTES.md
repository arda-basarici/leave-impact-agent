# Report notes — Leave Impact Agent

Raw material for milestone reports and posts: decision narratives distilled at the
moment they happen, so the reports can tell the story without excavating chat logs.
Append-only, newest first. Each entry is a self-contained story with its date and the
decisions it feeds.

---

## 2026-09-10 — The rules are questions to the fact base: a verdict table caught the veto the code had hidden, and "uncovered, not unknown" turned out to be arithmetic

*M1 step 4 of the build plan, the deterministic core in `core/`: value specs, the fact
base with gaps and the run condition, closure, the authority table, the viability
rule, the plan side, the chain checks (commits `bc8582a`, `8cafa99`, `f30451d`, with
review follow-ups `8d5a192`, `b8f3805`, `5b5fc4c`; 221 tests including doctests at
the seal). Feeds: the M1 report's deterministic-core and evaluation-design sections
— why the same rule functions serve the generator and the evaluator, and what
"derived per run condition" costs in practice; the M1 post.*

The step opened with a five-question interview, one ruling per exchange, and each
answer went past an external low-context reviewer before it was ruled. That loop
earned its keep in the first question. The proposal was that a fact's value shape is
the predicate's to declare — a value spec on each registry row, validated at
construction and mirrored as the JSON tag — with a single `Requirement(count,
skill)` shape for what a clause asks. The reviewer wanted the requirement's criterion
tagged on the wire so a sealed answer key survives a later grade or country
criterion; the counter-argument was that a one-variant union is structure ahead of
need. The compromise was to tag the wire and keep Python narrow. One question later
the ruling on `hard_rule` — a policy criterion such as "an employee, not a
contractor" living inside the same requirement — made the union real, and the wire
shape was already right. The lesson the report can carry is about sealed artifacts:
a format decision is cheap before the first world is sealed and expensive after,
which is the one place where "you aren't going to need it" loses to a tag.

Two rulings shaped everything downstream. Absence became a record of its own: a
`Gap` says the record was observed and the field held no value, planted where a
scenario class plants missing information, and never a failed read — a failed read
is the run condition, a set of reachable sources passed beside the run context
because one scenario runs under several. That split lets closure read in five steps:
a positive fact is known true, a domain source unreachable in this run is unknown for
inaccessibility, a gap is unknown for absence, an open domain is unknown for
insufficiency, and only then is zero evidence false. The second ruling kept a
requirement's count away from any individual: criteria assess a person, the count
judges a plan, so one viable person against a two-person clause is a viable candidate
and an invalid plan. `load` was pruned from the reasons a candidate can fail for —
no first-set scenario names it, and a threshold would be either a constant the agent
can only be told or a clause no scenario uses; it returns when a class gives it
semantics.

The build ran in three commits, reviewed as foundation first and dependents together.
The moment worth telling is in part 2. Once the viability rule existed, the five-person
test fixture was run under three conditions — every source reachable, the tracker
down, the calendar down — and the verdicts printed as a table for Arda's read. One row
was wrong on sight: with the tracker down, the ticket's component could not be read,
and the code had marked the whole need unresolved, so the leaver herself showed as
*unknown* although her leave was a known failure. The ruling said a known failure
dominates an unresolved question; the code had let one unreadable fact veto every
other criterion. The fix made an unreadable component one unresolved criterion and
kept the leave window — a run input, not a fact the rule establishes, since a run
whose HR system is down still knows which leave it investigates. A meeting whose
schedule is unreachable stays an unresolved need for everyone, because without the
window no criterion has anything to ask. The table caught what the tests had not,
because the tests encoded the same assumption the code did.

The same table produced the case the post should open with. The release meeting's
clause asks for two Kafka engineers who are employees. With the tracker down, one
candidate's Kafka lives only in a ticket comment and reads inaccessible; the other
three are settled — on leave, in an overlapping meeting, a contractor. The expected
outcome is *uncovered*, not *unknown*. That looks like a mistake until the rule is
read: with `V` viable and `U` unknown against a required `n`, the outcome is assign
when `V ≥ n`, uncovered when `V + U < n`, unknown otherwise. Here `V + U = 1 < 2`:
even if the unknown resolved in the candidate's favour, one person cannot fill a
two-person clause, so the epistemic gap does not change the answer. The formula
reasons about what the unknowns could become, and "uncovered" here is a certain
conclusion, not caution. That is the distinction the vocabulary was built to make
measurable, showing up unprompted in a fixture.

The two review rounds found five things, every one reproduced against the shipped
code before it was adopted, which matters because the reviewer could not run the
suite and worked from the pushed diffs. The one that would have bitten silently: the
closure function validated the subject of a query but not the value, so asking
whether someone holds `"Kafka"` where a lower-case slug is declared returned a known
false rather than raising — a programming error turned into a statement about the
world. The one I got wrong: the reviewer asked for a runtime check that a
requirement's criteria are the criterion classes, and I left it out as "the type
checker's job". The reviewer's follow-up showed the chain: the value spec admitted
the object, and the codec's unreachable branch would have failed with an assertion
instead of a `ValueError`. The codebase's own rule, that an object which exists is
valid, applied, and the check went in shaped so the strict type checker does not flag
it as redundant. The one that reached back: a source-conflict claim could describe a
skill set or two sources agreeing, neither a disagreement — a hole from the
claim-vocabulary step that only became observable once the chain checks trusted the
claim. It is now refused at both levels, the claim constructor and the authority
rule, because the two answer different questions: can a report represent this, and
may the table resolve this.

The last finding drew the boundary the evaluator will live on. The chain checks read
a report alone and never ask the fact base; an unknown assessment must derive from
unknown claims shaped as the rule emits them. A clause-shaped unknown originally
passed for any clause, so an assessment could be justified by an unrelated policy.
The tightening: the clause must be one the report's own constraint claims cite for
something that could apply to the impact — the artifact itself, or a component when
the artifact is a ticket. Whether the ticket really belongs to that component is
truth, and stays the evaluator's; that the report has not justified an unknown with a
stranger's clause is coherence, and the checker can say so from the report. Report-
internal versus truth-dependent is the same line the uncovered check keeps: a report
with no viable assessment passes the chain check even if it simply stopped assessing,
and a separate completeness check that takes the candidate universe is where the
world enters.

[PRELIMINARY — the fixture is five people and two impacts; the first generated world
at step 13 is where these rules meet thirty scenarios and the tool-failure runs, and
where the "every non-skilled candidate turns unknown when the tracker is down"
behaviour, correct under the closure rule, gets its first measured cost.]

Figure: the fixture's verdict table — four people × two impacts × three run
conditions, verdict and reason per cell, expected outcome per row (regenerable from
`tests/unit/world_fixture.py` and `assess_impact`); the "uncovered with one unknown"
cell annotated with the `V + U < n` arithmetic.

## 2026-09-09 — The gate had a name all along: the 5-series block is an account review, and the public threads never said so

*M0's trailing thread, the Bedrock Support case (case 178776610200708; detail in
`probes/FINDINGS.md`, the dated 2026-09-09 entry). Feeds: the report's model-seam
section, as the second half of the "listed is not callable" story; a teaching aside
on where to look when the public record looks unresolved.*

The 26 August entry below ended with a research pass that found no official
criterion for the Sonnet 5 / Opus 5 block and no confirmed fix in any public thread,
and with a Support case queued "for the record". The case was opened the next day
and the answer came back within hours: access to those models "requires an account
review process", which Support submits on the customer's behalf once it has a
business use case (task types, usage pattern, why the region) and a business website.
That is the criterion the seven-source research pass could not find, and the reason
it could not is ordinary: the people who got this answer stopped posting. A thread
that looks unresolved on re:Post is often one where the resolution moved into a
private channel. The lesson for the report is small and transferable — when a gate
behaves like account state, ask the account's owner before surveying the crowd, and
do it early, because the answer arrived faster than the research did.

The case then sat unanswered through the platform detour, auto-closed after ten
days, and was re-opened and answered on 9 September. The reply is deliberately plain
about what this is: an individual developer's portfolio project, synthetic data, a
few hundred evaluation requests per run a handful of times a week under a Budgets
cap, Frankfurt because the rest of the stack lives there, the portfolio site as the
"business website". Inventing a company to pass a review would be a poor trade for
a project whose pitch is honest measurement, and a refusal is itself a usable fact:
"an individual account was reviewed and declined" is more credible in a report than
"blocked, cause unknown". [PRELIMINARY — the review's outcome and duration are
pending; either revises this entry's last paragraph.]

Nothing in the plan moved. The ruling not to build around the 5-series was made for
schedule reasons, not for lack of a path, and the review has no stated duration;
M2's Anthropic candidates stay Haiku 4.5 and Sonnet 4.6, and a pass later is a
one-line edit to the model list in the platform stack.

## 2026-08-26 — Listed is not callable: the Bedrock catalogue said AUTHORIZED to every model the runtime then refused

*M0 day 2, the bedrock probe (PARTIAL, then PASS for the reachable shortlist, same
day; detail in `probes/FINDINGS.md`, prices in `probes/captures/bedrock/models.md`).
Feeds: the report's model-seam and cost sections; a teaching aside for any post about
"choosing a model on Bedrock".*

The probe's question was modest: for each of six shortlisted models, does the
instance role get a round-trip, a tool call, and a prompt-cache hit, and what does
the model cost in Frankfurt. Four days earlier the account bootstrap had recorded
"Bedrock needs no model-access request in this account", on the strength of Haiku 4.5
answering cold. On the day, the three Amazon Nova rows passed everything on the first
run (`probe-run-1.jsonl`), and every Anthropic row failed — for two different
reasons that took a while to tell apart.

The control plane was no help in telling them apart. `get-foundation-model-availability`
reported AUTHORIZED and AVAILABLE for all six; the Bedrock console's old "Model
access" page has been retired; the catalogue lists the 5-series with a price. Only the
runtime knew the truth, and it knew it per model: Haiku 4.5 wanted Anthropic's
"use case details" form, which the console offers on the first playground invoke;
Sonnet 5, Opus 5 and Opus 4.8 were "not available for this account, contact AWS
Sales"; Sonnet 4.6 answered with no form at all. Reproducing the failures from an
AdministratorAccess session settled that this was account state, not the role's
grant — which mattered, because the grant had just been pinned to the shortlist and
was the first suspect.

The form's behaviour was the surprise worth recording. It was submitted at ~20:02;
Haiku 4.5 opened three minutes later. Sonnet 4.6, which had been open *before* the
form, went form-gated, then spent six minutes returning AccessDenied, then opened at
20:15:58, and flapped once more mid-run. Propagation is per model and not monotonic:
a model you could call can stop answering while the form works its way through. The
practical rule for a fresh account: budget twenty minutes and a retry loop, and
never trust the first answer in either direction. The 5-series gate did not move,
and a research pass (seven sources, re:Post and r/aws threads since roughly June)
found the same signature across regions and account types with no official
criterion and no confirmed fix — so the ruling was not to plan around the 5-series
at all. A fix later is a one-line edit to the model list in `variables.tf`; a
Support case is queued for the record.

> ⚠ REVISED by the 2026-09-09 entry — the Support case named the criterion: a
> manual account review with a business use case and website as intake.

Two smaller facts fell out. Anthropic's rows are not in the Pricing API (it carries
only legacy Claude 2/3 US SKUs), so their prices came from the pricing page read in a
browser by a subagent; the `eu.` inference profiles cost a flat 10 % over `global.`
across the board. And Nova Pro missed its cache once in five passes — an `eu.`
profile can route a call to a region that has not yet seen the prefix — which is a
line item for the M2 cost model, since the $0.75-per-investigation estimate assumes
caching works.

What the shortlist looks like after all this: two Anthropic models (Haiku 4.5,
Sonnet 4.6) and three Amazon (Nova Lite, Nova Pro, Nova 2 Lite), all answering from
the role, with Nova Lite about 14× cheaper than Haiku 4.5 on input. The choice among
them is deliberately not made here; M2's evaluation on the golden set makes it. The
probe's job was to find out what can be measured, and the honest summary is that the
catalogue could not tell us.

Figure: a small table — model × (control-plane says / runtime does / minutes to open
after the form) — makes the "listed ≠ callable" point in one glance.

## 2026-08-26 — The subject GitHub actually sends: an OIDC trust policy that matched the documentation and not the token

*M0 day 2, the oidc-deploy floor (PASS; detail in `probes/FINDINGS.md`,
`captures/oidc-deploy/`). Feeds: the report's deployment section (keyless CD, the
production gate) and the hosting appendix.*

The floor was preregistered as one sentence: a commit to `main` changes the running
service on the instance, with no AWS key stored anywhere. The mechanism is standard
— GitHub Actions federates into the account through OIDC, assumes a deploy role, and
runs the deploy script on the host over SSM `send-command` — and the probe plan
carried one open fact to record: what `sub` claim the token actually has, since
repositories created after mid-2026 were rumoured to emit a new form.

The rumour was right and the documentation was not, or at least not for this
repository. The trust policy was first written with the documented, name-based
subject. STS refused twelve retries with "Not authorized to perform
sts:AssumeRoleWithWebIdentity" before the job log gave up the real claim:
`repo:arda-basarici@133336041/leave-impact-agent@1342572683:environment:production`
— owner and repository each carrying their numeric id. Pinning the trust to that
form is the stronger pin, not a workaround: a repository renamed or deleted and
re-created under the same name inherits nothing, because the ids differ. The role is
trusted by repository *and environment*, which is why the production gate is part
of the security story rather than a convenience.

The gate had its own lesson. A workflow that references an environment which does
not exist creates it, bare; the first deploy went straight through with nobody
asked. Only after a reviewer and a `main`-only branch policy were set on the
environment did the re-run stop at "Review pending". A new GitHub environment is
not a gate until someone configures it to be one — worth one line in any runbook
that leans on it.

Two identity flips are on record: the first approved run replaced "no application"
with `leaveimpact 51d3f16`, and the very next commit — the one that recorded the
probe — flipped it to `leaveimpact 2f028b2` at 12:26:24Z through the same gate. In
between, the boot script changed (the proxy stack took over the shared network and
`trusted_proxies` is now rendered from the same pinned Cloudflare ranges as the
security group), so the instance itself was replaced: new instance, same Elastic
IP and data volume, certificate re-read from Parameter Store, HTTPS 200 with no
manual step, in 1m13s (the first boot had taken 4m53s, most of it waiting for the
secrets to be put). "The host regenerates from code" stopped being a claim and
became a measured event.

One deviation from the plan's wording is deliberate and should be told as such: the
row said "pushes an arm64 image to ECR", and there is no ECR. The baseline review
had already ruled GHCR as the registry, and a second registry would have existed
only to satisfy the row. The thing the row exists to prove — federation, a role
trusted by repository and environment, a commit landing on the host through SSM —
is exercised in full; preregistered criteria stay as written and the findings carry
the deviation with its reason.

## 2026-08-24 — One command, three systems, zero duplicates: the seed spike closed probe day 1 — and a network fault earned its place in the adapter design

*The last day-1 probe of M0 (seed-spike, criterion preregistered in `probes/README.md`
before the run). Feeds: the M0 probe-days post; the report's world-generator section
(the spec→projections→manifest seam) and its evaluation-design section (stable-now);
the M2 adapter section (the retry lesson).*

The spike's question was whether the M1 generator's core seam works at all: one org
spec — 5 people, 1 project, 8 issues, a week of meetings, 2 approved leaves —
projected into three systems that never see each other, idempotently. The three
systems (Frappe HR on the box, Jira Cloud Free, Google Calendar) are deliberately not
synchronized; what makes them "the same org" is only that all three projections read
the same spec, keyed by the same employee ids. Consistency by construction, not by
reconciliation — the project's ground-truth-by-construction signature applied to the
environment itself.

Before the spike could run, a ruling: the earlier probes had left residue (a "Probe
Org" company in Frappe, auto-created projects in Jira, test events in calendars), and
Arda asked for clean plates. The options differed in kind. Scrubbing shared systems
can never prove it got everything — every future world inherits doubt about what's
left. Fresh containers — a new Frappe site per world (`bench new-site` ≈ 2 min, the
Host header selects the site), a new Jira project key, new secondary calendars — are
provably clean *by creation*, and "reset a world" becomes drop-and-recreate instead of
a cleanup audit. Arda ratified fresh containers; the compose frontend switched from a
pinned single-site name to `$host` routing the same hour, and the probe created its
own site (`hr-w1`) rather than inheriting the probe site's residue. One honest limit:
Jira Free is one site, so the *project key* is the container there — residue outside
the world's key coexists but is invisible to the agent's tools, which query by
project and owner field.

The run itself passed everything on the first attempt (capture:
`probes/captures/seed-spike/run-01.json` — 64 creations). Two results matter beyond
"it worked." First, **Jira Free accepted everything over REST** — including creating
the `W1` project itself with the company-managed kanban template, previously an
open question, and JQL date arithmetic on custom date fields: `"Opened On" <=
"2026-09-08" AND ("Resolved On" IS EMPTY OR "Resolved On" > "2026-09-08")` returned
exactly the spec's open set per person. World dates as custom fields — the ruling
that had closed the resolution-date gap on paper the day before — now holds in
practice, and the manual CSV import is fully out of the seeding path. Second,
**stable-now became mechanical**: the spike's verify step computes `answer(now)` —
who is on leave in now's week, which issues are open as of now, which calendar
blocks are busy — at two instants inside a declared stable interval (Sep 8 and
Sep 10) and requires identical answers. It held, and the *reason* it held is the
design's teeth: the spec plants no world date inside the declared interval. That
guarantee is now the generator's contract, not a hope.

The idempotence half took a fight. Reruns kept dying on a transient transport fault:
an authorized Frappe GET would intermittently hang or get connection-reset, and the
origin's nginx access log proved the request *never arrived* — something between the
client and the box (the Cloudflare edge, or the hosting provider's connection
policing; the stream's fix log already records SSH resets on the same box under rapid
connections) was killing it. Unauthenticated calls never failed in reproduction; the
same call passed moments later. Mid-diagnosis Arda made a process correction that
shaped the outcome: don't burrow — surface what's known and discuss the approach.
The known facts supported a pragmatic fix over a root-cause hunt: a retry on
*connection-level* faults only (never on HTTP errors), safe here because every write
is find-or-create. Run 5 then delivered the criterion cleanly — **0 creations,
identical verify results** — and its capture shows the retry earning its keep: two
faults on one call, third attempt clean (`run-05.json`; runs 02–04 are the fault
captures). The transferable lesson went into FINDINGS: every M1/M2 adapter needs
connection-fault retries, because the transport to real external tools is measurably
imperfect even at probe scale. Root cause stays open in the fix log (cheapest next
clue: Cloudflare's Security → Events page).

A design consequence surfaced by Arda's question rather than any probe: when this
project is shared, *nobody visits the three tools*. They are the agent's world —
credentialed, private (a Free Jira site, Frappe behind Caddy on the box, a consumer
Google account) — not the audience's window. The audience surface is the demo
milestone's report view, which means evidence there must be **self-contained**: the
quoted fact, its source system, its provenance rendered in the report itself, with
deep links decorative at best. Noted for the demo milestone's design before any of
its UI exists.

Figure: the twin-instant check as a small diagram (one week band, two `now` marks,
three system answers converging to the same tuple); or the run-01 vs run-05 creation
counts (64 → 0) as the idempotence before/after.

## 2026-08-23 — Two vendor surprises from the HRIS probe: the setting that is silently ignored, and the approval check the admin token walks through

*M0 day 1, the frappe-rest probe (PASS same day; detail in `probes/FINDINGS.md`).
Written 2026-08-24 from the stream session log and FINDINGS. Feeds: the M0 probe-days
post; the report's adapter section (vendor-behavior risk) and its security/permissions
section (the runtime principal ruling).*

The HRIS probe was supposed to verify a boring round-trip — employees, leave
allocations, leave applications over REST — and it did (balance arithmetic exact:
20 → 15 for a Mon–Fri week, → 19 for a single day; capture
`probes/captures/frappe-rest/run-03.json`). What earns this entry are two behaviors
no documentation had promised.

First, a silent ignore. Frappe HR v16 resolves an employee's holiday list only
through a *submitted Holiday List Assignment* document. The legacy fields the v15
docs describe — `Company.default_holiday_list`, `Employee.holiday_list` — are still
accepted by the API and then ignored: run 2 set both and leave creation still failed
with "No Holiday List was found" (`run-02.json` is the failure capture). The lesson
is not about holiday lists; it's that a vendor API can accept a write and quietly do
nothing with it, which is exactly the class of behavior a generator that claims
ground truth by construction cannot tolerate on faith. The seed's independent
read-back verification exists for this reason, and this was its first live
justification.

Second, an inverted wart. Going in, the worry was that setting `leave_approver`
would need workarounds. Setting it turned out trivial — the real finding pointed the
other way: an *Approved, submitted* leave application whose approver is **not** the
submitting principal goes through when the token belongs to a System Manager. The
admin token bypasses the approval check entirely. For the generator this is a
convenience (it seeds approved history in one call — the god of its world needs no
approver's consent). For the agent it is a threat model: the same convenience in the
investigator's hands would let it fabricate approved state. The ruling that fell out:
the agent's runtime principal must be a role-scoped User, never the Administrator
token — least privilege has to hold at *both* layers, the tool registry in the
harness and the API principal underneath it. One probe, one sentence in the security
section that would otherwise have been discovered in production.

A third, quieter fact rounded the picture: backdated `posting_date` is taken as
given, so Frappe needs no custom-field detour for world dates — its documents' own
date fields already separate world time from the vendor's `creation` timestamp. The
same split Jira needed custom fields to achieve, Frappe gives away.

## 2026-08-23 — The box doesn't build: how a missing Docker image ruled the supply chain, and a reviewer tightened "pinned" into a digest

*M0 day 1, the frappe-up probe (PASS; detail in `probes/FINDINGS.md`). Written
2026-08-24 from the stream session log and FINDINGS. Feeds: the report's
ops/deployment section; candidate material for a post on supply-chain discipline at
hobby scale.*

The plan said "run Frappe HR in Compose on the box." The catch discovered en route:
**no official image carries the HR app.** `frappe/erpnext` ships without `hrms`, and
hrms requires erpnext — so somebody had to build a custom image, and the question
became *who and where*. The candidates: a one-time build on the box, builds from the
workstation, or CI as the only manufacturer. The first two died on the same
principle, now written into DESIGN: **production hosts consume artifacts, they never
manufacture them.** A box that builds its own images is a box whose running software
cannot be traced to a commit; a workstation build is the same problem with worse
reproducibility. So GitHub Actions builds the image from a pinned `frappe_docker`
commit (frappe 16.31.0 / erpnext 16.32.3 / hrms 16.16.0, `apps.json` fed in as a
BuildKit secret), pushes to GHCR — and the build took 4m36s against a 15-minute
estimate.

The sharpening came from outside: an external reviewer corrected the claim that
referencing the image by a version *tag* made it "pinned." A tag is mutable — whoever
can push the registry can move it, and the box would follow silently. The box now
references the image **by digest** (`FRAPPE_IMAGE=ghcr.io/…@sha256:…` in the box's
env file), which is immutable by construction; the `:16` and git-sha tags exist for
humans only. Updating means editing one line — an explicit act with a diff, never an
ambient drift. The correction was adopted the same day; the reviewer's other
suggestion (trigger builds only on image-input changes) turned out to already be the
workflow's shape.

One measured number worth keeping: the running stack's idle footprint with a site
installed is ~0.9 GB (box `used` 604 → 1,472 MB, `captures/frappe-up/`), against
Frappe's "8 GB recommended" sizing that had shaped early memory planning — recommended
sizing is not measured need, and the box's 16 GB holds two tenants comfortably.

## 2026-08-23 — Employees who never log in: the person model that dissolved the 10-user ceiling

*The world-shape rulings session (ruling 2 of five, written to DESIGN "The world's
shape") and the Jira probe that proved it the same day (PASS; detail in
`probes/FINDINGS.md`). Written 2026-08-24 from the stream session log and FINDINGS.
Feeds: the report's world-design section — likely its opening argument; the M0/M1
posts.*

The blocking question looked like a licensing problem: Jira Free allows 10 users, the
synthetic org wants 25–30 people, and buying seats for fake employees violates the
project's $0-tools constraint (org tools cost nothing; the spend is AWS and tokens —
Arda's line). Every path that treated synthetic people as *Atlassian accounts* was
some mix of expensive, fragile, and dishonest (a "dev instance" is licensed for
dev/testing only; shared accounts fake what they claim to test).

The ruling dissolved the problem instead of solving it: **synthetic employees are
domain entities, not vendor users.** In Jira they exist as values of a single-select
custom field (`Synthetic Owner`, keyed by employee id), `assignee` stays empty, and
actor identity — who *technically* wrote the comment, whose token created the issue —
sits outside the truth model entirely, as vendor plumbing. The 10-user ceiling
doesn't bind because the org consumes one service account, whatever its size. The
same model transferred unchanged to the HRIS (employees are `Employee` records keyed
by `employee_number`, the manager relation a domain link, one service User as
everyone's approver) and to Calendar (one OAuth principal owning one secondary
calendar per person). Three vendors, one identity rule.

The probe then proved Free holds up its end (`probes/captures/jira/`): the select
field created over REST and placed on screens, exact JQL per person
(`"Synthetic Owner" = "emp_001 — Probe Alice"` returns that person's issues and
nothing else), comments naming synthetic people round-tripping with the service
account as author — exactly as the actor-identity ruling expects — and an idempotent
second run. The one real limitation surfaced honestly: CSV import (the only way to
backdate Jira's own `created` timestamp) cannot set `resolutiondate`, is UI-only, and
its first attempt silently stamped import-time on every row because the wizard's
date-format field kept its default against the file's format — a silent fallback, not
an error. The consequence became a better ruling the next day: world dates live in
custom date fields the generator controls (`Opened On`, `Resolved On`), Jira's own
timestamps are hidden as vendor time, and the CSV import is demoted to cosmetics.
The vocabulary that keeps all of this straight — synthetic world → vendor
representation → domain-facing tools, with adapters that translate identity and
never launder a planted inconsistency — is Arda's framing, and it's the sentence the
report's world section should open with.

Figure: the three-layer diagram (world / vendor representation / domain tools) with
the person model crossing it — one synthetic employee shown as a field value in Jira,
an Employee record in the HRIS, a calendar id in Google, and *no user account
anywhere*.

---

*Candidates not yet written (material exists; write when a report or post needs it):*

- *M0 closes with every row verified, the non-blocking one too (2026-08-26) — Slack
  proved on the first run after a scripted-not-run interlude; the ruling to finish
  trailing probes rather than carry them, and the 90-day-history fact that makes
  Slack content a run-time write in the world generator. The cost line as an
  honesty anecdote: the design doc's ~$21 held and the working estimate of ~$18–19
  was the low guess (Pricing API, `probes/captures/instance/pricing.md`). Material:
  SESSION_LOG session 7, FINDINGS slack entry.*
- *The instance floor (2026-08-26) — the whole host from Terraform, the secrets rail
  (Origin CA pair as SecureString, read at boot by a path-scoped role), the
  Cloudflare-only security group, and the three interview rulings annotated lasting
  vs cheap. Material: SESSION_LOG session 5, FINDINGS instance entry.*

- *The hosting ruling (2026-08-22) — app on AWS, HRIS on the box, decided by the
  career-strategy gap's own wording; tombstoned extremes and the preregistered
  ephemeral-compute probe. Material: SESSION_LOG 2026-08-22 (design session part 1),
  DESIGN's hosting matrix.*
- *The three-lens review pivot (2026-08-23) — three independent review agents
  converged on "the world's shape is undecided," moving the next step from a probe to
  five rulings. Material: SESSION_LOG 2026-08-23 (calendar session).*
- *Calendar scopes measured, not assumed (2026-08-23) — `calendar.app.created` can
  create calendars it then cannot list; the working non-sensitive scope pair; the
  UTC-authoring slip as a timezone-distractor lesson. Material: SESSION_LOG +
  FINDINGS calendar entry.*
- *The vision method (2026-08-20→22) — grading SteamLens's vision with build
  hindsight, draft-then-interview, deploy-from-day-one as a mid-interview ruling.
  Material: SESSION_LOG founding entry, VISION.md.*
- *Probe day 0 as a teach-through (2026-08-22) — the AWS account bootstrapped with
  every term defined at first use; why the admin SSO user beats root. Material:
  SESSION_LOG day-0 entry, the AWS study file.*
