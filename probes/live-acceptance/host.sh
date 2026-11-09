#!/bin/bash
# The live path's acceptance sampler on the app host (the demo milestone's step 16), sent
# over SSM by send.ps1 with one of four actions substituted into this file. `check` (the
# final smoke's check before the flag goes on) starts nothing: it prints the host's header
# and runs access_check.py inside the worker container, whose lines say whether each of the
# two Access names is nonempty there and what the edge answers the Frappe login page with
# the pair and without it; only lines that check wrote are passed on. `start` makes
# a work directory, writes the memory baseline's sampler into it and leaves a detached loop
# sampling every CADENCE seconds into samples.jsonl until a stop file appears or DURATION
# passes, so one sampling spans a whole public attempt from before the first click to after
# its closure with no SSM command held open; `stop` writes the stop file, waits for the loop
# to end and prints the sample count and the containers' state after; `fetch` prints one
# slice of samples.jsonl as base64 from a byte offset, since SSM cuts a command's stdout at
# 24,000 characters, and the sender reassembles the slices byte for byte. The loop runs in
# its own session with its standard streams closed, so the command's end does not end it;
# the first command prints the loop's pid and its first sample so a loop that did not
# survive is seen at once. No password is read: the sampler reads cgroups, /proc and
# `docker inspect` only, and the containers are listed with `docker ps`; the check reads
# the Access pair where the worker already holds it and prints no value. The cadence is
# the sender's parameter: 5 s at the acceptance, 2 s at the final smoke, whose active
# phases are too short for 5.
set -u
ACTION="<action>"
WORK="<work>"
OFFSET="<offset>"
CADENCE="<cadence>"
DURATION=${DURATION:-5400}
SLICE=15000

case "$ACTION" in
check)
  echo "== host $(date -u +%FT%TZ)"
  cd /srv/app || exit 1
  echo "deployed $(cat DEPLOYED)"
  docker ps --format '{{.Names}} {{.Status}}'
  echo "== the worker's Access pair, read inside its container"
  echo "<base64 of access_check.py>" | base64 -d \
    | docker exec -i leaveimpact-worker-1 python - 2>/dev/null \
    | grep -E '^(access|frappe) ' || echo "the check printed no line"
  ;;
start)
  WORK=$(mktemp -d /tmp/live-acceptance.XXXXXX)
  chmod 755 "$WORK"
  echo "work $WORK"
  echo "<base64 of sampler.py>" | base64 -d > "$WORK/sampler.py"
  chmod 644 "$WORK/sampler.py"
  echo "== host $(date -u +%FT%TZ)"
  uname -r
  echo "cpus $(nproc)"
  echo "cadence $CADENCE duration $DURATION"
  cd /srv/app || exit 1
  echo "deployed $(cat DEPLOYED)"
  docker ps --format '{{.Names}} {{.Status}}'
  cat > "$WORK/loop.sh" <<LOOP
#!/bin/bash
started=\$(date +%s)
echo \$\$ > "$WORK/loop.pid"
while [ ! -e "$WORK/stop" ] && [ \$(( \$(date +%s) - started )) -lt $DURATION ]; do
  python3 "$WORK/sampler.py" acceptance >> "$WORK/samples.jsonl"
  sleep $CADENCE
done
rm -f "$WORK/loop.pid"
LOOP
  chmod 755 "$WORK/loop.sh"
  setsid nohup "$WORK/loop.sh" > "$WORK/loop.log" 2>&1 < /dev/null &
  sleep $((CADENCE + 2))
  echo "loop pid $(cat "$WORK/loop.pid" 2>/dev/null || echo none)"
  echo "samples $(wc -l < "$WORK/samples.jsonl" 2>/dev/null || echo 0)"
  echo "first $(head -c 400 "$WORK/samples.jsonl" 2>/dev/null)"
  ;;
stop)
  touch "$WORK/stop"
  for _ in $(seq 1 12); do
    [ -e "$WORK/loop.pid" ] || break
    sleep 2
  done
  echo "loop pid after stop: $(cat "$WORK/loop.pid" 2>/dev/null || echo ended)"
  echo "samples $(wc -l < "$WORK/samples.jsonl")"
  echo "bytes $(stat -c %s "$WORK/samples.jsonl")"
  echo "== after $(date -u +%FT%TZ)"
  docker ps --format '{{.Names}} {{.Status}}'
  echo "== loop log (last lines)"
  tail -n 3 "$WORK/loop.log"
  ;;
fetch)
  echo "bytes $(stat -c %s "$WORK/samples.jsonl")"
  echo "offset $OFFSET"
  echo "slice $(tail -c "+$((OFFSET + 1))" "$WORK/samples.jsonl" | head -c "$SLICE" | base64 -w0)"
  ;;
*)
  echo "unknown action $ACTION"
  exit 2
  ;;
esac
echo "== done $(date -u +%T)"
