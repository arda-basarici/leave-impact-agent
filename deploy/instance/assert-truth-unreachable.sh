#!/bin/bash
# The public evidence that the application cannot reach the answer key: run on the
# host, under the real instance profile, right after deploy.sh in the same SSM command
# (ruling 1 of the step 12 interview, 2026-09-12; the canary of 2026-09-13). Three calls,
# in this order:
#
#   1. a list of the world bucket's `worlds/` succeeds — the positive control, so a
#      refusal below cannot be a broken credential or a dead endpoint;
#   2. a list of the truth bucket is refused with the AccessDenied code specifically;
#   3. a get of a key KNOWN TO EXIST in the truth bucket is refused with AccessDenied.
#      Known to exist, because S3 answers a get of an absent key with AccessDenied
#      whenever list is denied, whatever GetObject says — so only a real key proves the
#      get is refused (the finding that corrected the 2026-09-12 reasoning). The key is
#      the platform's canary, the one platform-owned object in either bucket.
#
# Anything else fails the command and turns the deploy run red. That red is not an
# application failure and there is no rollback: the app just deployed may be healthy
# while the boundary is not, and the fix is in the platform's IAM, not in an image.
set -euo pipefail

REGION=eu-central-1
WORLD_BUCKET=leave-impact-world-445743457479
TRUTH_BUCKET=leave-impact-truth-445743457479
CANARY=access-probe/read-denied-canary

identity=$(aws sts get-caller-identity --region "$REGION" --query Arn --output text)
echo "boundary probe under: $identity"
case "$identity" in
  *:assumed-role/leave-agent-instance/*) ;;
  *) echo "boundary probe: not the instance role, refusing to draw a conclusion"; exit 1 ;;
esac

aws s3api list-objects-v2 --region "$REGION" --bucket "$WORLD_BUCKET" --prefix worlds/ --max-keys 1 > /dev/null
echo "boundary probe: positive control passed, worlds/ listed under the instance role"

errors=$(mktemp)
trap 'rm -f "$errors"' EXIT
refused() {
  if "$@" 2> "$errors"; then
    echo "boundary probe: NOT refused: $*"
    exit 1
  fi
  if ! grep -q '(AccessDenied)' "$errors"; then
    echo "boundary probe: refused for another reason than AccessDenied: $*"
    cat "$errors"
    exit 1
  fi
  echo "boundary probe: refused with AccessDenied: $*"
}
refused aws s3api list-objects-v2 --region "$REGION" --bucket "$TRUTH_BUCKET" --max-keys 1
refused aws s3api get-object --region "$REGION" --bucket "$TRUTH_BUCKET" --key "$CANARY" /dev/null

echo "boundary probe: PASS — the truth bucket is unreachable from the instance role"
