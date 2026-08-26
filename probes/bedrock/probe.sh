#!/bin/bash
# Bedrock probe — runs ON THE INSTANCE (over `ssm send-command`) so every call
# is authorised by the instance role's `invoke-shortlisted-models` policy, not
# by a human's SSO session. Three facts per shortlisted model, one JSON line
# each: a plain Converse round-trip (availability + latency), a Converse call
# with a tool the prompt demands (does the model emit a `toolUse` block?), and
# the same ~3k-token cached system prompt sent twice (does `cacheWriteInputTokens`
# then `cacheReadInputTokens` move?). Nothing here is a benchmark — the model
# choice waits for M2's measurements; this records what exists and how it bills.
set -uo pipefail
REGION=eu-central-1
MODELS=(
  eu.anthropic.claude-haiku-4-5-20251001-v1:0
  eu.anthropic.claude-sonnet-5
  eu.anthropic.claude-opus-5
  eu.amazon.nova-lite-v1:0
  eu.amazon.nova-pro-v1:0
  eu.amazon.nova-2-lite-v1:0
)

# A cacheable prefix has a per-model floor (Claude Haiku 2048 tokens, Nova ~1k);
# ~3k tokens of deterministic filler clears every floor without a real document.
FILLER=$(for i in $(seq 1 220); do printf 'Policy clause %d: employees on approved leave hand over open work to a named substitute before the leave starts. ' "$i"; done)
CACHED_SYSTEM=$(jq -cn --arg t "$FILLER" '[{"text":$t},{"cachePoint":{"type":"default"}}]')

TOOLS='{"tools":[{"toolSpec":{"name":"lookup_employee","description":"Look up an employee record by id.","inputSchema":{"json":{"type":"object","properties":{"employee_id":{"type":"string"}},"required":["employee_id"]}}}}]}'

converse() { # $1 model, $2 extra args… ; prints the JSON response or an {"error":…} object
  local model=$1; shift
  local out err; local t0=$(date +%s%N)
  out=$(aws bedrock-runtime converse --region "$REGION" --model-id "$model" --output json "$@" 2>&1)
  local rc=$?; local ms=$(( ($(date +%s%N) - t0) / 1000000 ))
  if [ $rc -ne 0 ]; then jq -cn --arg e "$out" --argjson ms "$ms" '{error:$e, wallMs:$ms}'; else echo "$out" | jq -c --argjson ms "$ms" '. + {wallMs:$ms}'; fi
}

for m in "${MODELS[@]}"; do
  plain=$(converse "$m" --messages '[{"role":"user","content":[{"text":"Reply with the single word: ok"}]}]')
  echo "$plain" | jq -c --arg m "$m" '{model:$m, probe:"plain", text:(.output.message.content[0].text? // null), usage, latencyMs:.metrics.latencyMs?, wallMs, error}'

  tool=$(converse "$m" --messages '[{"role":"user","content":[{"text":"Use the lookup_employee tool to fetch employee emp_001. Do not answer without calling the tool."}]}]' --tool-config "$TOOLS")
  echo "$tool" | jq -c --arg m "$m" '{model:$m, probe:"tool", stopReason, toolUse:([.output.message.content[]? | select(.toolUse) | .toolUse] | first // null), usage, error}'

  for pass in 1 2; do
    c=$(converse "$m" --system "$CACHED_SYSTEM" --messages '[{"role":"user","content":[{"text":"How many policy clauses are there? Answer with a number only."}]}]')
    echo "$c" | jq -c --arg m "$m" --argjson p "$pass" '{model:$m, probe:"cache", pass:$p, text:(.output.message.content[0].text? // null), usage, error}'
  done
done
