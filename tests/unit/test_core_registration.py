"""The preregistration: the committed draft is the encoder's own bytes and declares what was
ruled, twenty-four cells of four systems with four of them in one conditional group; a
pendable field is a value or a pending statement and nothing else; a frozen registration
has nothing pending but its world's version, and refuses each other pending value by name;
a bound one names the frozen commit and shares its procedure; a cell or a comparison names
only what is registered; what a system's execution needs is read one way; the schedule
digest moves with what is injected and with nothing about how the file spells it; and an
unknown key, a missing field, a wrong type, another format and a reformatted file all
refuse at decode naming what was wrong."""

import json
from dataclasses import replace
from typing import cast

import pytest

from leaveimpact.agent.composer import composing_policy
from leaveimpact.core import (
    OUTAGE_PROTOCOL,
    PREFETCH_PROTOCOL,
    AgentSystem,
    Basis,
    CheckReading,
    FullContextSystem,
    GroupDecision,
    MeasuredWorld,
    Pending,
    Registration,
    RegistrationStatus,
    ReportingScope,
    RulesOnlySystem,
    Source,
    StratumLevel,
    SystemKind,
    anchor_table_digest,
    blocking,
    condition_id,
    decode_registration,
    decode_registration_bytes,
    encode_registration,
    pending_fields,
    prefetch_rule,
    procedure_digest,
    procedure_projection,
    registration_bytes,
    schedule_digest,
)
from leaveimpact.core.attribution import AttributionTable, Match, ObservationKind
from tests.unit.registration_fixture import (
    COMMIT,
    DIGEST,
    DRAFT,
    DRAFT_FILE,
    MECHANISM,
    ROLE,
    TABLE,
    bound,
    decided,
    frozen,
    named,
)

GROUP = "full_context_under_outage"
WORLD = "f" * 64
STOPS = frozenset({"end_turn", "tool_use"})
# The fixture's rows, the first renamed: a constrained row goes before its kind's open one.
ROWS = (replace(TABLE.rows[0], identifier="any_other_complete_response"), *TABLE.rows[1:])


def _draft_tree() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(DRAFT_FILE.read_bytes()))


def _tree(registration: Registration) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(registration_bytes(registration)))


def _nested(data: object, *path: str | int) -> dict[str, object]:
    for step in path:
        data = cast("dict[str | int, object]", data)[step]
    return cast("dict[str, object]", data)


def _cells(data: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", data["cells"])


# --- The committed draft ----------------------------------------------------------------------


def test_the_committed_draft_is_the_encoders_own_bytes() -> None:
    raw = DRAFT_FILE.read_bytes()
    assert registration_bytes(decode_registration_bytes(raw)) == raw


def test_the_draft_lists_twenty_four_cells_twenty_with_no_group_and_four_in_one() -> None:
    assert DRAFT.status is RegistrationStatus.DRAFT
    assert [system.kind for system in DRAFT.systems] == list(SystemKind)
    scopes = {condition.id: condition.reporting for condition in DRAFT.outage.conditions}
    assert scopes == {
        "normal": ReportingScope.ANSWER_QUALITY,
        "jira_down": ReportingScope.ANSWER_QUALITY,
        "calendar_down": ReportingScope.ANSWER_QUALITY,
        "frappe_down": ReportingScope.DEGRADED_CONDITION,
        "corpus_down": ReportingScope.DEGRADED_CONDITION,
    }
    assert [(level.name, level.filler_tokens == 0) for level in DRAFT.corpus_levels] == [
        ("base", True),
        ("padded", False),
    ]
    # Every system under the normal condition at both levels, and under each outage at the
    # base level alone: no outage is crossed with a size.
    assert {cell.place for cell in DRAFT.cells} == {
        (kind, condition, level)
        for kind in SystemKind
        for condition in scopes
        for level in ("base", "padded")
        if level == "base" or condition == "normal"
    }
    grouped = [cell for cell in DRAFT.cells if cell.group is not None]
    assert (len(DRAFT.cells), len(DRAFT.cells) - len(grouped), len(grouped)) == (24, 20, 4)
    # The four are full context under each outage, and they are one group with one decision.
    assert {(cell.system, cell.level, cell.group) for cell in grouped} == {
        (SystemKind.FULL_CONTEXT, "base", GROUP)
    }
    assert {cell.condition for cell in grouped} == set(scopes) - {"normal"}
    (group,) = DRAFT.cell_groups
    assert group.name == GROUP and isinstance(group.decision, Pending) and not group.runs
    assert not any(DRAFT.runs(cell) for cell in grouped)
    assert all(DRAFT.runs(cell) for cell in DRAFT.cells if cell.group is None)


def test_the_draft_names_what_this_code_computes() -> None:
    rule = prefetch_rule()
    registered = DRAFT.prefetch
    assert (registered.identifier, registered.digest) == (rule.identifier, rule.digest)
    assert registered.protocol_version == PREFETCH_PROTOCOL[1]
    assert DRAFT.outage.protocol == OUTAGE_PROTOCOL
    # The composing policy is the harness's to compute and the anchor table core's.
    assert DRAFT.stated_facts.composing_policy == composing_policy()
    assert DRAFT.stated_facts.anchor_table == anchor_table_digest()


def test_the_draft_marks_its_numbers_unmeasured_amends_nothing_and_tunes_on_no_scenario() -> None:
    assert {system.caps.basis for system in DRAFT.systems} == {Basis.UNMEASURED}
    assert DRAFT.budget.basis is Basis.UNMEASURED
    assert (DRAFT.amendment.amends, DRAFT.amendment.prior_full_set_results) == (None, False)
    assert (DRAFT.world.tuned_scenarios, DRAFT.world.frozen_commit) == (0, None)
    assert isinstance(DRAFT.world.version, Pending)


def test_the_draft_registers_one_primary_and_what_is_named_beside_it() -> None:
    statistics = DRAFT.statistics
    primary = statistics.primary
    assert (primary.check, primary.reading) == ("correct_whole", CheckReading.END_TO_END)
    assert (primary.condition, primary.level) == ("normal", "padded")
    assert primary.systems == (SystemKind.AGENT, SystemKind.FULL_CONTEXT)
    assert primary.breakdowns == (StratumLevel.TIER,)
    assert [(c.systems, c.level) for c in statistics.secondary] == [
        ((SystemKind.AGENT, SystemKind.SINGLE_SHOT), "base"),
        ((SystemKind.AGENT, SystemKind.SINGLE_SHOT), "padded"),
    ]
    # The descriptive places are named outright: the outages run at the base level only.
    assert [(place.condition, place.level) for place in statistics.descriptive.places] == [
        ("normal", "base"),
        ("normal", "padded"),
        ("jira_down", "base"),
        ("calendar_down", "base"),
    ]
    assert len(statistics.descriptive.pairs) == 6
    # Padded less base, for each system that reads documents; rules only is equal by
    # construction and is left out.
    assert [(c.system, c.levels, c.condition) for c in statistics.level_contrasts] == [
        (kind, ("padded", "base"), "normal")
        for kind in (SystemKind.AGENT, SystemKind.SINGLE_SHOT, SystemKind.FULL_CONTEXT)
    ]
    assert statistics.interval_method == "paired_scenario_bootstrap_within_tier"
    assert statistics.headroom.reference is SystemKind.RULES_ONLY
    assert statistics.mechanism == MECHANISM
    assert [entry.identifier for entry in DRAFT.supporting] == [
        "vector_retrieval",
        "multi_agent",
        "second_model",
        "authoring",
    ]
    assert all(isinstance(entry.inclusion, Pending) for entry in DRAFT.supporting)


def test_the_drafts_pending_values_in_the_files_order() -> None:
    assert pending_fields(DRAFT) == (
        "world.version",
        "systems.agent.variant",
        "systems.agent.roles",
        "systems.single_shot.variant",
        "systems.single_shot.roles",
        "systems.single_shot.query_protocol",
        "systems.single_shot.search_limit",
        "systems.full_context.variant",
        "systems.full_context.roles",
        "corpus_levels.padded.filler_tokens",
        f"cell_groups.{GROUP}.decision",
        "run_accounting.redispatch",
        "attribution",
        "stated_facts.entry_schema",
        "supporting.vector_retrieval.inclusion",
        "supporting.multi_agent.inclusion",
        "supporting.second_model.other_model",
        "supporting.second_model.inclusion",
        "supporting.authoring.inclusion",
    )
    rules_only = DRAFT.system(SystemKind.RULES_ONLY)
    assert isinstance(rules_only, RulesOnlySystem) and rules_only.variant == "reference"


# --- What a system's execution needs ----------------------------------------------------------


def test_what_blocks_a_system_is_its_own_pending_values_and_what_every_model_call_needs() -> None:
    # Rules only calls no model: nothing the model systems wait on blocks it, and neither
    # does the padded level's pending size.
    assert blocking(DRAFT, SystemKind.RULES_ONLY) == ()
    shared = ("run_accounting.redispatch", "attribution", "stated_facts.entry_schema")
    assert blocking(DRAFT, SystemKind.AGENT) == (
        "systems.agent.variant",
        "systems.agent.roles",
        *shared,
    )
    resolved = named()
    assert blocking(resolved, SystemKind.AGENT) == ()
    assert blocking(resolved, SystemKind.FULL_CONTEXT) == ()
    # The query protocol can only be pending in this format, so single-shot stays blocked.
    assert blocking(resolved, SystemKind.SINGLE_SHOT) == (
        "systems.single_shot.variant",
        "systems.single_shot.roles",
        "systems.single_shot.query_protocol",
        "systems.single_shot.search_limit",
    )
    # A named system is still blocked while the table its dispatches are read by is pending.
    untabled = replace(resolved, attribution=Pending("the rows"))
    assert blocking(untabled, SystemKind.AGENT) == ("attribution",)
    assert blocking(untabled, SystemKind.RULES_ONLY) == ()
    # A system the registration does not hold blocks nothing; its absence is the caller's.
    assert blocking(frozen(), SystemKind.SINGLE_SHOT) == ()


# --- Pending and the lifecycle ----------------------------------------------------------------


def test_a_resolved_registration_round_trips_with_values_where_the_draft_was_pending() -> None:
    resolved = named()
    data = _tree(resolved)
    assert decode_registration(data) == resolved
    assert encode_registration(resolved) == data
    assert decode_registration_bytes(registration_bytes(resolved)) == resolved
    agent = resolved.system(SystemKind.AGENT)
    full_context = resolved.system(SystemKind.FULL_CONTEXT)
    assert isinstance(agent, AgentSystem) and isinstance(full_context, FullContextSystem)
    assert agent.roles == (ROLE,) and ROLE.prompt_digests == (("system", DIGEST),)
    assert "systems.agent.roles" not in pending_fields(resolved)


def test_a_pendable_field_is_one_of_value_and_pending_and_nothing_else() -> None:
    data = _draft_tree()
    _nested(data, "systems", 0)["variant"] = {"value": "graph-1", "pending": "later"}
    with pytest.raises(ValueError, match="variant is an object with exactly one of 'value' and"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "systems", 0)["variant"] = "graph-1"
    with pytest.raises(ValueError, match="variant is a JSON object, got str"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "systems", 0)["variant"] = {"pending": ""}
    with pytest.raises(ValueError, match="a pending value says what resolves it"):
        decode_registration(data)


def test_a_field_not_declared_pendable_cannot_be_pending() -> None:
    data = _draft_tree()
    _nested(data, "systems", 1, "caps")["token_cap"] = {"pending": "after calibration"}
    with pytest.raises(ValueError, match="token_cap is an integer, got dict"):
        decode_registration(data)


def test_the_query_protocol_can_only_be_pending_in_this_format() -> None:
    data = _draft_tree()
    _nested(data, "systems", 2)["query_protocol"] = {"value": "leave policy"}
    with pytest.raises(ValueError, match="query_protocol can only be pending"):
        decode_registration(data)


def test_a_frozen_registration_has_nothing_pending_but_its_worlds_version() -> None:
    held = frozen()
    assert held.status is RegistrationStatus.FROZEN
    assert pending_fields(held) == ("world.version",)
    assert decode_registration_bytes(registration_bytes(held)) == held
    # Each value the draft holds pending is refused by name when it is put back, one at a
    # time, the single-shot system's aside: this format cannot freeze that system at all.
    waiting = Pending("not yet")
    agent, rules_only, full_context = held.systems
    assert isinstance(agent, AgentSystem) and isinstance(full_context, FullContextSystem)
    padded = held.corpus_levels[1]
    (group,) = held.cell_groups
    second_model = held.supporting[2]

    def systems(changed: object, at: int) -> tuple[object, ...]:
        return tuple(changed if position == at else s for position, s in enumerate(held.systems))

    put_back: dict[str, dict[str, object]] = {
        "systems.agent.variant": {"systems": systems(replace(agent, variant=waiting), 0)},
        "systems.agent.roles": {"systems": systems(replace(agent, roles=waiting), 0)},
        "systems.rules_only.variant": {
            "systems": systems(replace(rules_only, variant=waiting), 1)
        },
        "systems.full_context.variant": {
            "systems": systems(replace(full_context, variant=waiting), 2)
        },
        "systems.full_context.roles": {
            "systems": systems(replace(full_context, roles=waiting), 2)
        },
        "corpus_levels.padded.filler_tokens": {
            "corpus_levels": (held.corpus_levels[0], replace(padded, filler_tokens=waiting))
        },
        f"cell_groups.{GROUP}.decision": {"cell_groups": (replace(group, decision=waiting),)},
        "run_accounting.redispatch": {
            "run_accounting": replace(held.run_accounting, redispatch=waiting)
        },
        "attribution": {"attribution": waiting},
        "stated_facts.entry_schema": {
            "stated_facts": replace(held.stated_facts, entry_schema=waiting)
        },
        "statistics.mechanism": {"statistics": replace(held.statistics, mechanism=waiting)},
        "supporting.second_model.other_model": {
            "supporting": (
                *held.supporting[:2],
                replace(second_model, other_model=waiting),
                held.supporting[3],
            )
        },
        "supporting.second_model.inclusion": {
            "supporting": (
                *held.supporting[:2],
                replace(second_model, inclusion=waiting),
                held.supporting[3],
            )
        },
    }
    for name, change in put_back.items():
        with pytest.raises(ValueError, match="nothing pending but its world, got ") as refused:
            replace(held, **change)
        assert str(refused.value).endswith(f"got {name}"), name
    # The draft frozen as it stands names every one of them at once.
    data = _draft_tree()
    data["status"] = "frozen"
    with pytest.raises(ValueError, match="nothing pending but its world, got systems.agent"):
        decode_registration(data)


def test_a_frozen_registration_holds_its_worlds_version_pending_and_names_no_commit() -> None:
    held = frozen()
    with pytest.raises(ValueError, match="so the world's version is pending"):
        replace(held, world=MeasuredWorld(WORLD, None, 0))
    with pytest.raises(ValueError, match="named exactly by a bound registration"):
        replace(held, world=replace(held.world, frozen_commit=COMMIT))
    with pytest.raises(ValueError, match="tuned on no scenario of its world, got 6"):
        replace(held, world=replace(held.world, tuned_scenarios=6))
    # A draft may say it tuned on some; it is a draft's to change before the freeze.
    assert replace(DRAFT, world=replace(DRAFT.world, tuned_scenarios=6)).world.tuned_scenarios


def test_a_frozen_registration_refuses_unmeasured_numbers() -> None:
    held = frozen()
    with pytest.raises(ValueError, match="numbers are calibrated, got unmeasured budget"):
        replace(held, budget=replace(held.budget, basis=Basis.UNMEASURED))
    agent = held.systems[0]
    unmeasured = replace(agent, caps=replace(agent.caps, basis=Basis.UNMEASURED))
    with pytest.raises(ValueError, match="got unmeasured agent caps"):
        replace(held, systems=(unmeasured, *held.systems[1:]))


def test_a_bound_registration_names_the_frozen_commit_and_changes_nothing_else() -> None:
    held = frozen()
    made = bound(WORLD, held)
    assert made.status is RegistrationStatus.BOUND and pending_fields(made) == ()
    assert (made.world.version, made.world.frozen_commit) == (WORLD, COMMIT)
    assert decode_registration_bytes(registration_bytes(made)) == made
    with pytest.raises(ValueError, match="named exactly by a bound registration"):
        replace(made, world=MeasuredWorld(WORLD, None, 0))
    with pytest.raises(ValueError, match="a bound registration has nothing pending, got world"):
        replace(made, world=MeasuredWorld(Pending("later"), COMMIT, 0))

    # The procedure is what binding leaves alone: the status, the world's version and the
    # frozen commit are out of it, and everything else is in.
    assert procedure_projection(made) == procedure_projection(held)
    assert procedure_digest(made) == procedure_digest(held)
    projected = procedure_projection(made)
    assert "status" not in projected and projected["world"] == {"tuned_scenarios": 0}
    assert set(projected) == set(encode_registration(made)) - {"status"}
    assert procedure_digest(bound("e" * 64, held, frozen_commit="d" * 40)) == procedure_digest(held)
    # Anything else moves it: the seed, the amendment, a group's decision.
    seeded = replace(made, statistics=replace(made.statistics, seed=made.statistics.seed + 1))
    amended = replace(made, amendment=replace(made.amendment, amends=COMMIT))
    undone = bound(WORLD, frozen(run_group=False))
    for other in (seeded, amended, undone):
        assert procedure_digest(other) != procedure_digest(held)


# --- What only the whole can check -------------------------------------------------------------


def test_a_cell_is_registered_once_and_names_what_is_registered() -> None:
    data = _draft_tree()
    _cells(data).append(_cells(data)[0])
    with pytest.raises(ValueError, match="a cell is registered once"):
        decode_registration(data)
    for key, value, refusal in (
        ("condition", "slack_down", "a cell names a registered condition, got 'slack_down'"),
        ("level", "doubled", "a cell names a registered level, got 'doubled'"),
        ("group", "sometimes", "a cell names a registered group, got 'sometimes'"),
    ):
        data = _draft_tree()
        # The last cell is in no comparison, so only the cell's own check can refuse it.
        _cells(data)[-1][key] = value
        with pytest.raises(ValueError, match=refusal):
            decode_registration(data)
    data = _draft_tree()
    cast("list[object]", data["systems"]).pop()
    with pytest.raises(ValueError, match="a cell names a registered system, got full_context"):
        decode_registration(data)


def test_a_group_holds_a_cell_and_its_decision_gives_a_reason_only_when_it_is_not_run() -> None:
    data = _draft_tree()
    for cell in _cells(data):
        cell["group"] = None
    with pytest.raises(ValueError, match="a conditional group holds at least one cell"):
        decode_registration(data)
    with pytest.raises(ValueError, match="a group that is not run says why"):
        GroupDecision(False, None)
    with pytest.raises(ValueError, match="one that is run gives no reason"):
        GroupDecision(True, "the budget allowed it")
    run, not_run = decided(DRAFT, True), decided(DRAFT, False)
    grouped = [cell for cell in DRAFT.cells if cell.group is not None]
    assert all(run.runs(cell) for cell in grouped)
    assert not any(not_run.runs(cell) for cell in grouped)
    assert decode_registration_bytes(registration_bytes(not_run)) == not_run


def test_a_system_kind_a_level_and_a_condition_are_each_registered_once() -> None:
    data = _draft_tree()
    systems = cast("list[object]", data["systems"])
    systems.append(systems[1])
    with pytest.raises(ValueError, match="a system kind is registered once"):
        decode_registration(data)
    data = _draft_tree()
    conditions = cast("list[object]", _nested(data, "outage")["conditions"])
    conditions.append({"unreachable": ["jira"], "reporting": "degraded_condition"})
    with pytest.raises(ValueError, match="a condition is registered once"):
        decode_registration(data)
    data = _draft_tree()
    levels = cast("list[object]", data["corpus_levels"])
    levels.append(levels[1])
    with pytest.raises(ValueError, match="a corpus level is registered once"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "corpus_levels", 0)["filler_tokens"] = {"value": 5}
    with pytest.raises(ValueError, match="the base level is the world with no filler added"):
        decode_registration(data)


def test_a_comparison_is_made_between_registered_cells_under_an_answer_quality_condition() -> None:
    data = _draft_tree()
    _nested(data, "statistics", "primary")["condition"] = "frappe_down"
    with pytest.raises(ValueError, match="under an answer-quality condition, got 'frappe_down'"):
        decode_registration(data)
    data = _draft_tree()
    # No outage runs at the padded level, so no cell is there to compare.
    _nested(data, "statistics", "secondary", 0)["condition"] = "jira_down"
    _nested(data, "statistics", "secondary", 0)["level"] = "padded"
    with pytest.raises(
        ValueError, match="between registered cells, got agent under 'jira_down' at 'padded'"
    ):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "primary")["check"] = "plausible"
    with pytest.raises(ValueError, match="a comparison names a registered check"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "primary")["systems"] = ["agent", "agent"]
    with pytest.raises(ValueError, match="a comparison is between two systems"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "primary")["breakdowns"] = ["overall"]
    with pytest.raises(ValueError, match="never a breakdown of it"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "level_contrasts", 0)["levels"] = ["padded", "padded"]
    with pytest.raises(ValueError, match="a level contrast is between two levels"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "descriptive", "places", 0)["level"] = "doubled"
    with pytest.raises(ValueError, match="a comparison names a registered level, got 'doubled'"):
        decode_registration(data)


def test_the_sections_own_invariants_hold_on_decode() -> None:
    data = _draft_tree()
    _nested(data, "systems", 0, "caps")["finalization_call_reserve"] = 20
    with pytest.raises(ValueError, match="the finalization call reserve sits inside the call cap"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "budget")["admission_threshold_usd"] = 280
    with pytest.raises(ValueError, match="at or below its limit, got 280 over 270"):
        decode_registration(data)
    for position, name in ((1, "rules-only retrieves"), (3, "full context searches")):
        data = _draft_tree()
        _nested(data, "systems", position, "retrieval")["kind"] = "full_text"
        with pytest.raises(ValueError, match=f"{name} nothing"):
            decode_registration(data)
    data = _draft_tree()
    _nested(data, "systems", 2)["search_limit"] = {"value": 21}
    with pytest.raises(ValueError, match=r"the search limit lies in 1\.\.20, got 21"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics")["confidence_percent"] = 100
    with pytest.raises(ValueError, match="strictly between 0 and 100 percent, got 100"):
        decode_registration(data)
    data = _tree(named())
    roles = cast("list[object]", _nested(data, "systems", 0, "roles")["value"])
    roles.append(roles[0])
    with pytest.raises(ValueError, match="a role is registered once per system"):
        decode_registration(data)
    data = _tree(named())
    _nested(data, "systems", 0, "roles")["value"] = []
    with pytest.raises(ValueError, match="registers at least one role"):
        decode_registration(data)
    data = _draft_tree()
    sides = cast("list[object]", _nested(data, "supporting", 0)["systems"])
    sides[1] = sides[0]
    with pytest.raises(ValueError, match="vector_retrieval is between two systems"):
        decode_registration(data)


# --- The schedule digest ----------------------------------------------------------------------


def test_the_schedule_digest_ignores_how_the_file_spells_the_schedule() -> None:
    data = _draft_tree()
    outage = _nested(data, "outage")
    conditions = cast("list[dict[str, object]]", outage["conditions"])
    outage["conditions"] = list(reversed(conditions))
    # The corpus outage read for answer quality: how it is reported is not what is injected.
    conditions[4]["reporting"] = "answer_quality"
    respelled = decode_registration(data)
    assert respelled.outage != DRAFT.outage
    assert schedule_digest(respelled.outage) == schedule_digest(DRAFT.outage)


def test_the_schedule_digest_moves_with_a_source_set_and_with_the_protocol() -> None:
    registered = schedule_digest(DRAFT.outage)
    data = _draft_tree()
    _nested(data, "outage", "protocol")["version"] = 2
    assert schedule_digest(decode_registration(data).outage) != registered
    data = _draft_tree()
    _nested(data, "outage", "conditions", 4)["unreachable"] = ["corpus", "jira"]
    for cell in _cells(data):
        if cell["condition"] == "corpus_down":
            cell["condition"] = "corpus+jira_down"
    assert schedule_digest(decode_registration(data).outage) != registered


def test_a_condition_is_named_by_the_sources_it_cannot_reach() -> None:
    assert condition_id([]) == "normal"
    assert condition_id([Source.JIRA, Source.CALENDAR]) == "calendar+jira_down"


# --- Strict decoding --------------------------------------------------------------------------


def test_another_format_refuses_before_anything_else() -> None:
    data = _draft_tree()
    data["format_version"] = 1
    del data["cells"]
    with pytest.raises(ValueError, match="this code reads registration format 3, got 1"):
        decode_registration(data)
    data["format_version"] = True
    with pytest.raises(ValueError, match="format_version is an integer, got True"):
        decode_registration(data)


def test_a_surplus_or_missing_field_refuses_naming_the_object() -> None:
    data = _draft_tree()
    data["notes"] = "x"
    with pytest.raises(ValueError, match=r"a registration has fields .*surplus \['notes'\]"):
        decode_registration(data)
    data = _draft_tree()
    del _nested(data, "budget")["ceiling_usd"]
    with pytest.raises(ValueError, match=r"the budget has fields .*missing \['ceiling_usd'\]"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "systems", 1)["roles"] = {"pending": "never"}
    with pytest.raises(ValueError, match=r"the rules_only system has fields .*surplus \['roles'\]"):
        decode_registration(data)
    # The scenario sets left the registration, and so did the rules-only system's policy.
    data = _draft_tree()
    data["scenario_sets"] = {}
    with pytest.raises(ValueError, match=r"surplus \['scenario_sets'\]"):
        decode_registration(data)


def test_a_wrong_type_or_an_unknown_member_refuses_by_name() -> None:
    data = _draft_tree()
    _nested(data, "statistics")["resamples"] = 10000.0
    with pytest.raises(ValueError, match="resamples is an integer, got float"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "amendment")["prior_full_set_results"] = 0
    with pytest.raises(ValueError, match="prior_full_set_results is true or false, got int"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "amendment")["amends"] = "main"
    with pytest.raises(ValueError, match="commit is a forty-hex git commit, got 'main'"):
        decode_registration(data)
    data = _draft_tree()
    data["status"] = "final"
    with pytest.raises(ValueError, match="final"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "outage", "conditions", 1)["unreachable"] = ["slack"]
    with pytest.raises(ValueError, match="slack"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "world")["version"] = {"value": "golden"}
    with pytest.raises(ValueError, match="the world's version"):
        decode_registration(data)


def test_the_bytes_decoder_accepts_only_the_one_written_form() -> None:
    raw = DRAFT_FILE.read_bytes()
    compact = json.dumps(json.loads(raw), ensure_ascii=False, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="not its one written form"):
        decode_registration_bytes(compact)
    with pytest.raises(ValueError, match="not its one written form"):
        decode_registration_bytes(raw.replace(b"\n", b"\r\n"))
    duplicated = raw.replace(b'"status": "draft",', b'"status": "frozen",\n  "status": "draft",')
    with pytest.raises(ValueError, match="not its one written form"):
        decode_registration_bytes(duplicated)
    # An attribution table's constraint written out of order decodes to the same table,
    # so the bytes that hold it are not the written form.
    constrained = replace(
        TABLE.rows[0], match=Match(ObservationKind.COMPLETE_RESPONSE, stop_reasons=STOPS)
    )
    table = AttributionTable((constrained, *ROWS))
    tabled = registration_bytes(replace(named(), attribution=table))
    assert b'"end_turn",\n            "tool_use"' in tabled
    reordered = tabled.replace(
        b'"end_turn",\n            "tool_use"', b'"tool_use",\n            "end_turn"'
    )
    assert decode_registration(json.loads(reordered)) == decode_registration_bytes(tabled)
    with pytest.raises(ValueError, match="not its one written form"):
        decode_registration_bytes(reordered)


def test_an_amending_registration_names_the_commit_it_amends() -> None:
    data = _draft_tree()
    data["amendment"] = {"amends": COMMIT, "prior_full_set_results": True}
    amended = decode_registration(data)
    assert (amended.amendment.amends, amended.amendment.prior_full_set_results) == (COMMIT, True)


# --- Format 3: the input bound, the counting model, the count's retries --------------------


def test_every_system_registers_the_one_input_bound_method() -> None:
    for system in DRAFT.systems:
        bound = system.caps.input_bound
        assert (bound.name, bound.version) == ("provider_count", 1)
    for index in range(len(DRAFT.systems)):
        assert _nested(_draft_tree(), "systems", index, "caps")["input_bound"] == {
            "method": "provider_count",
            "version": 1,
        }


@pytest.mark.parametrize(
    ("bound", "message"),
    [
        ({"method": "request_bytes", "version": 1}, "an input-bound method is a registered one"),
        ({"method": "provider_count", "version": 2}, "registered at version 1, got 2"),
        ({"method": "provider_count"}, "the input bound"),
        ("provider_count", "input_bound is a JSON object"),
    ],
)
def test_caps_naming_a_method_the_registry_lacks_are_refused(bound: object, message: str) -> None:
    data = _draft_tree()
    _nested(data, "systems", 0, "caps")["input_bound"] = bound
    with pytest.raises(ValueError, match=message):
        decode_registration(data)


def test_caps_without_an_input_bound_are_another_format() -> None:
    data = _draft_tree()
    del _nested(data, "systems", 2, "caps")["input_bound"]
    with pytest.raises(ValueError, match="the caps"):
        decode_registration(data)


def test_a_role_names_the_model_its_requests_are_counted_against() -> None:
    tree = _tree(named())
    roles = cast("list[dict[str, object]]", _nested(tree, "systems", 0, "roles")["value"])
    assert roles[0]["counting_model_id"] == ROLE.counting_model_id == "some-model"
    assert decode_registration(tree) == named()
    del roles[0]["counting_model_id"]
    with pytest.raises(ValueError, match="a role"):
        decode_registration(tree)
    with pytest.raises(ValueError, match="the investigator counting model"):
        replace(ROLE, counting_model_id="")


def test_the_counts_retries_are_registered_by_reference_to_the_redispatch_policy() -> None:
    assert DRAFT.run_accounting.count_retry.value == "redispatch_policy"
    data = _draft_tree()
    _nested(data, "run_accounting")["count_retry"] = "three_times"
    with pytest.raises(ValueError, match="'three_times' is not a valid CountRetryRule"):
        decode_registration(data)
    data = _draft_tree()
    del _nested(data, "run_accounting")["count_retry"]
    with pytest.raises(ValueError, match="run accounting"):
        decode_registration(data)


def test_a_registration_never_retries_after_a_defect() -> None:
    data = _draft_tree()
    _nested(data, "run_accounting", "retry")["after"] = "defect"
    with pytest.raises(ValueError, match="never retried after a defect"):
        decode_registration(data)


def test_the_redispatch_policy_states_its_backoff_as_delay_ms() -> None:
    tree = _tree(named())
    assert _nested(tree, "run_accounting", "redispatch")["value"] == {
        "max_dispatches": 2,
        "delay_ms": 1_000,
    }
    _nested(tree, "run_accounting", "redispatch")["value"] = {
        "max_dispatches": 2,
        "max_delay_ms": 1_000,
    }
    with pytest.raises(ValueError, match="a re-dispatch policy"):
        decode_registration(tree)


def test_a_format_2_file_is_refused_by_its_version() -> None:
    data = _draft_tree()
    data["format_version"] = 2
    with pytest.raises(ValueError, match="this code reads registration format 3, got 2"):
        decode_registration(data)
