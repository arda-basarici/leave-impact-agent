"""The report view: a closed attempt's export as the plain data one page states, built by
pure functions and rendered by templates that format nothing themselves.

A report page is rendered from the export alone (the demo milestone's entry ruling on the
report view, as amended at its build step): nothing is re-read from a vendor or resolved
from the cache at render time, so the page is identical for a replay and a finished live
run and a vendor outage changes no page that exists. The export already holds every
record the run read, whole, as the outcome of the operation that read it, a document with
its sections' text and a ticket with its comments; so a corpus section or a comment is
shown as this run read it, by the clause or comment id a claim cites, and a citation no
completed read of the run returned renders "evidence unavailable" with the page intact.
A record the run's own reads returned two ways is shown as withdrawn with nothing
credited, by the core's own rule (``read_coverage``), the same rule the harness concluded
under and the evaluator replays over, so the page invents no third reading of a repeated
read. A person is named exactly when an employee record with that id is among the reads,
the id beside the name; otherwise the id alone.

The ending comes first and an empty or interrupted report never reads as an all-clear: a
completed run with no impact claim says it reported none, beside what it read, and never
that none exists, since that is the grader's question and the surface may not import the
grader. A cap-exhausted run shows the registered caps beside its accounted consumption and
names no stopping bound, since the log records that the approval was requested at the cap
and not which resource. Every sentence is a deterministic template over a claim's fields;
model prose reaches the page only as a quotation marked inside the text it was read from,
or as a coverage action's rationale, which the page labels model-generated.

The grouping loses no claim. Assessments and actions sit under the impact their key
names; one whose impact is not in the set is listed as unlinked; a derivation names its
target by anchor and is never rendered inside the claim that cites it, so a cycle cannot
recurse; the core's structural check of the claim set is shown as a defect banner. The
page's one input beyond the export is the log's accept instant per position, read off the
admitted state by the read model, since an export holds positions and not instants and the
timeline shows the same clock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime
from enum import StrEnum
from typing import assert_never, cast

from leaveimpact.app.public import PublicReplay
from leaveimpact.core.claims import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    ClaimType,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    Impact,
    ImpactKey,
    ImpactSubtype,
    SourceConflict,
    Unknown,
    UnknownReason,
    Verdict,
    key_order,
    structural_problems,
)
from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ClaimId
from leaveimpact.core.model_calls import ParsedBatch
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.read_coverage import coverage_from_reads
from leaveimpact.core.refs import (
    EntityRef,
    EvidenceRef,
    clause_ref,
    comment_ref,
    employee_ref,
    leave_ref,
)
from leaveimpact.core.run_ending import (
    ApprovalState,
    Approver,
    DispatchSite,
    HarnessSite,
    InputBoundSite,
    OperationSite,
)
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import TerminalStatus
from leaveimpact.core.run_trace import Operation, is_completed_read, is_failed_read, records_of
from leaveimpact.core.stated import Admitted, StatedFact
from leaveimpact.core.token_counting import COUNTING_RULES
from leaveimpact.core.values import (
    FactValue,
    Requirement,
    SkillCriterion,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan

Instants = Mapping[int, datetime]
"""The log's accept instant per position, for the positions the page labels."""


# --- The view ------------------------------------------------------------------------


class EvidenceStatus(StrEnum):
    """What the page can show for a cited record."""

    SHOWN = "shown"
    """The record as this run first read it."""
    WITHDRAWN = "withdrawn"
    """The run's own reads returned it two ways; nothing is credited (the core's rule)."""
    UNAVAILABLE = "unavailable"
    """No completed read of the run returned it."""


@dataclass(frozen=True, slots=True)
class QuoteView:
    """A model-supplied quotation from the recorded source, and whether the text as read
    contains it."""

    text: str
    predicate: str
    found: bool
    excluded: str | None
    """The composition's reason for leaving the admitted statement out of the view, when it
    did (a carrier withdrawn, a structured field contradicting it); ``None`` when it stands."""


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One evidence reference as the page shows it: the record's fields as the run read
    them, or a section's or comment's text with the record holding it, the admitted
    quotations read from it, and every position that returned it, the first one's log
    instant beside it."""

    source: Source
    target: EntityRef
    field: str | None
    status: EvidenceStatus
    label: str
    fields: tuple[tuple[str, str], ...]
    text: str | None
    held_by: str | None
    quotes: tuple[QuoteView, ...]
    positions: tuple[int, ...]
    recorded_at: datetime | None


@dataclass(frozen=True, slots=True)
class DerivationLink:
    """A claim this one was derived from, by anchor; ``available`` when the set holds it."""

    claim_id: ClaimId
    available: bool


@dataclass(frozen=True, slots=True)
class ClaimBlock:
    """One claim as the page states it: the sentence, its evidence, its derivations, and the
    fields only some kinds carry (a conflict's observations, an action's rationale)."""

    claim_id: ClaimId
    kind: ClaimType
    sentence: str
    evidence: tuple[EvidenceItem, ...]
    derived_from: tuple[DerivationLink, ...]
    observations: tuple[tuple[str, str], ...] = ()
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class ImpactSection:
    """An impact with the candidates assessed for it and the plan's action on it."""

    impact: ClaimBlock
    assessments: tuple[ClaimBlock, ...]
    actions: tuple[ClaimBlock, ...]


@dataclass(frozen=True, slots=True)
class ConstraintSection:
    """A constraint, what it applies to, and the impact about that artifact if one is
    claimed."""

    constraint: ClaimBlock
    applies_to: str
    impact_id: ClaimId | None


@dataclass(frozen=True, slots=True)
class LeaveView:
    """The leave under investigation as the HR record read in this run states it."""

    person: str
    start: date
    end: date
    days: int
    kind: str
    status: str
    evidence: EvidenceItem


@dataclass(frozen=True, slots=True)
class CapLine:
    """A registered cap beside the run's accounted consumption of it."""

    resource: str
    consumed: str
    cap: str
    at_cap: bool


@dataclass(frozen=True, slots=True)
class EndingView:
    """How the run ended, first on the page: the headline, the approval and failure lines,
    the anchor on the trail where a failure sits, the caps when the run stopped at them,
    what the run read, and whether it reported any impact."""

    status: TerminalStatus
    headline: str
    details: tuple[str, ...]
    failure_anchor: str | None
    caps: tuple[CapLine, ...]
    reads_summary: str
    empty: bool


@dataclass(frozen=True, slots=True)
class ConditionView:
    """The sources the run could not reach, and the unknowns recorded as caused by that."""

    unreachable: tuple[Source, ...]
    unknown_ids: tuple[ClaimId, ...]


@dataclass(frozen=True, slots=True)
class ReportHeader:
    """The page's identity: the public name, the scenario and its date in the reference
    timezone, the system, the world, and the run's window on the log's clock."""

    public_id: str
    title: str | None
    scenario_id: str
    scenario_date: date
    timezone: str
    system: str
    world_version: str
    admitted_at: datetime
    terminal_at: datetime


@dataclass(frozen=True, slots=True)
class ReportView:
    """The whole page, in the manager's reading order."""

    header: ReportHeader
    ending: EndingView
    condition: ConditionView
    leave_id: str
    leave: LeaveView | None
    impacts: tuple[ImpactSection, ...]
    constraints: tuple[ConstraintSection, ...]
    unknowns: tuple[ClaimBlock, ...]
    conflicts: tuple[ClaimBlock, ...]
    unlinked: tuple[ClaimBlock, ...]
    problems: tuple[str, ...]

    def claim_ids(self) -> tuple[ClaimId, ...]:
        """Every claim the page states, in page order; the acceptance's "each exactly once"."""
        ids: list[ClaimId] = []
        for section in self.impacts:
            ids.append(section.impact.claim_id)
            ids.extend(block.claim_id for block in section.assessments)
            ids.extend(block.claim_id for block in section.actions)
        ids.extend(section.constraint.claim_id for section in self.constraints)
        for blocks in (self.unknowns, self.conflicts, self.unlinked):
            ids.extend(block.claim_id for block in blocks)
        return tuple(ids)


# --- The reads, indexed --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Part:
    """A section or a comment as first returned, inside the record holding it."""

    text: str
    parent: EntityRef


class _Reads:
    """The run's completed reads by reference: each record as first returned, each section
    and comment as first returned with its parent, every position that returned each, and
    the references the core's coverage mapping withdrew."""

    def __init__(self, operations: Iterable[Operation]) -> None:
        made = tuple(operations)
        self.first: dict[EntityRef, Observed[Entity]] = {}
        self.parts: dict[EntityRef, _Part] = {}
        self.positions: dict[EntityRef, list[int]] = {}
        for operation in made:
            if operation.position is None or not is_completed_read(operation.outcome):
                continue
            for record in records_of(operation.outcome):
                self.first.setdefault(record.ref, record)
                self.positions.setdefault(record.ref, []).append(operation.position)
                for ref, part in _parts_of(record):
                    self.parts.setdefault(ref, part)
                    self.positions.setdefault(ref, []).append(operation.position)
        self.withdrawn = coverage_from_reads(made).unobserved

    def label(self, ref: EntityRef) -> str:
        """The record's name or title with its id when the run read it; the id alone when
        it did not."""
        record = self.first.get(ref)
        if record is None:
            part = self.parts.get(ref)
            if part is None:
                return ref.id
            return f"{ref.id} of {self.label(part.parent)}"
        value = record.value
        match value:
            case Employee() | Team() | Component():
                name = value.name
            case WorkItem() | CalendarEvent() | Document():
                name = value.title
            case Leave():
                return ref.id
            case _:
                assert_never(value)
        return f"{name} ({ref.id})"


def _parts_of(record: Observed[Entity]) -> tuple[tuple[EntityRef, _Part], ...]:
    value = record.value
    if isinstance(value, Document):
        return tuple(
            (clause_ref(section.id), _Part(section.text, record.ref)) for section in value.sections
        )
    if isinstance(value, WorkItem):
        return tuple(
            (comment_ref(comment.id), _Part(comment.text, record.ref)) for comment in value.comments
        )
    return ()


@dataclass(frozen=True, slots=True)
class _Statements:
    """The admitted statements by the carrier they were read from, and the composition's
    exclusion reason for each it left out of the view."""

    by_carrier: Mapping[EntityRef, tuple[StatedFact, ...]]
    excluded: Mapping[StatedFact, str]


def _admitted_statements(export: RunExport) -> _Statements:
    """The statements the fact-admission rules admitted, by carrier, with the exclusions."""
    by_carrier: dict[EntityRef, list[StatedFact]] = {}
    for call in export.trace.model_calls:
        if call.answer is None:
            continue
        for batch in call.answer.fact_batches:
            if not isinstance(batch, ParsedBatch):
                continue
            for entry in batch.entries:
                if isinstance(entry, Admitted):
                    by_carrier.setdefault(entry.fact.carrier, []).append(entry.fact)
    excluded = {
        left_out.fact: left_out.reason.value.replace("_", " ")
        for left_out in export.trace.composition.exclusions
    }
    return _Statements({carrier: tuple(facts) for carrier, facts in by_carrier.items()}, excluded)


def _text(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return ", ".join(_text(item) for item in items) if items else "none"
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _fields_of(record: Observed[Entity]) -> tuple[tuple[str, str], ...]:
    """A record's fields as read, the sections and comments left to their own items."""
    value = record.value
    return tuple(
        (field.name, _text(getattr(value, field.name)))
        for field in fields(value)
        if field.name not in ("sections", "comments")
    )


def _evidence(
    cited: EvidenceRef,
    reads: _Reads,
    statements: _Statements,
    instants: Instants,
) -> EvidenceItem:
    target = cited.target
    positions = tuple(reads.positions.get(target, ()))
    recorded_at = instants.get(positions[0]) if positions else None
    record = reads.first.get(target)
    part = reads.parts.get(target)
    if target in reads.withdrawn:
        status = EvidenceStatus.WITHDRAWN
    elif record is not None or part is not None:
        status = EvidenceStatus.SHOWN
    else:
        status = EvidenceStatus.UNAVAILABLE
    shown = status is EvidenceStatus.SHOWN
    text = part.text if shown and part is not None else None
    return EvidenceItem(
        source=cited.source,
        target=target,
        field=cited.field,
        status=status,
        label=reads.label(target),
        fields=_fields_of(record) if shown and record is not None else (),
        text=text,
        held_by=reads.label(part.parent) if part is not None else None,
        quotes=tuple(
            QuoteView(
                fact.quote,
                fact.predicate.value,
                text is not None and fact.quote in text,
                statements.excluded.get(fact),
            )
            for fact in statements.by_carrier.get(target, ())
        ),
        positions=positions,
        recorded_at=recorded_at,
    )


# --- The sentences --------------------------------------------------------------------------

_REASONS: Mapping[AssessmentReason, str] = {
    AssessmentReason.SKILL: "fails the skill criterion",
    AssessmentReason.COMPONENT: "is not on the component",
    AssessmentReason.AVAILABILITY: "is not available",
    AssessmentReason.HARD_RULE: "fails a rule of the clause",
}

_UNKNOWN_REASONS: Mapping[UnknownReason, str] = {
    UnknownReason.ABSENT: "the record holds no value for it",
    UnknownReason.INACCESSIBLE: "the source was unreachable",
    UnknownReason.AMBIGUOUS: "the evidence read is ambiguous",
    UnknownReason.CONFLICTING: "the evidence read conflicts",
    UnknownReason.INSUFFICIENT: "the evidence read is insufficient",
}

_RULES: Mapping[AuthorityRule, str] = {
    AuthorityRule.SYSTEM_OF_RECORD_WINS: "the system of record wins",
}


def _phrase(name: PredicateName) -> str:
    return name.value.replace("_", " ")


def value_text(value: FactValue, label: _Reads) -> str:
    """A fact value as a sentence says it."""
    match value:
        case EntityRef():
            return label.label(value)
        case str():
            return value
        case DateSpan():
            return f"{value.start.isoformat()} to {value.end.isoformat()}"
        case InstantSpan():
            return f"{value.start.isoformat()} to {value.end.isoformat()}"
        case Requirement():
            people = "person" if value.count == 1 else "people"
            criteria = [
                f"with the skill {criterion.skill}"
                if isinstance(criterion, SkillCriterion)
                else f"employed as {criterion.employment_type.value}"
                for criterion in value.criteria
            ]
            tail = f", each {' and '.join(criteria)}" if criteria else ""
            return f"at least {value.count} {people}{tail}"
        case date():
            return value.isoformat()
        case _:
            assert_never(value)


def impact_sentence(claim: Impact, reads: _Reads) -> str:
    artifact = reads.label(claim.artifact)
    match claim.subtype:
        case ImpactSubtype.DEADLINE:
            return f"A deadline the leave affects: {artifact}."
        case ImpactSubtype.MEETING:
            return f"A meeting the leave affects: {artifact}."
        case ImpactSubtype.RESPONSIBILITY:
            return f"An obligation of the leaver's the leave affects: {artifact}."
        case _:
            assert_never(claim.subtype)


def constraint_sentence(claim: Constraint, reads: _Reads) -> str:
    return f"{reads.label(clause_ref(claim.clause_id))} applies to {reads.label(claim.applies_to)}."


def assessment_sentence(claim: CandidateAssessment, reads: _Reads) -> str:
    who = reads.label(employee_ref(claim.employee_id))
    artifact = reads.label(claim.impact_key.artifact)
    match claim.verdict:
        case Verdict.VIABLE:
            return f"{who} can cover {artifact}."
        case Verdict.NON_VIABLE:
            reasons = "; ".join(_REASONS[reason] for reason in claim.reasons)
            return f"{who} cannot cover {artifact}: {reasons}."
        case Verdict.UNKNOWN:
            return f"Whether {who} can cover {artifact} is unknown."
        case _:
            assert_never(claim.verdict)


def action_sentence(claim: CoverageAction, reads: _Reads) -> str:
    artifact = reads.label(claim.impact_key.artifact)
    match claim.action:
        case CoverageActionKind.ASSIGN:
            names = ", ".join(reads.label(employee_ref(who)) for who in claim.assignee_ids)
            return f"Assign {names} to {artifact}."
        case CoverageActionKind.UNCOVERED:
            return f"{artifact} is left uncovered."
        case CoverageActionKind.UNKNOWN:
            return f"Whether {artifact} is covered is unknown."
        case _:
            assert_never(claim.action)


def unknown_sentence(claim: Unknown, reads: _Reads) -> str:
    return (
        f"The {_phrase(claim.required_fact)} of {reads.label(claim.subject)} could not be "
        f"established: {_UNKNOWN_REASONS[claim.reason]}."
    )


def conflict_sentence(claim: SourceConflict, reads: _Reads) -> str:
    said = "; ".join(
        f"{observation.source.value} says {value_text(observation.value, reads)}"
        for observation in claim.observations
    )
    return (
        f"The sources disagree on the {_phrase(claim.predicate)} of {reads.label(claim.entity)}: "
        f"{said}. Resolved as {value_text(claim.resolved_value, reads)} by the rule that "
        f"{_RULES[claim.authority_rule]}."
    )


def sentence_of(claim: Claim, reads: _Reads) -> str:
    """The deterministic sentence for ``claim`` over the run's reads."""
    match claim:
        case Impact():
            return impact_sentence(claim, reads)
        case Constraint():
            return constraint_sentence(claim, reads)
        case CandidateAssessment():
            return assessment_sentence(claim, reads)
        case CoverageAction():
            return action_sentence(claim, reads)
        case Unknown():
            return unknown_sentence(claim, reads)
        case SourceConflict():
            return conflict_sentence(claim, reads)
        case _:
            assert_never(claim)


# --- The blocks -----------------------------------------------------------------------------


def _block(
    claim: Claim,
    reads: _Reads,
    statements: _Statements,
    instants: Instants,
    held: frozenset[ClaimId],
) -> ClaimBlock:
    observations: tuple[tuple[str, str], ...] = ()
    rationale: str | None = None
    if isinstance(claim, SourceConflict):
        observations = tuple(
            (observation.source.value, value_text(observation.value, reads))
            for observation in claim.observations
        )
    if isinstance(claim, CoverageAction):
        rationale = claim.rationale
    return ClaimBlock(
        claim_id=claim.claim_id,
        kind=claim.claim_type,
        sentence=sentence_of(claim, reads),
        evidence=tuple(
            _evidence(cited, reads, statements, instants) for cited in claim.evidence_refs
        ),
        derived_from=tuple(
            DerivationLink(other, other in held) for other in claim.derived_from_claim_ids
        ),
        observations=observations,
        rationale=rationale,
    )


def _reads_summary(operations: Iterable[Operation]) -> str:
    completed = 0
    returned = 0
    failed = 0
    sources: set[str] = set()
    for operation in operations:
        if is_completed_read(operation.outcome):
            completed += 1
            returned += len(records_of(operation.outcome))
            if operation.source is not None:
                sources.add(operation.source.value)
        elif is_failed_read(operation.outcome):
            failed += 1
    reached = ", ".join(sorted(sources)) if sources else "no source"
    summary = f"{completed} completed reads returned {returned} records from {reached}"
    if failed:
        summary += f"; {failed} reads failed"
    return summary + "."


def _cap_lines(export: RunExport) -> tuple[CapLine, ...]:
    caps = export.record.caps
    usage = export.record.usage
    lines = [
        CapLine(
            "model calls",
            str(usage.model_calls),
            str(caps.call_cap),
            usage.model_calls >= caps.call_cap,
        )
    ]
    total = 0
    whole = True
    for name in COUNTING_RULES[caps.counting_rule]:
        held = usage.value(name)
        if held is None:
            # An unreported counter is unknown to the page, never zero; the harness alone
            # knows whether the configuration proves its absence (``count_tokens``).
            whole = False
            continue
        value, reported = held
        total += value
        whole = whole and reported == usage.dispatches
    consumed = f"{total:,}" if whole else f"at least {total:,}"
    lines.append(
        CapLine(
            f"tokens under the rule {caps.counting_rule}",
            consumed,
            f"{caps.token_cap:,}",
            whole and total >= caps.token_cap,
        )
    )
    return tuple(lines)


def _failure_anchor(export: RunExport) -> str | None:
    failure = export.record.failure
    if failure is None:
        return None
    site = failure.site
    match site:
        case OperationSite():
            operation = export.trace.operation(site.operation)
            return None if operation is None else f"op-{operation.position}"
        case DispatchSite():
            return f"call-{site.model_call}"
        case InputBoundSite():
            return f"count-{site.counting_operation}"
        case HarnessSite():
            return None
        case _:
            assert_never(site)


def ending_view(export: RunExport, *, empty: bool) -> EndingView:
    """How ``export``'s run ended, as both pages state it first; ``empty`` when the report
    holds no impact claim."""
    record = export.record
    details: list[str] = []
    never_claimed = not record.timing.segments
    match record.status:
        case TerminalStatus.COMPLETED:
            headline = "The run completed."
            if empty:
                headline += " It reported no impact."
        case TerminalStatus.CAP_EXHAUSTED:
            headline = "The run stopped under the registered caps and reported what it had."
        case TerminalStatus.FAILED:
            headline = (
                "Nothing ran: no worker claimed the attempt."
                if never_claimed
                else "The run failed."
            )
        case _:
            assert_never(record.status)
    failure = record.failure
    if failure is not None:
        details.append(f"Failed by {failure.category.value}: {failure.reason}")
    abandonment = record.abandonment
    if abandonment is not None:
        details.append(
            f"Abandoned by {abandonment.authority}: {abandonment.reason.value.replace('_', ' ')}"
        )
    approval = record.approval
    match approval.state:
        case ApprovalState.NOT_REQUESTED:
            details.append("No approval was requested.")
        case ApprovalState.REQUESTED_UNAPPROVED:
            details.append("An approval was requested and never given.")
        case ApprovalState.APPROVED:
            who = "automatically" if approval.approver is Approver.AUTOMATIC else "by a person"
            details.append(f"The plan was approved {who}.")
        case _:
            assert_never(approval.state)
    caps = _cap_lines(export) if record.status is TerminalStatus.CAP_EXHAUSTED else ()
    if caps:
        details.append(
            f"Finalization reserve: {record.caps.finalization_call_reserve} calls, "
            f"{record.caps.finalization_token_reserve:,} tokens."
        )
    return EndingView(
        status=record.status,
        headline=headline,
        details=tuple(details),
        failure_anchor=_failure_anchor(export),
        caps=caps,
        reads_summary=_reads_summary(export.trace.operations),
        empty=empty,
    )


def _leave(
    export: RunExport, reads: _Reads, statements: _Statements, instants: Instants
) -> LeaveView | None:
    ref = leave_ref(export.context.leave_id)
    record = reads.first.get(ref)
    if record is None or ref in reads.withdrawn or not isinstance(record.value, Leave):
        return None
    leave = record.value
    return LeaveView(
        person=reads.label(employee_ref(leave.employee_id)),
        start=leave.start,
        end=leave.end,
        days=DateSpan(leave.start, leave.end).days,
        kind=leave.kind.value,
        status=leave.status.value,
        evidence=_evidence(EvidenceRef(record.source, ref), reads, statements, instants),
    )


def header_view(replay: PublicReplay, export: RunExport) -> ReportHeader:
    """The identity both pages open with: the public name, the context and the run's window."""
    record = export.record
    context = export.context
    return ReportHeader(
        public_id=replay.public_id,
        title=replay.title,
        scenario_id=context.scenario_id,
        scenario_date=context.today,
        timezone=context.reference_timezone,
        system=f"{record.system.kind.value} ({record.system.variant})",
        world_version=context.world_version,
        admitted_at=record.timing.admitted_at,
        terminal_at=record.timing.terminal_at,
    )


def report_view(replay: PublicReplay, export: RunExport, instants: Instants) -> ReportView:
    """The page for ``export`` under the public name ``replay`` gives it, each position's
    log instant from ``instants``; pure, and total over any export the type admits."""
    claims = export.trace.claims
    reads = _Reads(export.trace.operations)
    statements = _admitted_statements(export)
    held = frozenset(claim.claim_id for claim in claims)

    def block(claim: Claim) -> ClaimBlock:
        return _block(claim, reads, statements, instants, held)

    impacts = sorted((c for c in claims if isinstance(c, Impact)), key=lambda c: key_order(c.key))
    assessments = [c for c in claims if isinstance(c, CandidateAssessment)]
    actions = [c for c in claims if isinstance(c, CoverageAction)]
    impact_keys: dict[ImpactKey, ClaimId] = {}
    for impact in impacts:
        impact_keys.setdefault(impact.key, impact.claim_id)
    sections = tuple(
        ImpactSection(
            block(impact),
            tuple(block(c) for c in assessments if c.impact_key == impact.key),
            tuple(block(c) for c in actions if c.impact_key == impact.key),
        )
        for impact in impacts
    )
    by_artifact: dict[EntityRef, ClaimId] = {}
    for impact in impacts:
        by_artifact.setdefault(impact.artifact, impact.claim_id)
    constraints = tuple(
        ConstraintSection(block(c), reads.label(c.applies_to), by_artifact.get(c.applies_to))
        for c in claims
        if isinstance(c, Constraint)
    )
    unknowns = tuple(block(c) for c in claims if isinstance(c, Unknown))
    conflicts = tuple(block(c) for c in claims if isinstance(c, SourceConflict))
    unlinked = tuple(
        block(c)
        for c in claims
        if isinstance(c, CandidateAssessment | CoverageAction) and c.impact_key not in impact_keys
    )
    record = export.record
    context = export.context
    unreachable = tuple(sorted(set(Source) - record.observed_condition.reachable))
    return ReportView(
        header=header_view(replay, export),
        ending=ending_view(export, empty=not impacts),
        condition=ConditionView(
            unreachable,
            tuple(
                c.claim_id
                for c in claims
                if isinstance(c, Unknown) and c.reason is UnknownReason.INACCESSIBLE
            ),
        ),
        leave_id=context.leave_id,
        leave=_leave(export, reads, statements, instants),
        impacts=sections,
        constraints=constraints,
        unknowns=unknowns,
        conflicts=conflicts,
        unlinked=unlinked,
        problems=structural_problems(claims),
    )


__all__ = [
    "CapLine",
    "ClaimBlock",
    "ConditionView",
    "ConstraintSection",
    "DerivationLink",
    "EndingView",
    "EvidenceItem",
    "EvidenceStatus",
    "ImpactSection",
    "Instants",
    "LeaveView",
    "QuoteView",
    "ReportHeader",
    "ReportView",
    "ending_view",
    "header_view",
    "report_view",
    "sentence_of",
    "value_text",
]
