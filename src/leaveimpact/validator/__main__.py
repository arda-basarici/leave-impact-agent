"""The validation job: ``python -m leaveimpact.validator --world-version HEX``.

The composition of one validation run and nothing of its logic: the request from the
command line and the runner's identifiers, the deployment from the environment through
the shared wiring, the stores as readers, the one publication callable, and the
validator's composition over them. What it prints is what a reader of the Actions log
needs: the verdict's word, the key it landed at and its version id — never a credential
or a host. A fault in the raw configuration exits with status 2 and its message; a
refused verdict exits with status 1 after publishing, so the run is red and the verdict
is still there to read; an approved one exits 0. Everything else propagates as the loud
operational failure it is.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from leaveimpact.adapters.wiring import (
    ConfigurationError,
    deployment_from_env,
    readers_for,
    verdict_publisher,
)
from leaveimpact.validator.entrypoint import parse_request, validate_world
from leaveimpact.validator.verdict import Approval


def main(argv: Sequence[str] | None = None) -> int:
    try:
        request = parse_request(sys.argv[1:] if argv is None else argv, os.environ)
        deployment = deployment_from_env(os.environ)
    except ConfigurationError as error:
        print(f"leaveimpact.validator: {error}", file=sys.stderr)
        return 2

    published = validate_world(
        request, deployment.hosts, readers_for(deployment), verdict_publisher(deployment)
    )
    print(f"verdict_key={published.key}")
    print(f"verdict_version_id={published.version_id}")
    print(f"world_version={request.world_version}")
    print(f"approval={published.approval.value}")
    return 0 if published.approval is Approval.APPROVED else 1


if __name__ == "__main__":
    sys.exit(main())
