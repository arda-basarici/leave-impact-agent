"""A rules-only run's provenance comes from the registration: the assigned sources, the
schedule's digest, the registered caps and variant under each of the five conditions, with
the model systems still pending; and a registration this harness cannot execute as written
refuses, naming what differs: an unregistered arm, another outage protocol, another
prefetch, another reporting policy, a pending variant, no rules-only system."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.report import REPORTING_POLICY
from leaveimpact.core import (
    HarnessRevision,
    Pending,
    PricingBasis,
    RegisteredPrefetch,
    Registration,
    RulesOnlySystem,
    Source,
    SystemKind,
    TreeState,
    decode_registration_bytes,
    pending_fields,
    schedule_digest,
)

DRAFT = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)
HARNESS = HarnessRevision("b" * 40, TreeState.CLEAN)
COMMIT = "c" * 40
PRICING = PricingBasis("a" * 64, "USD", date(2026, 9, 1), ())


def provenance(registration: Registration, condition: str) -> RunProvenance:
    return rules_only_provenance(
        registration, condition, harness=HARNESS, preregistration_commit=COMMIT, pricing=PRICING
    )


def with_rules_only(registration: Registration, system: RulesOnlySystem) -> Registration:
    others = tuple(s for s in registration.systems if s.kind is not SystemKind.RULES_ONLY)
    return replace(registration, systems=(*others, system))


def rules_only_of(registration: Registration) -> RulesOnlySystem:
    system = registration.system(SystemKind.RULES_ONLY)
    assert isinstance(system, RulesOnlySystem)
    return system


@pytest.mark.parametrize(
    ("condition", "down"),
    [
        ("normal", frozenset[Source]()),
        ("jira_down", frozenset({Source.JIRA})),
        ("calendar_down", frozenset({Source.CALENDAR})),
        ("frappe_down", frozenset({Source.FRAPPE})),
        ("corpus_down", frozenset({Source.CORPUS})),
    ],
)
def test_the_draft_gives_a_rules_only_run_its_provenance_under_each_registered_condition(
    condition: str, down: frozenset[Source]
) -> None:
    assert pending_fields(DRAFT), "the model systems are still pending and do not block this"
    built = provenance(DRAFT, condition)
    assert built.outage.scheduled_unreachable == down
    assert built.outage.schedule_digest == schedule_digest(DRAFT.outage)
    assert built.caps == DRAFT.caps.caps
    assert built.variant == "reference"
    assert (built.harness, built.preregistration_commit, built.pricing) == (
        HARNESS,
        COMMIT,
        PRICING,
    )


def test_the_registered_policy_is_the_one_declared_beside_the_policy() -> None:
    assert rules_only_of(DRAFT).policy == REPORTING_POLICY


def test_an_arm_that_is_not_registered_refuses() -> None:
    with pytest.raises(ValueError, match="no arm is registered for rules_only under 'slack_down'"):
        provenance(DRAFT, "slack_down")
    cut = replace(
        DRAFT,
        arms=tuple(
            arm
            for arm in DRAFT.arms
            if (arm.system, arm.condition) != (SystemKind.RULES_ONLY, "corpus_down")
        ),
    )
    with pytest.raises(ValueError, match="no arm is registered for rules_only under 'corpus_down'"):
        provenance(cut, "corpus_down")
    assert provenance(cut, "normal").variant == "reference"


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


def test_another_reporting_policy_refuses_in_each_of_its_three_parts() -> None:
    system = rules_only_of(DRAFT)
    for changed in (
        replace(system.policy, identifier="another-report"),
        replace(system.policy, version=system.policy.version + 1),
        replace(system.policy, tie_break="last_viable"),
    ):
        other = with_rules_only(DRAFT, replace(system, policy=changed))
        with pytest.raises(ValueError, match="the registered reporting policy is .*this harness"):
            provenance(other, "normal")


def test_a_pending_variant_or_no_rules_only_system_refuses() -> None:
    pending = with_rules_only(DRAFT, replace(rules_only_of(DRAFT), variant=Pending("not named")))
    with pytest.raises(ValueError, match=r"the rules-only variant is pending \(not named\)"):
        provenance(pending, "normal")
    kept = tuple(s for s in DRAFT.systems if s.kind is SystemKind.AGENT)
    agent_only = replace(
        DRAFT,
        systems=kept,
        arms=tuple(arm for arm in DRAFT.arms if arm.system is SystemKind.AGENT),
        statistics=replace(
            DRAFT.statistics,
            primary=(),
            descriptive=replace(DRAFT.statistics.descriptive, pairs=()),
        ),
    )
    with pytest.raises(ValueError, match="the registration names no rules-only system"):
        provenance(agent_only, "normal")
