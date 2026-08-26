#!/bin/bash
# Slack probe — a developer-sandbox workspace, one bot token, one channel:
# post a message, read it back. Non-blocking for M0 by the plan's own rule; a
# failure is recorded and the milestone exits anyway. The token comes from the
# environment (SLACK_BOT_TOKEN — never a file in this repo, never chat); the
# channel id from SLACK_CHANNEL. Output: the raw API responses, one per line,
# for `captures/slack/`.
set -euo pipefail
: "${SLACK_BOT_TOKEN:?bot token (xoxb-…) in the environment}"
: "${SLACK_CHANNEL:?channel id (C…) the bot is a member of}"

api() { curl -fsS -H "Authorization: Bearer $SLACK_BOT_TOKEN" "$@"; }

echo '# auth.test'
api https://slack.com/api/auth.test | jq -c '{ok, team, user, bot_id, error}'

echo '# chat.postMessage'
posted=$(api -H 'Content-Type: application/json; charset=utf-8' \
  -d "{\"channel\":\"$SLACK_CHANNEL\",\"text\":\"leave-impact probe $(date -u +%FT%TZ): Probe Alice hands the W1 sprint review to Bob during her leave.\"}" \
  https://slack.com/api/chat.postMessage)
echo "$posted" | jq -c '{ok, ts, channel, error}'
ts=$(echo "$posted" | jq -r .ts)

echo '# conversations.history (read back the same message by ts)'
api "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL&oldest=$ts&inclusive=true&limit=1" \
  | jq -c '{ok, error, messages: [.messages[] | {ts, user, text}]}'
