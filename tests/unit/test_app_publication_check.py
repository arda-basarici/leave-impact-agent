"""The publication-digests check over fakes: a published row whose record was written by the
day's writer reproduces under this code at both readable log formats, every difference is
named by its kind, an absent or unpublished record fails by name, and a log the store
refuses is the check's failure. The real stores are the integration test's."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import LoggedEvent, log_digest
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStoreInvariantBroken
from leaveimpact.agent.log_transition import AttemptState, Rules, fold
from leaveimpact.app.public import PublishableRow
from leaveimpact.app.publication_check import PublicationReads, verify_publications
from leaveimpact.core.inventory import PublicationStatus
from leaveimpact.core.run_export_json import export_bytes
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    SERVED,
    Rows,
    history_in_world,
    row,
)

RECORDED_AT = datetime(2026, 10, 23, 2, 15, tzinfo=UTC)


class Logs:
    """A log whose attempts are scripted by run and attempt; a missing one is the store's
    refusal."""

    def __init__(self, logs: dict[tuple[str, int], tuple[LoggedEvent, ...]]) -> None:
        self.logs = logs

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        events = self.logs.get((run_id, attempt))
        if events is None:
            raise LogStoreInvariantBroken(f"run {run_id} attempt {attempt} has no log")
        return fold(events, rules)


def record_for(
    events: tuple[LoggedEvent, ...],
    *,
    state: PublicationStatus = PublicationStatus.PUBLISHED,
    log: str | None = None,
    export: str | None = None,
    export_format: int | None = None,
) -> PublicationRecord:
    """The record the day's writer would have written for ``events``, each field replaceable."""
    folded = fold(events, histories.RULES)
    built = export_of(folded)
    content = export_bytes(built)
    inputs = folded.inputs
    assert inputs is not None
    return PublicationRecord(
        inputs.run_id,
        inputs.attempt,
        state,
        cases.COMMIT,
        built.format_version if export_format is None else export_format,
        log_digest(folded.events) if log is None else log,
        "runs/x",
        hashlib.sha256(content).hexdigest() if export is None else export,
        None,
        None,
        RECORDED_AT,
    )


def reads_over(
    logs: dict[tuple[str, int], tuple[LoggedEvent, ...]],
    records: dict[tuple[str, int], PublicationRecord | None],
    *rows_: PublishableRow,
) -> PublicationReads:
    return PublicationReads(
        rows=Rows(*rows_),
        log=Logs(logs),
        publication_of=lambda run_id, attempt: records.get((run_id, attempt)),
        configuration=CONFIGURATION,
        rules=histories.RULES,
    )


def test_a_published_row_reproduces_at_both_readable_log_formats() -> None:
    written = history_in_world(CLOSED, SERVED, run_id="run-written")
    older = histories.at_format(history_in_world(CLOSED, SERVED, run_id="run-older"), 3)
    reads = reads_over(
        {("run-written", 1): written, ("run-older", 1): older},
        {("run-written", 1): record_for(written), ("run-older", 1): record_for(older)},
        row("new", "run-written", SERVED),
        row("old", "run-older", SERVED),
    )
    checks = verify_publications(reads)
    assert [(check.name, check.passed) for check in checks] == [("new", True), ("old", True)]
    assert checks[0].detail.startswith("run run-written attempt 1: log format 4, export format 4, ")
    assert checks[1].detail.startswith("run run-older attempt 1: log format 3, export format 3, ")
    assert all(check.detail.endswith("events: both digests reproduced") for check in checks)


def test_every_difference_is_named_by_its_kind_and_never_by_its_value() -> None:
    events = history_in_world(CLOSED, SERVED)
    moved = {
        "log": record_for(events, log="1" * 64),
        "export": record_for(events, export="2" * 64),
        "format": record_for(events, export_format=3),
    }
    for kind, record in moved.items():
        reads = reads_over(
            {("run-12", 1): events}, {("run-12", 1): record}, row("a", "run-12", SERVED)
        )
        (check,) = verify_publications(reads)
        assert not check.passed, kind
        assert "1" * 64 not in check.detail and "2" * 64 not in check.detail
    for kind, text in (
        ("log", "the log digest differs"),
        ("export", "the export digest differs"),
        ("format", "the export is format 4; the record says 3"),
    ):
        reads = reads_over(
            {("run-12", 1): events}, {("run-12", 1): moved[kind]}, row("a", "run-12", SERVED)
        )
        (check,) = verify_publications(reads)
        assert check.detail.endswith(f"events: {text}"), (kind, check.detail)


def test_an_absent_or_unpublished_record_and_a_refused_log_fail_by_name() -> None:
    events = history_in_world(CLOSED, SERVED)
    pending = record_for(events, state=PublicationStatus.PENDING)
    reads = reads_over(
        {("run-12", 1): events},
        {("run-12", 1): pending, ("run-13", 1): None, ("run-14", 1): record_for(events)},
        row("pending", "run-12", SERVED),
        row("absent", "run-13", SERVED),
        row("unreadable", "run-14", SERVED),
    )
    checks = verify_publications(reads)
    assert [check.passed for check in checks] == [False, False, False]
    assert checks[0].detail == "run run-12 attempt 1: the publication record is pending"
    assert checks[1].detail == "run run-13 attempt 1: no publication record"
    assert checks[2].detail.startswith("run run-14 attempt 1: refused while reading: ")


def test_only_the_served_worlds_rows_are_checked() -> None:
    events = history_in_world(CLOSED, SERVED)
    elsewhere = replace(row("other", "run-12", SERVED), world_version=cases.CONTEXT.world_version)
    reads = reads_over({("run-12", 1): events}, {("run-12", 1): record_for(events)}, elsewhere)
    assert verify_publications(reads) == ()
