"""The domain, pure: what the real system believes, with no knowledge that a benchmark exists.

Holds the types every other package speaks (employee, team, work item, calendar event,
document, leave, and their ids), the predicate registry, the claim vocabulary with its
per-type grading keys, ``RunContext`` and world time, and the deterministic rules —
viability of a person for a need, the system-of-record authority table that resolves
conflicting observations, closed-world evaluation per declared evidence domain,
constraint checks. The investigator's deterministic core and the evaluator call the same
rule functions from here, which makes that sharing visible instead of duplicated (the
answer-key contract in DESIGN says why sharing rules is safe and sharing code between
generator and evaluator is not). Vendor-neutral ports that both the generator and the
investigator consume sit here too; an abstraction that describes how one vendor works
stays inside that vendor's adapter.

Boundary: never imports ``world`` — the production investigator depends on the domain
without depending on the benchmark that grades it; performs no I/O; reads no clock —
world time arrives in ``RunContext``, and the wall clock is read only at a composition
root. Populated step by step through the world milestone; the layout is the decision.

Callers import the public names from the package (``from leaveimpact.core import
Employee``); the module split is a navigation aid, not part of the contract.
"""

from leaveimpact.core import claims, claims_json, entities, enums, ids, predicates, refs, worldtime
from leaveimpact.core.claims import (
    ARTIFACT_KINDS,
    AssessmentKey,
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    ClaimType,
    ConflictKey,
    Constraint,
    ConstraintKey,
    CoverageAction,
    CoverageActionKind,
    GradingKey,
    Impact,
    ImpactKey,
    ImpactSubtype,
    SourceConflict,
    Unknown,
    UnknownKey,
    UnknownReason,
    Verdict,
    require_well_formed,
    structural_problems,
)
from leaveimpact.core.claims_json import decode_claim, decode_claims, encode_claim, encode_claims
from leaveimpact.core.entities import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    DocumentSection,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import (
    DocumentKind,
    EmploymentType,
    EntityKind,
    Grade,
    LeaveKind,
    LeaveStatus,
    Source,
    WorkItemStatus,
)
from leaveimpact.core.ids import (
    ClaimId,
    ClauseId,
    CommentId,
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    ScenarioId,
    SkillId,
    TeamId,
    WorkItemId,
    WorldVersion,
)
from leaveimpact.core.predicates import REGISTRY, Predicate, PredicateName, predicate
from leaveimpact.core.refs import (
    PREFIX_BY_KIND,
    TARGET_KINDS_BY_SOURCE,
    EntityRef,
    EvidenceRef,
    FactValue,
    Observation,
    clause_ref,
    comment_ref,
    component_ref,
    document_ref,
    employee_ref,
    event_ref,
    leave_ref,
    require_id,
    team_ref,
    work_item_ref,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan, RunContext, local_date

# The submodules are listed so the rendered reference keeps their docstrings — each
# carries the why of its part — beside the public names.
__all__ = [
    "claims",
    "claims_json",
    "entities",
    "enums",
    "ids",
    "predicates",
    "refs",
    "worldtime",
    "ARTIFACT_KINDS",
    "PREFIX_BY_KIND",
    "REGISTRY",
    "TARGET_KINDS_BY_SOURCE",
    "AssessmentKey",
    "AssessmentReason",
    "AuthorityRule",
    "CalendarEvent",
    "CandidateAssessment",
    "Claim",
    "ClaimId",
    "ClaimType",
    "ClauseId",
    "Comment",
    "CommentId",
    "Component",
    "ComponentId",
    "ConflictKey",
    "Constraint",
    "ConstraintKey",
    "CoverageAction",
    "CoverageActionKind",
    "DateSpan",
    "Document",
    "DocumentId",
    "DocumentKind",
    "DocumentSection",
    "Employee",
    "EmployeeId",
    "EmploymentType",
    "EntityKind",
    "EntityRef",
    "EventId",
    "EvidenceRef",
    "FactValue",
    "Grade",
    "GradingKey",
    "Impact",
    "ImpactKey",
    "ImpactSubtype",
    "InstantSpan",
    "Leave",
    "LeaveId",
    "LeaveKind",
    "LeaveStatus",
    "Observation",
    "Predicate",
    "PredicateName",
    "RunContext",
    "ScenarioId",
    "SkillId",
    "Source",
    "SourceConflict",
    "Team",
    "TeamId",
    "Unknown",
    "UnknownKey",
    "UnknownReason",
    "Verdict",
    "WorkItem",
    "WorkItemId",
    "WorkItemStatus",
    "WorldVersion",
    "clause_ref",
    "comment_ref",
    "component_ref",
    "decode_claim",
    "decode_claims",
    "document_ref",
    "employee_ref",
    "encode_claim",
    "encode_claims",
    "event_ref",
    "leave_ref",
    "local_date",
    "predicate",
    "require_id",
    "require_well_formed",
    "structural_problems",
    "team_ref",
    "work_item_ref",
]
