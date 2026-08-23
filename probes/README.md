# Probes — the preregistered plan

Each probe states its pass criterion *before* it runs (DESIGN's "the probe days"
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
| **jira** — Jira Cloud free tier. Ruled before running (2026-08-23, DESIGN "The world's shape"): synthetic employees are a single-select custom field keyed by employee id, `assignee` unassigned; the probe tests that model, not bare CRUD | (a) a single-select custom field `Synthetic Owner` created over REST on Free with ≥ 3 options (`emp_001 — Probe Alice` …) and shown on the project's create screen; (b) issues created with an option set, `assignee` empty, a `scenario:<id>` label; (c) JQL `"Synthetic Owner" = "emp_001 — Probe Alice"` returns exactly that person's issues; (d) a comment naming a synthetic person round-trips; (e) CSV import (UI wizard — no REST importer) with backdated `created`/`resolved` on 3 issues, read back over REST, dates recorded as-is — pass or fail is a finding, it gates the history ruling's scope; (f) a second run creates no duplicates (issue keys remembered in a manifest outside captures). The 10-user ceiling is no longer a criterion — it does not bind under the ruled model | `captures/jira/` field definition, options, issue payloads, JQL results, CSV read-back |
| **seed-spike** — one command lands 5 people / 1 project / a week of meetings / 2 leaves into all three systems | same org visible in all three; a second run creates no duplicates | `captures/seed-spike/` run logs ×2 |

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
