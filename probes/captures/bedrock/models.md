# Bedrock shortlist — what the instance role could call on 2026-08-26

Runs: `probes/bedrock/probe.sh` over `ssm send-command` on `i-0608c819327c72beb` —
run 1 (`9321c6da…`, `probe-run-1.jsonl`, before the Anthropic use-case form) and
run 2 (`915c20a6…`, `probe-run-2.jsonl`, ~10 min after submitting it; Sonnet 4.6
added to the shortlist between runs). The table shows the latest state per row.
Prices per 1M tokens. Provenance per column: Nova rows from the AWS Pricing API
(`pricing-eu-central-1-raw.json`, pulled 2026-08-26); Anthropic rows from the
Bedrock pricing page's Anthropic tab, read in a browser 2026-08-26 (the page is
a dynamic table — the Pricing API carries no current Anthropic SKUs, only the
legacy Claude 2/3 US rows). First-party API reference prices from Anthropic's
own table as cached 2026-06-24 in the claude-api skill.

| profile (`eu.`) | round-trip | tool-use | prompt cache | in / out (`eu.`) | in / out (`global.`) | cache write / read (`eu.`) | first-party in / out |
|---|---|---|---|---|---|---|---|
| anthropic.claude-haiku-4-5 | run 1 BLOCKED (use-case form); run 2: 750 ms model / 1547 ms wall, "ok" | `toolUse` emitted, input `{"employee_id":"emp_001"}` | write 4842 → read 4842 | 1.10 / 5.50 | 1.00 / 5.00 | 1.375 / 0.11 | 1.00 / 5.00 |
| anthropic.claude-sonnet-5 | BLOCKED — "not available for this account … contact AWS Sales" | — | — | 2.20 / 11.00 ¹ | 2.00 / 10.00 ¹ | 2.75 / 0.22 | 3.00 / 15.00 (2.00 / 10.00 intro to 2026-08-31) |
| anthropic.claude-opus-5 | BLOCKED — same account gate as Sonnet 5 | — | — | 5.50 / 27.50 | 5.00 / 25.00 | 6.875 / 0.55 | 5.00 / 25.00 |
| anthropic.claude-sonnet-4-6 (added run 2) | run 2 form-gated (propagation); run 3 (`3556a26e…`, 20:18): 872 ms, "ok" | one `ResourceNotFound` flap, then 3/3 `toolUse` with `{"employee_id":"emp_001"}` (`4d298d91…`) | write 4843 → read 4843 | 3.30 / 16.50 | 3.00 / 15.00 | 4.125 / 0.33 | 3.00 / 15.00 |
| amazon.nova-lite-v1 | 272 ms model / 1083 ms wall, "OK" | `toolUse` emitted, `stopReason=tool_use` | write 5172 → read 5172 | 0.078 / 0.312 | — | 0 / 0.0195 | — |
| amazon.nova-pro-v1 | 360 / 1162 ms, "Understood!" | `toolUse` emitted | write 5172 → read 5172 | 1.05 / 4.20 | — | 0 / 0.2625 | — |
| amazon.nova-2-lite-v1 | 523 / 1316 ms, "ok" | `toolUse` emitted | write 4886 → read 4886 | 0.429 / 3.597 | 0.39 / 3.27 | 0 / 0.107 | — |

¹ Bedrock lists Sonnet 5 at the first-party *intro* rate without labelling it;
expect 3.30 / 16.50 (`eu.`) and 3.00 / 15.00 (`global.`) after 2026-08-31.

Facts around the table:
- `eu.` profiles = `global.` + 10 % flat, for every Anthropic model; there is no
  separate Frankfurt list. `global.` may route outside the EU — a residency
  ruling for design session part 2 (synthetic data, so a story choice).
- The "Public Extended Access, 2×" rate seen earlier applies only to legacy
  Claude 3.5 Sonnet rows (6.00 / 30.00). Not a factor for any current model.
- The use-case form (submitted 2026-08-26 ~20:02 from the Frankfurt playground's
  first Haiku call — the console offers it on first invoke, the old "Model access"
  page is retired) opened Haiku 4.5 within 3 minutes. It did not move the
  5-series / Opus 4.8 gate (re-tested after: still "not available for this
  account"). Sonnet 4.6 went the other way for a while — open before the form,
  form-gated after it, then `AccessDenied` for six minutes, open again at 20:15:58
  (14 min after submitting) with one more flap during run 3. Propagation is
  per-model and non-monotonic; a fresh account should budget 20 minutes and a
  retry loop, not trust the first answer either way.
- Prompt-cache reads across `eu.` are not guaranteed: Nova Pro missed once in five
  passes (run 2 wrote 5172 again on its second call; three SSO passes right after
  all read 5172). The profile can route a call to a region that hasn't seen the
  prefix — an M2 cost-model fact, not a capability gap.
- Nova cache floors are met at ~5k tokens; cache *write* is free on Nova, reads
  cost ~25 % of input. Nova Lite's identical write→read token counts across two
  passes are the proof the cache actually engaged, not a reported capability.
- The Claude failures are account gates, not the role: the same two errors
  reproduce from an AdministratorAccess SSO session. `get-foundation-model-
  availability` reports AUTHORIZED / AVAILABLE for every one of them — the
  control-plane API does not reflect what the runtime enforces.
- Outside the shortlist, from the SSO session: `eu.anthropic.claude-sonnet-4-6`
  answered (8 in / 35 out) with no form; `eu.anthropic.claude-opus-4-8` is
  "not available for this account" like the 5-series.
- Nova Pro in the Pricing API has no `eu.` in-region *cache-write* row and Nova
  Lite v1 has no cache-write row at all — both still cached in practice.
