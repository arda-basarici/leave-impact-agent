#!/bin/bash
# The tick-cost probe's host script (the demo milestone's step 15), sent to the app host
# over SSM by send.ps1 with probe.py spliced in as base64, so the host fetches nothing.
# It prints the host's shape and the deployed sha, then runs the probe once in a one-off
# container of the deployed image on the stack's network (`--no-deps`: PostgreSQL is the
# running service; the container's memory is its own cgroup) and prints the reading. The
# working directory is printed first: SSM truncates a command's stdout at 24,000
# characters, and a truncated read is re-fetched from the file there by a second command.
# The Compose preamble is the lifecycle's (the password from Parameter Store, never
# printed). The ledger is the probe's own argument, the replay set's, independent of the
# demo configuration (which names the visitors' ledger since this step's first group).
set -u
REGION=eu-central-1
LEDGER=${LEDGER:-ledger-demo}
REPETITIONS=${REPETITIONS:-20}

WORK=$(mktemp -d /tmp/tick-cost.XXXXXX)
chmod 755 "$WORK"
echo "work $WORK"
echo "<base64 of probe.py>" | base64 -d > "$WORK/probe.py"
chmod 644 "$WORK/probe.py"

echo "== host $(date -u +%FT%TZ)"
uname -r
echo "cpus $(nproc)"
lscpu | grep -E 'Model name|Architecture' || true
cd /srv/app || exit 1
echo "deployed $(cat DEPLOYED)"
APP_TAG=$(cat DEPLOYED); export APP_TAG
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(aws ssm get-parameter --region "$REGION" --with-decryption --name /leave-agent/postgres-password --query Parameter.Value --output text) || exit 1
export POSTGRES_PASSWORD
docker compose ps --format '{{.Name}} {{.State}} {{.Status}}'

echo "== probe ledger=$LEDGER repetitions=$REPETITIONS $(date -u +%T)"
docker compose run --rm -T --no-deps -v "$WORK/probe.py:/tmp/probe.py:ro" app \
  python /tmp/probe.py --ledger "$LEDGER" --repetitions "$REPETITIONS" \
  > "$WORK/reading.json" 2> "$WORK/probe.err" < /dev/null
echo "probe exit $?"
# Compact, since SSM cuts a command's stdout at 24,000 characters and the indented reading
# over thirty attempts passed it once the idle figures joined (the second run, fetched whole
# from this directory by a second command); the file keeps the indented form.
echo "== reading"
python3 -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1])),separators=(',',':')))" "$WORK/reading.json"
echo "== stderr (first lines)"
sed -n 1,8p "$WORK/probe.err"
echo "== done $(date -u +%T)"
