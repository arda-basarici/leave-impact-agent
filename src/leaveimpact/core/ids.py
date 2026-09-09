"""Identifiers: one distinct type per entity kind, so ids of different kinds never mix.

Every id is a ``NewType`` over ``str``. The payoff is at the call site: a rule that takes a
need and an employee, or a projector that takes a scenario and a leave, receives several
string ids side by side, and swapping two of them is a bug the type checker now catches
instead of the validator weeks later. At run time an id is the plain string it wraps —
no object, no overhead, and it serializes as itself.

Ids are semantic, minted by the world generator (a claim id by the report's emitter),
and never a vendor's: ``emp_017`` names
an employee in every system, while the Jira option id, the calendar id and the Frappe
record name that represent that employee belong to the world manifest, projection's
receipt (DESIGN, "The generator: pure specification, materialized prose, frozen world").
Numbered kinds follow ``<prefix>_<number>`` zero-padded to three digits, so a listing of
up to a thousand sorts by number (past that, text order is still deterministic, which
is all canonical encoding needs) and a prefix says the kind at a glance; skills are
vocabulary keys
(``kafka``), not numbers. A world version is the content hash of the frozen bundle and
carries no prefix.
"""

from __future__ import annotations

import re
from typing import NewType

EmployeeId = NewType("EmployeeId", str)
TeamId = NewType("TeamId", str)
ComponentId = NewType("ComponentId", str)
WorkItemId = NewType("WorkItemId", str)
CommentId = NewType("CommentId", str)
EventId = NewType("EventId", str)
DocumentId = NewType("DocumentId", str)
ClauseId = NewType("ClauseId", str)
LeaveId = NewType("LeaveId", str)
SkillId = NewType("SkillId", str)
ScenarioId = NewType("ScenarioId", str)
ClaimId = NewType("ClaimId", str)
WorldVersion = NewType("WorldVersion", str)

NUMBERED_ID = re.compile(r"^[a-z]+_[0-9]{3,}$")
SKILL_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def _numbered(prefix: str, number: int) -> str:
    if number < 0:
        raise ValueError(f"an id number is never negative, got {prefix}:{number}")
    return f"{prefix}_{number:03d}"


def employee_id(number: int) -> EmployeeId:
    """The employee id for ``number``.

    >>> employee_id(17)
    'emp_017'
    >>> employee_id(1234)
    'emp_1234'
    """
    return EmployeeId(_numbered("emp", number))


def team_id(number: int) -> TeamId:
    """The team id for ``number`` (``team_003``)."""
    return TeamId(_numbered("team", number))


def component_id(number: int) -> ComponentId:
    """The component id for ``number`` (``comp_002``)."""
    return ComponentId(_numbered("comp", number))


def work_item_id(number: int) -> WorkItemId:
    """The work item id for ``number`` (``ticket_042``)."""
    return WorkItemId(_numbered("ticket", number))


def comment_id(number: int) -> CommentId:
    """The comment id for ``number`` (``comment_017``); numbered world-wide, not per ticket."""
    return CommentId(_numbered("comment", number))


def event_id(number: int) -> EventId:
    """The calendar event id for ``number`` (``event_009``)."""
    return EventId(_numbered("event", number))


def document_id(number: int) -> DocumentId:
    """The document id for ``number`` (``doc_004``)."""
    return DocumentId(_numbered("doc", number))


def clause_id(number: int) -> ClauseId:
    """The clause id for ``number`` (``clause_011``); numbered world-wide, not per document."""
    return ClauseId(_numbered("clause", number))


def leave_id(number: int) -> LeaveId:
    """The leave id for ``number`` (``leave_005``)."""
    return LeaveId(_numbered("leave", number))


def scenario_id(number: int) -> ScenarioId:
    """The scenario id for ``number`` (``scenario_012``)."""
    return ScenarioId(_numbered("scenario", number))


def claim_id(number: int) -> ClaimId:
    """The claim id for ``number`` (``claim_007``).

    The one numbered kind the world generator does not own: a claim id is minted by
    whichever emitter writes a report — the answer key or the agent — and identifies
    the claim inside that report only (DESIGN, "The vocabulary in code").
    """
    return ClaimId(_numbered("claim", number))


def skill_id(key: str) -> SkillId:
    """The skill id for vocabulary ``key`` — lower-case letters, digits and underscores.

    The skill vocabulary itself (which keys exist, their display names) is the world
    generator's; the domain only agrees on the key shape.

    >>> skill_id("kafka")
    'kafka'
    >>> skill_id("Kafka")
    Traceback (most recent call last):
    ...
    ValueError: a skill id is a lower-case vocabulary key, got 'Kafka'
    """
    if not SKILL_ID.match(key):
        raise ValueError(f"a skill id is a lower-case vocabulary key, got {key!r}")
    return SkillId(key)


def is_numbered_id(value: str) -> bool:
    """Whether ``value`` has the ``<prefix>_<number>`` shape every numbered id kind shares.

    A shape check, not a kind check: it accepts ``emp_017`` and ``ticket_042`` alike and
    rejects a vendor key such as ``LIA-42`` that leaked in where a world id belongs.

    >>> is_numbered_id("emp_017"), is_numbered_id("LIA-42")
    (True, False)
    """
    return NUMBERED_ID.match(value) is not None
