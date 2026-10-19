"""The projection of an evaluation artifact into the public results: aggregates copied as
recorded, from the artifact's written form, and nothing recomputed.

The artifact has an encoder and no decoder (the decoder question is parked with its
triggers), and the artifact a page's figures come from is a file on the workstation,
fetched once under the administrator profile; so this reads the artifact's JSON by the
field names its written form fixes (format 10) and copies each figure the public schema
declares into the public type, by the mapping the demo milestone's first build step wrote
down field by field. A figure is copied, never derived: a count stays the count, a float
the float, an interval's every field the recorded one, an unresolved interval's reason
the reason, a null a null. What the projection leaves out is left out whole (the listing,
the scenario ids, the audit counters, the fact tallies, the world objects' digests and
version ids), and a field the artifact lacks is a ``ValueError`` naming it, never a
default, so a projection of another format fails on its first missing name after the
format check refuses it by number.

The one thing the artifact cannot say of itself is the measurement world's disclosure
mark, which lives in the world spec in the truth bucket; the caller states it, and the
acceptance command reads the sealed mark and holds the committed statement to it. The
artifact's own digest is taken over the bytes given, so the provenance names exactly the
file that was read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import cast

from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
)
from leaveimpact.evaluator.artifact import ARTIFACT_FORMAT_VERSION
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
from leaveimpact.world.disclosure import Disclosure

__all__ = ["project_public_results"]

_Json = Mapping[str, object]


def project_public_results(raw: bytes, *, world_disclosure: Disclosure) -> PublicResults:
    """The public results of the artifact ``raw`` holds, its measurement world sealed under
    ``world_disclosure``. ``ValueError`` for an artifact of another format or one missing
    a field the projection reads."""
    artifact = as_object(json.loads(raw.decode("utf-8")), "the evaluation artifact")
    version = artifact.get("format_version")
    if version != ARTIFACT_FORMAT_VERSION:
        raise ValueError(
            f"the projection reads artifact format {ARTIFACT_FORMAT_VERSION}, got {version!r}"
        )
    analysis = object_field(artifact, "analysis")
    plan = object_field(analysis, "plan")
    return PublicResults(
        format_version=PUBLIC_RESULTS_FORMAT,
        provenance=_provenance(artifact, hashlib.sha256(raw).hexdigest()),
        disclosures=_disclosures(artifact, analysis, plan, world_disclosure),
        plan=_plan(plan),
        arms=tuple(_arm(arm) for arm in _objects(analysis, "arms")),
        primary=_comparison(object_field(analysis, "primary")),
        secondary=tuple(_comparison(c) for c in _objects(analysis, "secondary")),
        level_contrasts=tuple(_level_contrast(c) for c in _objects(analysis, "level_contrasts")),
        descriptive=tuple(_descriptive(d) for d in _objects(analysis, "descriptive")),
        mechanism_pending=optional_string_field(analysis, "mechanism_pending"),
        mechanism=_optional(analysis, "mechanism", _mechanism),
        headroom=tuple(_headroom(h) for h in _objects(analysis, "headroom")),
        not_run=tuple(_not_run(u) for u in _objects(analysis, "unbuilt")),
    )


# --- The parts -----------------------------------------------------------------------------


def _provenance(artifact: _Json, digest: str) -> Provenance:
    evaluator = object_field(artifact, "evaluator")
    registration = object_field(artifact, "registration")
    declared = object_field(registration, "declared")
    inventory = object_field(artifact, "harness_inventory")
    coverage = object_field(artifact, "coverage")
    listed: dict[str, int] = {}
    for entry in _objects(artifact, "listing"):
        disposition = string_field(entry, "disposition")
        listed[disposition] = listed.get(disposition, 0) + 1
    return Provenance(
        artifact_digest=digest,
        artifact_format_version=integer_field(artifact, "format_version"),
        label=string_field(artifact, "label"),
        world_version=string_field(object_field(artifact, "world"), "version"),
        evaluator_commit=string_field(evaluator, "commit"),
        registration_commit=string_field(evaluator, "registration_commit"),
        registration_status=string_field(registration, "status"),
        registration_digest=string_field(registration, "digest"),
        registration_procedure=string_field(registration, "procedure"),
        registration_frozen_commit=optional_string_field(registration, "frozen_commit"),
        registration_amends=optional_string_field(declared, "amends"),
        registration_prior_full_set_results=_bool(declared, "prior_full_set_results"),
        inventory_digest=string_field(inventory, "digest"),
        inventory_attempts=integer_field(inventory, "attempts"),
        inventory_builder_commit=string_field(inventory, "builder_commit"),
        inventory_ledger_id=string_field(inventory, "ledger_id"),
        inventory_taken_at=string_field(inventory, "taken_at"),
        runs_listed=tuple(sorted(listed.items())),
        coverage=Coverage(
            intended=integer_field(coverage, "intended"),
            admitted=integer_field(coverage, "admitted"),
            never_admitted=integer_field(coverage, "never_admitted"),
            admitted_beyond_intended=integer_field(coverage, "admitted_beyond_intended"),
            attempts=integer_field(coverage, "attempts"),
            exported=integer_field(coverage, "exported"),
            open=integer_field(coverage, "open"),
            closed_without_export=integer_field(coverage, "closed_without_export"),
            publication_incidents=integer_field(coverage, "publication_incidents"),
            failed_by_defect=integer_field(coverage, "failed_by_defect"),
            failed_by_infrastructure=integer_field(coverage, "failed_by_infrastructure"),
        ),
    )


def _disclosures(
    artifact: _Json, analysis: _Json, plan: _Json, world_disclosure: Disclosure
) -> Disclosures:
    return Disclosures(
        world_disclosure=world_disclosure.value,
        evaluated_by_changed_code=_bool(artifact, "evaluated_by_changed_code"),
        changed=tuple(
            ChangedPath(
                string_field(c, "path"),
                optional_string_field(c, "before"),
                optional_string_field(c, "after"),
            )
            for c in _objects(object_field(artifact, "evaluator"), "changed")
        ),
        repeats_per_scenario=integer_field(plan, "intended_repeats"),
        incidents=len(array_field(analysis, "incidents")),
        provenance_incidents=len(array_field(analysis, "provenance_incidents")),
    )


def _plan(plan: _Json) -> Plan:
    arms: list[PlanArm] = []
    for item in array_field(plan, "arms"):
        if not isinstance(item, list) or len(cast("list[object]", item)) != 3:
            raise ValueError("a plan arm is [system, condition, level]")
        system, condition, level = cast("list[object]", item)
        system = as_object(system, "a plan arm's system")
        arms.append(
            PlanArm(
                string_field(system, "kind"),
                string_field(system, "variant"),
                _strings(as_object(condition, "a plan arm's condition"), "unreachable"),
                _string(level, "a plan arm's level"),
            )
        )
    return Plan(
        confidence=_float(plan, "confidence"),
        seed=integer_field(plan, "seed"),
        resamples=integer_field(plan, "resamples"),
        intended_repeats=integer_field(plan, "intended_repeats"),
        counted_attempt=string_field(plan, "counted_attempt"),
        missing_repeat=string_field(plan, "missing_repeat"),
        max_attempts=integer_field(plan, "max_attempts"),
        arms=tuple(arms),
    )


def _arm(arm: _Json) -> ResultArm:
    system = object_field(arm, "system")
    return ResultArm(
        system=string_field(system, "kind"),
        variant=string_field(system, "variant"),
        condition=string_field(arm, "condition"),
        level=string_field(arm, "level"),
        reporting=optional_string_field(arm, "reporting"),
        cells=tuple(_cell(cell) for cell in _objects(arm, "cells")),
        consistency=tuple(
            RepeatConsistency(
                check=string_field(row, "check"),
                scenarios=integer_field(row, "scenarios"),
                all_pass=integer_field(row, "all_pass"),
                all_fail=integer_field(row, "all_fail"),
                disagree=integer_field(row, "disagree"),
                incomplete=integer_field(row, "incomplete"),
            )
            for row in _objects(arm, "consistency")
        ),
    )


def _cell(cell: _Json) -> Cell:
    accounting = object_field(cell, "accounting")
    cost = object_field(cell, "cost")
    return Cell(
        stratum=_stratum(cell),
        accounting=CellAccounting(
            scenarios=integer_field(accounting, "scenarios"),
            intended=integer_field(accounting, "intended"),
            made=integer_field(accounting, "made"),
            missing=integer_field(accounting, "missing"),
            surplus=integer_field(accounting, "surplus"),
            attempts=integer_field(accounting, "attempts"),
            graded=integer_field(accounting, "graded"),
            structurally_invalid=integer_field(accounting, "structurally_invalid"),
            limited=_tallies(accounting, "limited"),
            excluded=_tallies(accounting, "excluded"),
        ),
        cost=CellCost(
            runs=integer_field(cost, "runs"),
            attempts=integer_field(cost, "attempts"),
            pico_usd=integer_field(cost, "pico_usd"),
            floors=integer_field(cost, "floors"),
            per_run=_optional(cost, "per_run", _spread),
            duration_ms=_optional(cost, "duration_ms", _spread),
            lower_bound_durations=integer_field(cost, "lower_bound_durations"),
            segments=_optional(cost, "segments", _spread),
        ),
        checks=_optional_rows(cell, "checks", _check_estimate),
        measures=_optional_rows(cell, "measures", _ratio_estimate),
        degraded=_optional_rows(cell, "degraded", _degraded_row),
    )


def _spread(spread: _Json) -> Spread:
    return Spread(
        median=_float(spread, "median"),
        low=integer_field(spread, "low"),
        high=integer_field(spread, "high"),
    )


def _check_estimate(row: _Json) -> CheckEstimate:
    return CheckEstimate(
        check=string_field(row, "check"),
        stratum=_stratum(row),
        reading=string_field(row, "reading"),
        passed=_float(row, "passed"),
        scenarios=integer_field(row, "scenarios"),
        runs=integer_field(row, "runs"),
        not_checked=integer_field(row, "not_checked"),
        missing=integer_field(row, "missing"),
        unverifiable=integer_field(row, "unverifiable"),
        wilson=_optional(row, "wilson", _wilson),
        bootstrap=_optional(row, "bootstrap", _bootstrap),
        unresolved=optional_string_field(row, "unresolved"),
    )


def _ratio_estimate(row: _Json) -> RatioEstimate:
    return RatioEstimate(
        measure=string_field(row, "measure"),
        stratum=_stratum(row),
        numerator=integer_field(row, "numerator"),
        denominator=integer_field(row, "denominator"),
        scenarios=integer_field(row, "scenarios"),
        empty=integer_field(row, "empty"),
        interval=_optional(row, "interval", _bootstrap),
        unresolved=optional_string_field(row, "unresolved"),
    )


def _degraded_row(row: _Json) -> DegradedRow:
    return DegradedRow(
        exposure=string_field(row, "exposure"),
        outcome=string_field(row, "outcome"),
        reason=optional_string_field(row, "reason"),
        report=string_field(row, "report"),
        replay=string_field(row, "replay"),
        runs=integer_field(row, "runs"),
    )


def _wilson(interval: _Json) -> WilsonInterval:
    return WilsonInterval(
        low=_float(interval, "low"),
        high=_float(interval, "high"),
        confidence=_float(interval, "confidence"),
    )


def _bootstrap(interval: _Json) -> BootstrapInterval:
    return BootstrapInterval(
        low=_float(interval, "low"),
        high=_float(interval, "high"),
        confidence=_float(interval, "confidence"),
        seed=integer_field(interval, "seed"),
        resamples=integer_field(interval, "resamples"),
        valid=integer_field(interval, "valid"),
        quantile_rule=string_field(interval, "quantile_rule"),
        stratification=string_field(interval, "stratification"),
    )


def _check_comparison(row: _Json) -> CheckComparison:
    two_by_two = field_of(row, "two_by_two")
    table: tuple[int, int, int, int] | None = None
    if two_by_two is not None:
        cells = [_int(item, "two_by_two") for item in _array(two_by_two, "two_by_two")]
        if len(cells) != 4:
            raise ValueError(f"two_by_two has four cells, got {len(cells)}")
        table = (cells[0], cells[1], cells[2], cells[3])
    return CheckComparison(
        check=string_field(row, "check"),
        first_arm=string_field(row, "first_arm"),
        second_arm=string_field(row, "second_arm"),
        stratum=_stratum(row),
        reading=string_field(row, "reading"),
        paired=integer_field(row, "paired"),
        paired_with_incident=integer_field(row, "paired_with_incident"),
        first=_optional_float(row, "first"),
        second=_optional_float(row, "second"),
        two_by_two=table,
        interval=_optional(row, "interval", _bootstrap),
        unresolved=optional_string_field(row, "unresolved"),
    )


def _ratio_comparison(row: _Json) -> RatioComparison:
    return RatioComparison(
        measure=string_field(row, "measure"),
        first_arm=string_field(row, "first_arm"),
        second_arm=string_field(row, "second_arm"),
        stratum=_stratum(row),
        paired=integer_field(row, "paired"),
        paired_with_incident=integer_field(row, "paired_with_incident"),
        first=_optional_float(row, "first"),
        second=_optional_float(row, "second"),
        interval=_optional(row, "interval", _bootstrap),
        unresolved=optional_string_field(row, "unresolved"),
    )


def _comparison(result: _Json) -> ComparisonResult:
    registered = object_field(result, "registered")
    return ComparisonResult(
        registered=RegisteredComparison(
            check=string_field(registered, "check"),
            reading=string_field(registered, "reading"),
            condition=string_field(registered, "condition"),
            level=string_field(registered, "level"),
            systems=_pair(registered, "systems"),
            breakdowns=_strings(registered, "breakdowns"),
        ),
        overall=_optional(result, "overall", _check_comparison),
        breakdowns=tuple(_check_comparison(b) for b in _objects(result, "breakdowns")),
        unavailable=optional_string_field(result, "unavailable"),
    )


def _level_contrast(result: _Json) -> LevelContrastResult:
    registered = object_field(result, "registered")
    return LevelContrastResult(
        registered=RegisteredLevelContrast(
            system=string_field(registered, "system"),
            check=string_field(registered, "check"),
            reading=string_field(registered, "reading"),
            condition=string_field(registered, "condition"),
            levels=_pair(registered, "levels"),
            breakdowns=_strings(registered, "breakdowns"),
        ),
        overall=_optional(result, "overall", _check_comparison),
        breakdowns=tuple(_check_comparison(b) for b in _objects(result, "breakdowns")),
        unavailable=optional_string_field(result, "unavailable"),
    )


def _descriptive(result: _Json) -> DescriptiveResult:
    return DescriptiveResult(
        systems=_pair(result, "systems"),
        condition=string_field(result, "condition"),
        level=string_field(result, "level"),
        checks=tuple(_check_comparison(c) for c in _objects(result, "checks")),
        measures=tuple(_ratio_comparison(m) for m in _objects(result, "measures")),
        unavailable=optional_string_field(result, "unavailable"),
    )


def _mechanism(mechanism: _Json) -> Mechanism:
    return Mechanism(
        name=string_field(mechanism, "name"),
        stages=_strings(mechanism, "stages"),
        arms=tuple(_mechanism_arm(arm) for arm in _objects(mechanism, "arms")),
        contrasts=tuple(_mechanism_contrast(c) for c in _objects(mechanism, "contrasts")),
    )


def _mechanism_arm(arm: _Json) -> MechanismArm:
    system = object_field(arm, "system")
    return MechanismArm(
        system=string_field(system, "kind"),
        variant=string_field(system, "variant"),
        condition=string_field(arm, "condition"),
        level=string_field(arm, "level"),
        stages=tuple(_ratio_estimate(s) for s in _objects(arm, "stages")),
        by_predicate=tuple(_ratio_estimate(s) for s in _objects(arm, "by_predicate")),
    )


def _mechanism_contrast(contrast: _Json) -> MechanismContrast:
    return MechanismContrast(
        of=string_field(contrast, "of"),
        first=_arm_ref(object_field(contrast, "first")),
        second=_arm_ref(object_field(contrast, "second")),
        stages=tuple(_ratio_comparison(s) for s in _objects(contrast, "stages")),
        unavailable=optional_string_field(contrast, "unavailable"),
    )


def _arm_ref(ref: _Json) -> ArmRef:
    return ArmRef(
        system=string_field(ref, "system"),
        condition=string_field(ref, "condition"),
        level=string_field(ref, "level"),
    )


def _headroom(row: _Json) -> Headroom:
    return Headroom(
        condition=string_field(row, "condition"),
        level=string_field(row, "level"),
        scenarios=_optional_int(row, "scenarios"),
        not_passed=_optional_int(row, "not_passed"),
        unavailable=optional_string_field(row, "unavailable"),
    )


def _not_run(row: _Json) -> NotRun:
    cell = object_field(row, "cell")
    return NotRun(
        system=string_field(cell, "system"),
        condition=string_field(cell, "condition"),
        level=string_field(cell, "level"),
        group=optional_string_field(cell, "group"),
        why=string_field(row, "why"),
        detail=string_field(row, "detail"),
    )


# --- Readers the core's shape helpers do not hold --------------------------------------------


def _stratum(row: _Json) -> Stratum:
    stratum = object_field(row, "stratum")
    return Stratum(string_field(stratum, "kind"), string_field(stratum, "name"))


def _objects(data: _Json, key: str) -> tuple[_Json, ...]:
    return tuple(as_object(item, f"an item of {key}") for item in array_field(data, key))


def _optional[T](data: _Json, key: str, read: Callable[[_Json], T]) -> T | None:
    value = field_of(data, key)
    return None if value is None else read(as_object(value, key))


def _optional_rows[T](data: _Json, key: str, read: Callable[[_Json], T]) -> tuple[T, ...] | None:
    value = field_of(data, key)
    if value is None:
        return None
    return tuple(read(as_object(item, f"an item of {key}")) for item in _array(value, key))


def _array(value: object, key: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{key} is a JSON array, got {type(value).__name__}")
    return cast("list[object]", value)


def _string(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} is a string, got {type(value).__name__}")
    return value


def _int(value: object, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"an item of {what} is an integer, got {type(value).__name__}")
    return value


def _strings(data: _Json, key: str) -> tuple[str, ...]:
    return tuple(_string(item, f"an item of {key}") for item in array_field(data, key))


def _pair(data: _Json, key: str) -> tuple[str, str]:
    items = _strings(data, key)
    if len(items) != 2:
        raise ValueError(f"{key} has two items, got {len(items)}")
    return (items[0], items[1])


def _tallies(data: _Json, key: str) -> tuple[tuple[str, int], ...]:
    rows: list[tuple[str, int]] = []
    for item in array_field(data, key):
        pair = _array(item, key)
        if len(pair) != 2:
            raise ValueError(f"an item of {key} is [name, count], got {len(pair)} items")
        rows.append((_string(pair[0], f"an item of {key}"), _int(pair[1], key)))
    return tuple(rows)


def _bool(data: _Json, key: str) -> bool:
    value = field_of(data, key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} is a boolean, got {type(value).__name__}")
    return value


def _float(data: _Json, key: str) -> float:
    value = _optional_float(data, key)
    if value is None:
        raise ValueError(f"{key} is a number, got null")
    return value


def _optional_float(data: _Json, key: str) -> float | None:
    # A fraction the evaluator declares as a float is written as the number it computed,
    # which is an integer where whole runs were summed (the fixture artifacts' ``passed``
    # arrives as 24 where the reported artifact's is 24.0); the public form writes every
    # fraction as a float, so the value is kept and only its spelling is fixed.
    value = field_of(data, key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} is a number or null, got {type(value).__name__}")
    return float(value)


def _optional_int(data: _Json, key: str) -> int | None:
    value = field_of(data, key)
    return None if value is None else _int(value, key)
