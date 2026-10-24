#!/bin/bash
# The memory baseline's host script (the demo milestone's step 10), sent to the app host
# over SSM by send.ps1 with loader.py and sampler.py spliced in as base64, so the host
# fetches nothing. It prints the host's shape, then runs the eight levels the probe plan
# names: each starts the loader in a one-off container of the deployed image on the
# stack's network (`--no-deps`, stdin closed, the script bind mounted, its memory in its
# own cgroup), samples the host and the stack's containers three times while the load
# holds, waits for the loader's summary, and settles before the next. The working
# directory is printed first: SSM truncates a command's stdout at 24,000 characters, so a
# truncated read is re-fetched from the files there by a second command. The Compose
# preamble is the publish list's (the password from Parameter Store, never printed).
set -u
REGION=eu-central-1
HOLD=${HOLD:-45}
SETTLE=${SETTLE:-15}

WORK=$(mktemp -d /tmp/memory-baseline.XXXXXX)
chmod 755 "$WORK"
echo "work $WORK"
echo "<base64 of loader.py>" | base64 -d > "$WORK/loader.py"
echo "<base64 of sampler.py>" | base64 -d > "$WORK/sampler.py"
chmod 644 "$WORK/loader.py" "$WORK/sampler.py"

echo "== host $(date -u +%FT%TZ)"
uname -r
echo "cpus $(nproc)"
if swapon --show --noheadings | grep -q .; then swapon --show; else echo "no swap"; fi
docker info --format 'cgroup {{.CgroupDriver}} v{{.CgroupVersion}} docker {{.ServerVersion}}'
cd /srv/app || exit 1
echo "deployed $(cat DEPLOYED)"
APP_TAG=$(cat DEPLOYED); export APP_TAG
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(aws ssm get-parameter --region "$REGION" --with-decryption --name /leave-agent/postgres-password --query Parameter.Value --output text) || exit 1
export POSTGRES_PASSWORD
# Under the exports: Compose interpolates the file before it lists (the first run's
# "before" line printed interpolation errors instead of the state).
docker compose ps --format '{{.Name}} {{.State}} {{.Status}}'

sample() {
  python3 "$WORK/sampler.py" "$@" >> "$WORK/samples.jsonl"
}

# level <label> <readers> <streams> [sampler flags]
level() {
  local label=$1 readers=$2 streams=$3 extra=${4:-} pid=
  echo "== level $label readers=$readers streams=$streams $(date -u +%T)"
  if [ "$readers" -gt 0 ] || [ "$streams" -gt 0 ]; then
    docker compose run --rm -T --no-deps -v "$WORK/loader.py:/tmp/loader.py:ro" app \
      python /tmp/loader.py --base-url http://app:8000 --readers "$readers" \
      --streams "$streams" --hold "$HOLD" --label "$label" \
      > "$WORK/$label.loader.json" 2> "$WORK/$label.loader.err" < /dev/null &
    pid=$!
  fi
  sleep 15; sample "$label" $extra
  sleep 10; sample "$label" $extra
  sleep 10; sample "$label" $extra
  if [ -n "$pid" ]; then
    wait "$pid"
    echo "loader exit $?"
    cat "$WORK/$label.loader.json"
    echo
    sed -n 1,4p "$WORK/$label.loader.err"
  fi
  sleep "$SETTLE"
}

level idle 0 0 --processes
level r1 1 0
level r4 4 0
level r16 16 0
level s1 0 1
level s4 0 4
level s8 0 8
level r16s8 16 8

echo "== samples"
cat "$WORK/samples.jsonl"
echo "== after"
docker compose ps --format '{{.Name}} {{.State}} {{.Status}}'
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}'
echo "== done $(date -u +%T)"
