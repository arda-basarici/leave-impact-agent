#!/usr/bin/env bash
# The publication-digests check run on the app host over SSM, from the workstation under
# the administrator profile: every published replay's log and export digests regenerated
# from its log under the deployed image's code and held to its publication record
# (`python -m leaveimpact.app verify-publications`, the demo milestone's live-path step).
#
# The host side is the deploy's own compose invocation from the app directory, with the
# three variables the compose file interpolates put the way the deploy puts them: the data
# directory, the database password from its SSM parameter, and the image tag read off the
# running app container (the first run sent a bare `docker compose run` and compose refused
# to interpolate). The send, the poll and the read follow the runner driver's: one command
# under an execution timeout, polled until a terminal status with a deadline and a bound on
# failed polls, then one read of status, exit code and both outputs. The output names
# public ids, run ids, formats and counts, never a digest's value.
#
# Usage, from the repository root, after `aws sso login --profile leave-impact` (from
# PowerShell: `bash scripts/verify_publications.sh`, git's bash):
#     bash scripts/verify_publications.sh
# Exit status: 0 when the host's check ended Success with exit code 0 (its lines printed),
# 1 when the host's check failed (its lines and exit code printed), 2 when the send or the
# read was uncertain: no running host, the poll deadline passed, or the CLI kept failing.
set -euo pipefail

export AWS_PROFILE=${AWS_PROFILE:-leave-impact}
REGION=${LEAVE_IMPACT_AWS_REGION:-eu-central-1}
POLL_SECONDS=${POLL_SECONDS:-10}
POLL_FAILURES_BOUND=${POLL_FAILURES_BOUND:-6}
EXECUTION_TIMEOUT=${EXECUTION_TIMEOUT:-900}
DEADLINE_SECONDS=${DEADLINE_SECONDS:-1200}
OUT_DIR=${OUT_DIR:-$(mktemp -d)}
mkdir -p "$OUT_DIR"

instance=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=leave-agent-app" "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId" --output text)
if [ -z "$instance" ] || [ "$instance" = None ]; then
  echo "no running app host to send to" >&2
  exit 2
fi
echo "instance $instance"

HOST_SCRIPT=$(cat <<'HOST'
set -euo pipefail
cd /srv/app
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(aws ssm get-parameter --region eu-central-1 --with-decryption \
  --name /leave-agent/postgres-password --query Parameter.Value --output text)
export POSTGRES_PASSWORD
image=$(docker ps --filter label=com.docker.compose.service=app --format '{{.Image}}' | head -n 1)
if [ -z "$image" ]; then
  echo "no running app container to read the deployed tag from" >&2
  exit 1
fi
export APP_TAG="${image##*:}"
echo "deployed tag $APP_TAG"
docker compose run --rm app python -m leaveimpact.app verify-publications
HOST
)
printf '%s\n' "$HOST_SCRIPT" \
  | jq -Rs --arg t "$EXECUTION_TIMEOUT" '{commands: [.], executionTimeout: [$t]}' \
  > "$OUT_DIR/payload.json"

cid=$(aws ssm send-command --region "$REGION" --instance-ids "$instance" \
  --document-name AWS-RunShellScript --comment "verify-publications" \
  --parameters "file://$OUT_DIR/payload.json" --query Command.CommandId --output text)
echo "command $cid sent"

status=Pending
failures=0
deadline=$((SECONDS + DEADLINE_SECONDS))
while :; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "the poll passed its deadline with no terminal status; the send is uncertain" >&2
    exit 2
  fi
  if status=$(aws ssm get-command-invocation --region "$REGION" --command-id "$cid" \
      --instance-id "$instance" --query Status --output text 2> "$OUT_DIR/poll.err"); then
    failures=0
  elif grep -q InvocationDoesNotExist "$OUT_DIR/poll.err"; then
    status=Pending
  else
    failures=$((failures + 1))
    if [ "$failures" -ge "$POLL_FAILURES_BOUND" ]; then
      echo "$failures polls in a row failed, the last: $(head -1 "$OUT_DIR/poll.err"); the send is uncertain" >&2
      exit 2
    fi
    status=Pending
  fi
  case "$status" in
    Pending|InProgress|Delayed) sleep "$POLL_SECONDS" ;;
    *) break ;;
  esac
done

if ! aws ssm get-command-invocation --region "$REGION" --command-id "$cid" --instance-id "$instance" \
    --query '{Status:Status,Code:ResponseCode,Out:StandardOutputContent,Err:StandardErrorContent}' \
    --output json > "$OUT_DIR/result.json" 2> "$OUT_DIR/read.err"; then
  echo "the command ended $status and its result could not be read ($(head -1 "$OUT_DIR/read.err")); the send is uncertain" >&2
  exit 2
fi
jq -j .Out "$OUT_DIR/result.json"
jq -r .Err "$OUT_DIR/result.json" | sed '/^$/d; s/^/(stderr) /' >&2
code=$(jq -r .Code "$OUT_DIR/result.json")
case "$status" in
  Success)
    if [ "$code" = "0" ]; then exit 0; fi
    echo "the host reported Success with exit code $code; the send is uncertain" >&2
    exit 2 ;;
  Failed)
    echo "the host's check exited $code" >&2
    exit 1 ;;
  *)
    echo "the transport reported $status; the send is uncertain" >&2
    exit 2 ;;
esac
