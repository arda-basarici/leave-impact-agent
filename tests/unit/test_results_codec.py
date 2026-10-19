"""The public results' written form: a value round-trips through canonical bytes, and a file
that is not exactly a value of the declared types is refused by the path of the first
thing wrong, so a results page decodes nothing it was not declared to show."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

import pytest

from leaveimpact.core.jsonshape import canonical_bytes
from leaveimpact.results.codec import (
    decode_public_results,
    encode_public_results,
    public_results_bytes,
)
from leaveimpact.results.public import (
    PUBLIC_RESULTS_FORMAT,
    ArmRef,
    BootstrapInterval,
    Cell,
    CellAccounting,
    CellCost,
    ChangedPath,
    CheckComparison,
    CheckEstimate,
    ComparisonResult,
    Coverage,
    DegradedRow,
    DescriptiveResult,
    Disclosures,
    Headroom,
    LevelContrastResult,
    Mechanism,
    MechanismArm,
    MechanismContrast,
    NotRun,
    Plan,
    PlanArm,
    Provenance,
    PublicResults,
    RatioComparison,
    RatioEstimate,
    RegisteredComparison,
    RegisteredLevelContrast,
    RepeatConsistency,
    ResultArm,
    Spread,
    Stratum,
    WilsonInterval,
)

OVERALL = Stratum("overall", "overall")
TIER = Stratum("tier", "structured")
BOOTSTRAP = BootstrapInterval(
    0.2, 0.47, 0.95, 12405586217771241556, 10000, 10000, "linear", "clusters within strata"
)
AGENT = "agent/tool_loop_then_finalization normal at padded"
FULL = "full_context/prefetch_then_level_documents_one_call normal at padded"


def ratio(measure: str, stratum: Stratum = OVERALL) -> RatioEstimate:
    return RatioEstimate(measure, stratum, 884, 986, 30, 0, BOOTSTRAP, None)


def check(stratum: Stratum = OVERALL) -> CheckEstimate:
    return CheckEstimate(
        "correct_whole", stratum, "end_to_end", 24.0, 30, 30, 0, 0, 0,
        WilsonInterval(0.63, 0.90, 0.95), None, None,
    )


def cell(stratum: Stratum) -> Cell:
    return Cell(
        stratum,
        CellAccounting(30, 30, 30, 0, 0, 30, 30, 0, (("cap", 1),), ()),
        CellCost(30, 30, 2212544400000, 0, Spread(69066800000.0, 48505600000, 193970700000),
                 Spread(19893.5, 14077, 34924), 0, Spread(1.0, 1, 1)),
        (check(stratum),),
        (ratio("strict precision: all claims", stratum),),
        None,
    )


def comparison(stratum: Stratum, resolved: bool) -> CheckComparison:
    return CheckComparison(
        "correct_whole", AGENT, FULL, stratum, "end_to_end", 30, 0, 0.8, 0.47,
        (14, 10, 0, 6), BOOTSTRAP if resolved else None,
        None if resolved else "every_resample_equal",
    )


def results() -> PublicResults:
    registered = RegisteredComparison(
        "correct_whole", "end_to_end", "normal", "padded", ("agent", "full_context"), ("tier",)
    )
    return PublicResults(
        format_version=PUBLIC_RESULTS_FORMAT,
        provenance=Provenance(
            "f" * 64, 10, "reported", "2" * 64, "8" * 40, "5" * 40, "bound", "a" * 64,
            "5" * 64, "3" * 40, None, False, "6" * 64, 248, "8" * 40, "ledger-development",
            "2026-10-17T18:36:08.215618+00:00", (("eligible", 240),),
            Coverage(240, 240, 0, 0, 240, 240, 0, 0, 0, 0, 0),
        ),
        disclosures=Disclosures(
            "embargoed", True,
            (ChangedPath("src/leaveimpact/evaluator/cells.py", "0" * 40, "c" * 40),),
            1, 0, 0,
        ),
        plan=Plan(
            0.95, 20261003, 10000, 1, "earliest_not_infrastructure", "not_passed", 3,
            (PlanArm("agent", "tool_loop_then_finalization", (), "padded"),),
        ),
        arms=(
            ResultArm("agent", "tool_loop_then_finalization", "normal", "padded",
                      "answer_quality", (cell(OVERALL), cell(TIER)),
                      (RepeatConsistency("correct_whole", 30, 30, 0, 0, 0),)),
            ResultArm("rules_only", "reference", "corpus_down", "base", "degraded_condition",
                      (Cell(OVERALL, CellAccounting(30, 30, 30, 0, 0, 30, 0, 0, (), ()),
                            CellCost(30, 30, 0, 0, None, None, 0, None), None, None,
                            (DegradedRow("every_source", "limited", "cap", "complete",
                                         "replayed", 30),)),),
                      ()),
        ),
        primary=ComparisonResult(
            registered, comparison(OVERALL, True), (comparison(TIER, False),), None
        ),
        secondary=(ComparisonResult(registered, None, (), "an arm of the pair was not built"),),
        level_contrasts=(
            LevelContrastResult(
                RegisteredLevelContrast(
                    "agent", "correct_whole", "end_to_end", "normal", ("padded", "base"), ("tier",)
                ),
                comparison(OVERALL, False), (), None,
            ),
        ),
        descriptive=(
            DescriptiveResult(
                ("agent", "full_context"), "normal", "padded", (comparison(OVERALL, True),),
                (RatioComparison("recall: all claims", AGENT, FULL, OVERALL, 30, 0, 0.9, 1.0,
                                 None, "every_resample_equal"),),
                None,
            ),
        ),
        mechanism_pending=None,
        mechanism=Mechanism(
            "needed_prose_facts", ("returned", "emitted"),
            (MechanismArm("agent", "tool_loop_then_finalization", "normal", "padded",
                          (ratio("needed prose facts returned: all predicates"),),
                          (ratio("needed prose facts returned: has_skill"),)),),
            (MechanismContrast(
                "primary", ArmRef("agent", "normal", "padded"),
                ArmRef("full_context", "normal", "padded"),
                (RatioComparison("needed prose facts returned: all predicates", AGENT, FULL,
                                 OVERALL, 30, 0, 1.0, 1.0, None, "every_resample_equal"),),
                None,
            ),),
        ),
        headroom=(Headroom("normal", "padded", 30, 20, None),),
        not_run=(NotRun("full_context", "jira_down", "base", "full_context_under_outage",
                        "group_not_run", "full_context_under_outage"),),
    )


def test_a_value_round_trips_and_has_one_written_form() -> None:
    value = results()
    written = public_results_bytes(value)
    assert decode_public_results(written) == value
    assert public_results_bytes(decode_public_results(written)) == written
    assert written == public_results_bytes(replace(value))
    assert written == canonical_bytes(json.loads(written))


def written() -> dict[str, object]:
    return cast(dict[str, object], json.loads(public_results_bytes(results())))


def refused(data: dict[str, object]) -> str:
    with pytest.raises(ValueError) as caught:
        decode_public_results(json.dumps(data))
    return str(caught.value)


def test_another_format_is_refused_first() -> None:
    data = written()
    data["format_version"] = PUBLIC_RESULTS_FORMAT + 1
    assert f"format {PUBLIC_RESULTS_FORMAT}, got {PUBLIC_RESULTS_FORMAT + 1}" in refused(data)


def test_a_surplus_or_missing_field_is_refused_by_its_path() -> None:
    data = written()
    cast(dict[str, object], data["provenance"])["world_seed"] = 7
    message = refused(data)
    assert "the public results.provenance" in message and "surplus ['world_seed']" in message
    data = written()
    del cast(dict[str, object], data["plan"])["seed"]
    assert "missing ['seed']" in refused(data)


def test_a_count_takes_no_boolean_and_no_null_and_a_fraction_takes_no_integer() -> None:
    data = written()
    cast(dict[str, object], data["plan"])["resamples"] = True
    assert "the public results.plan.resamples is an integer, got bool" in refused(data)
    data = written()
    cast(dict[str, object], data["plan"])["resamples"] = None
    assert "the public results.plan.resamples is an integer, got NoneType" in refused(data)
    data = written()
    cast(dict[str, object], data["plan"])["confidence"] = 1
    assert "the public results.plan.confidence is a number with a fraction" in refused(data)


def test_a_fixed_width_array_keeps_its_width_and_an_optional_takes_null() -> None:
    data = written()
    primary = cast(dict[str, object], data["primary"])
    overall = cast(dict[str, object], primary["overall"])
    overall["two_by_two"] = [14, 10, 0]
    assert "the public results.primary.overall.two_by_two has 4 items, got 3" in refused(data)
    overall["two_by_two"] = None
    decoded = decode_public_results(json.dumps(data))
    assert decoded.primary.overall is not None and decoded.primary.overall.two_by_two is None


def test_a_number_that_is_not_finite_is_refused_on_both_sides() -> None:
    value = results()
    broken = replace(value, plan=replace(value.plan, confidence=float("nan")))
    with pytest.raises(ValueError, match="finite"):
        encode_public_results(broken)
    data = written()
    cast(dict[str, object], data["plan"])["confidence"] = float("inf")
    assert "the public results.plan.confidence is finite" in refused(data)
