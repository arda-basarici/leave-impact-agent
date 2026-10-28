"""Running the lifecycle and deploy shell scripts under fake binaries: a ``bash`` found
beside git on Windows (the system one there may be WSL's), a directory of fake ``aws``,
``docker``, ``curl``, ``chown``, ``gh`` and ``flock`` scripts put first on ``PATH``, and a
log every fake appends its command line to.

The fakes answer what the scripts read and record what they ran, so a test asserts the
composed command lines, the environment a container was handed, and the sequence of sends,
without an instance, a daemon or a network (the forecast lesson applied to shell: the path
a design promises runs on fakes before the promise is written). ``aws`` answers a parameter
read with ``value-of-<name>`` (or the ``UNSET`` placeholder for the one name in
``FAKE_UNSET_PARAMETER``), an instance lookup with ``i-fake`` (nothing under
``FAKE_NO_INSTANCE``), a send with ``cmd-<n>`` after
copying the payload, and an invocation read with the test's scripted ``response-<n>.json``,
``InProgress`` first as many times as ``pending-<n>`` holds, an ``InvocationDoesNotExist``
error first as many times as ``missing-<n>`` holds, and an ``ExpiredToken`` error on every
invocation read after the ``FAKE_INVOCATION_FAIL_AFTER``-th; a parameter read of the name
in ``FAKE_PARAMETER_FAIL`` fails as a throttled CLI does. ``curl`` writes an empty JSON
object to the ``-o`` path, or, once, under ``FAKE_CURL_FAIL_ONCE``, half a document and
exit 18. ``docker`` records its line and
the ``LEAVE_IMPACT_*``, ``POSTGRES_PASSWORD`` and ``APP_TAG`` variables of its environment,
writes the plan's two files under the mounted run directory for a ``plan`` command and
prints ``launch=launch-fake``, prints the scripted ``status.txt`` for a ``status``, and
answers a ``ps`` with the scripted ``running.txt`` (the attempt's container, when the test
says it still runs), and fails a ``compose stop`` with ``FAKE_DOCKER_STOP_EXIT`` (the
deploy's drain refused). ``chown`` only records, since the real one is a no-op on Windows and
the handover to the image's user is what a test asserts. ``gh`` answers the two Actions
API reads the driver's CI guard makes with the test's scripted ``ci-runs.json`` and
``ci-jobs.json``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_SCRIPT = REPO_ROOT / "deploy" / "instance" / "lifecycle.sh"
DRIVER_SCRIPT = REPO_ROOT / "deploy" / "runner" / "investigate.sh"
DEPLOY_SCRIPT = REPO_ROOT / "deploy" / "instance" / "deploy.sh"

_FAKE_AWS = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "aws $*" >> "$FAKE_LOG"
value_after() {
  local i
  for ((i = 2; i <= $#; i++)); do
    if [ "${!i}" = "$1" ]; then i=$((i + 1)); printf '%s' "${!i}"; return; fi
  done
}
case "$1 $2" in
  "ssm get-parameter")
    name=$(value_after --name "$@")
    if [ "$name" = "${FAKE_PARAMETER_FAIL:-}" ]; then
      echo "An error occurred (ThrottlingException) when calling GetParameter: Rate exceeded" >&2
      exit 254
    fi
    if [ "$name" = "${FAKE_UNSET_PARAMETER:-}" ]; then echo "UNSET"; else echo "value-of-$name"; fi
    ;;
  "ec2 describe-instances") [ -n "${FAKE_NO_INSTANCE:-}" ] || echo i-fake ;;
  "ssm send-command")
    n=$(( $(cat "$FAKE_DIR/sends" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "$FAKE_DIR/sends"
    source=$(value_after --parameters "$@")
    cp "${source#file://}" "$FAKE_DIR/payload-$n.json"
    echo "cmd-$n" ;;
  "ssm get-command-invocation")
    cid=$(value_after --command-id "$@")
    n=${cid#cmd-}
    printf '%s\n' "invocation $n" >> "$FAKE_LOG"
    reads=$(grep -c '^invocation ' "$FAKE_LOG")
    fail_after=${FAKE_INVOCATION_FAIL_AFTER:-}
    if [ -n "$fail_after" ] && [ "$reads" -gt "$fail_after" ]; then
      echo "An error occurred (ExpiredTokenException): the security token is expired" >&2
      exit 255
    fi
    missing=$(cat "$FAKE_DIR/missing-$n" 2>/dev/null || echo 0)
    if [ "$missing" -gt 0 ]; then
      echo $((missing - 1)) > "$FAKE_DIR/missing-$n"
      echo "An error occurred (InvocationDoesNotExist) when calling GetCommandInvocation" >&2
      exit 255
    fi
    pending=$(cat "$FAKE_DIR/pending-$n" 2>/dev/null || echo 0)
    if [ "$pending" -gt 0 ]; then
      echo $((pending - 1)) > "$FAKE_DIR/pending-$n"; echo InProgress; exit 0
    fi
    response="$FAKE_DIR/response-$n.json"
    test -f "$response" || { echo "no scripted response $n" >&2; exit 1; }
    if [ "$(value_after --query "$@")" = Status ]; then
      jq -r .Status "$response"
    else
      cat "$response"
    fi
    ;;
  *) echo "fake aws: $*" >&2; exit 1 ;;
esac
"""

_FAKE_FLOCK = r"""#!/usr/bin/env bash
# flock(1) is util-linux's and git's bash on Windows ships none; the deploy script takes
# it with -n, whose documented answer to a held lock is exit 1. FAKE_FLOCK_HELD scripts
# the held lock; otherwise the lock is taken.
set -euo pipefail
printf '%s\n' "flock $*" >> "$FAKE_LOG"
[ -z "${FAKE_FLOCK_HELD:-}" ] || exit 1
"""

_FAKE_DOCKER = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "docker $*" >> "$FAKE_LOG"
n=$(( $(cat "$FAKE_DIR/containers" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$FAKE_DIR/containers"
env | grep -E '^(LEAVE_IMPACT_|POSTGRES_PASSWORD=|APP_TAG=)' | sort > "$FAKE_DIR/docker-env-$n.txt"
mount=""
for ((i = 1; i <= $#; i++)); do if [ "${!i}" = "-v" ]; then i=$((i + 1)); mount="${!i}"; fi; done
host_dir="${mount%%:*}"
container_dir="${mount#*:}"
if [[ " $* " == *" leaveimpact.launch plan "* ]]; then
  out=""
  for ((i = 1; i <= $#; i++)); do if [ "${!i}" = "--out" ]; then i=$((i + 1)); out="${!i}"; fi; done
  target="$host_dir${out#"$container_dir"}"
  mkdir -p "$target"
  echo '{"request_id": "fake"}' > "$target/request.json"
  printf '%s\n' --system agent --condition normal --level base --region eu-central-1 \
    > "$target/work.args"
  echo "launch=launch-fake"
elif [[ " $* " == *" leaveimpact.launch status "* ]]; then
  cat "$FAKE_DIR/status.txt" 2>/dev/null || true
elif [[ " $* " == *" run --rm app python -m leaveimpact identity"* ]]; then
  # The image's identity line, the deploy's image check; FAKE_IDENTITY_SHA scripts a stale image.
  echo "leaveimpact ${FAKE_IDENTITY_SHA:-$DEPLOY_SHA}: the demo surface's image"
elif [[ " $* " == *" exec -T app python -c "* ]] && [[ " $* " == *"/ready"* ]]; then
  # The readiness route's body as the service answers it; FAKE_READY and FAKE_READY_SHA
  # script an unready service and a stale container answering for the new one.
  ready="${FAKE_READY:-true}"; sha="${FAKE_READY_SHA:-$DEPLOY_SHA}"
  printf '{"ready":%s,"code_version":"%s","served_world_version":"7b806ed6",' "$ready" "$sha"
  printf '"store_reachable":true,"served_world_ready":%s,"app_schema":true}
' "$ready"
elif [ "$1" = ps ]; then
  [ -z "${FAKE_DOCKER_PS_EXIT:-}" ] || exit "$FAKE_DOCKER_PS_EXIT"
  cat "$FAKE_DIR/running.txt" 2>/dev/null || true
elif [ "$1 $2" = "compose stop" ]; then
  # The deploy's drain; FAKE_DOCKER_STOP_EXIT scripts a stop the daemon refused.
  [ -z "${FAKE_DOCKER_STOP_EXIT:-}" ] || exit "$FAKE_DOCKER_STOP_EXIT"
fi
exit "${FAKE_DOCKER_EXIT:-0}"
"""

_FAKE_GH = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "gh $*" >> "$FAKE_LOG"
[ "$1" = api ] || { echo "fake gh: $*" >&2; exit 1; }
case "$2" in
  */actions/workflows/*/runs\?*) cat "$FAKE_DIR/ci-runs.json" ;;
  */actions/runs/*/jobs\?*) cat "$FAKE_DIR/ci-jobs.json" ;;
  *) echo "fake gh: $*" >&2; exit 1 ;;
esac
"""

_FAKE_CHOWN = r"""#!/usr/bin/env bash
printf '%s\n' "chown $*" >> "$FAKE_LOG"
"""

_FAKE_CURL = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "curl $*" >> "$FAKE_LOG"
for ((i = 1; i <= $#; i++)); do
  if [ "${!i}" = "-o" ]; then
    i=$((i + 1))
    if [ -n "${FAKE_CURL_FAIL_ONCE:-}" ] && [ ! -f "$FAKE_DIR/curl-failed" ]; then
      # A transfer that died mid-body: half a document on disk, the real curl's exit 18.
      touch "$FAKE_DIR/curl-failed"
      printf '{"half' > "${!i}"
      exit 18
    fi
    echo '{}' > "${!i}"
  fi
done
"""


def posix(path: Path) -> str:
    """``path`` as the bash under test spells it: on Windows the git bash form
    (``/c/Users/...``), elsewhere the path itself."""
    text = str(path)
    if os.name == "nt" and len(text) > 1 and text[1] == ":":
        return "/" + text[0].lower() + text[2:].replace("\\", "/")
    return text


def bash_path() -> str:
    """The bash the scripts run under: on Windows the one shipped with git, since the
    system's ``bash.exe`` may be WSL's and cannot see this filesystem the same way."""
    git = shutil.which("git")
    if os.name == "nt" and git is not None:
        for candidate in (
            Path(git).parents[1] / "usr" / "bin" / "bash.exe",
            Path(git).parents[2] / "usr" / "bin" / "bash.exe",
        ):
            if candidate.exists():
                return str(candidate)
    found = shutil.which("bash")
    if found is None:
        raise RuntimeError("no bash on PATH")
    return found


@dataclass(frozen=True)
class FakeBinaries:
    """The fakes' directory (first on ``PATH``), their shared scratch directory and the
    invocation log, with the environment that wires them."""

    bin_dir: Path
    fake_dir: Path
    log: Path

    def environment(self, **extra: str) -> dict[str, str]:
        """The process environment with the fakes first on ``PATH``, every ``LEAVE_IMPACT_*``
        variable and the compose secrets of this machine removed: what a container is handed
        must come from the script alone."""
        env = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith("LEAVE_IMPACT_") and name not in ("POSTGRES_PASSWORD", "APP_TAG")
        }
        env["PATH"] = str(self.bin_dir) + os.pathsep + env.get("PATH", "")
        env["FAKE_DIR"] = str(self.fake_dir)
        env["FAKE_LOG"] = str(self.log)
        env.update(extra)
        return env

    def lines(self, prefix: str) -> list[str]:
        """The recorded invocations of one fake, in order."""
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text().splitlines() if line.startswith(prefix)]

    def payload_exports(self, n: int) -> dict[str, str]:
        """The ``export`` lines of the ``n``-th send's payload, as name to value (the values
        bash-quoted by ``%q``, which these ids and URLs leave unchanged)."""
        import json

        payload = json.loads((self.fake_dir / f"payload-{n}.json").read_text())
        command = payload["commands"][0]
        exports: dict[str, str] = {}
        for line in command.splitlines():
            if line.startswith("export "):
                name, _, value = line[len("export ") :].partition("=")
                exports[name] = value
        return exports


def fake_binaries(root: Path) -> FakeBinaries:
    """The three fakes written under ``root``, executable, with an empty scratch dir."""
    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name, body in (
        ("aws", _FAKE_AWS),
        ("docker", _FAKE_DOCKER),
        ("curl", _FAKE_CURL),
        ("chown", _FAKE_CHOWN),
        ("gh", _FAKE_GH),
        ("flock", _FAKE_FLOCK),
    ):
        script = bin_dir / name
        script.write_text(body, newline="\n")
        script.chmod(0o755)
    fake_dir = root / "fake"
    fake_dir.mkdir()
    return FakeBinaries(bin_dir, fake_dir, fake_dir / "invocations.log")


def run_script(
    script: Path, env: Mapping[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """The script under bash with ``env``, output captured, never raising on its status."""
    return subprocess.run(
        [bash_path(), str(script)],
        env=dict(env),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
