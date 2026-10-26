"""Every published replay's digests regenerated from its log and held to its publication
record: the production acceptance of a format bump (the demo milestone's live-path step,
fork 10 as the external read amended it).

A replay page proves that an older log still renders; it says nothing about whether the
bytes the log was published as still reproduce. The publication record of each attempt
holds the digest of the closed log the reader folded and the digest of the export object it
wrote, both computed under the writer of that day. This reads every published row of the
served world, folds its log under the surface's rules, digests the log and the re-exported
bytes under the current code, and holds both to the record, with the export's format beside
the record's. A difference is named by its kind, never by its value; the operator runs it on
the instance after a deploy that moves a format or a codec, and the step's record cites the
count.

Nothing here writes: the reads are the surface's own (the publishable rows, the log's fold,
the reader's export) and the record's, and the module imports no module that sends a request
to a model or a vendor, which the restore drill's import test holds for its sibling and a
test here holds for this one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import log_digest
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStoreInvariantBroken
from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.public import PublishableRow
from leaveimpact.app.read_model import LogReads, PublishableReads
from leaveimpact.app.restore import Check
from leaveimpact.core.inventory import PublicationStatus
from leaveimpact.core.run_export_json import export_bytes


@dataclass(frozen=True, slots=True)
class PublicationReads:
    """Everything the verification reads, bound by the command to the instance's stores:
    the publishable rows, the log's fold, the publication record by run and attempt, and
    the configuration and rules the surface serves under."""

    rows: PublishableReads
    log: LogReads
    publication_of: Callable[[str, int], PublicationRecord | None]
    configuration: DemoConfiguration
    rules: Rules


def verify_publications(reads: PublicationReads) -> tuple[Check, ...]:
    """One check per published row of the served world, oldest first, named by its public
    id: passed when the record is published and the log digest, the export digest and the
    export format all reproduce from the log under this code."""
    rows = reads.rows.rows_for(reads.configuration.served_world_version)
    return tuple(_check(reads, row) for row in rows)


def _check(reads: PublicationReads, row: PublishableRow) -> Check:
    name = str(row.public_id)
    subject = f"run {row.run_id} attempt {row.attempt}"
    record = reads.publication_of(row.run_id, row.attempt)
    if record is None:
        return Check(name, False, f"{subject}: no publication record")
    if record.state is not PublicationStatus.PUBLISHED:
        return Check(name, False, f"{subject}: the publication record is {record.state.value}")
    try:
        state = reads.log.load(row.run_id, row.attempt, rules=reads.rules)
        export = export_of(state)
    except (LogStoreInvariantBroken, ValueError) as error:
        return Check(name, False, f"{subject}: refused while reading: {error}")
    inputs = state.inputs
    assert inputs is not None, "a closed attempt was admitted"
    content = export_bytes(export)
    differences: list[str] = []
    if log_digest(state.events) != record.log_digest:
        differences.append("the log digest differs")
    if hashlib.sha256(content).hexdigest() != record.object_digest:
        differences.append("the export digest differs")
    if export.format_version != record.export_format:
        differences.append(
            f"the export is format {export.format_version}; the record says "
            f"{record.export_format}"
        )
    what = "both digests reproduced" if not differences else "; ".join(differences)
    detail = (
        f"{subject}: log format {inputs.log_format_version}, export format "
        f"{export.format_version}, {len(state.events)} events: {what}"
    )
    return Check(name, not differences, detail)


__all__ = ["PublicationReads", "verify_publications"]
