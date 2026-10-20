"""The demo surface's operator commands, one command per execution: ``bootstrap`` applies
the app schema, which the deploy runs after the log's bootstrap and before the service
starts.

Apart from the package root's ``python -m leaveimpact``, which is the image's command
(serve with no argument, the identity line, the smoke) and answers to nothing else, so a
deploy's operator step cannot be mistaken for the service and the root's exact-argument
contract stays as the deploy test holds it. The command reads the database from the
environment the compose file composes, prints one line of what it established, and exits 1
on a refusal the store names (another schema version, a store that does not answer) and 2
on a command line that is not a command; the deploy fails on either before the service
starts, the DEPLOYED marker keeping the previous sha.

``main`` takes the store's constructor as a seam so the unit level drives it over a fake
and the integration level over the real database.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence

from leaveimpact.app.store import (
    SCHEMA_VERSION,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
)

DATABASE = "DATABASE_URL"
BOOTSTRAP = "bootstrap"

MakeStore = Callable[[str], AppStore]


def _store_over(dsn: str) -> AppStore:
    return AppStore(dsn=dsn)


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: MakeStore = _store_over,
) -> int:
    """``bootstrap`` applies the app schema to the database the environment names and
    prints the version established; 1 when the store refuses or does not answer, 2 on any
    other command line or without a database."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    environment = os.environ if env is None else env
    if arguments != [BOOTSTRAP]:
        print(
            f"leaveimpact.app: unknown arguments {arguments}; the one command is {BOOTSTRAP!r}",
            file=sys.stderr,
        )
        return 2
    dsn = environment.get(DATABASE, "").strip()
    if not dsn:
        print(f"leaveimpact.app: {DATABASE} is not set and the command needs it", file=sys.stderr)
        return 2
    try:
        store(dsn).ensure_schema()
    except (AppStoreInvariantBroken, AppStoreUnavailable) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    print(f"app schema version {SCHEMA_VERSION} established")
    return 0


if __name__ == "__main__":
    sys.exit(main())
