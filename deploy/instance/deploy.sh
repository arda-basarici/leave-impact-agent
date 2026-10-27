#!/bin/bash
# Lands one commit of the application on the host. Run as root on the instance
# by the workflow's deploy job over `ssm send-command` (never by hand — the
# job's approval gate is the only path to production), with DEPLOY_SHA and
# DEPLOY_DIGEST in the environment: the full commit sha, which is also the image
# tag CI pushed, and the manifest digest CI recorded for the image it built.
#
# What "deploy" means here: the compose file *of that commit* plus the image
# *of that commit*; the file fetched by sha and the image pulled by its digest, so
# the host runs exactly the bytes CI built and smoked, since a tag is a label the
# registry can move and the digest is the image's identity (the freeze step, fork 10
# with fork 32's split). A rollback is this script with an older sha and its digest.
# Secrets come from Parameter Store into the process environment for `compose up` —
# nothing is rendered to
# disk (compose.yaml's own rule). A failing `aws` inside `param` ends the deploy with
# the CLI's own error (the explicit return and `inherit_errexit`, as lifecycle.sh).
set -euo pipefail
shopt -s inherit_errexit

: "${DEPLOY_SHA:?full commit sha to deploy}"
: "${DEPLOY_DIGEST:?the manifest digest CI recorded for the image of that commit}"
REPO=arda-basarici/leave-impact-agent
REGION=eu-central-1
APP_DIR=${APP_DIR:-/srv/app}

# A parameter's value, or a failed deploy when it still holds the `UNSET` placeholder
# the platform stack creates it with (its ceremony puts the real value): a placeholder
# handed to compose would reach a host as a credential and fail there, later and worse.
param() {
  local value
  value=$(aws ssm get-parameter --region "$REGION" --with-decryption --name "$1" --query Parameter.Value --output text) || return $?
  case "$value" in
    UNSET*) echo "parameter $1 is not put: it still holds the UNSET placeholder" >&2; return 1 ;;
  esac
  printf '%s' "$value"
}

cd "$APP_DIR"
# One deploy on this host at a time, beside the workflow's concurrency group (for a
# command sent by hand, or two runs the group did not see). The lock is a descriptor the
# shell holds for the script's life, so a deploy that dies releases it, where a lock
# directory would outlive its maker; `-n` refuses at once rather than queueing behind a
# deploy whose state this one cannot know. Taken before anything is fetched or pulled.
exec 9> "$APP_DIR/deploy.lock"
flock -n 9 || { echo "another deploy holds $APP_DIR/deploy.lock; this one is refused" >&2; exit 1; }
curl -fsSL "https://raw.githubusercontent.com/$REPO/$DEPLOY_SHA/compose.yaml" -o compose.yaml

export APP_TAG="$DEPLOY_SHA"
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(param /leave-agent/postgres-password)
export POSTGRES_PASSWORD

# The app image by its digest, then given the sha tag the compose file names, so
# compose finds the tag present and pulls nothing for it; the service image is pulled
# by compose under its own pinned tag.
docker pull --quiet "ghcr.io/$REPO@$DEPLOY_DIGEST"
docker tag "ghcr.io/$REPO@$DEPLOY_DIGEST" "ghcr.io/$REPO:$DEPLOY_SHA"
docker compose pull --quiet postgres
docker compose up -d --wait postgres
# The corpus cache: every world under `worlds/` the serving rule admits is loaded
# into PostgreSQL under its version, verified against its manifest, and marked
# ready; a refusal fails the deploy here, before the application is declared
# landed. The bucket name is the platform contract's literal (the boundary probe
# below names the same bucket); the credentials are the instance role's, reached
# through the metadata service from inside the container (hop limit 2).
export LEAVE_IMPACT_WORLD_BUCKET=leave-impact-world-445743457479
export LEAVE_IMPACT_AWS_REGION="$REGION"
docker compose run --rm app python -m leaveimpact.cache
# The run log's schema, the same way: tables created where missing, the version row
# written where absent, the version checked, and a mismatch fails the deploy here.
# Nothing else creates them; the first live dispatch (2026-10-13) reached an instance
# that had never been bootstrapped and refused at its first ledger command.
docker compose run --rm app python -m leaveimpact.agent bootstrap-log
# The demo surface's own schema (the table of publishable attempts and its version row),
# the same way and apart from the log's: the readiness route reports the version as its
# third bit, so a deploy that skipped this line fails at the readiness check below.
docker compose run --rm app python -m leaveimpact.app bootstrap
# Two named checks, neither the sole gate (the demo entry's HTTP-shell ruling).
# The image check: the identity command states the commit the image was built from,
# the deploy's evidence since the `oidc-deploy` probe, and a container that cannot say
# so fails here before the service starts.
# The command is spelled whole: a `run` argument replaces the image's CMD, so a bare
# `identity` would be looked up as an executable, as the lifecycle's commands know.
IDENTITY=$(docker compose run --rm app python -m leaveimpact identity)
echo "identity: $IDENTITY"
[[ "$IDENTITY" == "leaveimpact $DEPLOY_SHA:"* ]]
# The readiness check: the service started and `--wait` returns on the compose
# healthcheck, which reads the readiness route; the bounded wait fails the deploy on
# a service that never becomes ready. The route's body is then read once more and
# printed as the deploy's evidence, and its revision must be the deployed sha, so a
# stale container answering "ready" cannot pass for the new one. On a failure here
# the script stops: the DEPLOYED marker below keeps the previous sha, the new
# container stays as it is for diagnosis, and a rollback is this script with the
# older sha and its digest.
docker compose up -d --wait --wait-timeout 120 app
READY=$(docker compose exec -T app python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=8).read().decode())")
echo "ready: $READY"
grep -q "\"code_version\":\"$DEPLOY_SHA\"" <<< "$READY"
grep -q '"ready":true' <<< "$READY"

# Every deploy pulls a new image and nothing ever removed the old ones: about 130
# deploys in a week filled the 12 GB root and the pull itself failed (2026-09-15,
# 134 images, 8.6 GB reclaimed by hand). A rollback pulls its sha again, so only
# the deployed image stays; the id is what is removed, since one id may carry
# several tags. awk, not grep -v: nothing to prune is the steady state, and
# grep's no-match exit is a failure under pipefail (the first deploy of this
# block failed exactly there, 2026-09-15).
KEEP_ID=$(docker images -q "ghcr.io/$REPO:$DEPLOY_SHA")
docker images "ghcr.io/$REPO" --format '{{.ID}}' | sort -u | awk -v keep="$KEEP_ID" '$1 != keep' \
  | xargs -r docker image rm -f
docker image prune -f

echo "$DEPLOY_SHA" > "$APP_DIR/DEPLOYED"
echo "deployed $DEPLOY_SHA ($DEPLOY_DIGEST) at $(date -u +%FT%TZ)"
