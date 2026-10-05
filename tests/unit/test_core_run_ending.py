"""How an attempt ended: a failure's typed site, an abandonment, the reservation tied to its
reason, the approval's three states, and the composition's placements."""

import pytest

from leaveimpact.core import PredicateName, Requirement, SkillCriterion, work_item_ref
from leaveimpact.core.ids import skill_id
from leaveimpact.core.run_ending import (
    Abandonment,
    AbandonmentReason,
    Approval,
    ApprovalState,
    Approver,
    ClaimAuthor,
    ComposingPolicy,
    Composition,
    DispatchPhase,
    DispatchSite,
    HarnessSite,
    HarnessSiteName,
    KeptReason,
    OperationSite,
    RequirementPlacement,
    Reservation,
    ReservationState,
)
from leaveimpact.core.run_trace import ModelCallId, OperationId
from leaveimpact.core.stated import PlacementState, SpanPlacement, StatedFact
from tests.unit import stated_fixture as f

POLICY = ComposingPolicy("rules-composer", "c" * 64)
DIGEST = "d" * 64


def requirement(span: str) -> StatedFact:
    """One clause's requirement, stated with the target span ``span``."""
    return StatedFact(
        PredicateName.REQUIRES,
        f.CLAUSE_REF,
        Requirement(1, (SkillCriterion(skill_id("kafka")),)),
        f.CLAUSE_REF,
        f"{f.TITLE} and Ledger sync each need one Kafka person",
        span,
    )


def test_a_failure_site_is_an_operation_a_dispatch_or_a_named_harness_site() -> None:
    assert OperationSite(OperationId("op-3")).operation == "op-3"
    site = DispatchSite(ModelCallId("call-2"), 1, DispatchPhase.PARSE)
    assert (site.model_call, site.dispatch, site.phase.value) == ("call-2", 1, "parse")
    assert HarnessSite(HarnessSiteName.ABANDONED).site.value == "abandoned"
    assert "admission" not in {name.value for name in HarnessSiteName}
    with pytest.raises(ValueError, match="at least 1"):
        DispatchSite(ModelCallId("call-2"), 0, DispatchPhase.SEND)
    with pytest.raises(ValueError, match="a harness site"):
        HarnessSite("admission")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a dispatch phase"):
        DispatchSite(ModelCallId("call-2"), 1, "parse")  # type: ignore[arg-type]


def test_an_abandonment_names_its_authority_the_generation_it_fenced_and_its_reason() -> None:
    abandoned = Abandonment("operator", 3, AbandonmentReason.CANCELLED)
    assert (abandoned.authority, abandoned.ownership_generation) == ("operator", 3)
    assert abandoned.reason is AbandonmentReason.CANCELLED
    with pytest.raises(ValueError, match="the abandoning authority"):
        Abandonment(" ", 3, AbandonmentReason.CANCELLED)
    with pytest.raises(ValueError, match="an ownership generation is an integer"):
        Abandonment("operator", True, AbandonmentReason.CANCELLED)
    with pytest.raises(ValueError, match="an abandonment's reason"):
        Abandonment("operator", 3, "cancelled")  # type: ignore[arg-type]
    assert [reason.value for reason in AbandonmentReason] == ["cancelled", "interrupted"]


def test_a_reservation_is_reconciled_or_kept_with_its_reason_and_states_what_was_charged() -> None:
    kept = Reservation(
        5_000_000_000, ReservationState.KEPT, KeptReason.UNRESOLVED_DISPATCH, 12, 5_000_000_000
    )
    assert kept.kept_reason is KeptReason.UNRESOLVED_DISPATCH
    settled = Reservation(5_000_000_000, ReservationState.RECONCILED, None, 13, 297_000_000)
    assert (settled.kept_reason, settled.charged_pico_usd) == (None, 297_000_000)
    with pytest.raises(ValueError, match="a reason is given exactly for a kept reservation"):
        Reservation(1, ReservationState.RECONCILED, KeptReason.USAGE_INCOMPLETE, 1, 0)
    with pytest.raises(ValueError, match="a reason is given exactly for a kept reservation"):
        Reservation(1, ReservationState.KEPT, None, 1, 0)
    with pytest.raises(ValueError, match="a reservation in pico-dollars is at least 0"):
        Reservation(-1, ReservationState.RECONCILED, None, 1, 0)
    with pytest.raises(ValueError, match="the amount charged in pico-dollars is at least 0"):
        Reservation(1, ReservationState.RECONCILED, None, 1, -1)
    # A breached allocation is charged as observed, so the charge is not bounded by the amount.
    assert Reservation(1, ReservationState.RECONCILED, None, 1, 2).charged_pico_usd == 2


def test_an_approval_holds_a_digest_once_requested_and_an_approver_once_given() -> None:
    assert Approval(ApprovalState.NOT_REQUESTED, None, None).payload_digest is None
    waiting = Approval(ApprovalState.REQUESTED_UNAPPROVED, None, DIGEST)
    assert waiting.approver is None
    assert (
        Approval(ApprovalState.APPROVED, Approver.AUTOMATIC, DIGEST).approver is Approver.AUTOMATIC
    )
    assert "pending" not in {state.value for state in ApprovalState}
    with pytest.raises(ValueError, match="an approver is named exactly"):
        Approval(ApprovalState.REQUESTED_UNAPPROVED, Approver.HUMAN, DIGEST)
    with pytest.raises(ValueError, match="an approver is named exactly"):
        Approval(ApprovalState.APPROVED, None, DIGEST)
    with pytest.raises(ValueError, match="held exactly when an approval was requested"):
        Approval(ApprovalState.NOT_REQUESTED, None, DIGEST)
    with pytest.raises(ValueError, match="held exactly when an approval was requested"):
        Approval(ApprovalState.APPROVED, Approver.HUMAN, None)
    with pytest.raises(ValueError, match="the review payload's digest is a SHA-256"):
        Approval(ApprovalState.APPROVED, Approver.HUMAN, "x")


def test_a_composition_places_each_span_once_and_keeps_two_spans_of_one_clause() -> None:
    placed = RequirementPlacement(
        requirement(f.TITLE),
        SpanPlacement(PlacementState.PLACED, artifact=work_item_ref(f.TICKET.id)),
    )
    unplaced = RequirementPlacement(
        requirement("Ledger sync"), SpanPlacement(PlacementState.UNPLACED)
    )
    composed = Composition(ClaimAuthor.RULES, POLICY, (placed, unplaced), ())
    assert [entry.placement.state.value for entry in composed.placements] == ["placed", "unplaced"]
    assert placed.fact.statement == unplaced.fact.statement
    with pytest.raises(ValueError, match="a requirement's span is placed once"):
        Composition(ClaimAuthor.RULES, POLICY, (placed, placed), ())
    with pytest.raises(ValueError, match="a claim set's author"):
        Composition("rules", POLICY, (), ())  # type: ignore[arg-type]
    skill = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, f.REMARK)
    with pytest.raises(ValueError, match="only a requirement has a span to place, got has_skill"):
        RequirementPlacement(skill, SpanPlacement(PlacementState.UNPLACED))
