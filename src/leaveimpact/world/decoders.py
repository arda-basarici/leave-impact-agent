"""The sealed artifacts read back: the world spec and the scenario specs from their bytes.

The validator is the first consumer of a sealed file as bytes — the projectors read the
assembled world in memory — so the decoders arrive with it and cover what it reads: the
world spec, into ``PlantedWorldSpec``, and the scenario specs, into the same scenario-spec
records the world assembled. The truth manifest has no decoder here on purpose: this
module is within the validator's reach, so that decoder sits alone in ``truth_decoder``,
which the import law gates by module path to its named readers.

Strict in the manifest decoder's manner: exactly the declared fields, each of its declared
shape, an id of the kind the field names, an enum member by its value, a digest of
SHA-256 shape, the artifact discriminator equal to the file's name — and every semantic
check the domain constructors already make, since a decoded record is built through them.
A file that decodes is one the validator can act on; anything else refuses naming the
field, never a ``KeyError`` from deep inside. Unknown fields are refused too, because a
sealed artifact grows only through this codec, and a field the decoder does not know is a
version the reader does not understand.

Instants come back with their IANA zone when the file carried one; a timestamp whose
offset is not that zone's at that instant is refused rather than converted, and so is any
date or instant spelled other than the way the encoder writes it (``core``'s one rule for
sealed codecs), so the encoding of a decoding reproduces the bytes for every value the
decoder accepts, not only for bytes this project's encoder wrote; a bare offset stays a
bare offset.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from typing import TypeGuard

from leaveimpact.core.entities import CalendarEvent, Document, Leave, WorkItem
from leaveimpact.core.entities_json import (
    decode_component,
    decode_employee,
    decode_event,
    decode_leave,
    decode_team,
    decode_work_item,
)
from leaveimpact.core.entities_json import decode_document as _decode_document_value
from leaveimpact.core.ids import LeaveId, ScenarioId, is_numbered_id, skill_id
from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    string_field,
    string_item,
)
from leaveimpact.core.timeshape import decode_date_span, decode_instant
from leaveimpact.core.worldtime import date_at
from leaveimpact.world.artifacts import (
    SCENARIO_SPECS,
    TRUTH_MANIFEST,
    WORLD_SPEC,
    PlantedWorldSpec,
    ScenarioPlanting,
)
from leaveimpact.world.levels import BASE_LEVELS, SealedLevel
from leaveimpact.world.org import OrgSpec, decode_org_params
from leaveimpact.world.plan import PlanRow
from leaveimpact.world.scenario import (
    ModifierName,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    ScenarioSpec,
    Tier,
)
from leaveimpact.world.version import GeneratorVersion


def decode_world_spec(content: bytes | str) -> PlantedWorldSpec:
    """The planted world ``content`` encodes: the value the world spec file is exactly.

    Scenario ids unique, one plan row and one slice per planting, the plan and the
    plantings in the same order — the record's own invariants, checked as it is built.
    ``filler`` and ``levels`` are present only in a file whose world holds more than the
    base level alone; a file without them was sealed by a generator that built no pool,
    and reads as that world, no pool and the base level.
    """
    data = _artifact(content, WORLD_SPEC, "the world spec")
    present = tuple(name for name in _POOL_FIELDS if name in data)
    expect_fields(
        data,
        ("artifact", "provenance", "org", "plan", "slices", "scenarios", "artifacts")
        + present,
        "the world spec",
    )
    provenance = object_field(data, "provenance")
    expect_fields(
        provenance,
        (
            "seed",
            "world_start",
            "plan_name",
            "generator_version",
            "interpreter",
            "vocabulary_digest",
            "semantic_digest",
        ),
        "provenance",
    )
    cited = object_field(data, "artifacts")
    expect_fields(cited, (SCENARIO_SPECS, TRUTH_MANIFEST), "the cited artifacts")
    return PlantedWorldSpec(
        seed=integer_field(provenance, "seed"),
        world_start=_date(string_field(provenance, "world_start")),
        plan_name=string_field(provenance, "plan_name"),
        generator_version=GeneratorVersion(string_field(provenance, "generator_version")),
        interpreter=_interpreter(provenance),
        vocabulary_digest=string_field(provenance, "vocabulary_digest"),
        semantic_digest=string_field(provenance, "semantic_digest"),
        org=_org(object_field(data, "org")),
        slices=tuple(decode_date_span(item, "a slice") for item in array_field(data, "slices")),
        plan=tuple(_plan_row(item) for item in array_field(data, "plan")),
        scenarios=tuple(_planting(item) for item in array_field(data, "scenarios")),
        scenario_specs_digest=string_field(cited, SCENARIO_SPECS),
        truth_manifest_digest=string_field(cited, TRUTH_MANIFEST),
        filler=tuple(
            _planted(item, _decode_document_value)
            for item in (array_field(data, "filler") if "filler" in data else ())
        ),
        levels=(
            tuple(_level(item) for item in array_field(data, "levels"))
            if "levels" in data
            else BASE_LEVELS
        ),
    )


_POOL_FIELDS = ("filler", "levels")
"""The world spec's names for the pool and its levels, absent from a file without a pool."""


def _level(item: object) -> SealedLevel:
    data = as_object(item, "a level")
    expect_fields(data, ("name", "filler_count"), "a level")
    return SealedLevel(string_field(data, "name"), integer_field(data, "filler_count"))


def decode_scenario_specs(content: bytes | str) -> tuple[ScenarioSpec, ...]:
    """The run inputs ``content`` encodes, one record per scenario, ids unique."""
    data = _artifact(content, SCENARIO_SPECS, "the scenario specs")
    expect_fields(data, ("artifact", "scenarios"), "the scenario specs")
    specs = tuple(_scenario_spec(item) for item in array_field(data, "scenarios"))
    ids = [spec.id for spec in specs]
    if len(set(ids)) != len(ids):
        raise ValueError(f"scenario ids are unique within the scenario specs, got {ids}")
    return specs


def _artifact(content: bytes | str, name: str, what: str) -> Mapping[str, object]:
    data = as_object(json.loads(content), what)
    found = field_of(data, "artifact")
    if found != name:
        raise ValueError(f"{what} is sealed as {name}, got {found!r}")
    return data


# --- Organization and plan --------------------------------------------------------------


def _org(data: Mapping[str, object]) -> OrgSpec:
    expect_fields(
        data,
        ("seed", "params", "generator_version", "teams", "employees", "components", "skills"),
        "the organization",
    )
    return OrgSpec(
        seed=integer_field(data, "seed"),
        params=decode_org_params(object_field(data, "params")),
        generator_version=GeneratorVersion(string_field(data, "generator_version")),
        teams=tuple(decode_team(item) for item in array_field(data, "teams")),
        employees=tuple(decode_employee(item) for item in array_field(data, "employees")),
        components=tuple(decode_component(item) for item in array_field(data, "components")),
        skills=tuple(skill_id(string_item(item, "skills")) for item in array_field(data, "skills")),
    )


def _plan_row(item: object) -> PlanRow:
    data = as_object(item, "a plan row")
    expect_fields(data, ("scenario_id", "tier", "scenario_class", "modifiers"), "a plan row")
    return PlanRow(
        scenario_id=_id_field(data, "scenario_id", "scenario", ScenarioId),
        tier=Tier(string_field(data, "tier")),
        scenario_class=ScenarioClassName(string_field(data, "scenario_class")),
        modifiers=tuple(
            ModifierName(string_item(item, "modifiers")) for item in array_field(data, "modifiers")
        ),
    )


# --- Scenario records ---------------------------------------------------------------------


def _scenario_spec(item: object) -> ScenarioSpec:
    data = as_object(item, "a scenario spec")
    expect_fields(
        data, ("id", "leave_id", "now", "reference_timezone", "window"), "a scenario spec"
    )
    return ScenarioSpec(
        id=_id_field(data, "id", "scenario", ScenarioId),
        leave_id=_id_field(data, "leave_id", "leave", LeaveId),
        now=decode_instant(field_of(data, "now"), "now"),
        reference_timezone=string_field(data, "reference_timezone"),
        window=decode_date_span(field_of(data, "window"), "the window"),
    )


def _planting(item: object) -> ScenarioPlanting:
    data = as_object(item, "a planting")
    expect_fields(data, ("scenario_id", "stable_interval", "owned"), "a planting")
    return ScenarioPlanting(
        scenario_id=_id_field(data, "scenario_id", "scenario", ScenarioId),
        stable_interval=decode_date_span(field_of(data, "stable_interval"), "the stable interval"),
        owned=_owned(object_field(data, "owned")),
    )


def _owned(data: Mapping[str, object]) -> OwnedEntities:
    expect_fields(data, ("leaves", "work_items", "events", "documents"), "owned entities")
    return OwnedEntities(
        leaves=tuple(_planted(item, decode_leave) for item in array_field(data, "leaves")),
        work_items=tuple(
            _planted(item, decode_work_item) for item in array_field(data, "work_items")
        ),
        events=tuple(_planted(item, decode_event) for item in array_field(data, "events")),
        documents=tuple(
            _planted(item, _decode_document_value) for item in array_field(data, "documents")
        ),
    )


def _planted[T: Leave | WorkItem | CalendarEvent | Document](
    item: object, record: Callable[[object], T]
) -> Planted[T]:
    data = as_object(item, "a planted record")
    expect_fields(data, ("record", "observable_from"), "a planted record")
    return Planted(
        entity=record(object_field(data, "record")),
        observable_from=_date(string_field(data, "observable_from")),
    )


def decode_document(content: bytes | str) -> Document:
    """The document one sealed object encodes; ``ValueError`` names what is malformed."""
    return _decode_document_value(json.loads(content))


# --- Ids, time, provenance ----------------------------------------------------------------


def _id[K: str](value: str, prefix: str, kind: Callable[[str], K]) -> K:
    if not is_numbered_id(value) or not value.startswith(f"{prefix}_"):
        raise ValueError(f"{value!r} is not a {prefix}_ id")
    return kind(value)


def _id_field[K: str](
    data: Mapping[str, object], key: str, prefix: str, kind: Callable[[str], K]
) -> K:
    return _id(string_field(data, key), prefix, kind)


def _date(text: str) -> date:
    return date_at(text, "a date")


def _interpreter(data: Mapping[str, object]) -> tuple[int, int]:
    items = array_field(data, "interpreter")
    if len(items) != 2:
        raise ValueError(f"interpreter is a pair of integers, got {items!r}")
    major, minor = items
    if not (_is_integer(major) and _is_integer(minor)):
        raise ValueError(f"interpreter is a pair of integers, got {items!r}")
    return (major, minor)


def _is_integer(value: object) -> TypeGuard[int]:
    # bool is an int in Python; JSON's true is not a version number.
    return isinstance(value, int) and not isinstance(value, bool)
