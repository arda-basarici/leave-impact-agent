# Leave Impact Agent — Vision

> **How to read this document: a frozen founding snapshot, not the current spec.**
> This is the bet the project starts from, written before any code. Once ratified
> it is never updated. From then on `DESIGN.md` is the living source of truth for
> decisions, and where the two disagree, DESIGN.md wins. Claims come in four
> strengths: **verified** (live-tested by this project's own probes) ·
> **desk-checked** (confirmed against current documentation and announcements,
> not yet exercised by this project's code; one strength below verified, promoted
> only by a probe) · **decided** (rulings, revisable as the design moves) ·
> **hypothesis** (estimates and method choices that specific milestones exist to
> test). Expect the build to diverge from this document on contact with reality;
> that divergence is part of the deliverable. The design phase decides how to
> realize and test this vision; it does not reopen product scope.

**Vision fixed 2026-08-22.**

---

## The product

**Before a manager can approve time off, someone has to check the projects, the
calendars, the client meetings, and work out who covers what. The agent does that
legwork across the org's systems and returns a concrete plan: X joins Thursday's
client call, Y picks up the release ticket.**

Leave tools check balances and policy rules, and approval itself takes a minute.
The expensive part is understanding what the absence means for the team: which
deadlines fall inside the window, which meetings lose their owner, whether the
natural replacement is themselves away that week. That context is fragmented
across HR, project, calendar, and communication systems; no single system holds
the answer, so assessing coverage means manual investigation across all of them.
(hypothesis: how much that burden costs in real orgs is assumed here, not
measured; the product bet rides on the fragmentation, which is structural, not
on any specific time figure.) The Leave Impact Agent investigates those questions across the
org's real systems and returns a decision-ready coverage plan. Every claim links
to the record behind it, every unknown is stated as unknown, and the human
approves, adjusts, or declines. The agent never makes the employment decision.

### A session, walked through

A visitor lands on the demo site and takes the manager's seat (the product faces
the manager; the employee side is just the request, which the scenario parameters
express). They pick a scenario, or generate a fresh one from the difficulty
knobs: say, senior backend engineer, 10 working days, starting in 12 days, with
one overlapping absence planted. The screen narrates the investigation live:

```
▸ Leave context (Frappe HR): balance sufficient, no policy conflict (deterministic, no LLM involved)
▸ Requester owns 7 open Jira issues; 3 due inside the window, 2 on the "v2.1 release" epic
▸ Calendar: 4 owned recurring meetings; 1 client call inside the window has no co-host
▸ Overlap check: one teammate on approved leave days 3–5, exactly when ISSUE-214 is due
▸ Hypothesis: release risk on v2.1. Checking who else has worked these components…
  2 candidates found; one is at 60% allocation per Jira assignment load
▸ Composing coverage plan with named substitutions + evidence list…
```

The report lands as the manager sees it: impact findings, each linking into the
actual system record behind it (the Jira issue, the calendar event, the HR entry),
and a coverage plan built from named substitutions, of the form "A joins the
client call in B's place; C takes over ISSUE-214 until return." What the org data
could not answer appears in a stated-unknowns section. The visitor approves,
adjusts, or declines, and can inspect every step the agent took; the audit trail
is part of the product surface.

Visitors steer through parameters, never through free text. Live runs are capped
per day with a visible budget ledger, and precomputed replays keep the demo
available at zero marginal cost.

---

## Positioning

The spine sentence: **an agent system whose world was built so its answers can be
checked.**

Agent demos are plentiful; agent systems that can state their own measured error
profile are rare, because evaluation requires ground truth and real orgs cannot
hand it over. This project constructs the world, so the true answer to every
scenario is known, and the agent's output is graded rather than admired. Building
eval worlds for agents is a real open industry problem; the differentiating claim
is **"built the eval world, not just the agent."**

The product embodies one archetype end to end: deterministic automation owns the
normal path, an agent investigates exceptions across fragmented systems, and a
human approves. An agent earns its place only where the investigation needs
semantic judgment over heterogeneous context; anything a database join can answer
is handled by plain code.

---

## The world it runs in — the one load-bearing idea

**Real tools, synthetic org, and one generator that doubles as the golden-dataset
generator.**

The org is generated: people, teams, projects, deadlines, meetings, ownership,
policies. But it lives in real systems rather than mocks, and the agent calls the
same APIs a production deployment would:

| System | Role | Strength |
|---|---|---|
| **Frappe HR** (self-hosted) | leave truth: balances, policies, approvals | desk-checked: GPLv3, active, auto-REST CRUD over leave doctypes. Known wart: `leave_approver` not settable via plain POST. **Footprint 4GB tight / 8GB recommended**, a real hosting line-item. Promoted to verified at M0. |
| **Jira Cloud free tier** | projects, issues, deadlines, assignment load | desk-checked: 10 users, full REST, no expiry. Promoted at M0. |
| **Google Calendar API** | meetings, ownership, overlaps | desk-checked: free now; billing enforcement announced for later 2026. This project's scale almost certainly stays free; watched as a risk. Promoted at M0. |
| **Slack developer sandbox** | announcements, coverage signals | desk-checked: the free workspace has a 90-day history limit, so the developer-program sandbox is the target. **The cuttable integration**, first out under schedule pressure. |
| **Generated document corpus** | the retrieval component: handbook, team runbooks, procedures, client requirements | decided; properties below |

Evidence comes in three source classes: **structured records** (HR entries, Jira
fields, calendar events), **unstructured live content** (Slack channels, issue
comments — read through each system's own API, shared spaces only), and the
**retrieved document corpus**. The corpus carries two committed properties, both
feeding the eval: **clauses that change answers** (the generator writes policy
text that materially alters specific scenarios' correct plans, so retrieval
quality is measured: a scenario whose answer key requires citing a clause catches
an agent that never looked) and **staleness as a dialable knob** (some runbooks
deliberately contradict the live systems; the correct behavior is preferring live
truth and flagging the contradiction, which is the everyday failure mode of real
retrieval deployments, reproducible here on demand).

The boundary between the corpus and the deterministic core is sharp. Hard
employment and leave rules (balances, notice periods, allowed leave types,
blackout rules) are enforced by plain code and real systems, never routed
through the LLM. The corpus holds operational knowledge: a release requires two
qualified engineers, a client expects a named technical contact, a database
handoff has a procedure. The agent retrieves that knowledge as evidence; it
never interprets employment eligibility.

Because the org is constructed, every scenario ships with a sealed answer key.
Its shape matters: **facts have exact ground truth** (which deadlines fall in
the window, who owns what, who is actually available), while **plans do not have
a unique right answer**. The key therefore records the planted relevant facts,
the planted distractors, the hard constraints, the viable and non-viable
substitutes, and the conditions any valid plan must satisfy. A generated plan is
graded by constraint satisfaction against those conditions, never by matching a
reference plan, so the benchmark rewards sound coverage rather than imitation of
one arbitrary solution.

Scenario generation is parameterized (overlapping absences, stale documents,
ambiguous ownership, deliberate distractors, evidence planted inside free text),
which makes internal consistency, difficulty, and information fragmentation
controlled, dialable properties. Resemblance to real organizations is a separate
question that construction cannot settle; it is carried openly as a known
limitation rather than claimed.

### The role split (decided)

- **Deterministic core:** leave balances, date arithmetic, hard leave rules
  (notice periods, allowed types, blackout rules), availability constraints.
  Enforced by real systems and plain code, never the LLM.
- **The agent:** cross-system investigation over fragmented information, evidence
  identification, coverage-plan construction.
- **The human:** approve / adjust / decline.

---

## What it refuses to do

- **No employment decisions.** The agent recommends and evidences; it never
  approves, rejects, or ranks people. The design avoids automated employment
  decisions and person-level judgments; regulatory classification of any
  production deployment would depend on its actual use and jurisdiction, and
  this document does not claim to settle it.
- **No judgments about people.** Impact findings are about work artifacts
  (deadlines, meetings, ownership), never about a person's performance or value.
- **No real personal data, ever.** The org is synthetic end to end and the demo
  never ingests a visitor's data. This rule is what makes the project publishable
  at all.
- **Shared work spaces only, never private messages.** The agent reads content
  where the team already shares it: channels, issue comments, documents. Direct
  messages are out of bounds even in the synthetic org, because the line a
  production deployment would enforce is part of the product.
- **No free-form prompt into a write-credentialed agent.** Demo inputs are
  constrained scenario parameters; visitors steer, they do not inject.
- **No invented facts.** Every factual premise in a report either carries a
  source link into the org systems or renders as a stated unknown, and every
  conclusion exposes the premises it was inferred from ("no qualified coverage
  exists for the migration on Aug 22" is an inference over sourced facts, and
  the report labels it as one). Ungrounded claims are measured as the eval's
  hallucination metric rather than covered by a disclaimer.

---

## The evaluation spine

Recovery against constructed truth. The golden dataset is emitted by the same
generator that builds the org, and every scenario carries its answer key.

Two independence rules keep the loop honest. **The agent never sees the answer
key:** it works only from what actually landed in the systems, and the sealed
truth manifest lives outside its reach. **The evaluator is not the generator's
echo:** an independent validation step re-reads the populated systems and
verifies the manifest's invariants against them (a shared bug in generation
would otherwise produce an eval that agrees perfectly with a wrong world), and a
hand-audited subset of scenarios anchors the whole construction.

- **Evidence precision / recall:** of the impacts that truly exist, how many did
  the agent find; of the claims it made, how many are real.
- **Ungrounded-claim rate:** any factual premise not traceable to org data, and
  any inference whose stated premises don't support it (named precisely; the
  mechanical check is link-verification against the systems).
- **Plan validity:** coverage plans graded by constraint satisfaction against
  the answer key's conditions (availability, allocation, hard rules), never by
  matching a reference plan.
- **Tool-call correctness:** right system, right query, right time.
- **Missing-information handling:** scenarios with deliberately absent data must
  yield stated unknowns instead of confident fiction.
- **Behavior under tool failure:** a downed system degrades the report honestly.
- **Document-vs-reality handling:** where a stale document contradicts a live
  system, the agent must prefer live truth and flag the contradiction.

Difficulty is parameterized, so results report by scenario tier instead of one
flattering average. (hypothesis: exact metric definitions and tiers are milestone
work; the dimensions above are the commitment.)

---

## Milestones

Each independently meaningful, with stated exit evidence. Deployment is not a
milestone: the system lives on the real host from M0 onward, and later milestones
inherit a running deployment rather than ending in one.

**M0 — Probe days (~2–3 days).** Frappe HR running on the deployment host at
its real footprint; REST round-trips against the core three systems (Frappe,
Jira, Calendar, including the `leave_approver` wart); a generator seed spike
proving org data can land in the real systems. Slack gets its own probe that
never blocks M0 exit, matching its cuttable status. Kills the fatal unknowns
before anything is designed on them. **Exit evidence:** the core three rows of
the desk-checked table promoted to verified.

**M1 — The world (~week 1).** Org/scenario generator populating the real systems.
**Exit evidence:** a generated org live in all systems, and the golden dataset
emitted alongside it.

**M2 — The investigator (~weeks 2–3).** Agent plus deterministic core, run
offline against golden scenarios. **Exit evidence:** the measured recovery
profile across the evaluation spine's dimensions, reported by difficulty tier.

**M3 — The demo (~week 4).** The public-facing product surface: narrated live
runs (capped, budget ledger) plus precomputed replays; the manager's report view
with evidence links and the audit trail. **Exit evidence:** a public URL a
stranger can use unassisted.

**M4 — The conversation (committed, strictly after M3).** The manager
interrogates the investigation ("why is Deniz not a viable replacement?"), with
answers grounded in the same evidence base and eval'd on the same golden
scenarios. Under schedule pressure M3's deployed, eval'd report is the protected
core and M4 slips whole rather than shipping ungrounded. **Exit evidence:** the
conversational surface live, with its grounding measured on the golden set.

**Envelope: 4–6 weeks, working target 4.** The range prices in the known pattern
that first estimates of this size run 1.5–2× understated.

---

## Decisions ledger — fixed at vision level

- **Deployed from day one.** The world stands up on the real host at M0 and the
  app ships continuously from its first slice, so deploy risk is spread across
  the build instead of loaded at the end. An already-provisioned host and a
  proven deploy pattern make this cheap; the HRMS footprint forces a real host
  anyway.
- **Real tools over mocks.** The integration pain is part of the point; mocks
  would hollow both the demo and the realism claim.
- **The generator is the golden-dataset generator.** One artifact, two jobs: it
  converts the demo-world weakness into the differentiating claim.
- **Human-in-the-loop as product identity.** The refusals list is load-bearing,
  not a disclaimer.
- **Constrained demo inputs, capped spend, visible ledger.**
- **Four systems is a ceiling.** Slack goes first under pressure; nothing new
  enters without a design ruling.
- **Postgres by default** for the app's own state store; Frappe's MariaDB stays
  Frappe's business.

---

## Deferred to the design phase, with triggers

- **Framework** (LangGraph as the default candidate), judged against this
  vision's capability requirements: narrated streaming, tool orchestration, a
  human-approval step, an audit trail, resumable runs.
- **Deployment target** (the existing VPS vs. a cloud provider): cost-gated,
  decided with real numbers. The deployed-from-day-one decision gives it a hard
  deadline: settled before M0, which lands on whichever target wins.
- **MCP as the tool layer** vs. plain function tools, judged on learning value
  against plumbing cost.
- **Conversational-surface mechanics** (M4): grounding method, refusal behavior,
  eval reuse.
- **Retrieval detail:** chunking and retrieval choices for the policy corpus (the
  corpus itself and its two properties are vision-level). Also: whether Slack and
  issue-comment history shares the retrieval index or stays tool-call-only.
- **Host sizing:** the HRMS footprint (4GB tight / 8GB recommended) decides the
  target host's size.
- **Post-approval execution:** whether the product ends at the approved report
  or executes the approved plan (approve leave in the HRMS, create handoff
  tasks, reassign meetings). The candidate architecture keeps the investigator
  on read-only credentials and routes execution through a separate executor
  with narrow deterministic write tools, entered only after human approval.
  Decided deliberately at design, demo implications included.

## Known risks, named

Week-1 infra eating the schedule (HRMS ops; mitigated by probes-first and the
cuttable-Slack rule) · generator realism judged by readers (mitigated by
parameterized difficulty and a published generation method; still a real
perception risk) · scope creep in integrations (the four-system ceiling) · demo
token spend (capped by design, ledger visible) · calendar-API billing enforcement
later 2026 (desk-checked risk; this project's scale likely exempt; watched, with
a self-hosted calendar as the named fallback) · employment-AI regulatory adjacency (the design avoids
automated decisions and person-level judgments and uses synthetic data only;
classification of a real deployment would depend on use and jurisdiction).
