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
  refreshes after 2026-08-30 before relying on it in M1. Confirmed 2026-09-11: a
  forced refresh of the 2026-08-24 production token (its access token 18 days expired)
  minted a new one and `calendars.get` read with it — the M1 calendar adapter can rely
  on the production refresh token.
- **Proven at the adapter's first recording (2026-09-12):** `calendars.delete` is
  permitted under `app.created` for calendars the app made (204); an `events.insert`
  with a caller-supplied id answers 409 on the second arrival, and the copy read back
  matches, so the insert is idempotent by id; the `calendars.insert` response carries
  the principal's account address under `dataOwner` and every event's `creator.email`
  — both scrubbed by key, the address also caught by signature in the cassette gate.
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

## frappe-up — PASS (2026-08-23)

Frappe HR stands on the box at `hr.ardabasarici.dev` behind Caddy + Cloudflare:
login from outside (`/api/method/login` → "Logged In" through the public host),
hrms modules present (HR, Payroll), versions exactly as pinned (frappe 16.31.0,
erpnext 16.32.3, hrms 16.16.0). Resident footprint idle with the site installed:
**~0.9 GB** (box `used` 604 → 1,472 MB; the stack's containers sum to ~0.65 GB,
the rest is page cache attributable to MariaDB), headroom 14.5 GB against the
≥ 1.5 GB criterion; swap (2 GB, added before the install) untouched. Only Caddy
publishes a port. Captures: `captures/frappe-up/free-before.txt`,
`free-after-resting.txt` (per-container `docker stats`, compose hash, image
digest), `outside-login.txt`.

Facts established beyond the criterion:
- **No official image carries hrms** — `frappe/erpnext` ships without it, and
  hrms requires erpnext. The image is built in CI from `frappe_docker`'s layered
  Containerfile (pinned commit) with `apps.json` as a BuildKit secret, pushed to
  GHCR, and the box references it **by digest** (DESIGN: hosts consume
  artifacts). Build time 4m36s on a standard runner — the 15-minute estimate was
  pessimistic; runner disk was not a problem. A package pushed by `GITHUB_TOKEN`
  from a public repo is public on GHCR (anonymous pull verified) — no registry
  login on the box.
- **`bench new-site` with erpnext + hrms: 2m08s.** The scheduler is disabled on
  a fresh site (`*** Scheduler is disabled ***` at the end of the install) and
  must be enabled explicitly — silent, and it would have stalled every queued job.
- The "8 GB" premise in DESIGN is Frappe's recommended sizing, not a measured
  need; the idle figure above replaces it. The seeded-org footprint is the seed
  spike's number.
- Frappe's nginx sets its own HSTS (2 y, `includeSubDomains; preload`) and
  nosniff; the Caddy stanza's copies were removed after the first capture
  showed both (the header duplicates are in `outside-login.txt`).
- The new-site admin password and DB root password live in `/srv/frappe/.env`
  on the box (generated there, never transmitted); they are not backed up and
  regenerate with the site. The MariaDB data dir is a bind mount
  (`/srv/frappe/data/db`) awaiting a dump step in the nightly box backup.

## frappe-rest — PASS (2026-08-23)

From the workstation through the public host with an `Administrator` API token
(`Authorization: token key:secret`): three Employees, three submitted Leave
Allocations and two submitted, Approved Leave Applications created and read back
over `/api/resource`; the leave balance read through one whitelisted method
(`get_leave_balance_on`: 20 → 15 for a Mon–Fri week, → 19 for a single day, 20
untouched — the arithmetic the agent will rely on). Run 4 issued zero creating
POSTs. Captures: `captures/frappe-rest/run-01.json` (failed: `Country` is
`Türkiye`, not `Turkey`), `run-02.json` (failed at Leave Application — see
below), `run-03.json` (the pass), `run-04.json` (idempotence). Script:
`probes/frappe/probe.py`.

**The person model holds for HR as it did for Jira.** Synthetic employees are
`Employee` records only (keyed by `employee_number` = the generator's id; Frappe's
`HR-EMP-0000n` name is vendor identity, kept in the manifest); `reports_to` links
Employee → Employee, so the manager relation is a domain fact with no login
behind it. The one `User` in play is a single service approver
(`probe.approver@…invalid`, `send_welcome_email: 0`, roles Leave Approver + HR
User) that every Employee names as `leave_approver` — vendor plumbing outside the
truth model, like Jira's comment author.

**The `leave_approver` "wart" is smaller than feared.** Setting the field on
Employee insert works plainly (no `set_value` detour, no server script); hrms
grants the Leave Approver role itself. The real finding: an `Approved`,
submitted Leave Application whose `leave_approver` is *not* the submitting
principal goes through — the System-Manager token bypasses the approver check.
Convenient for the generator (it seeds approved history in one call) and a
reminder that the agent's runtime token must not be this one (least privilege
is a role-scoped tool registry *and* a role-scoped API principal).

Facts established beyond the criterion:
- A fresh site has no Company; the setup wizard completes over REST
  (`setup_wizard.setup_complete` with language/country/timezone/currency/
  company/fiscal year) — the generator needs no UI step.
- **hrms 16 resolves holiday lists through a submitted `Holiday List Assignment`**
  (company- or employee-level, from a date). `Company.default_holiday_list` and
  `Employee.holiday_list` are accepted and ignored: run 2 set both and Leave
  Application still failed with "No Holiday List was found". Version-specific —
  v15 docs describe the old fields.
- Backdated `posting_date` on a Leave Application is taken as given (2026-08-01
  on a record created 2026-08-23) — Frappe's own `creation` is the vendor
  timestamp; world dates live in the document's own date fields, the same split
  Jira needed custom fields for. No CSV, no custom field.
- `docstatus: 1` on insert creates and submits in one call, for allocations and
  applications alike.

## seed-spike — PASS (2026-08-24)

One command (`probes/seed/probe.py`) lands the whole world — 5 people, 1 project,
8 issues, a week of meetings, 2 approved leaves — in all three systems, keyed by the
same employee ids. Run 1: 64 creations, every verify true. Run 5 is the idempotence
pair: **0 creations** and identical verify results. All four extended criteria hold:

- **Same org everywhere** — Frappe answers the on-leave set, Jira the per-person open
  issues, Calendar the busy blocks, all consistent with the one spec by construction.
- **Idempotence across all three** — find-or-create against the manifest
  (`~/.config/leave-impact/seed/manifest.json`); reruns add nothing.
- **World dates over REST on Free** — `Opened On`/`Resolved On` created as date-picker
  custom fields over REST, set at issue create, and **JQL date arithmetic on them
  works on Jira Free**: `"Opened On" <= "…" AND ("Resolved On" IS EMPTY OR …)` returns
  exactly the spec's open set per person. The resolution-date gap is closed for real.
- **Stable-now** — `answer(now)` at two instants inside the declared interval is
  identical; the guarantee that makes it hold is in the spec (no world date inside the
  interval), which is the generator's contract from here on.

Facts established beyond the criterion:
- **Fresh containers ruled and exercised:** the `hr-w1` Frappe site (bench new-site
  ~2 min; the compose frontend now routes by Host header — `FRAPPE_SITE_NAME_HEADER:
  $host` — so sites-per-world need one Caddy stanza + one DNS record each) and the
  Jira project `W1` **created over REST on Free** with the company-managed kanban
  template (`gh-kanban-template`) — no UI step needed. World-resolved issues also
  transition to Done over REST, so status agrees with the world date.
- **Transient edge faults are real:** runs 2–4 died on an authorized GET that never
  reached the origin's nginx (reset/timeout between client and Cloudflare edge;
  intermittent, same call passes moments later; unauthenticated calls unaffected in
  the reproductions). A connection-fault-only retry (never on HTTP errors) absorbed
  it — run 5's capture shows 2 faults on one call, third attempt clean. Lesson for
  M1/M2: **every adapter needs connection-level retries**; root cause unassigned
  (Cloudflare security events not yet checked), parked in FIXLOG.

Captures: `captures/seed-spike/run-01.json` (the creation run), `run-05.json` (the
0-creation idempotence run, transport faults visible in its exchange log); runs 02–04
are the fault captures — the failures are themselves the finding.

## instance — PASS (2026-08-26)

The AWS floor stands from Terraform alone: `infra/` grew from the budget skeleton to
the full host (32 resources, `plan` → `apply` with 0 changed / 0 destroyed). All
three criteria:
- **HTTPS 200 through the public hostname** — `https://leave-agent.ardabasarici.dev/`
  answers 200 in 0.35 s; the hello echoes `Cf-Visitor: {"scheme":"https"}`,
  `Server: cloudflare`, `Via: 2.0 Caddy` — the whole path visible in one response.
- **SSM session opened** — interactive `start-session` from the workstation (session
  id in the capture); no SSH client, no key pair, no port.
- **No port 22 from outside** — `nmap -Pn -p 22,80,443` on the Elastic IP: all three
  `filtered`; direct curls to the IP time out. `sshd` still listens *inside* the host
  (AL2023 default) but the security group admits 443 from Cloudflare's 15 pinned
  ranges and nothing else, so nothing reaches it.

Facts established beyond the criterion:
- **Boot to serving: 4m53s** (`11:32:45Z` → `11:37:38Z`), most of it the boot script
  polling Parameter Store until the origin cert pair was put — first boot heals
  itself once the values exist, no ordering ceremony between `apply` and the put.
- **Idle footprint 313 MB of 1.8 GB** (Docker + Caddy + hello, no swap); the data
  volume (20 GB gp3) formats and mounts at `/srv` from the boot script by UUID.
- **Secrets rail proven:** Origin CA pair put out-of-band as SecureString
  (`/leave-agent/origin-cert`, `/origin-key`, both at version 2 = real value replaced
  Terraform's placeholder), read at boot by the path-scoped instance role. The cert
  was issued for `leave-agent.ardabasarici.dev` alone — one pair per host, revocable
  without touching the box's wildcard.
- **Two workstation tools installed for the criteria:** Nmap 7.80 and the Session
  Manager plugin (winget).
- **Parked for M1:** the instance Caddyfile has no `trusted_proxies`, so the app
  sees Cloudflare's address in `X-Forwarded-For` — the box's Caddyfile block (same
  pinned ranges) must join it when the real app lands. Hardening candidate: stop
  `sshd` on the host outright (belt-and-suspenders; the SG already closes it).
- **Ongoing cost while running:** ~$12 instance + ~$2.6 EBS + $3.65 EIP ≈ $18–19/mo;
  stopping the instance between working days keeps EIP, volume, and DNS intact and
  drops the instance line.

Captures: `captures/instance/plan.txt` (the applied plan), `https-and-direct.txt`
(200 via Cloudflare; direct-to-IP timeouts), `nmap.txt`, `ssm-session.txt`,
`ssm-boot-state.txt` (boot markers, stack, volume, memory).

## oidc-deploy — PASS (2026-08-26)

A push to `main` lands on the instance with no stored AWS key: the workflow's
`deploy` job (after `check` and `image`) waits on the `production` environment's
reviewer gate, then federates into the account through OIDC, assumes
`leave-agent-deploy`, and runs `deploy/instance/deploy.sh` on the host over `ssm
send-command` — the compose file and the image *of that commit*, both by sha.

- **The token's `sub` format recorded** (the plan's open fact): repositories
  created after mid-2026 emit **`repo:<owner>@<id>/<repo>@<id>:environment:<name>`**
  — `repo:arda-basarici@133336041/leave-impact-agent@1342572683:environment:production`
  here. The documented name-only form was what the trust policy first carried; STS
  rejected it ("Not authorized to perform sts:AssumeRoleWithWebIdentity", 12
  retries). The ID form is the stronger pin: a renamed or re-created repository of
  the same name inherits nothing.
- **The response changed with the commit:** the host had no application before;
  after the approved run it answers `leaveimpact 51d3f16: no service yet; the
  baseline image runs and identifies itself` and `/srv/app/DEPLOYED` holds the full
  sha. The next commit (the one recording this probe) flipped it through the gate:
  `leaveimpact 2f028b2` at 12:26:24Z — two commits, two identities, one approval each.
- **The gate is real only once configured:** a workflow that references a missing
  environment auto-creates it *bare*; the first run went straight through. Reviewer
  (Arda) and a `main`-only deployment-branch policy were set through the API; the
  re-run paused at "Review pending" until approved.

Deviation from the plan's wording, by design: **no ECR.** The baseline review
(2026-08-22/23) had already ruled the image registry — CI publishes the deploy unit to
GHCR (`ci.yml`, `compose.yaml`), and the package pulls anonymously — so a second
registry would have existed only to satisfy this row. The floor the row exists to
prove (OIDC federation, a role trusted by repo + environment, a commit landing on
the host through SSM) is exercised in full.

Facts established beyond the criterion:
- **The host regenerates from code alone.** The boot script changed (proxy stack
  owning the shared `web` network, `trusted_proxies` rendered from the same pinned
  ranges as the security group), so the instance was *replaced*: new instance, same
  EIP and data volume, cert re-read from Parameter Store, HTTPS 200 with no manual
  step. Rebuild boot: **1m13s** (vs 4m53s the first time, which waited for the put).
- **Least privilege on the deploy role:** `SendCommand` only with the
  `AWS-RunShellScript` document and only on instances tagged `Name=leave-agent-app`
  (found by tag, so a replaced instance needs no workflow edit); `DescribeInstances`
  + `GetCommandInvocation` to find and read. The instance role gained nothing.
- **Secrets stay in the process:** the deploy script exports `POSTGRES_PASSWORD`
  from Parameter Store for `compose up` and renders no file — compose.yaml's rule,
  now exercised on the host. PostgreSQL is up and healthy on the data volume.

Captures: `captures/oidc-deploy/deploy-job-log.txt` (the job's evidence lines: `sub`,
command id, `Status: Success`, the identity output), `instance-after-deploy.txt`
(`DEPLOYED`, containers, boot markers, memory).

## bedrock — PARTIAL (2026-08-26)

Six shortlisted `eu.` inference profiles, called from the instance role over SSM
(`probes/bedrock/probe.sh`; the role's `invoke-shortlisted-models` policy is
pinned to those six profiles plus the 32 foundation-model ARNs they route to, via
`infra/bedrock.tf`). Three facts per model: round-trip, tool-use, prompt cache.
Capture: `captures/bedrock/models.md` (the table + prices), `probe-run-1.jsonl`.

- **Nova Lite, Nova Pro, Nova 2 Lite: all three facts PASS.** Each answers, each
  emits a `toolUse` block when the prompt demands the tool, and each caches: the
  ~5k-token system prefix shows `cacheWriteInputTokens` on the first call and
  the identical count under `cacheReadInputTokens` on the second. Frankfurt
  in-region prices from the Pricing API: Nova Lite 0.078 / 0.312, Nova 2 Lite
  0.429 / 3.60, Nova Pro 1.05 / 4.20 per M in / out; cache writes are free.
- **All three Claude rows BLOCKED, by two different account gates**, reproduced
  from an AdministratorAccess session, so not the role: Haiku 4.5 wants the
  "Anthropic use case details" form (retry 15 min after submitting); Sonnet 5 and
  Opus 5 (and, tested outside the list, Opus 4.8) are "not available for this
  account … contact AWS Sales". Sonnet 4.6 answers today with no form. The
  runtime's gates are invisible to `get-foundation-model-availability`, which
  reports AUTHORIZED / AVAILABLE for every one of them.
- **Prices recorded, one earlier open fact closed:** Anthropic rows are not in
  the Pricing API (only legacy Claude 2/3 US SKUs) — read from the pricing page
  in a browser: `eu.` = `global.` + 10 % flat (Haiku 4.5 1.10 / 5.50, Sonnet 5
  2.20 / 11.00 at the unlabelled intro rate, Opus 5 5.50 / 27.50). The "Public
  Extended Access 2×" rate the TODO carried belongs to legacy Claude 3.5 Sonnet
  rows only.
- **Correction to aws-bootstrap (2026-08-22), dated:** "Bedrock needs no
  model-access request in this account" no longer holds for Anthropic — Haiku
  4.5 answered cold on 08-22 and is form-gated on 08-26; the 5-series and Opus
  4.8 are account-gated outright. Nova never needed anything.

Status PARTIAL, not FAIL: the criterion asked for "Anthropic + ≥ 1 cheaper
non-Anthropic" round-trips; the non-Anthropic half passed in full, the Anthropic
half is blocked by account state that a form (Haiku) or a sales request (5-series)
may lift. The retry after the form is the open step; the shortlist in
`variables.tf` gets re-cut at design session part 2 on this table.

## bedrock — PASS for the reachable shortlist (2026-08-26, retry after the use-case form)

Correction to the PARTIAL entry above, same day. The Anthropic use-case form was
submitted at ~20:02 (the console offers it on the first playground invoke; the old
"Model access" page is retired). Haiku 4.5 opened within 3 minutes; Sonnet 4.6 —
added to the shortlist and the role's grant between runs — after 14 minutes, via a
six-minute `AccessDenied` interlude and one later flap. Runs 2 and 3 from the
instance role (`probe-run-2.jsonl`, `probe-run-3-sonnet-4-6.jsonl`):

- **Haiku 4.5 and Sonnet 4.6: all three facts PASS** — round-trip (750 / 872 ms
  model latency), `toolUse` with the right input, cache write ≈4.84k → read ≈4.84k.
- **Sonnet 5, Opus 5, Opus 4.8: still "not available for this account"** after the
  form — an account-level entitlement the form does not touch; the resolution path
  is a Sales/Support request (research in progress, recorded in the stream).
- **Nova Pro missed its cache once in five passes** (run 2 wrote the prefix again);
  three passes right after all read. An `eu.` profile can land a call in a region
  that has not seen the prefix — an M2 cost-model fact.

The criterion — one round-trip per model, Anthropic + ≥ 1 cheaper non-Anthropic,
with availability, tool-use and price recorded — is met: two Anthropic and three
Amazon models answer from the role; the three gated models are recorded as such
with their prices. `captures/bedrock/models.md` is the table.

## bedrock — the 5-series gate is an account review, by AWS's own answer (2026-09-09)

Correction to the two entries above, dated. The Support case opened 2026-08-27
(case 178776610200708, "Account and billing") was answered the same day: access to
Sonnet 5 and Opus 5 "requires an account review process", which Support submits on
the customer's behalf once given (1) a business use case — task types, usage
pattern, why the region — and (2) a business website URL. So the earlier finding
"no official criterion, no confirmed fix in any thread" (session 6's research over
public threads) is superseded: the gate is a manual review with a named intake, not
an unresolved fault; the public threads look unresolved because nobody posted the
Support answer. The case auto-closed after ten days unanswered (2026-09-06) and was
re-opened and answered 2026-09-09 — an honest individual-developer use case with
synthetic data, low bursty evaluation traffic under a Budgets cap, Frankfurt for
residency, and the portfolio site as the website. Outcome pending; the ruling "do
not plan around the 5-series" stands regardless, since the review has no stated
duration and M2's candidates are already Haiku 4.5 and Sonnet 4.6. A pass is a
`bedrock_models` list edit in the platform stack.

## slack — PASS (2026-08-26)

A free workspace (`leave-impact-sandbox`), a blank app (`leave-impact-probe`) with
three bot scopes (`chat:write`, `channels:history`, `channels:read`), one channel
the bot was invited to. `probes/slack/probe.sh` from the laptop with the token in
the environment (`captures/slack/probe-run.txt`):

- **`auth.test`** ok — the token resolves to the workspace and the bot user.
- **`chat.postMessage`** ok — `ts 1787767817.658809` in `C0BSTFJ5FKP`.
- **`conversations.history`** filtered to that `ts` returns the same message, text
  intact, authored by the bot's user id — the post/read round-trip the criterion
  asks for, on the first run.

Facts for the world milestone: Slack's new-app dialog offers "Blank app" (the old
"From scratch") and the settings UI lives under `app.slack.com/app-settings/`;
`conversations.history` on a public channel needs the bot invited, otherwise
`not_in_channel`; the free plan's 90-day history window bounds how far back a
seeded conversation can be read — a generator that seeds Slack writes at run time,
not a dated backlog. Machine-side: a bare `bash` from PowerShell is WSL's
(`system32\bash.exe`) and sees no Windows environment — Git Bash by full path.

## benchmark-trust — PASS (2026-09-12)

The second half of the platform handoff's acceptance (the benchmark buckets and
roles, applied the same day): the `benchmark` environment's OIDC trust proven by a
run, not by the policy text — the deploy role's own lesson, its subject shape having
been learned live on 2026-08-26. A throwaway `workflow_dispatch` job under the
environment (removed after this record; run 34719626730, 21:20 UTC, approved at the
environment's reviewer gate):

- **The subject** the token carries is
  `repo:arda-basarici@133336041/leave-impact-agent@1342572683:environment:benchmark`,
  audience `sts.amazonaws.com`, ref `refs/heads/main` — the environment form, pinned
  by numeric ids, exactly what both trust policies match.
- **Both roles assumed:** `assumed-role/leave-agent-generator/GitHubActions` and
  `assumed-role/leave-agent-validator/GitHubActions`, each read back from
  `get-caller-identity` before anything else ran under it.
- **The generator's two models answer under its role:** Haiku 4.5 ("Hello") and
  Nova Pro ("Hello!") through `bedrock-runtime converse` in eu-central-1 — the
  split invoke policy holds, and the account-level access opened on 2026-08-26 is
  reachable from the new role.
- **The validator's boundary, positive control first:** a list of the world
  bucket's `worlds/` succeeds under the validator role; then a list of the truth
  bucket and a get of a `truth-manifest/` key are both refused with the
  `AccessDenied` code specifically. Two calls, because a missing key reads as
  AccessDenied only while list is also denied; a broken credential would have
  failed the positive control instead.

Facts for step 12: `aws-actions/configure-aws-credentials` re-invoked in one job with
`unset-current-credentials: true` switches roles cleanly; a two-hour session is
available to the workflows (`max_session_duration` 7200 on both roles) and a
web-identity session is not role chaining, so the one-hour chaining cap does not
apply. The instance role's own refusal on truth is not this probe's claim: it is the
deploy job's post-deploy step, landing with step 12.

**Correction, 2026-09-13 (the step 12 interview, found by the external reviewer):**
the validator's get above proved nothing about `GetObject`. S3 answers a get of an
absent key with AccessDenied whenever list is denied, precisely so the caller cannot
learn whether the key exists — and the truth bucket was empty when the probe ran. The
sentence "a missing key reads as AccessDenied only while list is also denied" is true
and was read backwards: it makes the get ambiguous, not meaningful. The list refusal
stands. A meaningful get needs a key known to exist; the platform stream holds the
ticket for a canary object at `access-probe/read-denied-canary`, and both the
deploy-time probe and the validator's refusal check target it once it exists.

## objectstore — PASS (2026-09-13)

The SDK shape of every conditional-write outcome, observed under the generator role
before the S3 store took its form (`probes/objectstore/probe.py` states the criterion;
run 34724172889, approved at the `benchmark` gate; the throwaway workflow removed
after this record). World bucket only: `preparing/` expires in a day, the refused put
on `worlds/` created nothing (listed empty afterwards), the truth bucket untouched.

| step | call | observed |
|---|---|---|
| 1 | conditional put (`IfNoneMatch="*"`), absent key | 200; the response carries `VersionId` and `ETag` |
| 2 | the same put again, same bytes | `botocore.exceptions.ClientError`, code `PreconditionFailed`, HTTP 412, `Error.Condition` = `If-None-Match` |
| 3 | the same put, different bytes | identical to 2 — S3 does not compare bytes; present-and-equal is the store's own get-and-compare |
| 4 | head, get by version id, plain put on `preparing/`, get latest | head and get return the version id and ETag; the plain put makes a new version; bytes read back equal on both |
| 5 | plain put on a final prefix (`worlds/`) | exception class `AccessDenied` (a modeled subclass of `ClientError`), code `AccessDenied`, HTTP 403, message names the explicit deny in the resource-based policy |
| 6 | get / head of a missing key | get: class `NoSuchKey`, HTTP 404 (list is granted on this bucket, so existence is not hidden); head: `ClientError` with code `"404"` and message `Not Found` |
| 7 | list under the probe prefix / an empty prefix | `KeyCount` 1 with the key; `KeyCount` 0 and no `Contents` field at all |
| 8 | list under the refused key's prefix | `KeyCount` 0 — a refused put leaves nothing |

Consequences for the store: `put_if_absent` maps 412 to a read-back and byte
comparison (equal → present-and-equal, unequal → refused with the digest mismatch
named); 403 is refused outright; the type stubs mark `VersionId`, `ETag`, `Key` and
`KeyCount` as not required, and the store treats their absence as a fault, since a
versioned bucket always returns them. On a bucket that denies list (the truth bucket
for the validator), a get of a missing key reads AccessDenied, not `NoSuchKey` — the
correction above.

**Also observed, for the trust-hardening note of 2026-09-13:** the token of a plain
`workflow_dispatch` job carries `job_workflow_ref` equal to `workflow_ref`, both
`arda-basarici/leave-impact-agent/.github/workflows/objectstore-probe.yml@refs/heads/main`,
and `workflow` = the workflow's display name. The docs describe the claim for reusable
workflows only; it is populated for every job. So a `job_workflow_ref` condition in
each role's trust policy can bind the generator role to `generate-world.yml` and the
validator role to `validate-world.yml` without a second environment and without
reusable workflows. Recorded for the platform TODO; not a step 12 change.

## deploy-boundary — PASS (2026-09-13)

The instance role's own refusal on the truth bucket, proven on the host on every deploy
(ruling 1 of the step 12 interview; the script `deploy/instance/assert-truth-unreachable.sh`
in the same SSM command as the deploy). First live run: CI run 34729636594, the deploy
of commit `ff9038d`, approved at the production gate, 01:07 UTC:

- **Identity:** `assumed-role/leave-agent-instance/i-03f6f59aec7e9716c`, the real instance
  profile, asserted before any conclusion.
- **Positive control:** a list of the world bucket's `worlds/` succeeded under it.
- **Refused with `AccessDenied`, both:** a list of the truth bucket, and a get of the
  platform's canary `access-probe/read-denied-canary` — a key known to exist, which is
  what makes the get meaningful (the correction recorded under the trust probe).

The step's claim is now evidenced on every deploy rather than stated: the application's
principal cannot list or read the answer key, and a red deploy run that names this probe
is a boundary failure to fix in the platform's IAM, never an application rollback.

## first-world — PASS (2026-09-13, approved 21:53 UTC)

The first world generated, projected and validated through the two `benchmark`
workflows: seed 1, world start 2026-01-05, the default 28 people in 5 teams, Tier 1's
ten scenarios. World version `d674d5763715549f49e82c251977cfe5093b6bf09099c165b5d7c94d7de33046`.

- **Generation, attempt 1 (run 34780738512, 20:26 UTC): red at the first vendor call.**
  The truth artifacts sealed first as designed (world spec 20:26:23, truth manifest
  20:26:24), then Frappe's `HR Settings` GET answered 403 with Cloudflare's challenge
  page. The zone's free-plan Bot Fight Mode challenges cloud-network clients on their
  first request, proven from three networks the same evening:

  | client | `/api/method/ping` on `hr-w1` |
  |---|---|
  | GitHub-hosted runner, `python-httpx/0.28.1` | 403 challenge (the run) |
  | AWS app instance 3.68.138.190, curl's UA and the httpx UA | 403, `cf-mitigated: challenge`, ray `a3aa0592fcad7a40-DUS` |
  | workstation, both UAs | 200 |

  Cloudflare's docs: Bot Fight Mode runs outside the ruleset engine and cannot be
  skipped by any rule, zone-wide only; Super Bot Fight Mode (Pro) can be skipped by a
  custom rule; the ordering against an Access service token is undocumented. The
  2026-08-30 "machine clients pass" observation rested on UptimeRobot, a verified bot
  Bot Fight Mode exempts, so it said nothing about unverified cloud clients; this run
  was the first such client ever to reach the Frappe hostnames. Ruled in the platform
  stream (its commit `b894ac6`): Bot Fight Mode off, the paid-plan trigger re-cut, the
  service-to-service connectivity row (a private tunnel network) re-opened for M2 entry.
- **Attempt 2 (same run id, 21:25–21:32 UTC): green in 375.6 s.** The truth objects
  kept attempt 1's timestamps — the content-addressed restart hit the equal case on
  both, live, on its first try. Entry-point numbers: `checkpoint_count=106`,
  `checkpoint_p50_seconds=0.295`, `checkpoint_p95_seconds=0.623`,
  `checkpoint_total_seconds=40.021`, `checkpoint_bytes_written=491265`,
  `checkpoint_share_of_run=0.107`, `conditional_puts=2`. Per-record checkpointing
  costs a tenth of the run; no cadence change on this evidence. Projected: 28
  employees, 12 leave applications, 18 departments under Frappe company
  `World WD674D5763`; 9 issues in Jira project `WD674D5763`; calendars per person;
  no documents (Tier 1 plants none). The OIDC subject and `job_workflow_ref` claims
  logged as at the objectstore probe.
- **Validation, run 34784309718 (verdict `…/verdicts/34784309718-1.json`): refused.**
  One failed check: employee fidelity on `skills`, 18 of 28 employees; every
  exactness kind, every other fidelity kind and all ten scenario views passed. Cause:
  Frappe's list call over the skill child table returns rows in the join's
  unspecified order (`emp_002` live: redis, spark, go, airflow at idx 3, 4, 2, 1 —
  the projector had written sorted order faithfully); the reader kept that order,
  the sealed side carries a lexically sorted tuple, and fidelity is field equality.
  All 16 employees with three or more skills failed and 2 of the 5 with exactly two.
  A cassette holds one recorded order, so the suite could not have caught it. Fixed
  in `c9823a7` at the reader boundary (sorted, duplicate-free, a repeated skill
  refused as malformed); nothing regenerated or reprojected.
- **Validation, run 34785009950 (verdict `…/verdicts/34785009950-1.json`, 1 min
  38 s): approved.** Every check passed; the verdict's manifest digest
  `92576aa3…` equals the live world manifest's; both verdicts stand side by side
  under the version. The serving rule's three conditions hold for this world.

Not demonstrated, still open: the validator role's `GetObject` denial on
`truth-manifest/<version>.json` now that a real key exists (an IAM simulation from the
workstation was inconclusive; the honest proof is a negative probe step inside the
validate workflow, the deploy probe's shape), and the validator role's write surface
beyond the verdict key. The `benchmark` gate refusing a wrong subject: ruled not worth
demonstrating (the trust policy was read back 2026-09-12).

## measurement-world — PROSE PASS, calendars complete on resume, projection BLOCKED by a Frappe site collision (2026-09-14/15)

The step 15 measurement world (plan `tier1-plus-qualification`, seed 1, start 2026-01-05,
cap 4) under generator version 6, run 34803999468 at commit `8e17a65`. Four dispatches
before it were red inside the prose stage, each on a mechanism the unit level could not
see and a local probe (one writer call, one checker call, the raw tool input printed)
decided in minutes:

1. run 34802507979: 12 of 12 attempts refused by the required-fact anchor — the writer
   writes in the first person and never its own name; a fact about the comment's author
   is now anchored on its value alone.
2. run 34802945370: the checker's tool input "malformed" three times on one text — a
   value in the wrong form (subject and value of ownership reversed) was a protocol
   failure that aborted the stage; now an extraction finding that resamples the writer,
   and the checker is told what the text is (a comment by whom on which ticket).
3. run 34803388159: 12 of 12 refused by extraction — every sample offered to take the
   ticket ("I can take this on"), read as ownership; the writer prompt forbids offers,
   the brief allows the author's own ticket, a reversed entity pair is canonicalized.
4. probe only: readiness padding ("I'm ready to dig into this") read as hedged
   ownership and as availability claims; the ticket-comment register now asks for a
   remark about the work as it stands, a hedged mention of allowed context is no
   violation, the brief allows the ticket's component.

Then the prose stage passed: comment_001 accepted at attempt 3 (two extraction
refusals, 1 and 2 findings), comment_002 and comment_003 at attempt 1. The world sealed
as `785bc4cdd43d2718a61bf670f352f29ede43b4f7e37f3140fb7255c9cb65dce1` before its first
vendor write (truth manifest and world spec in the truth bucket, the materialization
record inside). Token counts and latencies are in that sealed record, not in the log:
the summary lines print only after projection.

Projection stopped at the calendar: `POST /calendars` → 403 `usageLimits /
quotaExceeded`, "Calendar usage limits exceeded". A world is one secondary calendar per
employee (28) under one consumer OAuth principal; the first world's 28 exist, and this
run's creations hit Google's creation quota partway. The quota is a rate on calendar
creation. Google's Workspace Help ("Avoid Calendar use limits", verified 2026-09-14):
"Do not create more than 60 calendars in a short period", time to replenish "possibly
several hours" — the period and the reset undefined, consumer accounts not addressed;
community reports put the block at 4–24 hours. The first world's 28 creations were 6.5
hours before this run's, so the window likely spans both: 56 plus the probe's three,
at the threshold. Practical rule: one world's projection per day. The checkpoint
under `preparing/` holds the calendars made, so the run continues with
`--resume 785bc4cd…` once the quota lifts — the resume proves the sealed provenance and
adds only what is missing (find-verify-add). Not yet known: the window, and how many
calendars this run made before the refusal (the checkpoint says). Structural note for
the remaining M1 worlds: every world costs 28 calendar creations against that quota;
a rate-aware projection (spacing creations, or a calendar budget per run) or a
Workspace tenant are the candidates if a resume alone does not carry the golden world.

**Sixth run, the resume (2026-09-15, run 34954239073, 30 hours after the refusal).**
The quota had lifted: the calendar loop completed and the checkpoint holds 28 of 28
calendars. Then the Frappe site inspection refused before any write: the 28 employee
numbers are held by company `World WD674D5763`, the first world, on `hr-w1`. Employee
document names are site-unique and the world names employees by number, which is why a
site holds one world (`deploy/frappe/README.md`, ruled 2026-08-24) and the platform
contract says "one hostname per world version". The measurement world had been
dispatched onto the first world's site, and the earlier runs never reached the
inspection because the calendar loop runs first. The inspection did its job: the
refusal names the site and the holder, and nothing was written to Frappe or Jira.
Resume stays possible on a new site: the checkpoint compares the Frappe config (the
company, derived from the version) and takes the observed host fresh, "diagnostic,
free to differ". Ruled 2026-09-15 (Arda): a second world site `hr-w2`, the ticket in
the platform stream (`handoffs/2026-09-15-world-site-hr-w2.md`); the `benchmark`
environment's Frappe URL and key pair move to it; the same resume command runs again.
Box headroom measured the same day: 13.9 GB of 16 GB available, the Frappe stack about
1.2 GB used of its 5.4 GB cap, a site's database about 120 MB on disk; the scheduler
container (162 MB of 256 MB) is the one that scales with sites.

**Seventh run, the resume on `hr-w2` (2026-09-15, run 34961862557).** The platform
side landed the site the same day (record, stanza, `bench new-site`, scheduler; the key
pair and the `benchmark` environment's Frappe values swapped by the owner). The runner
reached the new hostname with no edge challenge, so acceptance 2's platform half
passed; the generator's first write was refused by ERPNext itself: `POST
/api/resource/Company` → 417, `LinkValidationError: Could not find Warehouse Type:
Transit`. A fresh site whose setup wizard never ran lacks the fixtures a Company links
to. The M0 Frappe probe completes that wizard over REST as its step 0 (`probes/frappe/
probe.py`, `ensure_setup`) and had done so on `hr-w1` on 2026-08-23, so the generator's
preparation, which took over every other piece of site setup (naming rule, custom
fields, grades, leave types, company, holiday list, approver, skills), never took this
one and never met the refusal until the first truly fresh site. The answer given to the
platform ticket that morning ("nothing per site beyond the recipe") was wrong by
exactly this step. Ruled the same day (option 1 of three, with an external reviewer's
notes adopted): preparation gains an explicit, idempotent base-site readiness step
before any benchmark-specific preparation — read `setup_complete`, complete the wizard
with fixed non-semantic bootstrap values when unset, read the flag back and refuse
loudly if still unset (the call's return is not trusted); the wizard's company is
scaffolding outside the fact surface; the recipe stays new-site, scheduler, key pair.
The site timezone and the fiscal year are the two bootstrap values that could reach a
record later read; a regression test on that seam is owed when a world outside 2026 /
Europe/Istanbul exists, not before. The Frappe cassette was re-recorded on `hr-w1`
(the no-op branch, 87 requests); the fresh branch's live proof is the eighth run.

**Eighth run, PASS (2026-09-15, run 34964654568, 248 s, 90 checkpoints), validated
and approved (run 34965191151, validator version 1, seven exactness checks, seven
fidelity checks, thirteen scenario views; verdict `verdicts/34965191151-1.json`).**
The readiness step completed the wizard on the fresh `hr-w2` and the projection ran
from the checkpoint's 28 calendars. The measurement world is live.

**The prose numbers, recovered.** The stage's counters (tokens, latency, retries) were
printed only after sealing returned in the same process; the fifth run sealed and then
died in the calendar loop, so they died with it, and the resume had no prose stage. The
sealed record holds attempts, refusals by guard, digests and the accepted propositions
only (session 24's log had claimed tokens and latencies were in it; they were not).
Bedrock's CloudWatch metrics (`AWS/Bedrock`, per model id, one-minute resolution)
carried them, attributed to each dispatch by its time window; the hour's sums (40
writer calls, 31 checker calls) reconcile exactly, the ten calls in no run window being
the local probes between runs 3 and 5. Writer Haiku 4.5, checker Nova Pro; latency the
per-call average:

| run | writer calls | writer in / out | checker calls | checker in / out | latency w / c |
|---|---|---|---|---|---|
| 1 (author's name demanded) | 12 | 5,848 / 406 | 0 | — | 936 ms / — |
| 2 (reversed pair aborted the stage) | 1 | 493 / 32 | 4 | 5,704 / 456 | 810 / 1,109 ms |
| 3 (offers read as ownership) | 12 | 5,848 / 414 | 12 | 17,091 / 1,421 | 869 / 1,038 ms |
| 5 (prose passed) | 5 | 3,209 / 133 | 5 | 7,431 / 522 | 827 / 953 ms |

Each failure's shape is legible in the calls alone: run 1 never reached the checker
(3 targets × the cap of 4, every draft refused by the scanner); run 2 is one writer
call and the checker's retry budget spent on the protocol failure; run 3 is twelve and
twelve. The passing run is five and five: about 640 tokens in and 27 out per writer
call at 0.8 s, about 1,490 in and 104 out per checker call at 1.0 s. Cost Explorer for
2026-09-14: $0.093 for the night's 71 calls (Nova Pro $0.063 under "Amazon Bedrock",
Haiku $0.030 under "Claude Haiku 4.5 (Amazon Bedrock Edition)", a separate service
line); the passing run's share, proportional to tokens, about $0.015 for three
comments. Ruled 2026-09-15: the counters are printed before sealing begins and sealed
into the materialization record (`metrics`, absent from records sealed before, the
decoder accepting either), so they travel with the world they measured.

**The gate on those numbers (2026-09-15, session 26).** Six questions, one per
exchange, an external low-context reviewer's read on each and Arda's ruling; the
outcome block sits under DESIGN's "The hard tiers under the step 15 rulings". The
evidence: the sealed record (attempts 3, 1, 1; two extraction refusals on
`comment_001`, 1 and 2 findings, bodies discarded by design), the three texts (in the
benchmark-private world spec, `world-spec/<version>.json` in the truth bucket — the
handoff had pointed at `scenario-specs.json`, which holds only the slices), the table
above, and the code of the four fixes (`a011245`, `adacec1`, `8e17a65` — the last
carries fixes 3 and 4 and the reversed-pair canonicalization, which the handoff had
credited to `adacec1`).

- **Fix 1, adopted;** the docstring tightened to the mechanism: the target supplies the
  first-person subject, only the subject's anchor group drops, positionally, so every
  employee-subject row puts the subject first. Residual: a third-person claim about a
  listed employee inside a comment still needs the name in the body; no brief exercises
  it; unplanned.
- **Fix 2 and the canonical pair, adopted.** Residuals: the swap's no-guess branch has no
  live case (no prose predicate pairs equal subject and value kinds); protocol retries
  at temperature zero protect only against provider-side variation — run 2 spent three
  on an identical failure — no change, the narrowed class rare. An untyped refusal is
  charged to the writer's attempts and was indistinguishable from a content refusal in
  the record until the reason counts below.
- **Fix 3, adopted,** credited to suppressing offers, which are coverage signals the class
  does not own. The allowed ownership is legitimate context that holds only where
  ownership is true; `comment_001`'s pass, in which the checker typed "something I can
  work through" as hedged ownership, is not credited to it. The two refusal bodies are
  unknowable (log and record hold counts). Cost, observed not estimated: about $0.003 per
  attempt (the passing run's Cost Explorer share over five attempts), about $0.012 per
  target at the old cap, about $0.036 for three capped targets.
- **Fix 4, adopted, the hedge tolerance narrowed in code** (this session's records
  commit): tolerated only when a structured record establishes the allowed fact, refused
  when only other prose does; an allowed fact never evidenced by its own target, checked
  at construction. No digest moved, no version bump; the measurement world's hedged
  ownership is evidenced on the ticket's owner field and stays tolerated.
- **The cap, raised to eight.** The sensitivity arithmetic, on the one target's
  three-attempt pass read as a one-in-three per-attempt rate (a point estimate on one
  target, not a measurement): exhaustion at cap four about 20% per such target, at
  eight about 4%; five such targets in a world, about 67% and 18% that at least one
  exhausts. What the world showed is that "maximum observed three" justifies no cap;
  eight is a margin. An exhausted run re-dispatches sealing only. Attempts above four
  are read as a struggling brief at the audit; no new field.
- **Refusal feedback, rejected for M1** (DESIGN's outcome block has the reasons and the
  trigger).
- **Sealed refusal reasons and a canonicalized-pair counter, adopted;** the next commit,
  before the responsibility class's first measured world; old records decode the reasons
  as unavailable, never zero.
- **The three-character cut, retained** as a heuristic without contrary evidence; the
  sentence-start false refusal added to the existing test that pins both sides.
- **The hand sample, Arda's read:** `comment_002` and `comment_003` state exactly the
  planted skill, read correctly and completely; `comment_001`'s skill read correctly,
  its hedged ownership not in the text — checker overreach, the request's carrier line
  (the ticket's name beside the author) the only ownership cue, a hypothesis on one
  sample; the text a mild register slip (capability with a shade of willingness), not
  an offer. Three of three required facts right, one of three texts over-extracted, a
  sample of three that supports no rate. The three texts share one sentence frame
  ("I've worked with X before, so …") at temperature 0.7; the golden audit looks for
  the shape.

**Torn down 2026-09-15 (session 27).** The site `hr-w2` dropped on the box (`bench drop-site --no-backup --force`; database and user gone, the site folder archived in the bench); the platform's trigger row notes it fired, the edge stanza and record are platform's removal. Everything the gate ruled on survives the site: the sealed bundle and the verdict `verdicts/34965191151-1.json` in S3, the numbers above, the prose in the benchmark-private world spec. The world is no longer live anywhere; a re-read of its live shape would be a regeneration under the current generator, a new version.

## source-dependence — the step 8 carry probed at the responsibility class (2026-09-15)

A design-time probe, run on the unit fixtures at the 15.2 interview's second question
(the scripts committed as tooling under `probes/prose/` at `61b3f14`, the construction test that pins the first finding in the suite).
The carry from step 8: the foreign-fact required-sources drift test lands with the first
class whose dependence rests on a source none of its own artifacts require.

**The class requires the tracker with no tracker artifact.** The responsibility shape as
DESIGN rules it, built on the fixture organization (seed 7) with `construct` and the
required-sources rule:

| construction | required sources | verdicts |
|---|---|---|
| section naming the leaver, no clause | corpus, frappe | one viable |
| section + a procedure clause requiring Kafka applied to the section | corpus, frappe, jira | one viable, one non-viable by skill |
| the same + a foreign Jira comment restating the viable one's Kafka | corpus, frappe, jira | unchanged |
| the same + a foreign Jira comment giving the non-viable one Kafka | corpus, frappe, jira | the verdict moves |

The tracker enters through the known-negative: a candidate known not to hold a skill
needs both the HR record and the tracker to have answered, and assessments run over the
whole organization. The constraint on a section artifact was accepted by the existing
viability rule and construction verified clean, no `core` change.

**No current class produces silent drift.** Two more fixtures, foreign facts added to
the truth base and the conclusions tuple compared with the required set:

| class | foreign fact | conclusions | required set |
|---|---|---|---|
| qualification (skill only in a Jira comment) | a Jira comment restating the skill | unchanged | unchanged (calendar, corpus, frappe, jira) |
| qualification | a Jira ticket the candidate owns, due in the leave | unchanged | unchanged |
| contact-in-note, no clause | a Jira comment giving the candidate a skill | unchanged | unchanged (corpus, frappe) |
| contact-in-note, no clause | a Jira ticket the candidate owns, due in the leave | unchanged | unchanged |

Registry facts the argument rests on: the skill predicate's evidence domain is the HR
record and the tracker (a corpus fact of it is refused at construction; the composite's
ruling widened it to the corpus on 2026-09-15, re-probed below); ticket ownership
over the tracker and the corpus is single-valued and the corpus is never promoted under
a tracker outage. The conclusion and its re-arm conditions are DESIGN's (the 15.2
interview's second ruling).

**The cardinality class, probed at 15.3 (2026-09-15, the same two scripts).** The class
plants a ticket, so the tracker is required by provenance as well as by the known-negative
of the skill-failing candidate; the corpus by the policy, the HR record by the leave and the
employment type. On the fixture organization (seed 7 under generator version 10):

| construction | required sources | verdicts |
|---|---|---|
| the release, the two-person clause with skill and employment | corpus, frappe, jira | two viable, one non-viable by hard rule, one by skill |
| the same + a foreign tracker comment restating a viable holder's skill | unchanged | unchanged |
| the same + a foreign tracker comment giving the skill-failing candidate the skill | unchanged | the verdict moves |
| the same + a foreign tracker ticket a viable holder owns, due in the leave | unchanged | unchanged |

No silent drift: the one foreign fact that changes anything changes a verdict, and the
required set never moves. The employment rule is out of any foreign fact's reach, since the
predicate's evidence domain is the HR record alone, which is the reading the 15.2 argument
predicted for a class whose clause adds a criterion without adding a source.

**The skill predicate admits the corpus, re-probed at 15.4 (2026-09-15, the same two
scripts).** The composite's first ruling adds the corpus to the skill predicate's evidence
domain so a client note's section can evidence a candidate's skill. The change is global,
not the class's: a skill is a set, so a second positive source adds evidence and never a
conflict, and a known-negative on a skill now needs the HR record, the tracker and the
corpus to have answered. Both scripts run before and after the row change, the outputs
byte-identical: every clause-bearing construction already required the corpus through its
clause, the clause-free contact-in-note fixture has no skill known-negative, and the
structured tier authors no skill reason. What the change moves is the runtime rule the
investigator inherits: under a corpus outage nobody is found to lack a skill (DESIGN's 15.4
block).

## section-probe — the responsibility register through writer and checker, unsealed (2026-09-15)

The workstation probe the 15.2 rulings asked for before the class's first sealed world:
six constructions of the responsibility class over the fixture organization (six
clients, six contacts, six skills), each through one writer call, the two free guards,
one checker call and the containment guard, the text and the raw tool input read by
hand. Development probing under the SSO profile from the workstation, nothing sealed, no
rate claimed; Haiku 4.5 writing, Nova Pro checking, about three cents for the three runs.
Three runs, one change each, so every effect is attributable:

| run | change | accepted | dominant refusal |
|---|---|---|---|
| 1 | as committed (`8f8b5a9`) | 0 of 6 | the checker put the person as the subject and the client as the value of the responsibility, untyped on every text |
| 2 | the carrier rows' value-form line: the subject is the text itself (written as unknown), the value the employee the text names | 1 of 6 | other claims on the padding sentences (5 of 6, twice the required sentence itself filed beside its own proposition), a requirement hallucinated from "should be directed to" (2), the client read as a team value (2) |
| 3 | the client-note length one or two sentences; a statement recorded as a proposition, or one restating it, is never an other claim | 6 of 6 | none |

What the raw extractions showed. Told only "the subject is the clause", a checker with
no clause in its entity list read "Deniz is the contact responsible for the Northwind
account" as Deniz names-responsible Northwind; the parser binds a carrier row's subject to
the target whatever the checker wrote, so only the value's side needed saying. With one
fact, no allowed context and a length of two to four sentences, every extra sentence was
a paraphrase of the fact, and the checker filed it as an other claim about half the time
and turned it into a requirement twice; the length was the padding's source. The client
stayed in the checker's entity list (it is the scope guard of the review P2), since its
one symptom vanished with the padding.

The hand read of the six accepted texts, against the ruled checklist: the employee named
explicitly, six of six; the relation bound to the section with no author identity, six of
six; no invented claim, no first person, no hedge, no other claim, six of six. The
finding to carry: the six texts are one sentence with the names swapped, the brief's fact
line echoed, the sentence-frame convergence the gate flagged at its limit. The cause is
structural: the section has one fact and no context, and every elaboration was refused,
so the accepted shape is the fact restated. Accepted for M1 on record (the 15.2 addendum
in DESIGN); the golden audit reads the frame across the class.

**The composite's section, two facts of different subject shape (2026-09-15, 15.4; the
probe script takes the class by `PROBE_CLASS`).** The gate the composite's first ruling set
before its class commit: one section carrying the contact naming (subject the section
itself) and the cover's skill (subject the cover), the checker extracting both with the
right subjects and no extra proposition. Six constructions over the fixture organization,
the same models, two runs of one change each:

| run | change | accepted | refusal |
|---|---|---|---|
| 1 | as built | 4 of 6 | the checker's tool input without `other_claims` at all (twice), a schema field it marks required; every text carried both facts with the right subjects |
| 2 | the checker's system prompt: fill `other_claims` on every call, an empty list when there is nothing of that kind | 6 of 6 | none; the six texts identical to run 1's |

What the raw extractions showed. Both facts extracted on all twelve texts: the skill as a
proposition on the cover's id with the skill's vocabulary key, the naming as a proposition
the checker anchors on the person (subject and value the contact's id), which the carrier
rule accepts since a fact whose subject is the carrier anchors on its value alone. The
omission of an empty `other_claims` is a checker-format fault, not a text fault, and it
costs more than one attempt: the attempt loop re-checks the same text on a malformed
extraction, at temperature zero, so a repeatable omission exhausts the checker's retries and
aborts the target. Six of six after the sentence is a sample, not a rate; the audit at step 16
reads the sealed checker retry counts. The sentence frame: six of six two-sentence texts, each
sentence the brief's own fact description with the client's name in place of "the account
this note covers", the second fact varying nothing about the first's frame. Recorded, not
tuned, per the composite's second ruling; the human audit reads the realized texts.
