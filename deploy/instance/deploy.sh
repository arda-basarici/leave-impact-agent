#!/bin/bash
# Lands one commit of the application on the host. Run as root on the instance
# by the workflow's deploy job over `ssm send-command` (never by hand — the
# job's approval gate is the only path to production), with DEPLOY_SHA in the
# environment: the full commit sha, which is also the image tag CI pushed.
#
# What "deploy" means here: the compose file *of that commit* plus the image
# *of that commit*; both fetched by sha so the host runs exactly what CI tested,
# and a rollback is this script with an older sha. Secrets come from Parameter
# Store into the process environment for `compose up` — nothing is rendered to
# disk (compose.yaml's own rule).
set -euo pipefail

: "${DEPLOY_SHA:?full commit sha to deploy}"
REPO=arda-basarici/leave-impact-agent
REGION=eu-central-1
APP_DIR=/srv/app

param() { aws ssm get-parameter --region "$REGION" --with-decryption --name "$1" --query Parameter.Value --output text; }

cd "$APP_DIR"
curl -fsSL "https://raw.githubusercontent.com/$REPO/$DEPLOY_SHA/compose.yaml" -o compose.yaml

export APP_TAG="$DEPLOY_SHA"
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(param /leave-agent/postgres-password)
export POSTGRES_PASSWORD

docker compose pull --quiet
docker compose up -d --wait postgres
# The baseline app has no long-running service yet: it identifies itself and
# exits, and that identity line is the deploy's evidence (the `oidc-deploy`
# probe's "response"). Flips to `up -d app` with the first service entry point.
docker compose run --rm app

echo "$DEPLOY_SHA" > "$APP_DIR/DEPLOYED"
echo "deployed $DEPLOY_SHA at $(date -u +%FT%TZ)"
