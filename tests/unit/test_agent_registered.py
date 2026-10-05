"""A rules-only run's provenance comes from the registration: the assigned sources, the
schedule's digest, the corpus level, the registered caps and variant for each of the six
cells the baseline has, with the model systems still pending; and a registration this
harness cannot execute as written refuses, naming what differs: a cell that is not
registered or whose group is not decided as run, another outage protocol, another prefetch,
another composing policy or anchor table, a pending variant, no rules-only system."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.agent.composer import composing_policy
from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.core import (
    HarnessRevision,
    Pending,
    PricingBasis,
    RegisteredCell,
    RegisteredPrefetch,
    Registration,
    RulesOnlySystem,
    Source,
    SystemKind,
    TreeState,
    pending_fields,
    schedule_digest,
)
from tests.unit.registration_fixture import DRAFT, decided

HARNESS = HarnessRevision("b" * 40, TreeState.CLEAN)
COMMIT = "c" * 40
PRICING = PricingBasis("a" * 64, "USD", date(2026, 9, 1), ())
GROUP = "full_context_under_outage"


def provenance(registration: Registration, condition: str, level: str = "base") -> RunProvenance:
    return rules_only_provenance(
        registration,
        condition,
        level,
        harness=HARNESS,
        preregistration_commit=COMMIT,
        pricing=PRICING,
    )


def with_rules_only(registration: Registration, system: RulesOnlySystem) -> Registration:
    return replace(
        registration,
        systems=tuple(
            system if held.kind is SystemKind.RULES_ONLY else held for held in registration.systems
        ),
    )


def rules_only_of(registration: Registration) -> RulesOnlySystem:
    system = registration.system(SystemKind.RULES_ONLY)
    assert isinstance(system, RulesOnlySystem)
    return system


@pytest.mark.parametrize(
    ("condition", "level", "down"),
    [
        ("normal", "base", frozenset[Source]()),
        ("normal", "padded", frozenset[Source]()),
        ("jira_down", "base", frozenset({Source.JIRA})),
        ("calendar_down", "base", frozenset({Source.CALENDAR})),
        ("frappe_down", "base", frozenset({Source.FRAPPE})),
        ("corpus_down", "base", frozenset({Source.CORPUS})),
    ],
)
def test_the_draft_gives_a_rules_only_run_its_provenance_for_each_of_its_cells(
    condition: str, level: str, down: frozenset[Source]
) -> None:
    assert pending_fields(DRAFT), "the model systems are still pending and do not block this"
    built = provenance(DRAFT, condition, level)
    assert built.outage.scheduled_unreachable == down
    assert built.outage.schedule_digest == schedule_digest(DRAFT.outage)
    assert built.corpus_level == level
    assert built.caps == rules_only_of(DRAFT).caps.caps
    assert built.variant == "reference"
    assert (built.harness, built.preregistration_commit, built.pricing) == (
        HARNESS,
        COMMIT,
        PRICING,
    )


def test_a_cell_that_is_not_registered_refuses() -> None:
    refusal = "no cell is registered for rules_only under 'slack_down' at 'base'"
    with pytest.raises(ValueError, match=refusal):
        provenance(DRAFT, "slack_down")
    # No outage runs at the padded level, and a level nobody registered is no cell either.
    with pytest.raises(ValueError, match="under 'jira_down' at 'padded'"):
        provenance(DRAFT, "jira_down", "padded")
    with pytest.raises(ValueError, match="under 'normal' at 'doubled'"):
        provenance(DRAFT, "normal", "doubled")
    cut = replace(
        DRAFT,
        cells=tuple(
            cell
            for cell in DRAFT.cells
            if cell.place != (SystemKind.RULES_ONLY, "corpus_down", "base")
        ),
    )
    with pytest.raises(ValueError, match="rules_only under 'corpus_down' at 'base'"):
        provenance(cut, "corpus_down")
    assert provenance(cut, "normal").variant == "reference"


def test_a_cell_whose_group_is_not_decided_as_run_refuses() -> None:
    # The baseline's corpus-outage cell put into the conditional group, for the test.
    grouped = replace(
        DRAFT,
        cells=tuple(
            RegisteredCell(cell.system, cell.condition, cell.level, GROUP)
            if cell.place == (SystemKind.RULES_ONLY, "corpus_down", "base")
            else cell
            for cell in DRAFT.cells
        ),
    )
    for undecided in (grouped, decided(grouped, False)):
        with pytest.raises(ValueError, match=f"the group {GROUP}, which is not decided as run"):
            provenance(undecided, "corpus_down")
        assert provenance(undecided, "normal").variant == "reference"
    assert provenance(decided(grouped, True), "corpus_down").corpus_level == "base"


def test_another_outage_protocol_refuses() -> None:
    other = replace(DRAFT, outage=replace(DRAFT.outage, protocol=(DRAFT.outage.protocol[0], 2)))
    with pytest.raises(ValueError, match=r"registered outage protocol is .*, 2\), this harness"):
        provenance(other, "normal")


def test_another_prefetch_refuses_in_each_of_its_three_parts() -> None:
    registered = DRAFT.prefetch
    for changed in (
        replace(registered, identifier="another-prefetch"),
        replace(registered, protocol_version=registered.protocol_version + 1),
        replace(registered, digest="0" * 64),
    ):
        assert isinstance(changed, RegisteredPrefetch)
        with pytest.raises(ValueError, match="the registered prefetch is .*this harness plans"):
            provenance(replace(DRAFT, prefetch=changed), "normal")


def test_another_composing_policy_or_anchor_table_refuses() -> None:
    stated = DRAFT.stated_facts
    assert stated.composing_policy == composing_policy()
    for changed in (
        replace(stated.composing_policy, identifier="another-composer"),
        replace(stated.composing_policy, digest="0" * 64),
    ):
        other = replace(DRAFT, stated_facts=replace(stated, composing_policy=changed))
        with pytest.raises(
            ValueError, match="the registered composing policy is .*this harness composes under"
        ):
            provenance(other, "normal")
    other = replace(DRAFT, stated_facts=replace(stated, anchor_table="0" * 64))
    with pytest.raises(ValueError, match="the registered anchor table is 0{64}, this harness"):
        provenance(other, "normal")


def test_a_pending_variant_or_no_rules_only_system_refuses() -> None:
    pending = with_rules_only(DRAFT, replace(rules_only_of(DRAFT), variant=Pending("not named")))
    with pytest.raises(
        ValueError,
        match=r"the rules-only system has a value pending \(systems.rules_only.variant\)",
    ):
        provenance(pending, "normal")
    kept = SystemKind.RULES_ONLY
    statistics = DRAFT.statistics
    without = replace(
        DRAFT,
        systems=tuple(system for system in DRAFT.systems if system.kind is not kept),
        cells=tuple(cell for cell in DRAFT.cells if cell.system is not kept),
        statistics=replace(
            statistics,
            descriptive=replace(
                statistics.descriptive,
                pairs=tuple(pair for pair in statistics.descriptive.pairs if kept not in pair),
            ),
            headroom=replace(statistics.headroom, reference=SystemKind.AGENT),
        ),
    )
    with pytest.raises(ValueError, match="the registration names no rules-only system"):
        provenance(without, "normal")
