"""A rules-only run's provenance comes from the registration: the assigned sources, the
schedule's digest, the corpus level, the registered caps and variant for each of the six
cells the baseline has, with the model systems still pending; and a registration this
harness cannot execute as written refuses, naming what differs: a cell that is not
registered or whose group is not decided as run, another outage protocol, another prefetch,
another composing policy or anchor table, a pending variant, no rules-only system.

An investigator run's configuration comes the same way, and under the draft what the
registration holds pending is this code's: the draft names the variant, the development
table equals the fixtures' (one digest everywhere), the role, the prompt digests, the
surface and the entry schema are the shipped ones; a registered role or entry schema that
is not the code's refuses, and a registration past its draft refuses by name whatever it
still holds pending.
"""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.composer import composing_policy
from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.fact_entries import refused_by
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import (
    DEVELOPMENT_ATTRIBUTION_TABLE,
    DEVELOPMENT_REDISPATCH_POLICY,
    RoleFilling,
    effective_rules,
    model_system_provenance,
    rules_only_configuration,
    rules_only_provenance,
)
from leaveimpact.agent.surface import surface_digest
from leaveimpact.core import (
    AgentSystem,
    AttributionTable,
    CallConfiguration,
    CallSetting,
    ClaimAuthor,
    EntrySchema,
    HarnessRevision,
    OutageAssignment,
    Pending,
    PricingBasis,
    PricingSelection,
    RedispatchPolicy,
    RegisteredCell,
    RegisteredPrefetch,
    RegisteredRole,
    Registration,
    RegistrationStatus,
    Retrieval,
    RetrievalKind,
    RulesOnlySystem,
    SingleShotSystem,
    Source,
    System,
    SystemKind,
    TreeState,
    attribution_table_digest,
    pending_fields,
    schedule_digest,
)
from leaveimpact.core.tools import Role
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.registration_fixture import DRAFT, ROLE, decided, frozen, named, pending_roles

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


# --- The investigator under a draft ------------------------------------------------------------

FILLING = RoleFilling(
    "investigator",
    CallConfiguration("eu.vendor.model-v1", (CallSetting("temperature", 0),)),
    PricingSelection("vendor.model-v1", "eu-central-1", "on_demand"),
    "vendor.model-v1",
    200_000,
)


def agent(registration: Registration, condition: str = "normal", level: str = "base") -> Any:
    return model_system_provenance(
        registration,
        SystemKind.AGENT,
        condition,
        level,
        preregistration_commit=COMMIT,
        pricing=PRICING,
        role=FILLING,
    )


READER = RoleFilling(
    "reader",
    FILLING.configuration,
    FILLING.pricing,
    FILLING.counting_model_id,
    FILLING.context_allowance_tokens,
)


PENDING = pending_roles(DRAFT)
"""The committed draft before the first live run's step set its roles: what a run records
under a role nobody has registered is this code's."""


def baseline(
    kind: SystemKind, registration: Registration = PENDING, role: RoleFilling = READER
) -> Any:
    return model_system_provenance(
        registration,
        kind,
        "normal",
        "base",
        preregistration_commit=COMMIT,
        pricing=PRICING,
        role=role,
    )


def current_role() -> RegisteredRole:
    return RegisteredRole(
        FILLING.name,
        FILLING.configuration,
        load_prompt_assets().digests(),
        surface_digest(Role.INVESTIGATOR),
        FILLING.counting_model_id,
        FILLING.context_allowance_tokens,
    )


def test_the_draft_names_the_variant_and_the_development_table_is_the_fixtures() -> None:
    """The draft's agent variant is the shape the graph step fixed; the development table
    equals the fixtures' row for row, so every fixture record and every development run
    name one digest."""
    system = DRAFT.system(SystemKind.AGENT)
    assert isinstance(system, AgentSystem) and system.variant == "tool_loop_then_finalization"
    assert DEVELOPMENT_ATTRIBUTION_TABLE == cases.TABLE
    assert attribution_table_digest(DEVELOPMENT_ATTRIBUTION_TABLE) == cases.TABLE_DIGEST


def test_the_draft_gives_an_investigator_run_the_codes_values_for_what_it_holds_pending() -> None:
    held = agent(PENDING)
    role = current_role()
    assert held.system == System(SystemKind.AGENT, "tool_loop_then_finalization")
    assert held.model_configurations == (("investigator", FILLING.configuration),)
    assert held.pricing_selections == (("investigator", FILLING.pricing),)
    assert held.counting_identifiers == (("investigator", "vendor.model-v1"),)
    assert held.context_allowances == (("investigator", 200_000),)
    assert held.query_protocol is None and held.search_limit is None
    assert held.prompt_digests == load_prompt_assets().prompt_digests("investigator")
    assert held.tool_surface_digests == (("investigator", role.tool_surface_digest),)
    assert held.attribution_table == cases.TABLE_DIGEST
    assert held.redispatch == DEVELOPMENT_REDISPATCH_POLICY
    assert held.parser == refused_by()
    # What the draft binds is taken as registered.
    system = DRAFT.system(SystemKind.AGENT)
    assert isinstance(system, AgentSystem)
    assert (held.caps, held.retrieval, held.retry) == (
        system.caps.caps,
        system.retrieval,
        DRAFT.run_accounting.retry,
    )
    assert held.outage == OutageAssignment(frozenset(), schedule_digest(DRAFT.outage))
    assert (held.corpus_level, held.preregistration_commit) == ("base", COMMIT)
    assert held.pricing == PRICING
    assert held.composing_policy == composing_policy()
    assert held.claim_author is ClaimAuthor.RULES
    # The configuration freezes whole for an admission, every role tuple naming one role.
    assert agent(PENDING, "jira_down").outage.scheduled_unreachable == frozenset({Source.JIRA})


def test_the_committed_draft_holds_a_run_to_the_roles_it_names() -> None:
    """Since the first live run's step the draft names each model system's role; a filling
    that is not the registered one refuses by field, and the registered one is recorded."""
    with pytest.raises(ValueError, match="registered investigator role differs .* configuration"):
        agent(DRAFT)
    system = DRAFT.system(SystemKind.AGENT)
    assert isinstance(system, AgentSystem) and isinstance(system.roles, tuple)
    (registered,) = system.roles
    shipped = RoleFilling(
        registered.name,
        registered.configuration,
        FILLING.pricing,
        registered.counting_model_id,
        registered.context_allowance_tokens,
    )
    held = model_system_provenance(
        DRAFT,
        SystemKind.AGENT,
        "normal",
        "base",
        preregistration_commit=COMMIT,
        pricing=PRICING,
        role=shipped,
    )
    assert held.model_configurations == (("investigator", registered.configuration),)
    assert held.tool_surface_digests == (("investigator", registered.tool_surface_digest),)


def test_the_effective_rules_are_the_development_ones_under_the_draft_else_the_named() -> None:
    assert effective_rules(DRAFT) == Rules(
        DEVELOPMENT_ATTRIBUTION_TABLE, DEVELOPMENT_REDISPATCH_POLICY
    )
    settled = named(DRAFT)
    assert effective_rules(settled) == Rules(settled.attribution, settled.run_accounting.redispatch)  # type: ignore[arg-type]


def test_a_registered_role_or_entry_schema_that_is_not_the_codes_refuses() -> None:
    with pytest.raises(
        ValueError,
        match="the registered investigator role differs from this harness's on configuration, "
        "prompt_digests, tool_surface_digest",
    ):
        agent(named(DRAFT))
    with pytest.raises(
        ValueError, match="the registered agent roles are investigator, reviewer, this harness"
    ):
        agent(named(DRAFT, roles=(replace(ROLE, name="reviewer"), current_role())))
    with pytest.raises(ValueError, match="the registered entry schema is fact-entries-1 at ab"):
        agent(named(DRAFT, roles=(current_role(),)))
    mine = refused_by()
    settled = replace(
        named(DRAFT, roles=(current_role(),)),
        stated_facts=replace(
            DRAFT.stated_facts, entry_schema=EntrySchema(mine.parser, mine.schema_digest)
        ),
    )
    held = agent(settled)
    assert isinstance(settled.attribution, AttributionTable)
    assert held.attribution_table == attribution_table_digest(settled.attribution)
    assert held.redispatch == RedispatchPolicy(2, 1_000)


# --- The one-call baselines under a draft (the baselines step, forks 15 and 16) ---------------


def test_the_draft_gives_a_one_call_baseline_the_readers_values_and_its_registered_retrieval() -> (
    None
):
    """Both baselines record the reader role with this code's assets and empty surface, the
    variant the draft names, and the retrieval as registered; the single-shot's frozen
    inputs copy the registered query protocol and limit, full context's hold none."""
    single = baseline(SystemKind.SINGLE_SHOT)
    registered = DRAFT.system(SystemKind.SINGLE_SHOT)
    assert isinstance(registered, SingleShotSystem)
    assert single.system == System(SystemKind.SINGLE_SHOT, "prefetch_then_one_search_one_call")
    assert (single.query_protocol, single.search_limit) == (
        registered.query_protocol,
        registered.search_limit,
    )
    assert single.search_limit == 20 and single.retrieval.kind is RetrievalKind.FULL_TEXT
    assert single.model_configurations == (("reader", FILLING.configuration),)
    assert single.prompt_digests == load_prompt_assets(Role.READER).prompt_digests("reader")
    assert single.tool_surface_digests == (("reader", surface_digest(Role.READER)),)
    assert single.context_allowances == (("reader", 200_000),)
    assert single.caps == registered.caps.caps
    full = baseline(SystemKind.FULL_CONTEXT)
    assert full.system == System(SystemKind.FULL_CONTEXT, "prefetch_then_level_documents_one_call")
    assert full.query_protocol is None and full.search_limit is None
    assert full.retrieval.kind is RetrievalKind.NONE
    assert (full.prompt_digests, full.tool_surface_digests) == (
        single.prompt_digests,
        single.tool_surface_digests,
    )
    investigator = agent(PENDING)
    assert investigator.prompt_digests != single.prompt_digests
    assert investigator.tool_surface_digests[0][1] != single.tool_surface_digests[0][1]
    assert full.outage == OutageAssignment(frozenset(), schedule_digest(DRAFT.outage))


def test_a_filling_for_another_role_than_the_kind_runs_refuses_as_does_a_model_free_kind() -> None:
    with pytest.raises(ValueError, match="single_shot runs the reader role; the line fills"):
        baseline(SystemKind.SINGLE_SHOT, role=FILLING)
    with pytest.raises(ValueError, match="agent runs the investigator role; the line fills"):
        baseline(SystemKind.AGENT, role=READER)
    with pytest.raises(ValueError, match="rules_only calls no model"):
        baseline(SystemKind.RULES_ONLY)


def test_a_pending_single_shot_protocol_or_limit_refuses() -> None:
    def with_pending(**held: Any) -> Registration:
        return replace(
            DRAFT,
            systems=tuple(
                replace(system, **held) if isinstance(system, SingleShotSystem) else system
                for system in DRAFT.systems
            ),
        )

    for pending in (
        with_pending(query_protocol=Pending("later")),
        with_pending(search_limit=Pending("later")),
    ):
        with pytest.raises(ValueError, match="query protocol or search limit is pending"):
            baseline(SystemKind.SINGLE_SHOT, pending)
    with pytest.raises(ValueError, match="the single_shot's variant is pending"):
        baseline(SystemKind.SINGLE_SHOT, with_pending(variant=Pending("later")))


def test_a_frozen_registration_is_executed_as_registered_and_a_pending_variant_refuses() -> None:
    mine = refused_by()
    settled = frozen()
    past = replace(
        settled,
        systems=tuple(
            replace(system, roles=(current_role(),)) if isinstance(system, AgentSystem) else system
            for system in settled.systems
        ),
        stated_facts=replace(
            settled.stated_facts, entry_schema=EntrySchema(mine.parser, mine.schema_digest)
        ),
    )
    assert past.status is RegistrationStatus.FROZEN
    held = agent(past)
    assert held.system == System(SystemKind.AGENT, "graph")
    assert held.redispatch == RedispatchPolicy(2, 1_000)
    assert effective_rules(past) == Rules(past.attribution, past.run_accounting.redispatch)  # type: ignore[arg-type]
    system = DRAFT.system(SystemKind.AGENT)
    assert isinstance(system, AgentSystem)
    unnamed = replace(
        DRAFT,
        systems=tuple(
            replace(system, variant=Pending("later")) if held.kind is SystemKind.AGENT else held
            for held in DRAFT.systems
        ),
    )
    with pytest.raises(ValueError, match="the agent's variant is pending"):
        agent(unnamed)


def test_the_rules_only_configuration_is_the_provenance_in_the_lifecycles_form() -> None:
    """The first live run's step, fork 4: the frozen inputs of a rules-only run through the
    worker name no role, no table, no policy and no retrieval, and otherwise what
    ``rules_only_provenance`` fixes for the cell; a cell that is not registered refuses the
    same way."""
    configuration = rules_only_configuration(
        DRAFT, "jira_down", "base", preregistration_commit=COMMIT, pricing=PRICING
    )
    direct = provenance(DRAFT, "jira_down")
    assert configuration.system == System(SystemKind.RULES_ONLY, direct.variant)
    assert configuration.retrieval == Retrieval(RetrievalKind.NONE, None)
    assert (configuration.caps, configuration.outage, configuration.pricing) == (
        direct.caps,
        direct.outage,
        direct.pricing,
    )
    assert (configuration.corpus_level, configuration.preregistration_commit) == ("base", COMMIT)
    assert configuration.model_configurations == () and configuration.pricing_selections == ()
    assert configuration.prompt_digests == () and configuration.tool_surface_digests == ()
    assert configuration.attribution_table is None and configuration.redispatch is None
    assert configuration.query_protocol is None and configuration.search_limit is None
    assert configuration.context_allowances == ()
    assert configuration.retry == DRAFT.run_accounting.retry
    assert configuration.composing_policy == composing_policy()
    assert configuration.claim_author is ClaimAuthor.RULES
    frozen_inputs = configuration.frozen_for(
        histories.inputs(reservation=None, system=System(SystemKind.RULES_ONLY, "reference"))
    )
    assert frozen_inputs.reservation_pico_usd is None
    assert frozen_inputs.system.kind is SystemKind.RULES_ONLY
    with pytest.raises(ValueError, match="no cell is registered for rules_only under 'slack_down'"):
        rules_only_configuration(
            DRAFT, "slack_down", "base", preregistration_commit=COMMIT, pricing=PRICING
        )
