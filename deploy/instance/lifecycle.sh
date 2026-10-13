#!/bin/bash
# One step of a run's lifecycle on the app host, run as root over `ssm send-command`
# by the investigate and approve-run workflows (the first live run's step, fork 1):
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
# A run's files live under /run/leaveimpact/<run id>/ on the host's tmpfs, root
# only, bind-mounted into every container of the run at /run/job: the request file
# the launcher writes (the scenario's leave and instant, never on a log), the work
# command's cell flags, the two preregistration files, and run.env, the launch's
# non-secret inputs the later steps read back so their payloads carry only the
# step's own. Nothing is rendered to disk; a reboot clears the directory, and a
# step that finds it gone says so and stops, since the attempt's files cannot be
# rebuilt from a later step's inputs.
#
# Secrets (the PostgreSQL password; for `work`, the investigator's five read-only
# vendor principals from Parameter Store) enter the container through the process
# environment compose interpolates, never a command line, so neither `ps` nor the
# stored invocation output can show them; this script never runs under `set -x`.
# What it prints is what the lifecycle commands print: identities, counts, kinds,
# file names, the reservation. `review-approval` is not a word here, by that
# command's own rule (its output is the run's content; Session Manager only).
set -euo pipefail

: "${LIFECYCLE_COMMAND:?launch, work, status, deliver, publish or inventory}"
: "${RUN_SHA:?the commit the workflow was dispatched from}"
: "${RUN_ID:?the run id}"
: "${ATTEMPT:?the attempt number}"
REPO=arda-basarici/leave-impact-agent
REGION=eu-central-1
# Overridable for the fake-binary tests only; the instance has the defaults.
APP_DIR=${APP_DIR:-/srv/app}
RUN_ROOT=${RUN_ROOT:-/run/leaveimpact}
JOB_DIR=/run/job
WORLD_BUCKET=leave-impact-world-445743457479

# The twin of deploy.sh's `param`: a parameter's value, or a failed step when it still
# holds the `UNSET` placeholder the platform stack creates it with. A change is made in
# both; the payload carries one script and bash has no import.
param() {
  local value
  value=$(aws ssm get-parameter --region "$REGION" --with-decryption --name "$1" --query Parameter.Value --output text)
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
if [ "$LIFECYCLE_COMMAND" = launch ]; then
  mkdir -p "$run_dir"
  chmod 0700 "$RUN_ROOT" "$run_dir"
elif [ ! -f "$run_dir/run.env" ]; then
  echo "the run directory $run_dir holds no run.env: the host's tmpfs was cleared since the launch, and the attempt's files cannot be rebuilt by a later step" >&2
  exit 2
fi

fetch() {
  [ -s "$run_dir/$1" ] || curl -fsSL "https://raw.githubusercontent.com/$REPO/$RUN_SHA/preregistration/$1" -o "$run_dir/$1"
}
fetch registration.json
fetch prices.json

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
    # One nonce per process: a re-sent work is a new claimant of the same attempt.
    nonce="nonce-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
    mapfile -t cell < "$attempt_dir/work.args"
    run_app python -m leaveimpact.agent work --run "$RUN_ID" --attempt "$ATTEMPT" \
      --nonce "$nonce" --launch "$LAUNCH" --registration "$registration" --prices "$prices" \
      --approval "$APPROVAL" "${cell[@]}"
    ;;
  status)
    : "${RECOVERIES:?recoveries sent so far}" "${APPROVAL:?the policy work was dispatched with}"
    run_app python -m leaveimpact.launch status --run "$RUN_ID" --attempt "$ATTEMPT" \
      --registration "$registration" --recoveries "$RECOVERIES" --approval "$APPROVAL"
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
    # shellcheck source=/dev/null
    . "$run_dir/run.env"
    run_app python -m leaveimpact.agent inventory --registration "$registration" \
      --world-version "$WORLD_VERSION" --registration-commit "$REGISTRATION_COMMIT" \
      --ledger "$LEDGER"
    ;;
  *)
    echo "LIFECYCLE_COMMAND is launch, work, status, deliver, publish or inventory, not $LIFECYCLE_COMMAND" >&2
    exit 2
    ;;
esac
