"""The evaluation job: ``python -m leaveimpact.evaluator {prove,evaluate} --world-version HEX``.

The composition of one execution and none of its logic: the request from the command line
and the runner's identifiers, the stores from the environment, the checkout the job runs
from, and the two commands over them.

The job's log is public and the world it grades against is sealed, and that decides what
this module prints. A result is printed as the fields its command returns, which hold
nothing sealed. A refusal of a known kind is printed as its message: the configuration,
the checkout, the store, the sealed world's own refusal, the stored runs, each written to
name files, keys, commits and counts and nothing else. Anything else is printed as the
name of its type and no more, with no traceback, since a traceback prints the whole chain
of causes and a cause can quote what the rules were reading. An unexpected failure is then
reproduced where the output is private; the exit status still says it happened.

Exit status: 0 for a result, 1 for a refusal, 2 for a configuration fault, 3 for anything
unexpected.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    evaluation_publisher,
    store_readers,
    stores_from_env,
)
from leaveimpact.evaluator.artifact import AmbiguousRuns
from leaveimpact.evaluator.entrypoint import (
    Command,
    EvaluationRefused,
    evaluate,
    parse_request,
    prove,
    registration_of,
)
from leaveimpact.evaluator.repository import Repository, RepositoryRefused
from leaveimpact.evaluator.sealed_world import SealedWorldRefused

_REFUSALS = (
    RepositoryRefused,
    EvaluationRefused,
    AmbiguousRuns,
    SealedWorldRefused,
    AccessRefused,
    ObjectStoreUnreachable,
    ObjectStoreMisconfigured,
)
"""The failures whose message is written to be printed."""


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> int:
    """Run one command; ``env`` and ``root`` default to the process's environment and its
    working directory, the checkout the job runs from."""
    environment = os.environ if env is None else env
    try:
        request = parse_request(sys.argv[1:] if argv is None else argv, environment)
        stores = stores_from_env(environment)
    except ConfigurationError as error:
        print(f"leaveimpact.evaluator: {error}", file=sys.stderr)
        return 2
    repository = Repository(Path.cwd() if root is None else root)
    try:
        if request.command is Command.PROVE:
            proven = prove(
                request.world_version, store_readers(stores), registration_of(repository)
            )
            print(f"world_version={proven.world_version}")
            print(f"scenarios={proven.scenarios}")
            for condition, total in proven.targets:
                print(f"retrieval_targets[{condition}]={'no answer' if total is None else total}")
            print("wrote=nothing")
        else:
            published = evaluate(
                request, store_readers(stores), evaluation_publisher(stores), repository
            )
            print(f"evaluation_key={published.key}")
            print(f"evaluation_version_id={published.version_id}")
            print(f"label={published.label.value}")
            for disposition, count in published.dispositions:
                print(f"inventory[{disposition.value}]={count}")
    except _REFUSALS as refusal:
        print(f"leaveimpact.evaluator: refused: {refusal}", file=sys.stderr)
        return 1
    except Exception as unexpected:
        print(
            f"leaveimpact.evaluator: failed with {type(unexpected).__name__}; the traceback is "
            "withheld because this log is public",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
