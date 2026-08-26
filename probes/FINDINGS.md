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
  sha. (The next commit's deploy flips that line — recorded below when it lands.)
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
