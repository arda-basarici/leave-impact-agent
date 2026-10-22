#!/bin/bash
# The lifecycle of one run, driven from the GitHub runner: each step is one
# `ssm send-command` of deploy/instance/lifecycle.sh to the app host, waited for
# and read back, and the next step is what the launcher's `status` command answers
# (the first live run's step, forks 1 and 9). Run by the investigate workflow
# (MODE=run: launch, then work) and the continue-run workflow (MODE=continue:
# deliver a human's approval when a payload digest is given, then continue from
# status; with no digest, continue from status alone, which is how an attempt whose
# job ended after its closing gets its publish and inventory). Everything it needs is in the
# environment, so the workflow files stay a list of inputs and this file is what
# the fake-binary tests and shellcheck read.
#
# The walk. After a work send the state is read with `status` and its `next=` is
# acted on: `work` or `recover` sends work again (a recovery counted toward the
# bound the launcher enforces by answering `hold`), `wait` ends the job green and
# says a human decides, `publish` sends publish then inventory, `hold` ends the job
# red. A work send whose process exited 2 or 3 (a configuration fault, an unexpected
# failure) ends the job red at once: that is not a transport uncertainty and a
# re-send would meet it again. Any other status the process did not choose (137
# under the container's memory limit, 143, a daemon-side 125) is the host's doing,
# and the state is read, since a killed worker is exactly what the launcher's
# `recover` answer exists for (the step's batch review). A send the transport reports
# uncertainly (timed out, cancelled, lost) is never re-sent blind: the state is read
# first, and an in-flight command is never re-sent at all. The step's two probes
# (2026-10-13) showed what
# the timeout does: the agent kills the host's process tree with SIGKILL at the
# execution timeout (exit 137, no trap runs), and the work container outlives its
# killed client and runs on. So the host's `status` reports the attempt's container
# first, and while it reports `running` the driver only reads the state again, every
# poll interval, until the container has ended and the launcher's answer is acted
# on; a work the host refused beside a running container (exit 4) takes the same
# path. Work sends are bounded at four in one job (the first, two recoveries, one
# resumption after an approval), so a state that never progresses cannot loop.
# Every other step must succeed, and a refusal (exit 1) ends the job red with the
# printed reason: the agent's entry says a workflow must not proceed past one.
#
# The poll on a sent command is bounded and classifies its own failures (the batch
# review): a CLI error saying the invocation does not exist yet is the eventual
# consistency the poll waits through; any other error (an expired session, a
# throttle, a lost network) is counted, and six in a row, or a poll past the
# execution timeout plus a margin, or a final read that fails after a terminal
# status, end the send as uncertain. The job's credentials are the deploy role's
# one-hour session and a work send may run an hour, so an uncertain end can be one
# this job cannot read past: it then ends red naming continue-run as the path, which
# reads the state under fresh credentials. The recovery count is the attempt's own,
# counted by the log's fold at each claim and printed by `status` (`recoveries=`), so a
# continuation job continues the count and the bound of two in PROTOCOL holds over the
# attempt's whole history; until 2026-10-15 the count was this job's and every
# continuation granted the bound again (the step-14 review's finding). What this job
# bounds itself is its work sends, above.
#
# The inventory's scope is the admission's. `status` prints the world version and the
# registration commit the attempt was admitted under, and the publish step hands them
# with the workflow's ledger to `inventory`, so a continuation after a reboot of the
# host, whose run directory is gone, still publishes and lists a closed attempt (the
# step-14 review's finding, before the first reported dispatch), and an attempt is
# listed under the commit it was admitted under and never a later checkout's. `status`
# prints the ledger the attempt was admitted against the same way, and the host checks
# the workflow's ledger against it where the name is used, so a continuation naming
# another ledger than the admission's is refused after a reboot too (the replay step's
# external read). A status that printed none of the three ends the job red before
# publish, since the inventory could not be scoped.
#
# Identities are the workflow run's: run id `run-<GITHUB_RUN_ID>`, attempt
# `GITHUB_RUN_ATTEMPT`, request id `req-<run id>-a<attempt>` (a re-run of the job
# is the next attempt; a retry of a send inside the job is the same request, and
# the admission answers it with its receipt). The launch identity is the plan's
# printed one, held for every work send of the attempt; the continue-run workflow
# takes it as an input, with the policy the attempt was dispatched under, so an
# automatic attempt continued from another job is recovered and not waited for. The
# admitter and the threshold's authority are this workflow; the approver is the
# human who dispatched the continue-run workflow after reading the
# payload in Session Manager.
#
# Before any send the CI run that built the dispatched commit is read off the Actions
# API and every named required job must have concluded success (the guard below, the
# freeze step's fork 10); the workflow grants `actions: read` and the token for it.
#
# The job log is public: what this prints is each step's stored output (ids,
# counts, kinds, file names, the reservation) and its own decisions. The payloads
# carry no secret; the host reads those from Parameter Store itself.
set -euo pipefail

: "${MODE:?run or continue}"
: "${GITHUB_SHA:?}" "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}" "${GITHUB_ACTOR:?}"
: "${LEDGER:?the ledger the run is admitted against}"
HOST_SCRIPT=${HOST_SCRIPT:-deploy/instance/lifecycle.sh}
REGISTRATION_FILE=${REGISTRATION_FILE:-preregistration/registration.json}
INSTANCE_TAG=${INSTANCE_TAG:-leave-agent-app}
# The execution timeout sits above a cap-reading run; the poll is what waits, since
# the CLI's own waiter gives up after about a hundred seconds.
EXECUTION_TIMEOUT=${EXECUTION_TIMEOUT:-3600}
POLL_SECONDS=${POLL_SECONDS:-10}
# The poll's own bounds (the header): consecutive CLI failures before the send is
# uncertain, the margin past the execution timeout, and the CLI's own timeouts.
POLL_FAILURES_BOUND=${POLL_FAILURES_BOUND:-6}
POLL_MARGIN_SECONDS=${POLL_MARGIN_SECONDS:-300}
CLI_TIMEOUTS=(--cli-connect-timeout 10 --cli-read-timeout 60)
WORK_SENDS_BOUND=4
OUT_DIR=${RUNNER_TEMP:-/tmp}/lifecycle
SUMMARY=${GITHUB_STEP_SUMMARY:-/dev/null}
mkdir -p "$OUT_DIR"

AUTHORITY="workflow:investigate"
ADMITTER="workflow:investigate"
case "$MODE" in
  run)
    : "${INPUT_WORLD_VERSION:?}" "${INPUT_SCENARIO:?}" "${INPUT_SYSTEM:?}"
    : "${INPUT_CONDITION:?}" "${INPUT_LEVEL:?}" "${INPUT_APPROVAL:?}"
    : "${INPUT_FRAPPE_BASE_URL:?}" "${INPUT_JIRA_BASE_URL:?}"
    RUN_ID="run-$GITHUB_RUN_ID"
    ATTEMPT="$GITHUB_RUN_ATTEMPT"
    APPROVAL="$INPUT_APPROVAL"
    LAUNCH=""
    ;;
  continue)
    : "${INPUT_RUN_ID:?}" "${INPUT_ATTEMPT:?}" "${INPUT_LAUNCH:?}" "${INPUT_APPROVAL:?}"
    INPUT_PAYLOAD_DIGEST=${INPUT_PAYLOAD_DIGEST:-}
    # Typed by a human: held to their shapes here, before any send, as the host holds them
    # again before it touches the filesystem.
    if ! [[ "$INPUT_RUN_ID" =~ ^run-[0-9]+$ ]]; then
      echo "run_id is run-<workflow run id>, not '$INPUT_RUN_ID'"; exit 2
    fi
    if ! [[ "$INPUT_ATTEMPT" =~ ^[1-9][0-9]*$ ]]; then
      echo "attempt is a positive integer, not '$INPUT_ATTEMPT'"; exit 2
    fi
    RUN_ID="$INPUT_RUN_ID"
    ATTEMPT="$INPUT_ATTEMPT"
    # A continued attempt resumes under the policy it was dispatched with: under the
    # human policy an approval already given reads as approved and none requested as
    # work; under the automatic policy a request left open by a dead process is
    # recovered, not waited for.
    APPROVAL="$INPUT_APPROVAL"
    LAUNCH="$INPUT_LAUNCH"
    ;;
  *) echo "MODE is run or continue, not $MODE" >&2; exit 2 ;;
esac
REQUEST_ID="req-$RUN_ID-a$ATTEMPT"
# The registration's commit and its budget, from the checkout the run rides: the
# threshold receipt carries the registered dollars times 10^12, in 64-bit shell
# arithmetic, so the amounts are the file's own and not a hand-typed copy.
REGISTRATION_COMMIT=$(git log -1 --format=%H -- "$REGISTRATION_FILE")
test -n "$REGISTRATION_COMMIT" || { echo "no commit touches $REGISTRATION_FILE"; exit 2; }
THRESHOLD_PICO=$(( $(jq -r .budget.admission_threshold_usd "$REGISTRATION_FILE") * 1000000000000 ))
LIMIT_PICO=$(( $(jq -r .budget.admission_threshold_limit_usd "$REGISTRATION_FILE") * 1000000000000 ))

# The CI guard (the freeze step, fork 10; ruled at the first live run's close). The host's
# DEPLOYED check says the dispatched commit is the deployed one, not that the CI run that
# built it was green: a development deploy may be approved before the crash matrix ends,
# and a red matrix on a deployed commit is an incident, not a refusal. For the measurement
# this is not enough, so before any send the Actions API is read for the push run of the
# CI workflow on main at this commit, and every named required job of its latest attempt
# must have concluded success; pending, failed, cancelled, skipped and absent each refuse
# the dispatch, and the run and attempt read are printed. The two guards are independent.
# Probed on run 38615543839 (2026-10-14): attempt 1 failed the image job and skipped the
# deploy, attempt 2 re-ran every job, and `filter=latest` lists the five jobs at attempt 2.
CI_WORKFLOW=${CI_WORKFLOW:-ci.yml}
CI_REQUIRED_JOBS=${CI_REQUIRED_JOBS:-"check sweeps crash-matrix image deploy"}
: "${GITHUB_REPOSITORY:?}"
gh api "repos/$GITHUB_REPOSITORY/actions/workflows/$CI_WORKFLOW/runs?head_sha=$GITHUB_SHA&event=push&per_page=100" \
  > "$OUT_DIR/ci-runs.json"
# `tr` strips the carriage return a Windows jq appends, so the fake-binary tests read the
# same bytes the runner's jq prints.
mapfile -t ci_runs < <(jq -r '.workflow_runs[] | select(.head_branch == "main") | .id' "$OUT_DIR/ci-runs.json" | tr -d '\r')
case "${#ci_runs[@]}" in
  0) echo "no push run of $CI_WORKFLOW on main built $GITHUB_SHA; nothing is dispatched"; exit 1 ;;
  1) ;;
  *)
    echo "${#ci_runs[@]} push runs of $CI_WORKFLOW on main built $GITHUB_SHA (${ci_runs[*]}); one is expected, nothing is dispatched"
    exit 1
    ;;
esac
ci_run=${ci_runs[0]}
ci_attempt=$(jq -r --argjson id "$ci_run" '.workflow_runs[] | select(.id == $id) | .run_attempt' "$OUT_DIR/ci-runs.json" | tr -d '\r')
gh api "repos/$GITHUB_REPOSITORY/actions/runs/$ci_run/jobs?filter=latest&per_page=100" > "$OUT_DIR/ci-jobs.json"
ci_refused=""
for job in $CI_REQUIRED_JOBS; do
  state=$(jq -r --arg name "$job" \
    '[.jobs[] | select(.name == $name)] | if length == 0 then "absent" else "\(.[0].status)/\(.[0].conclusion)" end' \
    "$OUT_DIR/ci-jobs.json" | tr -d '\r')
  [ "$state" = "completed/success" ] || ci_refused="$ci_refused $job=$state"
done
if [ -n "$ci_refused" ]; then
  echo "CI run $ci_run attempt $ci_attempt of $GITHUB_SHA has required jobs not concluded success:$ci_refused; nothing is dispatched"
  exit 1
fi
echo "CI run $ci_run attempt $ci_attempt of $GITHUB_SHA: $CI_REQUIRED_JOBS concluded success"

IID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=$INSTANCE_TAG" Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text)
test -n "$IID" || { echo "no running $INSTANCE_TAG instance"; exit 1; }

sends=0
# One step: the export lines for the step, then the host script, as one command
# under the execution timeout. The stored output goes to a file named by the step
# and its ordinal and is echoed into the log prefixed by the step. Returns 0 on
# Success, 1 on Failed (RESPONSE_CODE holds the process's exit status), 2 when the
# transport reported the command uncertainly.
send() {
  local word=$1; shift
  sends=$((sends + 1))
  local stem="$OUT_DIR/$sends-$word"
  # The previous send's fields are cleared first, so an uncertain end leaves nothing
  # a later step could read as this send's answer.
  RESPONSE_CODE=""
  LAST_OUT=""
  {
    for pair in "$@"; do
      printf 'export %s=%q\n' "${pair%%=*}" "${pair#*=}"
    done
    cat "$HOST_SCRIPT"
  } | jq -Rs --arg t "$EXECUTION_TIMEOUT" '{commands: [.], executionTimeout: [$t]}' > "$stem.payload.json"
  # Printed before the send, so a response lost after SSM accepted the command (the job
  # then ends on the failed assignment below, and the host runs the command anyway) leaves
  # a log that says the send happened; a reader of the log tells "never sent" from "sent
  # and unread" by this line alone (the replay step's second external read).
  echo "$word: sending"
  local cid
  cid=$(aws ssm send-command --instance-ids "$IID" --document-name AWS-RunShellScript \
    --comment "$word $RUN_ID/$ATTEMPT" --parameters "file://$stem.payload.json" \
    --query Command.CommandId --output text)
  echo "$word: command $cid on $IID"
  local status failures=0 deadline=$((SECONDS + EXECUTION_TIMEOUT + POLL_MARGIN_SECONDS))
  while :; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "$word: the poll passed the execution timeout plus its margin with no terminal status; the send is uncertain"
      return 2
    fi
    if status=$(aws ssm get-command-invocation "${CLI_TIMEOUTS[@]}" --command-id "$cid" --instance-id "$IID" \
        --query Status --output text 2> "$stem.poll.err"); then
      failures=0
    elif grep -q InvocationDoesNotExist "$stem.poll.err"; then
      # The agent has not reported the invocation yet: the eventual consistency the
      # poll exists to wait through.
      status=Pending
    else
      failures=$((failures + 1))
      if [ "$failures" -ge "$POLL_FAILURES_BOUND" ]; then
        echo "$word: $failures polls in a row failed, the last: $(head -1 "$stem.poll.err"); the send is uncertain"
        return 2
      fi
      status=Pending
    fi
    case "$status" in
      Pending|InProgress|Delayed) sleep "$POLL_SECONDS" ;;
      *) break ;;
    esac
  done
  if ! aws ssm get-command-invocation "${CLI_TIMEOUTS[@]}" --command-id "$cid" --instance-id "$IID" \
      --query '{Status:Status,Code:ResponseCode,Out:StandardOutputContent,Err:StandardErrorContent}' \
      --output json > "$stem.json" 2> "$stem.read.err"; then
    echo "$word: the command ended $status and its result could not be read ($(head -1 "$stem.read.err")); the send is uncertain"
    return 2
  fi
  jq -r .Out "$stem.json" > "$stem.out"
  sed "s/^/$word: /" "$stem.out"
  jq -r .Err "$stem.json" | sed "s/^/$word (stderr): /"
  RESPONSE_CODE=$(jq -r .Code "$stem.json")
  LAST_OUT="$stem.out"
  case "$status" in
    Success) return 0 ;;
    Failed) echo "$word: the process exited $RESPONSE_CODE"; return 1 ;;
    *) echo "$word: the transport reported $status; the state is read before anything is re-sent"; return 2 ;;
  esac
}

field() {
  sed -n "s/^$2=//p" "$1" | head -1
}

# A send every step depends on: a refusal ends the job red (the output above said why);
# an uncertain end ends it red too, naming the path that reads the state under fresh
# credentials, since this job's may be the reason it could not.
must() {
  local outcome=0
  send "$@" || outcome=$?
  case "$outcome" in
    0) ;;
    2)
      echo "the state cannot be read from this job (its credentials are the deploy role's one-hour session); dispatch continue-run for $RUN_ID attempt $ATTEMPT with launch=$LAUNCH to continue from the recorded state"
      exit 1
      ;;
    *) exit 1 ;;
  esac
}

common=(
  "RUN_SHA=$GITHUB_SHA" "RUN_ID=$RUN_ID" "ATTEMPT=$ATTEMPT"
)

work_sends=0
ADMITTED_WORLD=""
ADMITTED_COMMIT=""
ADMITTED_LEDGER=""
case "$MODE" in
  run)
    must launch "${common[@]}" LIFECYCLE_COMMAND=launch \
      "WORLD_VERSION=$INPUT_WORLD_VERSION" "SCENARIO=$INPUT_SCENARIO" "SYSTEM=$INPUT_SYSTEM" \
      "CONDITION=$INPUT_CONDITION" "LEVEL=$INPUT_LEVEL" \
      "REGISTRATION_COMMIT=$REGISTRATION_COMMIT" "REQUEST_ID=$REQUEST_ID" \
      "ADMITTER=$ADMITTER" "AUTHORITY=$AUTHORITY" "LEDGER=$LEDGER" \
      "THRESHOLD_PICO=$THRESHOLD_PICO" "LIMIT_PICO=$LIMIT_PICO" \
      "FRAPPE_BASE_URL=$INPUT_FRAPPE_BASE_URL" "JIRA_BASE_URL=$INPUT_JIRA_BASE_URL"
    LAUNCH=$(field "$LAST_OUT" launch)
    test -n "$LAUNCH" || { echo "launch printed no launch identity"; exit 1; }
    step=work
    ;;
  continue)
    if [ -n "$INPUT_PAYLOAD_DIGEST" ]; then
      must deliver "${common[@]}" LIFECYCLE_COMMAND=deliver \
        "APPROVER=github:$GITHUB_ACTOR" "PAYLOAD_DIGEST=$INPUT_PAYLOAD_DIGEST"
    fi
    step=status
    ;;
esac

while :; do
  case "$step" in
    work)
      work_sends=$((work_sends + 1))
      if [ "$work_sends" -gt "$WORK_SENDS_BOUND" ]; then
        echo "the attempt did not progress after $WORK_SENDS_BOUND work sends; an operator decides"
        exit 1
      fi
      outcome=0
      send work "${common[@]}" LIFECYCLE_COMMAND=work "LAUNCH=$LAUNCH" "APPROVAL=$APPROVAL" || outcome=$?
      if [ "$outcome" -eq 1 ]; then
        case "$RESPONSE_CODE" in
          2|3)
            echo "work failed with exit status $RESPONSE_CODE (a configuration fault or an unexpected failure), which no re-send cures"
            exit 1
            ;;
          4)
            # The host refused to start beside the attempt's running container: not a
            # work send that counts, and the state is read until that container ends.
            work_sends=$((work_sends - 1))
            ;;
          1) ;;
          *)
            echo "work: the process ended with status $RESPONSE_CODE, which it does not choose for itself (the host killed it); the state is read"
            ;;
        esac
      fi
      step=status
      ;;
    status)
      must status "${common[@]}" LIFECYCLE_COMMAND=status "APPROVAL=$APPROVAL"
      next=$(field "$LAST_OUT" next)
      container=$(field "$LAST_OUT" container)
      recoveries=$(field "$LAST_OUT" recoveries)
      ADMITTED_WORLD=$(field "$LAST_OUT" world_version)
      ADMITTED_COMMIT=$(field "$LAST_OUT" registration_commit)
      ADMITTED_LEDGER=$(field "$LAST_OUT" ledger)
      echo "status: next=$next after ${recoveries:-?} recoveries, container=$container"
      if [ "$container" = running ] && { [ "$next" = work ] || [ "$next" = recover ]; }; then
        echo "status: the attempt's work container is still running; read again in $POLL_SECONDS s"
        sleep "$POLL_SECONDS"
        continue
      fi
      case "$next" in
        work) step=work ;;
        recover) step=work ;;
        wait)
          echo "## $RUN_ID attempt $ATTEMPT waits for a human: review-approval in Session Manager, then continue-run with launch=$LAUNCH" >> "$SUMMARY"
          echo "the attempt waits for a human's approval; this job ends"
          exit 0
          ;;
        publish) step=publish ;;
        hold)
          echo "the attempt is held past the recovery bound; an operator decides"
          exit 1
          ;;
        *) echo "status printed no next step the driver knows: '$next'"; exit 1 ;;
      esac
      ;;
    publish)
      if [ -z "$ADMITTED_WORLD" ] || [ -z "$ADMITTED_COMMIT" ] || [ -z "$ADMITTED_LEDGER" ]; then
        echo "status printed no world version, registration commit or ledger for the attempt; the inventory cannot be scoped and nothing is published"
        exit 1
      fi
      must publish "${common[@]}" LIFECYCLE_COMMAND=publish
      must inventory "${common[@]}" LIFECYCLE_COMMAND=inventory \
        "WORLD_VERSION=$ADMITTED_WORLD" "REGISTRATION_COMMIT=$ADMITTED_COMMIT" \
        "LEDGER=$LEDGER" "ADMITTED_LEDGER=$ADMITTED_LEDGER"
      {
        echo "## $RUN_ID attempt $ATTEMPT published"
        echo
        echo '```'
        cat "$LAST_OUT"
        echo '```'
      } >> "$SUMMARY"
      exit 0
      ;;
  esac
done
