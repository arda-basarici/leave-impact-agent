set -uo pipefail
REGION=eu-central-1
cd /srv/app || exit 9
echo "P1 DEPLOYED=$(cat DEPLOYED 2>/dev/null || echo none)"
docker images ghcr.io/arda-basarici/leave-impact-agent --format 'P1 image {{.Tag}} {{.CreatedAt}}' | head -3
df -h / | tail -1 | awk '{print "P1 disk used " $3 " of " $2 " (" $5 ")"}'
param() { aws ssm get-parameter --region "$REGION" --with-decryption --name "$1" --query Parameter.Value --output text; }
for n in frappe-api-key frappe-api-secret jira-email jira-token google-authorized-user-json; do
  v=$(param /leave-agent/$n 2>/dev/null) || { echo "P2 $n READ-FAILED"; continue; }
  case "$v" in UNSET*) echo "P2 $n UNSET";; "") echo "P2 $n EMPTY";; *) echo "P2 $n set";; esac
done
export APP_TAG="$(cat DEPLOYED)" PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(param /leave-agent/postgres-password); export POSTGRES_PASSWORD
export LEAVE_IMPACT_WORLD_BUCKET=leave-impact-world-445743457479 LEAVE_IMPACT_AWS_REGION="$REGION"
echo "<base64 of probe.py>" | base64 -d > /tmp/probe.py && chmod 644 /tmp/probe.py
docker compose run --rm --no-deps -v /tmp/probe.py:/tmp/probe.py:ro \
  -e P_WORLD_VERSION=7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4 \
  -e P_FRAPPE_BASE_URL=https://hr-w3.ardabasarici.dev \
  -e P_JIRA_BASE_URL=https://api.atlassian.com/ex/jira/9a47936a-48cf-49fb-83c1-c720400755af \
  -e P_MODEL=eu.anthropic.claude-haiku-4-5-20251001-v1:0 \
  -e P_COUNT_MODEL=anthropic.claude-haiku-4-5-20251001-v1:0 \
  -e P_FRAPPE_API_KEY="$(param /leave-agent/frappe-api-key)" \
  -e P_FRAPPE_API_SECRET="$(param /leave-agent/frappe-api-secret)" \
  -e P_JIRA_EMAIL="$(param /leave-agent/jira-email)" \
  -e P_JIRA_TOKEN="$(param /leave-agent/jira-token)" \
  -e P_GOOGLE_JSON="$(param /leave-agent/google-authorized-user-json)" \
  app python /tmp/probe.py
echo "P9 container exit $?"
rm -f /tmp/probe.py
