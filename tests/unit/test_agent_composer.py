"""The composer on the throwaway world: the baseline through it unchanged, a truthful stater
composed and graded in two layers (the composer alone, then the gates), and the scope rules
reaching the claims."""

from collections import Counter

import pytest

from leaveimpact.agent.composer import (
    Composed,
    compose,
    composing_policy,
    composing_specification,
    rules_only_composition,
)
from leaveimpact.agent.report import REPORTING_POLICY, rules_only_report
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    ClaimAuthor,
    Constraint,
    Operation,
    PredicateName,
    Source,
    derive_impacts,
)
from leaveimpact.core.admission import admit, run_lexicon
from leaveimpact.core.anchors import lexical_anchors, missing_anchors
from leaveimpact.core.binding import titled_artifacts
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.read_projection import StructuredReads, project_reads
from leaveimpact.core.readings import conclude_impacts
from leaveimpact.core.stated import (
    STATED_PREDICATES,
    Admitted,
    FactRefusal,
    PlacementState,
    Refused,
    StatedFact,
)
from leaveimpact.core.stated_view import Exclusion
from leaveimpact.evaluator.grading import Graded, correct_whole
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import evaluated
from tests.unit.reads_fixture import systems_holding
from tests.unit.stating_fixture import read_everything, truthful_statements
from tests.unit.throwaway_world import loaded_world

GRADED_UNDER: tuple[tuple[Source, ...], ...] = ((), (Source.JIRA,), (Source.CALENDAR,))
"""The conditions the evaluator grades a claim set under: the normal one and the two outages
that leave the leave and the policy readable."""


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def project(world: SealedWorld, scenario: Scenario, operations: list[Operation]) -> StructuredReads:
    return project_reads(operations, world.context_of(scenario).today)


def composed_truthfully(
    world: SealedWorld, scenario: Scenario, down: tuple[Source, ...], *, gated: bool
) -> tuple[list[Operation], Composed, list[Refused]]:
    operations, reads, leave, universe = read_everything(world, scenario, down)
    statements = truthful_statements(world, reads)
    refused: list[Refused] = []
    if gated:
        lexicon = run_lexicon(reads)
        decisions = [admit(stated, reads, lexicon) for stated in statements]
        refused = [decision for decision in decisions if isinstance(decision, Refused)]
        statements = tuple(d.fact for d in decisions if isinstance(d, Admitted))
    composed = compose(reads, statements, world.context_of(scenario), leave, universe)
    return operations, composed, refused


# --- The baseline is the same path with no statement ------------------------------------------


@pytest.mark.parametrize("down", GRADED_UNDER, ids=str)
def test_with_no_statement_the_composer_adds_nothing_to_the_direct_path(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    # The path as it was before the composer, written out: the projection's own view, the
    # composing pass with no constraint, the report. What this holds is that the join, the
    # binding and the scope rules change nothing when nothing was stated. It shares the
    # report writer with the path it checks, so it says nothing of that function; the
    # baseline's statements are held independently of the writer by the baseline's own
    # tests, and its totals and bytes by the graded gate.
    for scenario in world.scenarios:
        systems = systems_holding(world)
        for port in (systems.people, systems.work, systems.calendar, systems.documents):
            port.reachable = port.source not in down
        context = world.context_of(scenario)
        result = investigate(context, systems.ports)
        assert result.failure is None and result.abstention is None
        reads = project_reads(result.operations, context.today)
        view = reads.view()
        leave = scenario.investigated_leave
        universe = sorted(
            EmployeeId(r.ref.id) for r in reads.returned if r.ref.kind is EntityKind.EMPLOYEE
        )
        grounded = derive_impacts(
            view, context.leave_id, leave.employee_id, leave.span, context.reference_timezone
        ).grounded
        before = rules_only_report(
            conclude_impacts(
                view,
                grounded,
                (),
                leave.employee_id,
                leave.span,
                context.reference_timezone,
                universe,
            ),
            view,
        )
        assert result.claims == before, scenario.spec.id


def test_the_composing_policy_names_what_composes_and_the_baseline_records_it() -> None:
    specification = composing_specification()
    assert specification["reporting"] == {
        "identifier": REPORTING_POLICY.identifier,
        "version": REPORTING_POLICY.version,
        "tie_break": REPORTING_POLICY.tie_break,
    }
    assert specification["stated_predicates"] == [name.value for name in STATED_PREDICATES]
    assert specification["exclusions"] == [reason.value for reason in Exclusion]
    composition = rules_only_composition()
    assert composition.author is ClaimAuthor.RULES
    assert composition.policy == composing_policy()
    assert (composition.placements, composition.exclusions) == ((), ())
    # Pinned: a change to anything the specification names is a change of the policy, and
    # this literal is what makes it a decision.
    assert composing_policy().digest == (
        "bbcdbd9e23b4f2da3b583e2ec141d000f583f8d0e1764c47686d448c8ceabdfa"
    )


# --- The truthful stater, layer one: the composer alone ---------------------------------------


@pytest.mark.parametrize("down", GRADED_UNDER, ids=str)
def test_a_truthful_stater_composes_a_correct_report_on_every_scenario(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    whole: Counter[str] = Counter()
    constraints = 0
    for scenario in world.scenarios:
        operations, composed, _ = composed_truthfully(world, scenario, down, gated=False)
        outcome = evaluated(
            world, scenario, down=down, claims=composed.claims, operations=operations
        ).outcome
        assert isinstance(outcome, Graded), scenario.spec.id
        assert outcome.rows.structural_problems == ()
        assert outcome.report_findings == (), scenario.spec.id
        assert outcome.grounding is not None
        assert all(g.standing is Standing.REPRODUCED for g in outcome.grounding.claims), (
            scenario.spec.id
        )
        assert all(not g.missing_premises for g in outcome.grounding.claims)
        assert correct_whole(outcome), scenario.spec.id
        whole[scenario.key.tier.value] += 1
        constraints += sum(isinstance(claim, Constraint) for claim in composed.claims)
        # Nothing a truthful statement says is left out. A requirement is placed exactly
        # when the run read what its clause is scoped to: a meeting outside the window
        # read, or a ticket with the tracker down, leaves a true requirement unplaced, and
        # the report is right all the same, since that artifact is no impact of this leave.
        assert composed.composition.exclusions == ()
        read = {artifact for artifact, _ in titled_artifacts(project(world, scenario, operations))}
        for entry in composed.composition.placements:
            target = world.index.scope[ClauseId(entry.fact.subject.id)]
            named = world.index.parts[target].parent if target.kind is EntityKind.CLAUSE else target
            expected = PlacementState.PLACED if named in read else PlacementState.UNPLACED
            assert entry.placement.state is expected, (scenario.spec.id, entry.fact.subject.id)
            if expected is PlacementState.PLACED:
                assert entry.placement.artifact == named
    assert whole == {"structured": 10, "fragmented": 10, "adversarial": 10}
    assert constraints > 0


# --- Layer two: the gates over the same statements --------------------------------------------


@pytest.mark.parametrize("down", GRADED_UNDER, ids=str)
def test_the_gates_refuse_no_truthful_requirement(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    # This world's comments and model-written sections are stand-in text ("Stand-in text
    # for clause_017."), which names nobody, so only its requirement clauses, written from
    # the scenario classes' own templates, are text a gate can be asked about here. The
    # other kinds are replayed on a world with real prose (the composer group's replay).
    for scenario in world.scenarios:
        _, reads, leave, universe = read_everything(world, scenario, down)
        _, ungated, _ = composed_truthfully(world, scenario, down, gated=False)
        _, _, refused = composed_truthfully(world, scenario, down, gated=True)
        requirements = [r for r in refused if r.fact.predicate is PredicateName.REQUIRES]
        assert [(r.reason.value, r.fact.carrier.id) for r in requirements] == [], scenario.spec.id
        # What a provenance gate refuses is real whatever the text: with the tracker down a
        # runbook's ownership statement is about a ticket the run never read, and is refused
        # for its subject. Four such statements a scenario, and no report moves by them.
        provenance = [r for r in refused if r.reason is not FactRefusal.MISSING_ANCHOR]
        assert {(r.reason, r.fact.predicate) for r in provenance} <= {
            (FactRefusal.SUBJECT_NOT_READ, PredicateName.OWNS_WORK_ITEM)
        }
        assert bool(provenance) == (Source.JIRA in down)
        kept = tuple(
            stated
            for stated in truthful_statements(world, reads)
            if stated not in {r.fact for r in provenance}
        )
        gated = compose(reads, kept, world.context_of(scenario), leave, universe)
        assert gated.claims == ungated.claims, scenario.spec.id


def test_a_requirement_of_one_is_admitted_from_a_clause_that_writes_no_number(
    world: SealedWorld,
) -> None:
    # Fifteen of this world's seventeen requirement clauses ask for one person and none of
    # those writes "one": the count anchored, the guard refused every one of them.
    scenario = world.scenarios[0]
    _, reads, _, _ = read_everything(world, scenario, ())
    lexicon = run_lexicon(reads)
    requirements = [
        s for s in truthful_statements(world, reads) if s.predicate is PredicateName.REQUIRES
    ]
    counts = Counter(s.value.count for s in requirements)  # type: ignore[union-attr]
    assert counts == {1: 15, 2: 2}
    assert all(isinstance(admit(s, reads, lexicon), Admitted) for s in requirements)
    # The refusal the rule removes, held here by the table's other reading, which still
    # anchors the count: the fifteen clauses asking for one never write the number.
    unwritten = [
        s
        for s in requirements
        if missing_anchors(s.quote, lexical_anchors(s.as_fact(reads.today), lexicon))
    ]
    assert len(unwritten) == 15
    assert all(s.value.count == 1 for s in unwritten)  # type: ignore[union-attr]


# --- The scope rules reach the composition and the claims --------------------------------------


def test_a_clause_read_with_two_scopes_composes_no_constraint_and_says_why(
    world: SealedWorld,
) -> None:
    # A truthful run, and one more statement of one requirement: the same clause, its span
    # another ticket's title. The quote is the clause's text with that title beside it,
    # which is not what the clause says, so the statement is given as admitted: what is
    # under test is composition, and a model's second reading is its input.
    scenario, operations, reads, leave, universe, truthful = next(
        (
            s,
            *read_everything(world, s, ()),
            truthful_statements(world, read_everything(world, s, ())[1]),
        )
        for s in world.scenarios
        if any(
            isinstance(c, Constraint)
            for c in composed_truthfully(world, s, (), gated=False)[1].claims
        )
    )
    context = world.context_of(scenario)
    sound = compose(reads, truthful, context, leave, universe)
    constraint = next(claim for claim in sound.claims if isinstance(claim, Constraint))
    stated = next(
        s
        for s in truthful
        if s.predicate is PredicateName.REQUIRES and s.subject.id == constraint.clause_id
    )
    assert stated.target_span is not None
    other_ref, other_title = next(
        (artifact, title)
        for artifact, title in titled_artifacts(reads)
        if artifact.kind is EntityKind.WORK_ITEM
        and stated.target_span not in title
        and title not in stated.target_span
    )
    second = StatedFact(
        stated.predicate,
        stated.subject,
        stated.value,
        stated.carrier,
        f"{stated.quote} {other_title}",
        other_title,
    )
    for order in ((*truthful, second), (second, *truthful)):
        composed = compose(reads, order, context, leave, universe)
        assert not any(
            isinstance(claim, Constraint) and claim.clause_id == constraint.clause_id
            for claim in composed.claims
        )
        assert {(e.fact, e.reason) for e in composed.composition.exclusions} == {
            (stated, Exclusion.CONFLICTING_SCOPES),
            (second, Exclusion.CONFLICTING_SCOPES),
        }
        placed = {entry.fact: entry.placement.artifact for entry in composed.composition.placements}
        assert placed[second] == other_ref and placed[stated] == constraint.applies_to
        assert not composed.view.facts_about(stated.subject, PredicateName.REQUIRES)
        # The report without that constraint is the report of a run that never read it.
        unread = compose(reads, tuple(s for s in truthful if s != stated), context, leave, universe)
        assert composed.claims == unread.claims
        assert composed.claims != sound.claims
        assert operations
