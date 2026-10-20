"""The public names and view data of the demo surface, pure: what a URL carries, what a row
of the publishable table holds, and what a page is given to render.

A replay is addressed by a slug the operator chose at publication, never by the run id or
the attempt number (the workflow's naming and the retry history, which "public view data
only" keeps off every address and page): lowercase letters, digits and hyphens, starting
with a letter or digit, at most sixty-three characters, so it reads as a path segment with
no escaping and no case to confuse. ``PublishableRow`` is the table's row as the store
reads it back; ``PublicationDraft`` what the operator command asks the store to write,
the timestamp left to the database's clock. ``PublicAttempt`` and ``PublicReplay`` are
the views the templates receive: the listing's entry, and the replay page's header with
the attempt's ending, each built by the read model from an admitted row and nothing a
visitor should not learn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import NewType

from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.run_record import TerminalStatus

PublicId = NewType("PublicId", str)
"""A replay's public name, the slug a URL carries; made by ``public_id_of``."""

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def public_id_of(value: str) -> PublicId:
    """``value`` as a public id; ``ValueError`` naming the rule otherwise.

    >>> public_id_of("scenario-03")
    'scenario-03'
    >>> public_id_of("Scenario 3")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: a public id is lowercase letters, digits and hyphens, ... got 'Scenario 3'
    """
    if not _SLUG.match(value):
        raise ValueError(
            "a public id is lowercase letters, digits and hyphens, starting with a letter or "
            f"digit, at most 63 characters, got {value!r}"
        )
    return PublicId(value)


@dataclass(frozen=True, slots=True)
class PublicationDraft:
    """What the operator asks the store to write: the row without its timestamp, which the
    database's clock supplies, never the machine's."""

    public_id: PublicId
    run_id: str
    attempt: int
    world_version: WorldVersion
    scenario_id: ScenarioId
    title: str | None
    published_by: str


@dataclass(frozen=True, slots=True)
class PublishableRow:
    """One row of the publishable table as the store reads it back."""

    public_id: PublicId
    run_id: str
    attempt: int
    world_version: WorldVersion
    scenario_id: ScenarioId
    title: str | None
    published_at: datetime
    published_by: str

    def agrees_with(self, draft: PublicationDraft) -> bool:
        """Whether ``draft`` describes this row in every field the operator states, so a
        repeat of one publication is a no-op and a repeat with other content a conflict."""
        return (
            self.public_id == draft.public_id
            and self.run_id == draft.run_id
            and self.attempt == draft.attempt
            and self.world_version == draft.world_version
            and self.scenario_id == draft.scenario_id
            and self.title == draft.title
            and self.published_by == draft.published_by
        )


@dataclass(frozen=True, slots=True)
class PublicAttempt:
    """The listing's entry: the name, the scenario, the title and when it was published."""

    public_id: PublicId
    scenario_id: ScenarioId
    title: str | None
    published_at: datetime


@dataclass(frozen=True, slots=True)
class PublicReplay:
    """The replay page's header: the listing's entry and how the attempt ended, ``None`` for
    an attempt still open (a live run, once those exist)."""

    public_id: PublicId
    scenario_id: ScenarioId
    title: str | None
    published_at: datetime
    status: TerminalStatus | None

    @property
    def status_label(self) -> str:
        """The ending as a page says it.

        >>> at = datetime(2026, 1, 1)
        >>> PublicReplay(PublicId("x"), ScenarioId("s"), None, at, None).status_label
        'in progress'
        >>> capped = TerminalStatus.CAP_EXHAUSTED
        >>> PublicReplay(PublicId("x"), ScenarioId("s"), None, at, capped).status_label
        'stopped at the cap'
        """
        match self.status:
            case None:
                return "in progress"
            case TerminalStatus.COMPLETED:
                return "completed"
            case TerminalStatus.CAP_EXHAUSTED:
                return "stopped at the cap"
            case TerminalStatus.FAILED:
                return "failed"
