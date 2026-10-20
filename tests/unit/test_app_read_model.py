"""The read model and the operator's draft over an in-memory log: the listing as the table's
projection of the served world alone; the content resolution refusing, as one ``None``, an
unknown name, a row of another world (the log never read), a row the log has no attempt
for, and a row the admission contradicts in world or scenario (the false row of the step's
external read), each defect reported with the public id; the view's ending; the
registration's rules refused on a digest the configuration does not name; and the draft
refusing an unknown, an open and an other-world attempt while copying the admission's world
and scenario, never the operator's."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.agent.registered import effective_rules
from leaveimpact.app.public import PublicAttempt, PublicId
from leaveimpact.app.publishing import PublishRefused, PublishRequest, draft_of
from leaveimpact.app.read_model import Admitted, admitted, listing, replay_view, rules_under
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.run_record import TerminalStatus
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import MemoryLog
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    OTHER_WORLD,
    SERVED,
    Rows,
    admission_only,
    history_in_world,
    row,
)
from tests.unit.registration_fixture import COMMITTED, COMMITTED_FILE

RULES = histories.RULES
SCENARIO = ScenarioId("scenario_003")
AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class CountingLog:
    """The in-memory log with its loads counted, so a test asserts a read never reached it."""

    def __init__(self, log: MemoryLog) -> None:
        self.log = log
        self.loads = 0

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        self.loads += 1
        return self.log.load(run_id, attempt, rules=rules)


@pytest.fixture
def log() -> CountingLog:
    """Three attempts in one log: a closed run of the served world (``run-12``), a closed run
    of another world (``run-13``), an open run of the served world (``run-14``)."""
    memory = MemoryLog()
    memory.seed(history_in_world(CLOSED, SERVED))
    memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-13"))
    memory.seed(admission_only(SERVED, run_id="run-14"))
    return CountingLog(memory)


# --- the listing ---------------------------------------------------------------------------------


def test_the_listing_is_the_projection_of_the_served_world_and_reads_no_log() -> None:
    rows = Rows(row("served", "run-12", SERVED), row("embargoed", "run-13", OTHER_WORLD))
    assert listing(rows, CONFIGURATION) == (PublicAttempt(PublicId("served"), SCENARIO, None, AT),)


# --- the content resolution --------------------------------------------------------------------


def test_a_row_of_the_served_world_the_admission_agrees_with_is_admitted(log: CountingLog) -> None:
    rows = Rows(row("served", "run-12", SERVED))
    result = admitted(PublicId("served"), rows, log, CONFIGURATION, RULES)
    assert isinstance(result, Admitted)
    assert result.row is rows.rows[0]
    assert result.state.inputs is not None and result.state.closed is not None
    view = replay_view(result)
    assert (view.public_id, view.scenario_id, view.status) == (
        "served",
        SCENARIO,
        TerminalStatus.COMPLETED,
    )


def test_an_unknown_name_and_a_row_of_another_world_are_none_with_the_log_never_read(
    log: CountingLog, caplog: pytest.LogCaptureFixture
) -> None:
    rows = Rows(row("embargoed", "run-13", OTHER_WORLD))
    assert admitted(PublicId("nobody"), rows, log, CONFIGURATION, RULES) is None
    assert admitted(PublicId("embargoed"), rows, log, CONFIGURATION, RULES) is None
    assert log.loads == 0
    assert caplog.records == []


def test_a_false_row_carrying_the_served_world_for_another_worlds_attempt_serves_nothing(
    log: CountingLog,
) -> None:
    """The step's external read: the row's world version is a projection; the admission is
    what the attempt is, and a forged or mistaken row that disagrees is refused as a defect
    the operator reads in the process's log, never as a page."""
    reported: list[str] = []
    rows = Rows(row("forged", "run-13", SERVED))
    assert (
        admitted(PublicId("forged"), rows, log, CONFIGURATION, RULES, report=reported.append)
        is None
    )
    assert log.loads == 1
    assert len(reported) == 1
    assert (
        "'forged'" in reported[0] and OTHER_WORLD in reported[0] and "serves nothing" in reported[0]
    )


def test_a_row_whose_scenario_disagrees_with_the_admission_serves_nothing(log: CountingLog) -> None:
    reported: list[str] = []
    rows = Rows(row("wrong-scenario", "run-12", SERVED, ScenarioId("scenario_999")))
    assert (
        admitted(
            PublicId("wrong-scenario"), rows, log, CONFIGURATION, RULES, report=reported.append
        )
        is None
    )
    assert reported and "scenario_999" in reported[0] and "scenario_003" in reported[0]


def test_a_row_for_an_attempt_the_log_lacks_is_none_and_reported(log: CountingLog) -> None:
    reported: list[str] = []
    rows = Rows(row("ghost", "run-99", SERVED))
    assert (
        admitted(PublicId("ghost"), rows, log, CONFIGURATION, RULES, report=reported.append) is None
    )
    assert reported == [
        "publishable row 'ghost' names an attempt the log cannot load: run run-99 has no attempt 1"
    ]


def test_a_defect_is_reported_to_the_process_log_by_default(
    log: CountingLog, caplog: pytest.LogCaptureFixture
) -> None:
    rows = Rows(row("ghost", "run-99", SERVED))
    with caplog.at_level("WARNING", logger="leaveimpact.app.read_model"):
        assert admitted(PublicId("ghost"), rows, log, CONFIGURATION, RULES) is None
    assert [record.getMessage() for record in caplog.records] == [
        "publishable row 'ghost' names an attempt the log cannot load: run run-99 has no attempt 1"
    ]


def test_an_open_attempts_view_has_no_status(log: CountingLog) -> None:
    rows = Rows(row("live", "run-14", SERVED))
    result = admitted(PublicId("live"), rows, log, CONFIGURATION, RULES)
    assert isinstance(result, Admitted)
    assert replay_view(result).status is None


# --- the registration's rules ------------------------------------------------------------------


def test_the_rules_are_the_committed_registrations_and_another_digest_is_refused() -> None:
    content = COMMITTED_FILE.read_bytes()
    assert rules_under(CONFIGURATION, content) == effective_rules(COMMITTED)
    with pytest.raises(
        ValueError, match="is not the configured .*rules the demo configuration does not name"
    ):
        rules_under(CONFIGURATION, content + b"\n")
    other = replace(CONFIGURATION, registration_digest="f" * 64)
    with pytest.raises(ValueError, match="not the configured ffffffffffff"):
        rules_under(other, content)


# --- the operator's draft ----------------------------------------------------------------------


def request(run_id: str, title: str | None = None) -> PublishRequest:
    return PublishRequest(run_id, 1, PublicId("example"), title, "operator:test")


def test_the_draft_copies_the_admissions_world_and_scenario(log: CountingLog) -> None:
    draft = draft_of(request("run-12", "The handover nobody wrote down"), CONFIGURATION, log, RULES)
    assert not isinstance(draft, PublishRefused)
    assert (draft.public_id, draft.run_id, draft.attempt) == ("example", "run-12", 1)
    assert (draft.world_version, draft.scenario_id) == (SERVED, SCENARIO)
    assert (draft.title, draft.published_by) == ("The handover nobody wrote down", "operator:test")


@pytest.mark.parametrize(
    ("run_id", "reason"),
    [
        (
            "run-99",
            "run run-99 attempt 1 cannot be loaded from the log: run run-99 has no attempt 1",
        ),
        ("run-14", "run run-14 attempt 1 is open; a replay is a closed run"),
        (
            "run-13",
            f"run run-13 attempt 1 is a run of world {OTHER_WORLD}, not the served world {SERVED}; "
            "only the served world is publishable",
        ),
    ],
)
def test_an_unknown_an_open_and_an_other_world_attempt_are_refused_by_name(
    log: CountingLog, run_id: str, reason: str
) -> None:
    assert draft_of(request(run_id), CONFIGURATION, log, RULES) == PublishRefused(reason)
