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
