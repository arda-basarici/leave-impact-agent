"""The container's command until the first application slice: state the image's identity.

An image that can say which commit built it is the provenance floor every later
artifact (event logs, eval runs, reports) inherits — the Dockerfile refuses to build
without ``CODE_VERSION``, and this entry point is how a running container proves it
received one. Replaced by the real service entry point when the first HTTP surface
lands; Compose's ``restart`` policy flips with it.
"""

import os
import sys


def main() -> int:
    version = os.environ.get("LEAVEIMPACT_CODE_VERSION")
    if not version:
        print(
            "leaveimpact: LEAVEIMPACT_CODE_VERSION unset — image built without provenance",
            file=sys.stderr,
        )
        return 1
    print(f"leaveimpact {version}: no service yet; the baseline image runs and identifies itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
