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
`arda`, `AdministratorAccess` permission set, 8 h sessions, MFA required (portal
`https://d-99674c1aee.awsapps.com/start`, also reachable as
`https://ssoins-6987073305182688.portal.eu-central-1.app.aws`) · budget
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
