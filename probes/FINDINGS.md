# Probe findings

One entry per probe, appended when it runs: pass/fail against the criterion in
`README.md`, the number or fact it established, the capture path. Never edited after
the fact — a wrong finding gets a dated correction below it.



## box-upgrade — PASS (2026-08-22)

netcup Lite 1 → Lite 3 in place. `free -h` reports 15 Gi total after reboot
(16 GB nominal); both containers (`steamlens-app-1`, `box-proxy-caddy-1`) came back
unattended within a minute, `box-firewall` active, `/healthz` answers 200 from
outside with worker and database ok. Capture: `captures/box-upgrade/free-before.txt`,
`free-after.txt`.

Facts established beyond the criterion: the pre-upgrade box was **4 GB, not the 2 GB**
the baseline review and the TODO memory-split bullet assumed — re-derive the Compose
memory budget from the real numbers. Resting footprint ~550–650 MB (OS + app + Caddy,
idle). **No swap configured** — decide before the `frappe-up` probe.

## aws-bootstrap — PASS (2026-08-22)

`aws sts get-caller-identity` answers under the Identity Center profile
`leave-impact` as `assumed-role/AWSReservedSSO_AdministratorAccess_…/arda`; budget
visible and API-captured. Captures: `captures/aws-bootstrap/` (caller identity,
leftover sweep, budget + notifications, anomaly subscription, state bucket,
Bedrock access test).

What was set up, in order: root MFA, no root keys, billing access for non-root
identities · a 17-region read-only sweep (old Amplify project remnants: none; the
account is clean) · Identity Center single-region instance in `eu-central-1`, user
`arda`, `AdministratorAccess` permission set, 8 h sessions, MFA required (the
portal URL lives in the stream's access note, off the public repo) · budget
`leave-impact-monthly` $30/month with actual 50/80/100 % + forecast 25 % alerts ·
the AWS-created anomaly monitor kept, its subscription re-tuned from "$100 AND 40 %,
daily" to "$2 absolute, daily" (individual alerts require an SNS topic — deferred to
Terraform's `observability.tf`) · state bucket `leave-impact-tfstate-445743457479`
(versioned, public access blocked, SSE-S3) · `infra/` skeleton with the S3 backend
(`use_lockfile`, no DynamoDB) and the budget imported; `terraform plan` clean.

Facts established beyond the criterion:
- **Bedrock needs no model-access request in this account**: first Converse calls
  to `eu.amazon.nova-lite-v1:0` (311 ms) and
  `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (719 ms) answered cold. Every
  current Claude and Nova model in Frankfurt is `INFERENCE_PROFILE`-only — invoked
  through the `eu.` (EU-routed) or `global.` profile IDs, not a bare model ID;
  only `claude-3-haiku` is hosted on-demand in-region. The model-access step in the
  probe plan is obsolete; the model *choice* waits for the agent measurements.
- Accepted deviation: the workload runs in the organization's management account
  (one-owner project; a separate workload account is the multi-account practice).
- Provider quirk: `aws_budgets_budget` (provider 6.x) rejects `metrics` without
  `filter_expression`; omitting both updates via the legacy `CostTypes` path, and
  the budget still measures unblended cost (verified post-apply).
- Budget *actions* (auto-stop / deny policies) deliberately not attached — they would
  kill the demo mid-month; a high-line kill switch is a candidate for the instance probe.

## calendar — PASS (2026-08-23)

Three secondary calendars (Probe Alice / Bob / Carol) under one consumer OAuth
principal; seven events written (a planted Tuesday 13:00–15:00 overlap: Alice + Bob in
the customer review, Carol's vendor call starting inside it); `freeBusy.query` across
the three calendar ids returns exactly those busy blocks; `events.list` returns the
titled events. Second and third runs: every calendar verified via `calendars.get`,
every event `exists` (deterministic base32hex ids → 409) — no duplicates. Captures:
`captures/calendar/` (one run file per scope × publishing status, `calendars.json`
person → calendar-id map).

Facts established beyond the criterion:
- **Account shape ruled: real Calendar behavior, simulated identity.** Secondary
  calendars are real Calendar objects — FreeBusy and event listing against them are
  the production endpoints. What is not modeled: the people as Google users (invites,
  RSVP, per-user permissions). The agent's questions (who is busy when, who owns
  which meeting) don't need those; a Workspace tenant would buy them at ~$7/user/month
  and admin setup, rejected for v1. Participants travel in `extendedProperties.private`
  as *world* facts; answer-key facts never enter an event — whatever the agent's
  credentials can read is world by definition.
- **Scopes, measured:** `calendar.app.created` alone permits `calendars.insert/get`,
  `events.insert/list` on app-created calendars but refuses `calendarList.list` (the
  app cannot discover its own calendars — it must remember ids, as the generator's
  manifest will) and `freeBusy.query` (403 even on app-created calendars). Adding
  `calendar.freebusy` closes the gap. **`app.created + freebusy` is the working pair**;
  both are non-sensitive, so the consent screen needs no Google verification. The
  broad `calendar` scope (sensitive, touches the owner's real calendars) was never
  needed.
- **Publishing status:** External + *Testing* gates consent behind a test-user
  allow-list (403 `access_denied` until the owner was added) and, per Google's OAuth
  documentation, expires refresh tokens after 7 days — not deployable. Pushed to *In
  production* (non-sensitive scopes → no verification review); the production refresh
  token is the one the deployed agent will hold. **Follow-up:** confirm it still
  refreshes after 2026-08-30 before relying on it in M1.
- **OAuth client type: Desktop** — consent is a one-time local ceremony by the owner;
  what travels to the instance is the refresh token (SSM Parameter Store), never a
  consent flow. Client JSON + tokens live outside the repo under
  `LEAVE_IMPACT_GOOGLE_DIR`.
- Incident: the secret-onboarding snippet used a `$dir` variable across lines and a
  line ran in a shell where it was empty → the client JSON landed in the repo root
  (untracked; caught by listing). Snippets inline `$env:USERPROFILE\…` from now on.

### Corrections (2026-08-23, after the three-lens review)

- **calendar — times were authored in UTC onto Europe/Istanbul calendars.** The
  "Tuesday 13:00–15:00 overlap" above is 13:00–15:00 **UTC**, i.e. 16:00–18:00 on the
  calendars as a human sees them (captures: `+03:00` listings). Internally consistent
  — FreeBusy agrees with what was written — but the generator must author in the
  calendar's zone; the probe now does (`ZoneInfo`). A dialable timezone gap is also a
  legitimate distractor class for M1, not only a bug.
- **calendar — the `app.created`-alone failures have no capture.** The first script
  wrote its capture only on a fully successful run, so the `calendarList.list` and
  `freeBusy.query` 403s are asserted from terminal output, not evidence. The script
  now captures every run (failures included, sequence-stamped); a rerun with
  `--scope app-created` is pending to put the 403 on record. The person → calendar-id
  manifest moved out of `captures/` to the principal's secret dir — mutable state,
  not evidence. Earlier run files renamed to the sequence form (content unchanged).
- **aws-bootstrap — targeting identifiers redacted.** Not credentials, but in a
  public repo the Identity Center portal URL + username + alert email together are
  a phishing starter kit; the portal URLs moved to the stream's access note, the
  capture's `UserId` / role ARN and the subscriber email are redacted. The account
  id stays — `backend.tf` needs it and it is not a secret.

## jira — PASS (2026-08-23)

The probe site (Free; named in the stream's access note), project `PRB` created **company-managed over
REST** (`style=classic`, `assigneeType=UNASSIGNED`) — Free does not restrict the
project style. The ruled person model holds end to end: (a) a single-select custom
field `Synthetic Owner` (`customfield_10042`) created over REST with three options
(`emp_001 — Probe Alice` …) and placed on all three `PRB:` screens by REST; (b) four
issues with an option set, `assignee` null, label `scenario-probe-01`; (c) exact JQL
`"Synthetic Owner" = "emp_001 — Probe Alice"` returns {PRB-1, PRB-2} and nothing
else, per person; (d) a comment naming Probe Bob round-trips — author is the service
account, as the actor-identity ruling expects; (f) run 2 issued zero creating POSTs,
count unchanged at 4. Captures: `captures/jira/run-01-model.json` (first run),
`run-02-model.json` (idempotence), `run-05-readback-csv.json` (both CSV imports).

(e) **CSV import backdates `created`; it does not set `resolutiondate`.** The
wizard (new "Set up space / Map fields" flow) offers `Created` as a target and the
read-back shows the file's values exactly (`2026-03-03T10:00:00+0300`, local zone
honored). It offers no `Resolved`/resolution-date target, so `resolutiondate` stays
null even with Status=Done and Resolution=Done mapped. The first import landed all
three at import time (`2026-08-23T03:07`) because the date-format field kept its
default `dd/MMM/yy h:mm a` against a `yyyy-MM-dd HH:mm` file — a silent fallback to
now, not an error; the second import, in the wizard's own format, proved the
mechanism. Both imports landed in the auto-created team-managed project `KAN`: the
wizard offered only team-managed spaces at "Set up space". Two more limits: the
wizard did not list the `Synthetic Owner` select field as a mapping target, and it is
UI-only. Consequence for the history ruling: ticket *existence* history ("this ticket
was opened in March") is plantable via a one-time CSV step into a team-managed
project; *resolution* history is not; the import is not a general seeding path (owner
must be set over REST afterwards). Decide at the world milestone whether the manual
step is worth a history scenario class, or history stays out of the first truth model.

Facts established beyond the criterion: REST v3 `POST /search/jql` is the live search
endpoint (the classic `/search` is deprecated) · the site auto-creates a team-managed
`KAN` project and an example `SAM1` — the generator must target its own project key
and never assume an empty site · `Invoke-RestMethod` in PS 5.1 needs TLS 1.2 forced or
Atlassian answers 503 (gotchas).

**Addendum (2026-08-23, same day):** the resolution gap has the same answer as
ownership. The tool surface exposes only generator-controlled fields, so Jira's
`created` and `resolutiondate` are hidden and the world's dates live in custom date
fields set over plain REST on create (`Opened On`, `Resolved On`), which the adapter
exposes as `opened_on` / `resolved_on`; JQL date arithmetic works on custom date
fields. That removes the manual CSV step from the seeding path entirely; the import
is demoted to a cosmetic option for a human-facing board whose `created` column
should look aged (a demo-milestone question, not a world-milestone one).
