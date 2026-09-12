"""The sealed artifacts read back: the world spec and the scenario specs from their bytes.

The validator is the first consumer of a sealed file as bytes — the projectors read the
assembled world in memory — so the decoders arrive with it and cover what it reads: the
world spec, into ``PlantedWorldSpec``, and the scenario specs, into the same scenario-spec
records the world assembled. The truth manifest has no decoder here on purpose; its first
consumer is the evaluator, and a decoder the validator is forbidden to use would be one
the import law could not keep out of its reach.

Strict in the manifest decoder's manner: exactly the declared fields, each of its declared
shape, an id of the kind the field names, an enum member by its value, a digest of
SHA-256 shape, the artifact discriminator equal to the file's name — and every semantic
check the domain constructors already make, since a decoded record is built through them.
A file that decodes is one the validator can act on; anything else refuses naming the
field, never a ``KeyError`` from deep inside. Unknown fields are refused too, because a
sealed artifact grows only through this codec, and a field the decoder does not know is a
version the reader does not understand.

Instants come back with their IANA zone when the file carried one, so the encoding of a
decoding reproduces the sealed bytes; a bare offset stays a bare offset.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import TypeGuard
from zoneinfo import ZoneInfo

from leaveimpact.core.entities import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    DocumentSection,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import (
    DocumentKind,
    EmploymentType,
    Grade,
    LeaveKind,
    LeaveStatus,
    WorkItemStatus,
)
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    ScenarioId,
    SkillId,
    TeamId,
    WorkItemId,
    is_numbered_id,
    skill_id,
)
from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.world.artifacts import (
    SCENARIO_SPECS,
    TRUTH_MANIFEST,
    WORLD_SPEC,
    PlantedWorldSpec,
    ScenarioPlanting,
)
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
    """
    data = _artifact(content, WORLD_SPEC, "the world spec")
    expect_fields(
        data,
        ("artifact", "provenance", "org", "plan", "slices", "scenarios", "artifacts"),
        "the world spec",
    )
    provenance = object_field(data, "provenance")
    expect_fields(
        provenance,
        ("seed", "world_start", "generator_version", "interpreter", "vocabulary_digest"),
        "provenance",
    )
    cited = object_field(data, "artifacts")
    expect_fields(cited, (SCENARIO_SPECS, TRUTH_MANIFEST), "the cited artifacts")
    return PlantedWorldSpec(
        seed=integer_field(provenance, "seed"),
        world_start=_date(string_field(provenance, "world_start")),
        generator_version=GeneratorVersion(string_field(provenance, "generator_version")),
        interpreter=_interpreter(provenance),
        vocabulary_digest=string_field(provenance, "vocabulary_digest"),
        org=_org(object_field(data, "org")),
        slices=tuple(_span(item, "a slice") for item in array_field(data, "slices")),
        plan=tuple(_plan_row(item) for item in array_field(data, "plan")),
        scenarios=tuple(_planting(item) for item in array_field(data, "scenarios")),
        scenario_specs_digest=string_field(cited, SCENARIO_SPECS),
        truth_manifest_digest=string_field(cited, TRUTH_MANIFEST),
    )


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
        teams=tuple(_team(item) for item in array_field(data, "teams")),
        employees=tuple(_employee(item) for item in array_field(data, "employees")),
        components=tuple(_component(item) for item in array_field(data, "components")),
        skills=tuple(skill_id(string_item(item, "skills")) for item in array_field(data, "skills")),
    )


def _team(item: object) -> Team:
    data = as_object(item, "a team")
    expect_fields(data, ("id", "name"), "a team")
    return Team(id=_id_field(data, "id", "team", TeamId), name=string_field(data, "name"))


def _employee(item: object) -> Employee:
    data = as_object(item, "an employee")
    expect_fields(
        data,
        (
            "id",
            "name",
            "team_id",
            "manager_id",
            "skills",
            "location",
            "country",
            "timezone",
            "grade",
            "employment_type",
        ),
        "an employee",
    )
    manager = optional_string_field(data, "manager_id")
    skills = field_of(data, "skills")
    return Employee(
        id=_id_field(data, "id", "emp", EmployeeId),
        name=string_field(data, "name"),
        team_id=_id_field(data, "team_id", "team", TeamId),
        manager_id=None if manager is None else _id(manager, "emp", EmployeeId),
        skills=None if skills is None else tuple(_skills(data)),
        location=string_field(data, "location"),
        country=string_field(data, "country"),
        timezone=string_field(data, "timezone"),
        grade=Grade(string_field(data, "grade")),
        employment_type=EmploymentType(string_field(data, "employment_type")),
    )


def _skills(data: Mapping[str, object]) -> list[SkillId]:
    return [skill_id(string_item(item, "skills")) for item in array_field(data, "skills")]


def _component(item: object) -> Component:
    data = as_object(item, "a component")
    expect_fields(data, ("id", "name", "member_ids"), "a component")
    return Component(
        id=_id_field(data, "id", "comp", ComponentId),
        name=string_field(data, "name"),
        member_ids=_ids(data, "member_ids", "emp", EmployeeId),
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
        now=_instant(field_of(data, "now"), "now"),
        reference_timezone=string_field(data, "reference_timezone"),
        window=_span(field_of(data, "window"), "the window"),
    )


def _planting(item: object) -> ScenarioPlanting:
    data = as_object(item, "a planting")
    expect_fields(data, ("scenario_id", "stable_interval", "owned"), "a planting")
    return ScenarioPlanting(
        scenario_id=_id_field(data, "scenario_id", "scenario", ScenarioId),
        stable_interval=_span(field_of(data, "stable_interval"), "the stable interval"),
        owned=_owned(object_field(data, "owned")),
    )


def _owned(data: Mapping[str, object]) -> OwnedEntities:
    expect_fields(data, ("leaves", "work_items", "events", "documents"), "owned entities")
    return OwnedEntities(
        leaves=tuple(_planted(item, _leave) for item in array_field(data, "leaves")),
        work_items=tuple(_planted(item, _work_item) for item in array_field(data, "work_items")),
        events=tuple(_planted(item, _event) for item in array_field(data, "events")),
        documents=tuple(_planted(item, _document) for item in array_field(data, "documents")),
    )


def _planted[T: Leave | WorkItem | CalendarEvent | Document](
    item: object, record: Callable[[Mapping[str, object]], T]
) -> Planted[T]:
    data = as_object(item, "a planted record")
    expect_fields(data, ("record", "observable_from"), "a planted record")
    return Planted(
        entity=record(object_field(data, "record")),
        observable_from=_date(string_field(data, "observable_from")),
    )


# --- Planted records ----------------------------------------------------------------------


def _leave(data: Mapping[str, object]) -> Leave:
    expect_fields(data, ("id", "employee_id", "start", "end", "kind", "status"), "a leave")
    return Leave(
        id=_id_field(data, "id", "leave", LeaveId),
        employee_id=_id_field(data, "employee_id", "emp", EmployeeId),
        start=_date(string_field(data, "start")),
        end=_date(string_field(data, "end")),
        kind=LeaveKind(string_field(data, "kind")),
        status=LeaveStatus(string_field(data, "status")),
    )


def _work_item(data: Mapping[str, object]) -> WorkItem:
    expect_fields(
        data,
        (
            "id",
            "title",
            "owner_id",
            "status",
            "component_id",
            "opened_on",
            "resolved_on",
            "due_on",
            "comments",
        ),
        "a work item",
    )
    return WorkItem(
        id=_id_field(data, "id", "ticket", WorkItemId),
        title=string_field(data, "title"),
        owner_id=_id_field(data, "owner_id", "emp", EmployeeId),
        status=WorkItemStatus(string_field(data, "status")),
        component_id=_id_field(data, "component_id", "comp", ComponentId),
        opened_on=_date(string_field(data, "opened_on")),
        resolved_on=_optional_date(data, "resolved_on"),
        due_on=_optional_date(data, "due_on"),
        comments=tuple(_comment(item) for item in array_field(data, "comments")),
    )


def _comment(item: object) -> Comment:
    data = as_object(item, "a comment")
    expect_fields(data, ("id", "world_date", "author_id", "text"), "a comment")
    return Comment(
        id=_id_field(data, "id", "comment", CommentId),
        world_date=_date(string_field(data, "world_date")),
        author_id=_id_field(data, "author_id", "emp", EmployeeId),
        text=string_field(data, "text"),
    )


def _event(data: Mapping[str, object]) -> CalendarEvent:
    expect_fields(data, ("id", "title", "start", "end", "attendee_ids"), "an event")
    return CalendarEvent(
        id=_id_field(data, "id", "event", EventId),
        title=string_field(data, "title"),
        start=_instant(field_of(data, "start"), "start"),
        end=_instant(field_of(data, "end"), "end"),
        attendee_ids=_ids(data, "attendee_ids", "emp", EmployeeId),
    )


def _document(data: Mapping[str, object]) -> Document:
    expect_fields(data, ("id", "title", "kind", "effective_from", "sections"), "a document")
    return Document(
        id=_id_field(data, "id", "doc", DocumentId),
        title=string_field(data, "title"),
        kind=DocumentKind(string_field(data, "kind")),
        effective_from=_date(string_field(data, "effective_from")),
        sections=tuple(_section(item) for item in array_field(data, "sections")),
    )


def _section(item: object) -> DocumentSection:
    data = as_object(item, "a section")
    expect_fields(data, ("id", "text"), "a section")
    return DocumentSection(
        id=_id_field(data, "id", "clause", ClauseId), text=string_field(data, "text")
    )


# --- Ids, time, provenance ----------------------------------------------------------------


def _id[K: str](value: str, prefix: str, kind: Callable[[str], K]) -> K:
    if not is_numbered_id(value) or not value.startswith(f"{prefix}_"):
        raise ValueError(f"{value!r} is not a {prefix}_ id")
    return kind(value)


def _id_field[K: str](
    data: Mapping[str, object], key: str, prefix: str, kind: Callable[[str], K]
) -> K:
    return _id(string_field(data, key), prefix, kind)


def _ids[K: str](
    data: Mapping[str, object], key: str, prefix: str, kind: Callable[[str], K]
) -> tuple[K, ...]:
    return tuple(_id(string_item(item, key), prefix, kind) for item in array_field(data, key))


def _date(text: str) -> date:
    return date.fromisoformat(text)


def _optional_date(data: Mapping[str, object], key: str) -> date | None:
    text = optional_string_field(data, key)
    return None if text is None else _date(text)


def _span(item: object, what: str) -> DateSpan:
    data = as_object(item, what)
    expect_fields(data, ("start", "end"), what)
    return DateSpan(_date(string_field(data, "start")), _date(string_field(data, "end")))


def _instant(item: object, what: str) -> datetime:
    """An aware instant, in its IANA zone when the file names one, else at its offset."""
    data = as_object(item, what)
    expect_fields(data, ("at", "timezone"), what)
    instant = datetime.fromisoformat(string_field(data, "at"))
    if instant.tzinfo is None:
        raise ValueError(f"{what} carries its offset, got {data['at']!r}")
    zone = optional_string_field(data, "timezone")
    return instant if zone is None else instant.astimezone(ZoneInfo(zone))


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
