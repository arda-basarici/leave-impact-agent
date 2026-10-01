"""The truth manifest read back from its sealed bytes: decoding the bytes yields the projection of
the assembled world, and the decoder accepts only bytes that re-encode to themselves. The three
fields a sealed manifest may lack (a key's two derived sets, the record's counters, a refusal's
reasons) come back unavailable and never empty, each on its own; ``null`` in a set's place, a
field missing or surplus at any level, a foreign id, a wrong discriminator and bytes in any other
spelling are each refused naming what was expected."""

import json
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from leaveimpact.world import (
    COUNTER_NAMES,
    DEFAULT_PARAMS,
    Bundle,
    GuardName,
    MaterializationMetrics,
    Refusal,
    RefusalReason,
    WorldSpec,
    assemble_semantic_world,
    assemble_world,
    bundle,
    canonical_bytes,
    compose,
    encode_truth_manifest,
    truth_manifest_of,
)
from leaveimpact.world.truth_decoder import decode_truth_manifest
from tests.unit.prose_fixture import record_for

WORLD_START = date(2026, 1, 1)
REFERENCE_SEED = 7


@pytest.fixture(scope="module")
def structured() -> WorldSpec:
    """The tier-one reference world: no brief, no record."""
    return assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)


@pytest.fixture(scope="module")
def golden() -> WorldSpec:
    """The reference seed under the golden plan, composed with stand-in prose: every key shape
    the three tiers produce, briefs for comments and sections, and a record carrying both of
    its optional fields (the counters, a refusal's reasons)."""
    semantic = assemble_semantic_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START, "golden")
    bodies = {
        brief.id: f"Stand-in text for {brief.id}."
        for scenario in semantic.scenarios
        for brief in scenario.briefs
    }
    base = record_for(bodies)
    first, *rest = base.targets
    refused = Refusal(
        1,
        GuardName.EXTRACTION,
        2,
        ((RefusalReason.OTHER_CLAIM, 1), (RefusalReason.UNTYPED_PROPOSITION, 1)),
    )
    record = replace(
        base,
        targets=(replace(first, attempts=2, refusals=(refused,)), *rest),
        metrics=MaterializationMetrics(
            tuple((name, 5 if name == "writer_attempts" else 0) for name in COUNTER_NAMES)
        ),
    )
    return compose(semantic, bodies, record)


@pytest.fixture(scope="module")
def sealed(golden: WorldSpec) -> Bundle:
    return bundle(golden)


def truth_json(sealed: Bundle) -> Any:
    return json.loads(sealed.truth_manifest.content)


# --- The round trip -----------------------------------------------------------------------


def test_decoding_the_sealed_bytes_yields_the_projection_of_the_world(
    structured: WorldSpec, golden: WorldSpec, sealed: Bundle
) -> None:
    assert decode_truth_manifest(sealed.truth_manifest.content) == truth_manifest_of(golden)
    plain = bundle(structured).truth_manifest.content
    assert decode_truth_manifest(plain) == truth_manifest_of(structured)
    # The golden plan is what makes the claim worth making: every shape a key takes.
    manifest = truth_manifest_of(golden)
    keys = [row.key for row in manifest.scenarios]
    assert any(key.expected_conflicts for key in keys) and any(key.distractors for key in keys)
    assert any(key.expected_unknowns for key in keys) and any(key.constraints for key in keys)
    assert manifest.facts.gaps and any(row.briefs for row in manifest.scenarios)


def test_encoding_a_decoding_of_the_sealed_bytes_yields_the_bytes(sealed: Bundle) -> None:
    decoded = decode_truth_manifest(sealed.truth_manifest.content)
    assert canonical_bytes(encode_truth_manifest(decoded)) == sealed.truth_manifest.content
    # Text is the same manifest as its bytes.
    assert decode_truth_manifest(sealed.truth_manifest.content.decode("utf-8")) == decoded


# --- Absent is unavailable, never empty ---------------------------------------------------


def test_a_key_sealed_before_a_derived_set_decodes_it_as_unavailable_on_its_own(
    sealed: Bundle,
) -> None:
    data = truth_json(sealed)
    del data["scenarios"][0]["key"]["expected_conflicts"]
    older = canonical_bytes(data)
    first, second, *_ = decode_truth_manifest(older).scenarios
    assert first.key.expected_conflicts is None and first.key.expected_unknowns is not None
    assert second.key.expected_conflicts is not None
    # Accepted means re-encoded to the same bytes: the absent field stayed absent.
    del data["scenarios"][0]["key"]["expected_unknowns"]
    neither = decode_truth_manifest(canonical_bytes(data)).scenarios[0].key
    assert (neither.expected_conflicts, neither.expected_unknowns) == (None, None)


def test_an_empty_derived_set_is_known_empty_and_null_is_refused(sealed: Bundle) -> None:
    data = truth_json(sealed)
    empty = next(row["key"] for row in data["scenarios"] if row["key"]["expected_conflicts"] == [])
    scenario_id = empty["scenario_id"]
    decoded = decode_truth_manifest(sealed.truth_manifest.content)
    [key] = [row.key for row in decoded.scenarios if row.key.scenario_id == scenario_id]
    assert key.expected_conflicts == ()
    empty["expected_conflicts"] = None
    with pytest.raises(ValueError, match="expected_conflicts is a JSON array, got NoneType"):
        decode_truth_manifest(canonical_bytes(data))


def test_the_records_counters_and_a_refusals_reasons_come_back_as_sealed(sealed: Bundle) -> None:
    present = decode_truth_manifest(sealed.truth_manifest.content).materialization
    assert present is not None and present.metrics is not None
    assert present.metrics.value("writer_attempts") == 5
    assert present.targets[0].refusals[0].reasons == (
        (RefusalReason.OTHER_CLAIM, 1),
        (RefusalReason.UNTYPED_PROPOSITION, 1),
    )
    # The measurement world's shape: a record with no counters, a refusal with no reasons.
    data = truth_json(sealed)
    del data["materialization"]["metrics"]
    del data["materialization"]["targets"][0]["refusals"][0]["reasons"]
    older = decode_truth_manifest(canonical_bytes(data)).materialization
    assert older is not None and older.metrics is None
    assert older.targets[0].refusals == (Refusal(1, GuardName.EXTRACTION, 2),)
    assert older.targets[0].refusals[0].reasons is None


def test_a_record_sealed_before_a_counter_existed_holds_the_counters_its_run_had(
    sealed: Bundle,
) -> None:
    """The counters of a record sealed between their arrival and the canonicalized-pair counter
    (no such record was sealed, the shape was real in code): the later counter is unavailable,
    never zero, and the bytes come back exactly, which acceptance by the decoder is."""
    data = truth_json(sealed)
    counters = data["materialization"]["metrics"]
    data["materialization"]["metrics"] = {name: counters[name] for name in COUNTER_NAMES[:16]}
    assert "canonicalized_pairs" not in data["materialization"]["metrics"]
    earlier = decode_truth_manifest(canonical_bytes(data)).materialization
    assert earlier is not None and earlier.metrics is not None
    assert earlier.metrics.value("canonicalized_pairs") is None
    assert earlier.metrics.value("writer_attempts") == 5


def test_a_world_without_prose_decodes_in_both_of_its_shapes(structured: WorldSpec) -> None:
    manifest = truth_manifest_of(structured)
    assert decode_truth_manifest(canonical_bytes(encode_truth_manifest(manifest))) == manifest
    stage_ran = replace(manifest, materialization=record_for({}))
    decoded = decode_truth_manifest(canonical_bytes(encode_truth_manifest(stage_ran)))
    assert decoded == stage_ran and decoded.materialization is not None


# --- Strictness ---------------------------------------------------------------------------


def test_a_manifest_sealed_before_the_record_is_refused_at_the_top_level(sealed: Bundle) -> None:
    data = truth_json(sealed)
    del data["materialization"]
    # The first world's shape, and it holds older keys too: the top level is what refuses.
    del data["scenarios"][0]["key"]["expected_conflicts"]
    with pytest.raises(
        ValueError, match=r"the truth manifest has fields .* missing \['materialization'\]"
    ):
        decode_truth_manifest(canonical_bytes(data))


def test_a_surplus_field_is_refused_naming_it_at_every_level(sealed: Bundle) -> None:
    for path in ((), ("scenarios", 0), ("scenarios", 0, "key"), ("facts",), ("materialization",)):
        data = truth_json(sealed)
        holder = data
        for step in path:
            holder = holder[step]
        holder["notes"] = "hand-edited"
        with pytest.raises(ValueError, match=r"surplus \['notes'\]"):
            decode_truth_manifest(canonical_bytes(data))


def test_the_wrong_discriminator_is_refused(sealed: Bundle) -> None:
    with pytest.raises(ValueError, match="the truth manifest is sealed as truth-manifest.json"):
        decode_truth_manifest(sealed.scenario_specs.content)


def test_bytes_in_another_spelling_are_refused_as_not_canonical(sealed: Bundle) -> None:
    data = truth_json(sealed)
    pretty = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_truth_manifest(pretty)
    reordered = {"scenarios": data["scenarios"], **data}
    assert list(reordered) != list(data)
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_truth_manifest(canonical_bytes(reordered))
    # A repeated JSON key parses to its last value, so the bytes name a field twice.
    repeated = sealed.truth_manifest.content.replace(
        b'{"artifact":"truth-manifest.json",',
        b'{"artifact":"x","artifact":"truth-manifest.json",',
        1,
    )
    with pytest.raises(ValueError, match="not its canonical encoding"):
        decode_truth_manifest(repeated)


def test_an_id_of_another_kind_is_refused_naming_the_kind(sealed: Bundle) -> None:
    data = truth_json(sealed)
    data["scenarios"][0]["key"]["scenario_id"] = "emp_001"
    with pytest.raises(ValueError, match="'emp_001' is not a scenario_ id"):
        decode_truth_manifest(canonical_bytes(data))
    data = truth_json(sealed)
    comment = next(
        brief["target"]
        for row in data["scenarios"]
        for brief in row["briefs"]
        if brief["target"]["kind"] == "comment"
    )
    comment["work_item_id"] = comment["author_id"]
    with pytest.raises(ValueError, match="a work_item id has the form ticket_NNN"):
        decode_truth_manifest(canonical_bytes(data))
    data = truth_json(sealed)
    data["scenarios"][0]["key"]["impacts"][0]["must_assess"][0]["employee_id"] = "ticket_001"
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN"):
        decode_truth_manifest(canonical_bytes(data))


def test_what_the_domain_constructors_refuse_does_not_decode(sealed: Bundle) -> None:
    data = truth_json(sealed)
    impacts = data["scenarios"][0]["key"]["impacts"]
    impacts.append(impacts[0])
    with pytest.raises(ValueError, match="impact keys are unique"):
        decode_truth_manifest(canonical_bytes(data))
    data = truth_json(sealed)
    data["materialization"]["targets"].pop()
    with pytest.raises(ValueError, match="the materialization record covers"):
        decode_truth_manifest(canonical_bytes(data))
    data = truth_json(sealed)
    data["scenarios"][0]["key"]["tier"] = "tier_nine"
    with pytest.raises(ValueError, match="'tier_nine' is not a valid Tier"):
        decode_truth_manifest(canonical_bytes(data))
    data = truth_json(sealed)
    data["facts"]["facts"][0]["observable_from"] = "20260101"
    with pytest.raises(ValueError, match="observable_from is spelled '20260101'"):
        decode_truth_manifest(canonical_bytes(data))
