"""Fixture support for the demo surface's publishability: a recorded history moved into a
named world and run, so a test holds a closed attempt of the served world beside one of
another world in one log, and the configuration that serves the first.

The log histories freeze the fixtures' context (world ``7b806ed6``, ``scenario_003``), and
the demo configuration requires a sixty-four-hex served version, so a history's admission is
re-stated here with the world version the test names; every later event is kept as recorded,
since the fold compares the admission's table and policy with the rules and never its
context. ``run_id`` moves the whole history under another run so two attempts coexist in
one log.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from leaveimpact.agent.log_events import Admitted, LoggedEvent
from leaveimpact.app.config import DemoConfiguration, committed_configuration
from leaveimpact.app.public import PublicId, PublishableRow
from leaveimpact.core.ids import ScenarioId, WorldVersion
from tests.unit import log_histories as histories

CONFIGURATION: DemoConfiguration = committed_configuration()
SERVED: WorldVersion = CONFIGURATION.served_world_version
OTHER_WORLD = WorldVersion("2" * 64)
"""A world the configuration does not serve, standing for the embargoed measurement world."""
SCENARIO = ScenarioId("scenario_003")
"""The fixtures' scenario, which ``history_in_world`` keeps."""
PUBLISHED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

CLOSED = "facts beside tools in one answer"


def row(
    public_id: str,
    run_id: str,
    world: WorldVersion,
    scenario: ScenarioId = SCENARIO,
    title: str | None = None,
) -> PublishableRow:
    """A publishable row for attempt 1 of ``run_id``, as the operator would have written it."""
    return PublishableRow(
        PublicId(public_id), run_id, 1, world, scenario, title, PUBLISHED_AT, "operator:test"
    )


class Rows:
    """The publishable table as a list, the store's two reads over it."""

    def __init__(self, *rows: PublishableRow) -> None:
        self.rows = rows

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]:
        return tuple(each for each in self.rows if each.world_version == world_version)

    def row_of(self, public_id: PublicId) -> PublishableRow | None:
        return next((each for each in self.rows if each.public_id == public_id), None)


def admission_only(world_version: WorldVersion, *, run_id: str) -> tuple[LoggedEvent, ...]:
    """An attempt admitted and nothing more: open, under ``world_version`` and ``run_id``."""
    return history_in_world(CLOSED, world_version, run_id=run_id)[:1]


def history_in_world(
    name: str, world_version: WorldVersion, *, run_id: str | None = None
) -> tuple[LoggedEvent, ...]:
    """The recorded history ``name`` with its admission re-stated under ``world_version``
    and, when given, ``run_id``; the fixtures' scenario kept."""
    events = histories.HISTORIES[name]()
    first = events[0]
    assert isinstance(first.event, Admitted)
    inputs = first.event.inputs
    context = replace(inputs.context, world_version=world_version)
    moved = replace(inputs, context=context, run_id=run_id or inputs.run_id)
    return (replace(first, event=Admitted(moved)), *events[1:])
