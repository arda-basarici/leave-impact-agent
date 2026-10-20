"""One export carrying every claim type and every reference kind an evidence reference can
name, on the stated-fact fixture's small world, for the report view's tests (the evaluator's
truthful-report fixture is ``report_fixture`` beside it; this one is the demo surface's).

Test infrastructure. The format fixtures accept the export contract on fifteen cases and
none holds all six claim types; the report view needs one that does, with a derivation
chain, a rationale, a conflict with two observations, an unknown, and a citation of each
record kind a source holds (an employee, a team and a leave from the HR system; a component,
a work item and a comment from the tracker; an event; a document and a clause). The run
read everything it cites: the prefetch's seven reads, one model call that admitted three
statements (the comment's skill remark, the runbook's requirement and the owner it names),
and the model's own re-read of the ticket, which returns the ticket unchanged. The variants
below bend one thing each: a ticket returned twice with different contents, so the core's
coverage withdraws it and its comment; a citation no read returned; a claim set with a
dangling derivation, a cycle and an orphan assessment.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from leaveimpact.agent.log_events import (
    ApprovalRequested,
    Approved,
    Completed,
    LoggedEvent,
    OperationEvent,
    OperationResult,
    PrefetchKey,
    Resumed,
)
from leaveimpact.core import (
    Admitted,
    Answer,
    AsOperation,
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    ClaimAuthor,
    ClaimId,
    ComposingPolicy,
    Composition,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    Entity,
    EvidenceRef,
    Excluded,
    Exclusion,
    Impact,
    ImpactKey,
    ImpactSubtype,
    Leave,
    LeaveKind,
    LeaveStatus,
    ModelCall,
    Observation,
    Observed,
    Operation,
    OperationId,
    Outcome,
    PredicateName,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    Requirement,
    RunExport,
    SkillCriterion,
    Source,
    SourceConflict,
    StatedFact,
    Team,
    ToolCall,
    Unknown,
    UnknownReason,
    Verdict,
    WorkItemStatus,
    component_ref,
    document_ref,
    event_ref,
    leave_ref,
    team_ref,
    work_item_ref,
)
from leaveimpact.core.ids import (
    WorldVersion,
    claim_id,
    clause_id,
    leave_id,
    skill_id,
    team_id,
    work_item_id,
)
from leaveimpact.core.run_ending import Approver
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import stated_fixture as f

TEAM = Team(team_id(1), "Payments team")
LEAVE = Leave(
    leave_id(5),
    f.ALICE.id,
    date(2026, 3, 9),
    date(2026, 3, 13),
    LeaveKind.ANNUAL,
    LeaveStatus.APPROVED,
)
"""Alice's leave, the one the fixtures' context names (``leave_005``)."""
LEAVE_REF = leave_ref(LEAVE.id)
TEAM_REF = team_ref(TEAM.id)
COMPONENT_REF = component_ref(f.PAYMENTS.id)
EVENT_REF = event_ref(f.MEETING.id)
DOCUMENT_REF = document_ref(f.RUNBOOK.id)

REQUIREMENT_QUOTE = f"The {f.TITLE} release needs two people with Kafka experience."
OWNER_QUOTE = f"Deniz Kaya owns {f.TITLE}."
REQUIRES = StatedFact(
    PredicateName.REQUIRES,
    f.CLAUSE_REF,
    Requirement(2, (SkillCriterion(skill_id("kafka")),)),
    f.CLAUSE_REF,
    REQUIREMENT_QUOTE,
    f.TITLE,
)
NAMES_OWNER = StatedFact(
    PredicateName.NAMES_RESPONSIBLE, f.CLAUSE_REF, f.DENIZ_REF, f.CLAUSE_REF, OWNER_QUOTE
)
RATIONALE = "Deniz ran the previous migration and is on the component."

INSTANTS = {
    position: cases.ADMITTED + timedelta(milliseconds=100 * position) for position in range(1, 40)
}
"""The log's accept instants the tests hand the view, one per position."""


def _read(
    ordinal: int, position: int, tool: str, source: Source, outcome: Outcome, **arguments: str
) -> Operation:
    return Operation(
        OperationId(f"prefetch/{ordinal}"),
        PrefetchOrigin(),
        tool,
        source,
        dict(arguments),
        outcome,
        position,
    )


def prefetch_reads() -> tuple[Operation, ...]:
    """The prefetch's seven reads at positions 3 to 9: the leave, the people, the team, the
    components, the tickets, the meeting, the runbook."""
    return (
        _read(
            1,
            3,
            "leave",
            Source.FRAPPE,
            RecordOutcome(Observed[Entity](LEAVE, Source.FRAPPE)),
            id=LEAVE.id,
        ),
        _read(2, 4, "employees", Source.FRAPPE, RecordsOutcome(cases.PEOPLE)),
        _read(
            3,
            5,
            "team",
            Source.FRAPPE,
            RecordOutcome(Observed[Entity](TEAM, Source.FRAPPE)),
            id=TEAM.id,
        ),
        _read(
            4,
            6,
            "components",
            Source.JIRA,
            RecordsOutcome((Observed[Entity](f.PAYMENTS, Source.JIRA),)),
        ),
        _read(5, 7, "work_items", Source.JIRA, RecordsOutcome(cases.TICKETS)),
        _read(
            6,
            8,
            "events_within",
            Source.CALENDAR,
            RecordsOutcome((Observed[Entity](f.MEETING, Source.CALENDAR),)),
        ),
        cases.read_document(9, 7, f.RUNBOOK),
    )


def model_call() -> ModelCall:
    """One call answered at position 20: a tool call that became the ticket re-read, and a
    batch admitting the three statements."""
    answer = Answer(
        True,
        (ToolCall("tu_1", "work_item", AsOperation(OperationId("call-1/tu_1"))),),
        (cases.batch(Admitted(cases.SKILL), Admitted(REQUIRES), Admitted(NAMES_OWNER)),),
    )
    return cases.answered("call-1", 20, answer, stop_reason="tool_use", shown=("prefetch/1",))


def ticket_reread(ticket: Observed[Entity] = cases.TICKETS[0]) -> Operation:
    """The model's re-read of the ticket at position 25, returning ``ticket``."""
    return cases.asked("tu_1", "call-1", 25, RecordOutcome(ticket))


def _id(number: int) -> ClaimId:
    return claim_id(number)


DEADLINE = ImpactKey(LEAVE.id, ImpactSubtype.DEADLINE, f.TICKET_REF)
MEETING = ImpactKey(LEAVE.id, ImpactSubtype.MEETING, EVENT_REF)
OBLIGATION = ImpactKey(LEAVE.id, ImpactSubtype.RESPONSIBILITY, f.CLAUSE_REF)


def claims() -> tuple[Claim, ...]:
    """Eleven claims: three impacts (a deadline, a meeting, an obligation named in the
    runbook), the clause's constraint on the ticket, Deniz assessed for the deadline (viable)
    and the meeting (not available), the plan (Deniz assigned to the deadline with a
    rationale; the meeting left uncovered; the obligation's coverage unknown), one unknown
    about Deniz's employment type, and the ticket's owner stated two ways and resolved."""
    return (
        Impact(
            claim_id=_id(1),
            evidence_refs=(
                EvidenceRef(Source.JIRA, f.TICKET_REF, "due_on"),
                EvidenceRef(Source.FRAPPE, LEAVE_REF),
            ),
            leave_id=LEAVE.id,
            subtype=ImpactSubtype.DEADLINE,
            artifact=f.TICKET_REF,
        ),
        Impact(
            claim_id=_id(2),
            evidence_refs=(
                EvidenceRef(Source.CALENDAR, EVENT_REF, "attendee_ids"),
                EvidenceRef(Source.FRAPPE, LEAVE_REF),
            ),
            leave_id=LEAVE.id,
            subtype=ImpactSubtype.MEETING,
            artifact=EVENT_REF,
        ),
        Impact(
            claim_id=_id(3),
            evidence_refs=(
                EvidenceRef(Source.CORPUS, f.CLAUSE_REF),
                EvidenceRef(Source.CORPUS, DOCUMENT_REF),
            ),
            leave_id=LEAVE.id,
            subtype=ImpactSubtype.RESPONSIBILITY,
            artifact=f.CLAUSE_REF,
        ),
        Constraint(
            claim_id=_id(4),
            evidence_refs=(EvidenceRef(Source.CORPUS, f.CLAUSE_REF),),
            clause_id=clause_id(11),
            applies_to=f.TICKET_REF,
        ),
        CandidateAssessment(
            claim_id=_id(5),
            evidence_refs=(
                EvidenceRef(Source.FRAPPE, f.DENIZ_REF, "skills"),
                EvidenceRef(Source.JIRA, f.COMMENT_REF),
            ),
            derived_from_claim_ids=(_id(1), _id(4)),
            impact_key=DEADLINE,
            employee_id=f.DENIZ.id,
            verdict=Verdict.VIABLE,
        ),
        CandidateAssessment(
            claim_id=_id(6),
            evidence_refs=(EvidenceRef(Source.CALENDAR, EVENT_REF),),
            derived_from_claim_ids=(_id(2),),
            impact_key=MEETING,
            employee_id=f.DENIZ.id,
            verdict=Verdict.NON_VIABLE,
            reasons=(AssessmentReason.AVAILABILITY,),
        ),
        CoverageAction(
            claim_id=_id(7),
            evidence_refs=(
                EvidenceRef(Source.JIRA, COMPONENT_REF, "member_ids"),
                EvidenceRef(Source.FRAPPE, TEAM_REF),
            ),
            derived_from_claim_ids=(_id(5),),
            impact_key=DEADLINE,
            action=CoverageActionKind.ASSIGN,
            assignee_ids=(f.DENIZ.id,),
            rationale=RATIONALE,
        ),
        CoverageAction(
            claim_id=_id(8),
            evidence_refs=(),
            derived_from_claim_ids=(_id(6),),
            impact_key=MEETING,
            action=CoverageActionKind.UNCOVERED,
        ),
        Unknown(
            claim_id=_id(9),
            evidence_refs=(EvidenceRef(Source.FRAPPE, f.DENIZ_REF, "employment_type"),),
            subject=f.DENIZ_REF,
            required_fact=PredicateName.EMPLOYED_AS,
            reason=UnknownReason.INSUFFICIENT,
        ),
        SourceConflict(
            claim_id=_id(10),
            evidence_refs=(
                EvidenceRef(Source.JIRA, f.TICKET_REF, "owner_id"),
                EvidenceRef(Source.CORPUS, f.CLAUSE_REF),
            ),
            entity=f.TICKET_REF,
            predicate=PredicateName.OWNS_WORK_ITEM,
            observations=(
                Observation(Source.JIRA, f.ALICE_REF),
                Observation(Source.CORPUS, f.DENIZ_REF),
            ),
            resolved_value=f.ALICE_REF,
            authority_rule=AuthorityRule.SYSTEM_OF_RECORD_WINS,
        ),
        CoverageAction(
            claim_id=_id(11),
            evidence_refs=(),
            derived_from_claim_ids=(_id(9),),
            impact_key=OBLIGATION,
            action=CoverageActionKind.UNKNOWN,
        ),
    )


def all_types() -> RunExport:
    """The export: the prefetch, the call, the re-read, the eleven claims; completed and
    approved automatically, the request stamped at position 30."""
    return cases.export(
        (model_call(),), (*prefetch_reads(), ticket_reread()), claims=claims(), request=30
    )


def ticket_returned_two_ways() -> RunExport:
    """The same run whose re-read returned the ticket with another status, so the coverage
    withdraws the ticket and its comment, and the composition excludes the skill statement
    read from that comment."""
    changed = replace(f.TICKET, status=WorkItemStatus.DONE)
    composition = Composition(
        ClaimAuthor.RULES,
        ComposingPolicy("stated-fact-composer", cases.DIGEST),
        (),
        (Excluded(cases.SKILL, Exclusion.CARRIER_WITHDRAWN),),
    )
    return cases.export(
        (model_call(),),
        (*prefetch_reads(), ticket_reread(Observed[Entity](changed, Source.JIRA))),
        claims=claims(),
        composition=composition,
        request=30,
    )


UNREAD_TICKET = work_item_ref(work_item_id(99))


def citing_an_unread_record() -> RunExport:
    """The same run with the deadline impact also citing a ticket no read returned."""
    held = claims()
    impact = held[0]
    assert isinstance(impact, Impact)
    cited = replace(
        impact, evidence_refs=(*impact.evidence_refs, EvidenceRef(Source.JIRA, UNREAD_TICKET))
    )
    return cases.export(
        (model_call(),), (*prefetch_reads(), ticket_reread()), claims=(cited, *held[1:]), request=30
    )


def reported_history(
    world_version: WorldVersion = cases.CONTEXT.world_version, *, run_id: str = "run-12"
) -> tuple[LoggedEvent, ...]:
    """The all-types run as the log holds it, under ``world_version`` and ``run_id``, for the
    page tests: the same reads and claims, the one call admitting the skill statement alone
    (the two runbook statements are hand-built admissions the fold's own gates need not
    reproduce), approved automatically and completed."""
    expected = cases.facts_beside_tools().record.reservation
    assert expected is not None
    log = histories.History()
    frozen = histories.inputs(reservation=expected.pico_usd)
    context = replace(frozen.context, world_version=world_version)
    log.admit(replace(frozen, run_id=run_id, context=context))
    log.claim()
    leave_read = OperationResult(
        "leave",
        Source.FRAPPE,
        {"id": LEAVE.id},
        RecordOutcome(Observed[Entity](LEAVE, Source.FRAPPE)),
    )
    team_read = OperationResult(
        "team", Source.FRAPPE, {"id": TEAM.id}, RecordOutcome(Observed[Entity](TEAM, Source.FRAPPE))
    )
    reads = (
        OperationEvent(PrefetchKey(1), leave_read),
        histories.prefetch(2, "employees", Source.FRAPPE, cases.PEOPLE),
        OperationEvent(PrefetchKey(3), team_read),
        histories.prefetch(
            4, "components", Source.JIRA, (Observed[Entity](f.PAYMENTS, Source.JIRA),)
        ),
        histories.prefetch(5, "work_items", Source.JIRA, cases.TICKETS),
        histories.prefetch(
            6, "events_within", Source.CALENDAR, (Observed[Entity](f.MEETING, Source.CALENDAR),)
        ),
        histories.document_read(7, f.RUNBOOK),
    )
    for ordinal, read in enumerate(reads, start=1):
        log.worker(read, offset=100 + ordinal)
    log.worker(histories.count_start("call-1"), offset=400)
    log.worker(histories.count_outcome("call-1"), offset=500)
    log.worker(histories.intent(1, shown=("prefetch/1",)), offset=600)
    log.worker(
        histories.outcome(
            1,
            1,
            histories.complete("tool_use"),
            response=histories.body(
                "tool_use",
                histories.text("Looking at the ticket."),
                histories.tool_use("tu_1", "work_item", {"id": "ticket_042"}),
                histories.payload_text(histories.entry_of(cases.SKILL)),
            ),
        ),
        offset=1_500,
    )
    log.worker(histories.model_read(1, "tu_1", RecordOutcome(cases.TICKETS[0])), offset=1_700)
    held = claims()
    log.worker(ApprovalRequested(held, cases.RULES, False), offset=8_700)
    log.outside(
        histories.AUTOMATIC.identity,
        Approved(Approver.AUTOMATIC, cases.review_payload_digest(held, cases.RULES)),
    )
    log.worker(Resumed(), offset=8_800)
    log.worker(
        Completed(histories.settlement_of(expected)),
        offset=9_000,
        at=cases.ADMITTED + timedelta(milliseconds=9_000),
    )
    return log.logged()


ORPHAN = ImpactKey(LEAVE.id, ImpactSubtype.DEADLINE, f.REGIONAL_REF)


def malformed_set() -> RunExport:
    """A decodable export whose claim set is not well-formed: the viable assessment derived
    from a claim not in the set, the two plan actions derived from each other, and an
    assessment for an impact nobody claimed."""
    held = list(claims())
    viable = held[4]
    assert isinstance(viable, CandidateAssessment)
    held[4] = replace(viable, derived_from_claim_ids=(_id(1), _id(99)))
    assign = held[6]
    uncovered = held[7]
    assert isinstance(assign, CoverageAction) and isinstance(uncovered, CoverageAction)
    held[6] = replace(assign, derived_from_claim_ids=(_id(8),))
    held[7] = replace(uncovered, derived_from_claim_ids=(_id(7),))
    held.append(
        CandidateAssessment(
            claim_id=_id(12),
            evidence_refs=(),
            impact_key=ORPHAN,
            employee_id=f.DENIZ.id,
            verdict=Verdict.UNKNOWN,
        )
    )
    return cases.export(
        (model_call(),), (*prefetch_reads(), ticket_reread()), claims=tuple(held), request=30
    )


__all__ = [
    "INSTANTS",
    "LEAVE",
    "OWNER_QUOTE",
    "RATIONALE",
    "REQUIREMENT_QUOTE",
    "UNREAD_TICKET",
    "all_types",
    "citing_an_unread_record",
    "claims",
    "malformed_set",
    "reported_history",
    "ticket_returned_two_ways",
]
