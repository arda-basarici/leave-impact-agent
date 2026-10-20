"""The demo surface's operator commands, one command per execution: ``bootstrap`` applies
the app schema, which the deploy runs after the log's bootstrap and before the service
starts; ``publish`` writes a replay's row in the table of publishable attempts.

Apart from the package root's ``python -m leaveimpact``, which is the image's command
(serve with no argument, the identity line, the smoke) and answers to nothing else, so an
operator step cannot be mistaken for the service and the root's exact-argument contract
stays as the deploy test holds it. Both commands read the database from the environment the
compose file composes; ``publish`` also reads the registration the image ships, at the path
its environment names, and refuses one whose digest is not the committed configuration's
(the read model's rule), since the attempt it verifies is folded under those rules. Each
prints one line of what it established and exits 1 on a refusal the stores name (another
schema version, a store that does not answer, an attempt that is not a closed run of the
served world, a name or an attempt already published) and 2 on a command line that is not
a command or an environment that lacks what the command needs.

``main`` takes the two stores' constructors, the configuration, the registration's bytes
and the registration's reading as seams, so the unit level drives it over fakes and the
integration level over the real database with a fixture history folded under the fixtures'
rules; the real reading, ``read_model.rules_under``, is the default and has its own tests.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from leaveimpact.agent.log_store import LogStore, LogStoreInvariantBroken, LogStoreUnavailable
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.main import DATABASE, REGISTRATION_FILE
from leaveimpact.app.public import public_id_of
from leaveimpact.app.publishing import PublishRefused, PublishRequest, draft_of
from leaveimpact.app.read_model import rules_under
from leaveimpact.app.store import (
    SCHEMA_VERSION,
    AlreadyPublished,
    AppStore,
    AppStoreInvariantBroken,
    AppStoreUnavailable,
    AttemptPublished,
    PublicationConflict,
    Published,
    SlugTaken,
    connect_bounded,
)

BOOTSTRAP = "bootstrap"
PUBLISH = "publish"


class LogSession(Protocol):
    """The log for one command: loaded from, then closed."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...

    def close(self) -> None: ...


MakeStore = Callable[[str], AppStore]
MakeLog = Callable[[str], LogSession]


def _store_over(dsn: str) -> AppStore:
    return AppStore(dsn=dsn)


def _log_over(dsn: str) -> LogSession:
    # The log store under the app's bounds, one command's lifetime, closed by the command.
    return LogStore(dsn=dsn, connect=connect_bounded)


def _registration_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: MakeStore = _store_over,
    log: MakeLog = _log_over,
    configuration: Callable[[], DemoConfiguration] = committed_configuration,
    registration: Callable[[str], bytes] = _registration_bytes,
    rules: Callable[[DemoConfiguration, bytes], Rules] = rules_under,
) -> int:
    """``bootstrap`` applies the app schema to the database the environment names;
    ``publish --run <id> --attempt <n> --as <public-id> --by <who> [--title <t>]`` writes
    a replay's row after verifying the attempt against the log. 0 with one printed line, 1
    when a store refuses or does not answer or the attempt is not publishable, 2 on any
    other command line or an environment that lacks the database or the registration."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    environment = os.environ if env is None else env
    try:
        parsed = _parser().parse_args(arguments)
    except SystemExit:
        return 2
    dsn = environment.get(DATABASE, "").strip()
    if not dsn:
        print(f"leaveimpact.app: {DATABASE} is not set and the command needs it", file=sys.stderr)
        return 2
    if parsed.command == BOOTSTRAP:
        return _bootstrap(store(dsn))
    return _publish(parsed, dsn, environment, store, log, configuration, registration, rules)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.app",
        description="The demo surface's operator commands, one per execution.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        BOOTSTRAP,
        description=(
            "Create the app's tables where missing and check their version; the deploy runs it."
        ),
    )
    publishing = commands.add_parser(
        PUBLISH, description="Publish a closed run of the served world as a replay."
    )
    publishing.add_argument("--run", required=True, help="the run id the log holds")
    publishing.add_argument("--attempt", required=True, type=int, help="the attempt number")
    publishing.add_argument(
        "--as", dest="public_id", required=True, help="the public name the URL carries"
    )
    publishing.add_argument("--by", required=True, help="who publishes")
    publishing.add_argument("--title", default=None, help="an introduced example's title")
    return parser


def _bootstrap(app: AppStore) -> int:
    try:
        app.ensure_schema()
    except (AppStoreInvariantBroken, AppStoreUnavailable) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    print(f"app schema version {SCHEMA_VERSION} established")
    return 0


def _publish(
    parsed: argparse.Namespace,
    dsn: str,
    environment: Mapping[str, str],
    store: MakeStore,
    log: MakeLog,
    configuration: Callable[[], DemoConfiguration],
    registration: Callable[[str], bytes],
    rules: Callable[[DemoConfiguration, bytes], Rules],
) -> int:
    registration_file = environment.get(REGISTRATION_FILE, "").strip()
    if not registration_file:
        print(
            f"leaveimpact.app: {REGISTRATION_FILE} is not set and publishing folds the "
            "attempt under the registration's rules",
            file=sys.stderr,
        )
        return 2
    try:
        public_id = public_id_of(parsed.public_id)
        demo = configuration()
        folding = rules(demo, registration(registration_file))
    except (OSError, ValueError) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    request = PublishRequest(parsed.run, parsed.attempt, public_id, parsed.title, parsed.by)
    reads = log(dsn)
    try:
        draft = draft_of(request, demo, reads, folding)
        if isinstance(draft, PublishRefused):
            print(f"leaveimpact.app: refused: {draft.reason}", file=sys.stderr)
            return 1
        outcome = store(dsn).publish(draft)
    except (
        AppStoreInvariantBroken,
        AppStoreUnavailable,
        LogStoreInvariantBroken,
        LogStoreUnavailable,
    ) as error:
        print(f"leaveimpact.app: refused: {error}", file=sys.stderr)
        return 1
    finally:
        reads.close()
    match outcome:
        case Published(row):
            print(
                f"published {row.public_id}: run {row.run_id} attempt {row.attempt}, world "
                f"{row.world_version} scenario {row.scenario_id}, at "
                f"{row.published_at.isoformat()} by {row.published_by}"
            )
            return 0
        case AlreadyPublished(row):
            print(
                f"already published {row.public_id} at {row.published_at.isoformat()} by "
                f"{row.published_by}; nothing changed"
            )
            return 0
        case SlugTaken(existing):
            reason = (
                f"{existing.public_id} already names run {existing.run_id} attempt "
                f"{existing.attempt}"
            )
        case AttemptPublished(existing):
            reason = (
                f"run {existing.run_id} attempt {existing.attempt} is already published as "
                f"{existing.public_id}"
            )
        case PublicationConflict(existing):
            reason = (
                f"{existing.public_id} is published with title {existing.title!r} by "
                f"{existing.published_by!r}; a repeat states other content and changes nothing"
            )
    print(f"leaveimpact.app: refused: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
