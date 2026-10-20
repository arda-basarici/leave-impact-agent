"""The read model: the one admission every read of the demo surface passes, and the public
view data it returns.

Publishability is one predicate on every read (the demo milestone's ruling): the surface
serves the one world version its configuration names, an allowlist of one, when the cache
serves it, and an attempt only when the app-owned table of publishable attempts holds it.
The predicate has two functions here because the two kinds of read cost differently. The
listing reads the table's projection alone, one indexed query for the rows of the served
version, and loads no log, so thirty titles never fold thirty histories. A content read,
anything that shows or streams what an attempt did, goes through ``admitted``, which finds
the row, requires its world version to be the served one, then loads the attempt from the
log and compares the admission's world version and scenario with the row before returning
anything. The row's world version is a projection written by the operator; the admission
is what the attempt is, and a row that disagrees with it (an operator's mistake, or a
forged row carrying the allowlisted version for an embargoed attempt) serves nothing. The
export re-check alone would have left the narration, which reads events and builds no
export, over a false row (the step's external read); so the comparison is made here, once,
for every content read.

Every refusal is ``None``: an unknown name, a row the predicate refuses and a row the log
contradicts are indistinguishable from outside, so a forced row reveals neither the
attempt's existence nor its world. The contradiction is a defect of the deployment, not a
visitor's error, and is logged here with the public id and the reason, never shown. The
cache's half of the predicate (the served version marked ready) is the route's question,
answered 503 after admission is resolved, since an unavailable cache is an operational
state and not a secret.

``rules_under`` is the surface's reading of the registration: folding a model run needs
the registered attribution table and re-dispatch policy, so the composition root loads the
registration the image ships and this function refuses one whose digest is not the
configured ``registration_digest``, which makes the configuration's digest a live check of
what the service loads rather than a label.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from leaveimpact.agent.log_ending import status_of
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.agent.registered import effective_rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.public import PublicAttempt, PublicId, PublicReplay, PublishableRow
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.registration_json import decode_registration_bytes

_log = logging.getLogger(__name__)

Report = Callable[[str], None]
"""Where a contradiction between a row and the log is recorded: the process's log by
default, a test's list when it asserts the line."""


class PublishableReads(Protocol):
    """The table's two reads, as the store provides them."""

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]: ...

    def row_of(self, public_id: PublicId) -> PublishableRow | None: ...


class LogReads(Protocol):
    """The log's one read a content resolution needs."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...


@dataclass(frozen=True, slots=True)
class Admitted:
    """A content read's admission: the row and the attempt's state the log folds to, the
    two agreeing on world version and scenario."""

    row: PublishableRow
    state: AttemptState


def rules_under(configuration: DemoConfiguration, registration: bytes) -> Rules:
    """The rules the surface folds every attempt under, from the registration bytes the
    image ships; ``ValueError`` when their digest is not the configured one."""
    digest = hashlib.sha256(registration).hexdigest()
    if digest != configuration.registration_digest:
        raise ValueError(
            f"the registration file's digest {digest[:12]}… is not the configured "
            f"{configuration.registration_digest[:12]}…: the service would fold runs under "
            "rules the demo configuration does not name"
        )
    return effective_rules(decode_registration_bytes(registration))


def listing(reads: PublishableReads, configuration: DemoConfiguration) -> tuple[PublicAttempt, ...]:
    """The published attempts of the served world, oldest first: the projection, no log."""
    return tuple(
        PublicAttempt(row.public_id, row.scenario_id, row.title, row.published_at)
        for row in reads.rows_for(configuration.served_world_version)
    )


def admitted(
    public_id: PublicId,
    reads: PublishableReads,
    log: LogReads,
    configuration: DemoConfiguration,
    rules: Rules,
    *,
    report: Report = _log.warning,
) -> Admitted | None:
    """The attempt ``public_id`` names, admitted for content, or ``None``: no row, a row
    of another world, a row the log has no attempt for, or a row the admission contradicts.
    The last two are reported through ``report`` as defects; the answer stays ``None``."""
    row = reads.row_of(public_id)
    if row is None or row.world_version != configuration.served_world_version:
        return None
    try:
        state = log.load(row.run_id, row.attempt, rules=rules)
    except ValueError as error:
        report(f"publishable row {public_id!r} names an attempt the log cannot load: {error}")
        return None
    inputs = state.inputs
    if inputs is None:
        report(f"publishable row {public_id!r} names an attempt with no admission")
        return None
    context = inputs.context
    if (context.world_version, context.scenario_id) != (row.world_version, row.scenario_id):
        report(
            f"publishable row {public_id!r} says world {row.world_version} scenario "
            f"{row.scenario_id}; the admission says world {context.world_version} scenario "
            f"{context.scenario_id}; the row serves nothing"
        )
        return None
    return Admitted(row, state)


def replay_view(admitted: Admitted) -> PublicReplay:
    """The replay page's header over an admitted attempt: its ending when closed."""
    ending = status_of(admitted.state).ending
    row = admitted.row
    return PublicReplay(
        row.public_id,
        row.scenario_id,
        row.title,
        row.published_at,
        None if ending is None else ending.status,
    )
