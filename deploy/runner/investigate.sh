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
# re-send would meet it again. A send the transport reports uncertainly (timed out,
# cancelled, lost) is never re-sent blind: the state is read first, and an in-flight
# command is never re-sent at all. The step's two probes (2026-10-13) showed what
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
# Identities are the workflow run's: run id `run-<GITHUB_RUN_ID>`, attempt
# `GITHUB_RUN_ATTEMPT`, request id `req-<run id>-a<attempt>` (a re-run of the job
# is the next attempt; a retry of a send inside the job is the same request, and
# the admission answers it with its receipt). The launch identity is the plan's
# printed one, held for every work send of the attempt; the approve workflow takes
# it as an input. The admitter and the threshold's authority are this workflow;
# the approver is the human who dispatched the approve workflow after reading the
# payload in Session Manager.
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
    : "${INPUT_RUN_ID:?}" "${INPUT_ATTEMPT:?}" "${INPUT_LAUNCH:?}"
    INPUT_PAYLOAD_DIGEST=${INPUT_PAYLOAD_DIGEST:-}
    RUN_ID="$INPUT_RUN_ID"
    ATTEMPT="$INPUT_ATTEMPT"
    # A continued attempt resumes under the human policy whether or not a delivery is
    # made now: an approval already given reads as approved, and none requested as work.
    APPROVAL=human
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
  {
    for pair in "$@"; do
      printf 'export %s=%q\n' "${pair%%=*}" "${pair#*=}"
    done
    cat "$HOST_SCRIPT"
  } | jq -Rs --arg t "$EXECUTION_TIMEOUT" '{commands: [.], executionTimeout: [$t]}' > "$stem.payload.json"
  local cid
  cid=$(aws ssm send-command --instance-ids "$IID" --document-name AWS-RunShellScript \
    --comment "$word $RUN_ID/$ATTEMPT" --parameters "file://$stem.payload.json" \
    --query Command.CommandId --output text)
  echo "$word: command $cid on $IID"
  local status
  while :; do
    status=$(aws ssm get-command-invocation --command-id "$cid" --instance-id "$IID" \
      --query Status --output text 2>/dev/null || echo Pending)
    case "$status" in
      Pending|InProgress|Delayed) sleep "$POLL_SECONDS" ;;
      *) break ;;
    esac
  done
  aws ssm get-command-invocation --command-id "$cid" --instance-id "$IID" \
    --query '{Status:Status,Code:ResponseCode,Out:StandardOutputContent,Err:StandardErrorContent}' \
    --output json > "$stem.json"
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

common=(
  "RUN_SHA=$GITHUB_SHA" "RUN_ID=$RUN_ID" "ATTEMPT=$ATTEMPT"
)

work_sends=0
recoveries=0
case "$MODE" in
  run)
    send launch "${common[@]}" LIFECYCLE_COMMAND=launch \
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
      send deliver "${common[@]}" LIFECYCLE_COMMAND=deliver \
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
      if [ "$outcome" -eq 1 ] && [ "$RESPONSE_CODE" != 1 ] && [ "$RESPONSE_CODE" != 4 ]; then
        echo "work failed with exit status $RESPONSE_CODE, which no re-send cures"
        exit 1
      fi
      if [ "$outcome" -eq 1 ] && [ "$RESPONSE_CODE" = 4 ]; then
        # The host refused to start beside the attempt's running container: not a
        # work send that counts, and the state is read until that container ends.
        work_sends=$((work_sends - 1))
      fi
      step=status
      ;;
    status)
      send status "${common[@]}" LIFECYCLE_COMMAND=status "RECOVERIES=$recoveries" "APPROVAL=$APPROVAL"
      next=$(field "$LAST_OUT" next)
      container=$(field "$LAST_OUT" container)
      echo "status: next=$next after $recoveries recoveries, container=$container"
      if [ "$container" = running ] && { [ "$next" = work ] || [ "$next" = recover ]; }; then
        echo "status: the attempt's work container is still running; read again in $POLL_SECONDS s"
        sleep "$POLL_SECONDS"
        continue
      fi
      case "$next" in
        work) step=work ;;
        recover) recoveries=$((recoveries + 1)); step=work ;;
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
      send publish "${common[@]}" LIFECYCLE_COMMAND=publish
      send inventory "${common[@]}" LIFECYCLE_COMMAND=inventory
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
