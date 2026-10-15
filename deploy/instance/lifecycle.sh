#!/bin/bash
# One step of a run's lifecycle on the app host, run as root over `ssm send-command`
# by the investigate and continue-run workflows (the first live run's step, fork 1):
# the script travels inside the command payload after the `export` lines that
# name the step, so nothing is fetched from anywhere the host could be lied to by.
# LIFECYCLE_COMMAND is one word: `launch` (the plan, the ledger threshold as a
# receipt, the admission), `work`, `status`, `deliver`, `publish` or `inventory`;
# each is one `docker compose run` of the deployed image, and the python command's
# exit status is this script's.
#
# The commit a run rides is the one the workflow was dispatched from: RUN_SHA must
# equal the sha in DEPLOYED, so the image, the registration and price files (fetched
# at RUN_SHA, as deploy.sh fetches compose.yaml) and the registration commit the
# runner cites are all of one commit. A push between a deploy and a dispatch is
# refused here, and the run is re-dispatched after the next deploy.
#
# A run's files live under /run/leaveimpact/<run id>/ on the host's tmpfs, owned by
# the image's unprivileged user (uid 1000, the Dockerfile's `app`) and readable by
# nobody else, bind-mounted into every container of the run at /run/job: the request file
# the launcher writes (the scenario's leave and instant, never on a log), the work
# command's cell flags, the two preregistration files, and run.env, the launch's
# non-secret inputs the later steps read back so their payloads carry only the
# step's own. Nothing is rendered to disk; a reboot clears the directory. `work` is
# the one word that reads the launch's files (the cell flags, run.env's site URLs), so
# it alone says so and stops when they are gone, since they cannot be rebuilt from a
# later step's inputs. Every other word needs nothing a reboot clears: it remakes the
# private directory and fetches the pinned files (publish since the step's batch
# review; status, deliver and inventory since the step-14 review's finding, built
# before the first reported dispatch). `inventory` takes its scope, the world version
# and the registration commit the attempt was admitted under, from the step's own
# payload, which the driver read off `status`; so a closed attempt is published and
# listed after a reboot, and an approval is recorded even where no work can yet
# follow it.
#
# The work container is named for its attempt, because the SSM agent ends a timed-out
# command with SIGKILL to the host's process tree and the container outlives its
# client (the step's two timeout probes, 2026-10-13): `status` reports first whether
# that container is still running, so the driver polls instead of re-sending, and
# `work` refuses to start beside a running one (exit 4). A container that exited is
# removed before a new one takes the name. A work container of another attempt still
# running (a job the agent killed at its timeout leaves its container alive for up to
# an hour, and the next dispatch starts once that job has ended) would share the
# host's memory bound with the new one: `work` refuses it as a fault an operator
# decides (exit 3), never waited for or re-sent (the external read of the pre-dispatch
# commits).
#
# Secrets (the PostgreSQL password; for `work`, the investigator's five read-only
# vendor principals from Parameter Store) enter the container through the process
# environment compose interpolates, never a command line, so neither `ps` nor the
# stored invocation output can show them; this script never runs under `set -x`.
# What it prints is what the lifecycle commands print: identities, counts, kinds,
# file names, the reservation. `review-approval` is not a word here, by that
# command's own rule (its output is the run's content; Session Manager only).
#
# A failing `aws` inside `param` ends the step with the CLI's own error: bash drops
# errexit inside a command substitution unless told to inherit it, and without the
# explicit return the value came back empty with status 0 and the container refused
# with "is not set", the wrong cause (the step's batch review).
set -euo pipefail
shopt -s inherit_errexit

: "${LIFECYCLE_COMMAND:?launch, work, status, deliver, publish or inventory}"
: "${RUN_SHA:?the commit the workflow was dispatched from}"
: "${RUN_ID:?the run id}"
: "${ATTEMPT:?the attempt number}"
# The two ids name a directory this script makes and hands over recursively as root, and
# the continue-run workflow takes both as typed inputs: each is held to its one shape
# before anything on the filesystem (the external read of the pre-dispatch commits).
if ! [[ "$RUN_ID" =~ ^run-[0-9]+$ ]]; then
  echo "RUN_ID is run-<workflow run id>, not '$RUN_ID'" >&2
  exit 2
fi
if ! [[ "$ATTEMPT" =~ ^[1-9][0-9]*$ ]]; then
  echo "ATTEMPT is a positive integer, not '$ATTEMPT'" >&2
  exit 2
fi
REPO=arda-basarici/leave-impact-agent
REGION=eu-central-1
# Overridable for the fake-binary tests only; the instance has the defaults.
APP_DIR=${APP_DIR:-/srv/app}
RUN_ROOT=${RUN_ROOT:-/run/leaveimpact}
JOB_DIR=/run/job
WORLD_BUCKET=leave-impact-world-445743457479
APP_UID=1000
APP_GID=1000

# The twin of deploy.sh's `param`: a parameter's value, or a failed step when it still
# holds the `UNSET` placeholder the platform stack creates it with. A change is made in
# both; the payload carries one script and bash has no import.
param() {
  local value
  value=$(aws ssm get-parameter --region "$REGION" --with-decryption --name "$1" --query Parameter.Value --output text) || return $?
  case "$value" in
    UNSET*) echo "parameter $1 is not put: it still holds the UNSET placeholder" >&2; return 1 ;;
  esac
  printf '%s' "$value"
}

deployed=$(cat "$APP_DIR/DEPLOYED")
if [ "$deployed" != "$RUN_SHA" ]; then
  echo "the dispatched commit $RUN_SHA is not the deployed one $deployed" >&2
  exit 2
fi

run_dir="$RUN_ROOT/$RUN_ID"
attempt_dir="$run_dir/attempt-$ATTEMPT"
case "$LIFECYCLE_COMMAND" in
  work)
    # The one word that reads the launch's files (the header).
    if [ ! -f "$run_dir/run.env" ]; then
      echo "the run directory $run_dir holds no run.env: the host's tmpfs was cleared since the launch, and the attempt's files cannot be rebuilt by a later step" >&2
      exit 2
    fi
    ;;
  launch|status|deliver|publish|inventory)
    # The words that need nothing a reboot clears: the directory is made or remade.
    mkdir -p "$run_dir"
    chmod 0700 "$RUN_ROOT" "$run_dir"
    ;;
esac

# A complete file is kept; an absent one is fetched to a temporary name and moved into
# place only when the transfer succeeded, so a transfer that died mid-body leaves no
# partial file for the next step or the next attempt of the run to read as the
# registration (the step's batch review).
fetch() {
  [ -s "$run_dir/$1" ] && return 0
  local part="$run_dir/$1.part" status=0
  curl -fsSL "https://raw.githubusercontent.com/$REPO/$RUN_SHA/preregistration/$1" -o "$part" || status=$?
  if [ "$status" -ne 0 ]; then
    rm -f "$part"
    echo "fetching preregistration/$1 at $RUN_SHA failed (curl exit $status); nothing was kept" >&2
    return "$status"
  fi
  mv "$part" "$run_dir/$1"
}
fetch registration.json
fetch prices.json
# The container runs as the image's user and the directory is 0700: it is handed over
# whole, the files root wrote included (the first live dispatch failed on exactly this,
# the launcher refused the registration with a permission error).
chown -R "$APP_UID:$APP_GID" "$run_dir"

cd "$APP_DIR"
export APP_TAG="$RUN_SHA"
export PGDATA_HOST=/srv/pgdata
POSTGRES_PASSWORD=$(param /leave-agent/postgres-password)
export POSTGRES_PASSWORD
export LEAVE_IMPACT_WORLD_BUCKET="$WORLD_BUCKET"
export LEAVE_IMPACT_AWS_REGION="$REGION"

run_app() {
  docker compose run --rm -v "$run_dir:$JOB_DIR" app "$@"
}
container="lifecycle-$RUN_ID-a$ATTEMPT"
# The attempt's work container, if the daemon still runs it.
running_container() {
  docker ps --filter "name=^${container}\$" --filter status=running --format '{{.Names}}'
}
registration="$JOB_DIR/registration.json"
prices="$JOB_DIR/prices.json"

case "$LIFECYCLE_COMMAND" in
  launch)
    : "${WORLD_VERSION:?}" "${SCENARIO:?}" "${SYSTEM:?}" "${CONDITION:?}" "${LEVEL:?}"
    : "${REGISTRATION_COMMIT:?}" "${REQUEST_ID:?}" "${ADMITTER:?}" "${AUTHORITY:?}"
    : "${LEDGER:?}" "${THRESHOLD_PICO:?}" "${LIMIT_PICO:?}"
    : "${FRAPPE_BASE_URL:?}" "${JIRA_BASE_URL:?}"
    # The later steps read these back; every value here is one the job log already shows.
    {
      for name in WORLD_VERSION SCENARIO SYSTEM CONDITION LEVEL REGISTRATION_COMMIT \
          LEDGER ADMITTER AUTHORITY FRAPPE_BASE_URL JIRA_BASE_URL; do
        printf '%s=%q\n' "$name" "${!name}"
      done
    } > "$run_dir/run.env"
    chmod 0600 "$run_dir/run.env"
    plan=(plan --world-version "$WORLD_VERSION" --scenario "$SCENARIO" --system "$SYSTEM"
      --condition "$CONDITION" --level "$LEVEL"
      --registration "$registration" --registration-commit "$REGISTRATION_COMMIT"
      --prices "$prices" --region "$REGION"
      --run "$RUN_ID" --attempt "$ATTEMPT" --request-id "$REQUEST_ID" --admitter "$ADMITTER"
      --out "$JOB_DIR/attempt-$ATTEMPT")
    # Rules only reserves nothing: no ledger on its plan and no threshold receipt.
    if [ "$SYSTEM" != rules_only ]; then
      plan+=(--ledger "$LEDGER")
    fi
    run_app python -m leaveimpact.launch "${plan[@]}"
    if [ "$SYSTEM" != rules_only ]; then
      # Sent on every launch: an equal amount answers with the entry in force and writes
      # nothing (the group's review); the amounts are the registration's budget block.
      run_app python -m leaveimpact.agent set-threshold --ledger "$LEDGER" \
        --amount "$THRESHOLD_PICO" --authority "$AUTHORITY" \
        --registration-commit "$REGISTRATION_COMMIT" --limit "$LIMIT_PICO"
    fi
    run_app python -m leaveimpact.agent admit --registration "$registration" \
      --request "$JOB_DIR/attempt-$ATTEMPT/request.json"
    ;;
  work)
    : "${LAUNCH:?the launch identity the plan printed}" "${APPROVAL:?automatic or human}"
    # shellcheck source=/dev/null
    . "$run_dir/run.env"
    if [ ! -s "$attempt_dir/work.args" ]; then
      echo "the attempt directory $attempt_dir holds no work.args: launch did not run for this attempt" >&2
      exit 2
    fi
    export LEAVE_IMPACT_FRAPPE_BASE_URL="$FRAPPE_BASE_URL"
    export LEAVE_IMPACT_JIRA_BASE_URL="$JIRA_BASE_URL"
    LEAVE_IMPACT_FRAPPE_API_KEY=$(param /leave-agent/frappe-api-key)
    LEAVE_IMPACT_FRAPPE_API_SECRET=$(param /leave-agent/frappe-api-secret)
    LEAVE_IMPACT_JIRA_EMAIL=$(param /leave-agent/jira-email)
    LEAVE_IMPACT_JIRA_TOKEN=$(param /leave-agent/jira-token)
    LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_JSON=$(param /leave-agent/google-authorized-user-json)
    export LEAVE_IMPACT_FRAPPE_API_KEY LEAVE_IMPACT_FRAPPE_API_SECRET LEAVE_IMPACT_JIRA_EMAIL
    export LEAVE_IMPACT_JIRA_TOKEN LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_JSON
    foreign=$(docker ps --filter "name=^lifecycle-" --filter status=running --format '{{.Names}}' | grep -vx "$container" || true)
    if [ -n "$foreign" ]; then
      echo "another attempt's work container is running on this host: $foreign; an operator decides before this attempt's work is sent again" >&2
      exit 3
    fi
    if [ -n "$(running_container)" ]; then
      echo "a work container of this attempt is still running: $container; the state is read until it ends" >&2
      exit 4
    fi
    # An exited container of the name holds no process; a new one takes the name.
    docker rm -f "$container" > /dev/null 2>&1 || true
    # One nonce per process: a re-sent work is a new claimant of the same attempt.
    nonce="nonce-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
    mapfile -t cell < "$attempt_dir/work.args"
    docker compose run --rm --name "$container" -v "$run_dir:$JOB_DIR" app \
      python -m leaveimpact.agent work --run "$RUN_ID" --attempt "$ATTEMPT" \
      --nonce "$nonce" --launch "$LAUNCH" --registration "$registration" --prices "$prices" \
      --approval "$APPROVAL" "${cell[@]}"
    ;;
  status)
    : "${APPROVAL:?the policy work was dispatched with}"
    if [ -n "$(running_container)" ]; then echo "container=running"; else echo "container=none"; fi
    run_app python -m leaveimpact.launch status --run "$RUN_ID" --attempt "$ATTEMPT" \
      --registration "$registration" --approval "$APPROVAL"
    ;;
  deliver)
    : "${APPROVER:?the identity of the approver}" "${PAYLOAD_DIGEST:?the payload the approver read}"
    run_app python -m leaveimpact.agent deliver-approval --registration "$registration" \
      --run "$RUN_ID" --attempt "$ATTEMPT" --approver "$APPROVER" --payload-digest "$PAYLOAD_DIGEST"
    ;;
  publish)
    run_app python -m leaveimpact.agent publish --registration "$registration" \
      --run "$RUN_ID" --attempt "$ATTEMPT"
    ;;
  inventory)
    : "${WORLD_VERSION:?the world the attempt was admitted on}"
    : "${REGISTRATION_COMMIT:?the registration commit the attempt was admitted under}"
    : "${LEDGER:?the ledger id}"
    run_app python -m leaveimpact.agent inventory --registration "$registration" \
      --world-version "$WORLD_VERSION" --registration-commit "$REGISTRATION_COMMIT" \
      --ledger "$LEDGER"
    ;;
  *)
    echo "LIFECYCLE_COMMAND is launch, work, status, deliver, publish or inventory, not $LIFECYCLE_COMMAND" >&2
    exit 2
    ;;
esac
