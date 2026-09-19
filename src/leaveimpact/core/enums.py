"""The closed vocabularies of the domain, as ``StrEnum`` — their members are the wire format.

A ``StrEnum`` member *is* its string, so an entity serializes to the manifest, an answer
key or a report with the member's value and re-enters through the enum's constructor,
which rejects a value outside the vocabulary by name (the SteamLens contracts
precedent). A vocabulary lives here only when domain logic reads it: a work item's
status, a document's kind, an employee's employment terms that a policy clause may scope
by. Values an established outside namespace owns — an IANA zone key, a country code, a
city name — stay plain strings on the entity, since an enum would claim a vocabulary
the project does not own.

Members can grow as scenario classes arrive; a member is never renamed once a world has
been sealed under it, because sealed artifacts carry the value.
"""

from __future__ import annotations

from enum import StrEnum


def require_member[E: StrEnum](value: E, vocabulary: type[E], what: str) -> E:
    """``value`` if it is a member of ``vocabulary``; ``ValueError`` otherwise.

    A member equals its string, so a plain string passes every equality check and
    every dict lookup and fails only where a rule compares the member by identity, or
    where a message reads ``.value``: a silently skipped rule, an ``AttributeError``
    far from the cause. A constructor calls this on each enum-typed field so the
    near-miss fails at construction, naming the field; the JSON decoders never trip
    it, since they build members through the vocabulary's constructor.

    >>> require_member(WorkItemStatus.DONE, WorkItemStatus, "a status")
    <WorkItemStatus.DONE: 'done'>
    >>> require_member("done", WorkItemStatus, "a status")
    Traceback (most recent call last):
    ...
    ValueError: a status is a member of WorkItemStatus, got 'done'
    """
    if not isinstance(value, vocabulary):
        raise ValueError(f"{what} is a member of {vocabulary.__name__}, got {value!r}")
    return value


class Source(StrEnum):
    """The four systems evidence comes from — one adapter each, one boundary each.

    The corpus is the project's own document system, the fourth target beside the three
    vendors, so a policy clause is evidence from a source like any other.
    """

    FRAPPE = "frappe"
    JIRA = "jira"
    CALENDAR = "calendar"
    CORPUS = "corpus"


class EntityKind(StrEnum):
    """The kinds of thing a reference names: a fact's subject, an evidence target, an artifact.

    One vocabulary serves every reference: a predicate restricts itself to the kinds it
    is about, an impact key to the kinds its subtype allows. ``COMMENT`` exists for
    evidence alone — no predicate is about a comment, but a qualification may be
    evidenced by one, which is why comments carry ids.
    """

    EMPLOYEE = "employee"
    TEAM = "team"
    COMPONENT = "component"
    WORK_ITEM = "work_item"
    COMMENT = "comment"
    EVENT = "event"
    DOCUMENT = "document"
    CLAUSE = "clause"
    LEAVE = "leave"


class WorkItemStatus(StrEnum):
    """A work item's workflow state as the tracker reports it.

    "Blocked" is deliberately absent: in this world a blockage is said in a comment
    while the tracker still reads ``in_progress`` — the planted disagreement the
    investigator has to reconcile, which a status member would resolve for it.
    """

    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class DocumentKind(StrEnum):
    """What a corpus document is: the kinds that carry answer-changing prose.

    A runbook names owners and procedures; a client note names a contact; a procedure
    states what an activity requires; a policy scopes a rule to a population.
    """

    RUNBOOK = "runbook"
    CLIENT_NOTE = "client_note"
    PROCEDURE = "procedure"
    POLICY = "policy"


class LeaveKind(StrEnum):
    """The type of a leave record, as the HR system classifies it."""

    ANNUAL = "annual"
    SICK = "sick"
    PARENTAL = "parental"
    UNPAID = "unpaid"


class LeaveStatus(StrEnum):
    """Whether a leave is approved or still a request — a request is not yet an absence."""

    APPROVED = "approved"
    REQUESTED = "requested"


class EmploymentType(StrEnum):
    """The employment terms a policy clause may scope by (a contractor clause, say)."""

    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"


class Grade(StrEnum):
    """The seniority grade a policy clause may scope by."""

    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
