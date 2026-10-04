"""The preregistration: the committed draft is the encoder's own bytes and declares what was
ruled; a pendable field is a value or a pending statement and nothing else; a frozen
registration has nothing pending and no unmeasured number; an arm or a comparison names
only what is registered; the schedule digest moves with what is injected and with nothing
about how the file spells it; and an unknown key, a missing field, a wrong type, another
format and a reformatted file all refuse at decode naming what was wrong."""

import json
from pathlib import Path
from typing import cast

import pytest

from leaveimpact.core import (
    OUTAGE_PROTOCOL,
    PREFETCH_PROTOCOL,
    AgentSystem,
    Basis,
    Pending,
    Registration,
    RegistrationStatus,
    ReportingScope,
    RulesOnlySystem,
    SingleShotSystem,
    Source,
    SystemKind,
    condition_id,
    decode_registration,
    decode_registration_bytes,
    encode_registration,
    pending_fields,
    prefetch_rule,
    registration_bytes,
    schedule_digest,
)

DRAFT_FILE = Path(__file__).resolve().parents[2] / "preregistration" / "registration.json"
DIGEST = "ab" * 32
COMMIT = "c" * 40


def _draft_tree() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(DRAFT_FILE.read_bytes()))


def _draft() -> Registration:
    return decode_registration_bytes(DRAFT_FILE.read_bytes())


def _nested(data: object, *path: str | int) -> dict[str, object]:
    for step in path:
        data = cast("dict[str | int, object]", data)[step]
    return cast("dict[str, object]", data)


def _resolved_tree() -> dict[str, object]:
    """The draft with every pending value chosen and its numbers calibrated, the query
    protocol aside, which this format can only hold pending."""
    data = _draft_tree()
    model = {"model_id": "eu.some-model", "settings": [{"name": "temperature", "value": 0}]}
    prompts = [{"name": "system", "digest": DIGEST}]
    agent, _, single_shot = cast("list[dict[str, object]]", data["systems"])
    agent |= {
        "variant": {"value": "graph-1"},
        "model": {"value": model},
        "prompt_digests": {"value": prompts},
        "tool_surface_digest": {"value": DIGEST},
    }
    single_shot |= {
        "variant": {"value": "one-call"},
        "model": {"value": model},
        "prompt_digests": {"value": prompts},
        "search_limit": {"value": 5},
    }
    _nested(data, "scenario_sets")["development"] = {
        "value": [f"scenario_{n:03d}" for n in (2, 5, 11, 14, 23, 29)]
    }
    _nested(data, "caps")["basis"] = "calibrated"
    _nested(data, "budget")["basis"] = "calibrated"
    return data


# --- The committed draft ----------------------------------------------------------------------


def test_the_committed_draft_is_the_encoders_own_bytes() -> None:
    raw = DRAFT_FILE.read_bytes()
    assert registration_bytes(decode_registration_bytes(raw)) == raw


def test_the_draft_registers_three_systems_under_five_conditions_as_fifteen_arms() -> None:
    draft = _draft()
    assert draft.status is RegistrationStatus.DRAFT
    # Registration format 1 registers three systems; the fourth kind, full context, exists
    # for the run export and joins the registration with the registration's own format 2.
    registered = [kind for kind in SystemKind if kind is not SystemKind.FULL_CONTEXT]
    assert [system.kind for system in draft.systems] == registered
    scopes = {condition.id: condition.reporting for condition in draft.outage.conditions}
    assert scopes == {
        "normal": ReportingScope.ANSWER_QUALITY,
        "jira_down": ReportingScope.ANSWER_QUALITY,
        "calendar_down": ReportingScope.ANSWER_QUALITY,
        "frappe_down": ReportingScope.DEGRADED_CONDITION,
        "corpus_down": ReportingScope.DEGRADED_CONDITION,
    }
    assert {(arm.system, arm.condition) for arm in draft.arms} == {
        (kind, condition) for kind in registered for condition in scopes
    }
    assert len(draft.arms) == 15


def test_the_draft_names_the_prefetch_and_the_outage_protocol_this_code_computes() -> None:
    draft = _draft()
    rule = prefetch_rule()
    registered = draft.prefetch
    assert (registered.identifier, registered.digest) == (rule.identifier, rule.digest)
    assert registered.protocol_version == PREFETCH_PROTOCOL[1]
    assert draft.outage.protocol == OUTAGE_PROTOCOL


def test_the_draft_marks_its_caps_and_budget_unmeasured_and_amends_nothing() -> None:
    draft = _draft()
    assert draft.caps.basis is Basis.UNMEASURED
    assert draft.budget.basis is Basis.UNMEASURED
    assert (draft.amendment.amends, draft.amendment.prior_full_set_results) == (None, False)


def test_the_drafts_pending_values_are_the_model_systems() -> None:
    draft = _draft()
    assert pending_fields(draft) == (
        "systems.agent.variant",
        "systems.agent.model",
        "systems.agent.prompt_digests",
        "systems.agent.tool_surface_digest",
        "systems.single_shot.variant",
        "systems.single_shot.model",
        "systems.single_shot.prompt_digests",
        "systems.single_shot.query_protocol",
        "systems.single_shot.search_limit",
    )
    # The development scenarios are registered: the six the first dispatch selected.
    assert draft.scenario_sets.development == (
        "scenario_009",
        "scenario_010",
        "scenario_013",
        "scenario_018",
        "scenario_023",
        "scenario_028",
    )
    rules_only = draft.system(SystemKind.RULES_ONLY)
    assert isinstance(rules_only, RulesOnlySystem)
    assert rules_only.variant == "reference"


# --- Pending and the lifecycle ----------------------------------------------------------------


def test_a_resolved_registration_round_trips_with_values_where_the_draft_was_pending() -> None:
    data = _resolved_tree()
    resolved = decode_registration(data)
    assert pending_fields(resolved) == ("systems.single_shot.query_protocol",)
    assert encode_registration(resolved) == data
    assert decode_registration_bytes(registration_bytes(resolved)) == resolved
    agent = resolved.system(SystemKind.AGENT)
    single_shot = resolved.system(SystemKind.SINGLE_SHOT)
    assert isinstance(agent, AgentSystem) and isinstance(single_shot, SingleShotSystem)
    assert agent.prompt_digests == (("system", DIGEST),)
    assert single_shot.search_limit == 5
    assert not isinstance(resolved.scenario_sets.development, Pending)


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
    _nested(data, "caps")["token_cap"] = {"pending": "after calibration"}
    with pytest.raises(ValueError, match="token_cap is an integer, got dict"):
        decode_registration(data)


def test_the_query_protocol_can_only_be_pending_in_this_format() -> None:
    data = _draft_tree()
    _nested(data, "systems", 2)["query_protocol"] = {"value": "leave policy"}
    with pytest.raises(ValueError, match="query_protocol can only be pending"):
        decode_registration(data)


def test_a_frozen_registration_has_nothing_pending() -> None:
    data = _resolved_tree()
    data["status"] = "frozen"
    with pytest.raises(
        ValueError, match="nothing pending, got systems.single_shot.query_protocol"
    ):
        decode_registration(data)
    data = _draft_tree()
    data["status"] = "frozen"
    with pytest.raises(ValueError, match="nothing pending, got systems.agent.variant, "):
        decode_registration(data)


def _rules_only_tree() -> dict[str, object]:
    """The resolved registration cut down to the one system this format can freeze."""
    data = _resolved_tree()
    data["systems"] = [cast("list[object]", data["systems"])[1]]
    arms = cast("list[dict[str, str]]", data["arms"])
    data["arms"] = [arm for arm in arms if arm["system"] == "rules_only"]
    _nested(data, "statistics")["primary"] = []
    _nested(data, "statistics", "descriptive")["pairs"] = []
    return data


def test_a_frozen_registration_refuses_unmeasured_numbers() -> None:
    data = _rules_only_tree()
    data["status"] = "frozen"
    assert decode_registration(data).status is RegistrationStatus.FROZEN
    _nested(data, "budget")["basis"] = "unmeasured"
    with pytest.raises(ValueError, match="numbers are calibrated, got unmeasured budget"):
        decode_registration(data)
    _nested(data, "caps")["basis"] = "unmeasured"
    with pytest.raises(ValueError, match="got unmeasured caps and budget"):
        decode_registration(data)
    data["status"] = "draft"
    assert decode_registration(data).caps.basis is Basis.UNMEASURED


# --- What only the whole can check -------------------------------------------------------------


def test_an_arm_is_registered_once_and_names_a_registered_system_and_condition() -> None:
    data = _draft_tree()
    arms = cast("list[object]", data["arms"])
    arms.append(arms[0])
    with pytest.raises(ValueError, match="an arm is registered once"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "arms", 0)["condition"] = "slack_down"
    with pytest.raises(ValueError, match="an arm names a registered condition, got 'slack_down'"):
        decode_registration(data)
    data = _draft_tree()
    cast("list[object]", data["systems"]).pop()
    with pytest.raises(ValueError, match="an arm names a registered system, got single_shot"):
        decode_registration(data)


def test_a_system_kind_and_a_condition_are_each_registered_once() -> None:
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


def test_a_comparison_is_made_between_registered_arms_under_an_answer_quality_condition() -> None:
    data = _draft_tree()
    _nested(data, "statistics", "primary", 0)["condition"] = "frappe_down"
    with pytest.raises(ValueError, match="under an answer-quality condition, got 'frappe_down'"):
        decode_registration(data)
    data = _draft_tree()
    data["arms"] = cast("list[object]", data["arms"])[1:]
    with pytest.raises(ValueError, match="between registered arms, got agent under 'normal'"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "primary", 0)["check"] = "plausible"
    with pytest.raises(ValueError, match="a comparison names a registered check"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics", "primary", 0)["systems"] = ["agent", "agent"]
    with pytest.raises(ValueError, match="a comparison is between two systems"):
        decode_registration(data)


def test_the_sections_own_invariants_hold_on_decode() -> None:
    data = _draft_tree()
    _nested(data, "caps")["finalization_call_reserve"] = 20
    with pytest.raises(ValueError, match="the finalization call reserve sits inside the call cap"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "budget")["admission_threshold_usd"] = 280
    with pytest.raises(ValueError, match="at or below its limit, got 280 over 270"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "systems", 1, "retrieval")["kind"] = "full_text"
    with pytest.raises(ValueError, match="rules-only retrieves nothing"):
        decode_registration(data)
    data = _resolved_tree()
    _nested(data, "systems", 2)["search_limit"] = {"value": 21}
    with pytest.raises(ValueError, match=r"the search limit lies in 1\.\.20, got 21"):
        decode_registration(data)
    data = _resolved_tree()
    _nested(data, "scenario_sets", "development")["value"] = ["scenario_002"]
    with pytest.raises(ValueError, match="6 development scenarios are listed, got 1"):
        decode_registration(data)
    data = _draft_tree()
    _nested(data, "statistics")["confidence_percent"] = 100
    with pytest.raises(ValueError, match="strictly between 0 and 100 percent, got 100"):
        decode_registration(data)


# --- The schedule digest ----------------------------------------------------------------------


def test_the_schedule_digest_ignores_how_the_file_spells_the_schedule() -> None:
    draft = _draft()
    data = _draft_tree()
    outage = _nested(data, "outage")
    conditions = cast("list[dict[str, object]]", outage["conditions"])
    outage["conditions"] = list(reversed(conditions))
    conditions[3]["reporting"] = "answer_quality"
    respelled = decode_registration(data)
    assert respelled.outage != draft.outage
    assert schedule_digest(respelled.outage) == schedule_digest(draft.outage)


def test_the_schedule_digest_moves_with_a_source_set_and_with_the_protocol() -> None:
    registered = schedule_digest(_draft().outage)
    data = _draft_tree()
    _nested(data, "outage", "protocol")["version"] = 2
    assert schedule_digest(decode_registration(data).outage) != registered
    data = _draft_tree()
    _nested(data, "outage", "conditions", 4)["unreachable"] = ["corpus", "jira"]
    for arm in cast("list[dict[str, str]]", data["arms"]):
        if arm["condition"] == "corpus_down":
            arm["condition"] = "corpus+jira_down"
    assert schedule_digest(decode_registration(data).outage) != registered


def test_a_condition_is_named_by_the_sources_it_cannot_reach() -> None:
    assert condition_id([]) == "normal"
    assert condition_id([Source.JIRA, Source.CALENDAR]) == "calendar+jira_down"


# --- Strict decoding --------------------------------------------------------------------------


def test_another_format_refuses_before_anything_else() -> None:
    data = _draft_tree()
    data["format_version"] = 2
    del data["arms"]
    with pytest.raises(ValueError, match="this code reads registration format 1, got 2"):
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
    _nested(data, "systems", 1)["model"] = {"pending": "never"}
    with pytest.raises(ValueError, match=r"the rules_only system has fields .*surplus \['model'\]"):
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


def test_an_amending_registration_names_the_commit_it_amends() -> None:
    data = _draft_tree()
    data["amendment"] = {"amends": COMMIT, "prior_full_set_results": True}
    amended = decode_registration(data)
    assert (amended.amendment.amends, amended.amendment.prior_full_set_results) == (COMMIT, True)
