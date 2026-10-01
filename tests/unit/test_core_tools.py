"""The tool specifications: thirteen in one declared order naming each method once, the
method table the single authority for a tool's source and shape, validation exact with no
coercion and no default, the generated definition closed to unknown properties, and the
surface digest moving on exactly what the model sees."""

import re
from datetime import date
from typing import cast

import pytest

from leaveimpact.core import (
    METHOD_TABLE,
    SEARCH_LIMIT,
    TOOL_SPECIFICATIONS,
    Cardinality,
    DateSpan,
    EntityKind,
    IdArgument,
    InstantSpan,
    IntegerArgument,
    PortMethod,
    QueryArgument,
    Source,
    ToolSpecification,
    specification_named,
    tool_definition,
    tool_surface_digest,
    validate_arguments,
)
from leaveimpact.core.jsonshape import JsonObject


def _named(name: str) -> ToolSpecification:
    specification = specification_named(name)
    assert specification is not None, name
    return specification


SEARCH = _named("search")
LEAVES_WITHIN = _named("leaves_within")
EVENTS_WITHIN = _named("events_within")
EMPLOYEE = _named("employee")
INSTANTS = {
    "start": {"at": "2026-09-16T10:00:00+03:00", "timezone": "Europe/Istanbul"},
    "end": {"at": "2026-09-16T11:00:00+03:00", "timezone": "Europe/Istanbul"},
}


def test_thirteen_specifications_name_each_method_once_in_the_declared_order() -> None:
    assert len(TOOL_SPECIFICATIONS) == 13
    assert [s.method for s in TOOL_SPECIFICATIONS] == list(PortMethod)
    assert len({s.name for s in TOOL_SPECIFICATIONS}) == 13
    assert set(METHOD_TABLE) == set(PortMethod)
    assert specification_named("slack") is None


def test_the_method_table_is_the_one_authority_for_source_and_shape() -> None:
    assert SEARCH.facts.source is Source.CORPUS
    assert SEARCH.facts.entity_kind is EntityKind.DOCUMENT
    assert SEARCH.facts.cardinality is Cardinality.SEQUENCE
    assert EMPLOYEE.facts.cardinality is Cardinality.SINGLE
    by_source = {
        source: {s.name for s in TOOL_SPECIFICATIONS if s.facts.source is source}
        for source in Source
    }
    assert by_source[Source.FRAPPE] == {"employee", "employees", "team", "leave", "leaves_within"}
    assert by_source[Source.JIRA] == {"work_item", "work_items", "component", "components"}
    assert by_source[Source.CALENDAR] == {"event", "events_within"}
    assert by_source[Source.CORPUS] == {"document", "search"}


def test_a_specification_is_well_named_described_and_declares_each_argument_once() -> None:
    with pytest.raises(ValueError, match="lower-case words joined by underscores, got 'Leave'"):
        ToolSpecification("Leave", "a leave", PortMethod.LEAVE, ())
    with pytest.raises(ValueError, match="a tool is described"):
        ToolSpecification("leave", " ", PortMethod.LEAVE, ())
    with pytest.raises(ValueError, match="an argument is declared once"):
        ToolSpecification(
            "leave", "a leave", PortMethod.LEAVE, (IdArgument("id", EntityKind.LEAVE),) * 2
        )
    with pytest.raises(ValueError, match="the bounds are ordered"):
        IntegerArgument("limit", 5, 1)


def test_validation_is_exact_with_no_coercion_and_no_default() -> None:
    assert validate_arguments(SEARCH, {"query": "kafka owner", "limit": 5}) == {
        "query": "kafka owner",
        "limit": 5,
    }
    with pytest.raises(ValueError, match=r"search's arguments has fields .*missing \['limit'\]"):
        validate_arguments(SEARCH, {"query": "kafka"})
    with pytest.raises(ValueError, match=r"surplus \['page'\]"):
        validate_arguments(SEARCH, {"query": "kafka", "limit": 5, "page": 2})
    with pytest.raises(ValueError, match="limit is an integer, got '5'"):
        validate_arguments(SEARCH, {"query": "kafka", "limit": "5"})
    with pytest.raises(ValueError, match="limit is an integer, got True"):
        validate_arguments(SEARCH, {"query": "kafka", "limit": True})
    with pytest.raises(ValueError, match="limit is at most 20, got 21"):
        validate_arguments(SEARCH, {"query": "kafka", "limit": 21})
    with pytest.raises(ValueError, match="limit is at least 1, got 0"):
        validate_arguments(SEARCH, {"query": "kafka", "limit": 0})
    with pytest.raises(ValueError, match="query is non-blank"):
        validate_arguments(SEARCH, {"query": "  ", "limit": 5})
    with pytest.raises(ValueError, match="query is at most 200 characters, got 201"):
        validate_arguments(SEARCH, {"query": "k" * 201, "limit": 5})
    with pytest.raises(ValueError, match="search's arguments is a JSON object, got list"):
        validate_arguments(SEARCH, ["kafka", 5])


def test_ids_are_validated_in_their_kinds_namespace() -> None:
    assert validate_arguments(EMPLOYEE, {"id": "emp_017"}) == {"id": "emp_017"}
    with pytest.raises(ValueError, match="an employee id has the form emp_NNN, got 'ticket_042'"):
        validate_arguments(EMPLOYEE, {"id": "ticket_042"})
    with pytest.raises(ValueError, match="id is a string id, got int"):
        validate_arguments(EMPLOYEE, {"id": 17})


def test_date_spans_are_canonical_ordered_and_bounded() -> None:
    accepted = validate_arguments(
        LEAVES_WITHIN, {"span": {"start": "2026-09-10", "end": "2026-09-19"}}
    )
    assert accepted == {"span": DateSpan(date(2026, 9, 10), date(2026, 9, 19))}
    with pytest.raises(ValueError, match="a date is spelled '20260910'"):
        validate_arguments(LEAVES_WITHIN, {"span": {"start": "20260910", "end": "2026-09-19"}})
    with pytest.raises(ValueError):
        validate_arguments(LEAVES_WITHIN, {"span": {"start": "2026-09-19", "end": "2026-09-10"}})
    with pytest.raises(ValueError, match="span spans at most 366 days, got 367"):
        validate_arguments(LEAVES_WITHIN, {"span": {"start": "2026-01-01", "end": "2027-01-02"}})
    with pytest.raises(ValueError, match=r"span has fields .*surplus \['zone'\]"):
        validate_arguments(
            LEAVES_WITHIN, {"span": {"start": "2026-09-10", "end": "2026-09-19", "zone": "UTC"}}
        )


def test_instant_spans_are_zoned_canonical_and_bounded() -> None:
    accepted = validate_arguments(EVENTS_WITHIN, {"span": INSTANTS})
    assert isinstance(accepted["span"], InstantSpan)
    with pytest.raises(ValueError, match="span.start is spelled '2026-09-16T07:00:00Z'"):
        validate_arguments(
            EVENTS_WITHIN,
            {"span": {**INSTANTS, "start": {"at": "2026-09-16T07:00:00Z", "timezone": None}}},
        )
    late = {"at": "2026-10-20T11:00:00+03:00", "timezone": "Europe/Istanbul"}
    with pytest.raises(ValueError, match="span spans at most 31 days"):
        validate_arguments(EVENTS_WITHIN, {"span": {**INSTANTS, "end": late}})


def test_the_definition_requires_every_argument_and_closes_the_object() -> None:
    definition = tool_definition(SEARCH)
    assert definition["name"] == "search"
    schema = cast(JsonObject, definition["input_schema"])
    assert schema["required"] == ["query", "limit"]
    assert schema["additionalProperties"] is False
    properties = cast(JsonObject, schema["properties"])
    assert properties["limit"] == {"type": "integer", "minimum": 1, "maximum": 20}
    employee_schema = cast(JsonObject, tool_definition(EMPLOYEE)["input_schema"])
    employee_id = cast(JsonObject, cast(JsonObject, employee_schema["properties"])["id"])
    pattern = cast(str, employee_id["pattern"])
    assert re.match(pattern, "emp_017") and not re.match(pattern, "LIA-42")
    employees = cast(JsonObject, tool_definition(_named("employees"))["input_schema"])
    assert employees["required"] == []


def test_the_surface_digest_moves_on_what_the_model_sees_and_on_nothing_else() -> None:
    baseline = tool_surface_digest(TOOL_SPECIFICATIONS)
    assert baseline == tool_surface_digest(tuple(TOOL_SPECIFICATIONS))
    assert len(baseline) == 64
    reordered = TOOL_SPECIFICATIONS[1:] + TOOL_SPECIFICATIONS[:1]
    assert tool_surface_digest(reordered) != baseline
    described = tuple(
        ToolSpecification(s.name, s.description + " Also.", s.method, s.arguments)
        if s is SEARCH
        else s
        for s in TOOL_SPECIFICATIONS
    )
    assert tool_surface_digest(described) != baseline
    narrower = (QueryArgument("query", 200), IntegerArgument("limit", 1, 10))
    bounded = tuple(
        ToolSpecification(s.name, s.description, s.method, narrower) if s is SEARCH else s
        for s in TOOL_SPECIFICATIONS
    )
    assert tool_surface_digest(bounded) != baseline
    assert tool_surface_digest(TOOL_SPECIFICATIONS[:5]) != baseline
    with pytest.raises(ValueError, match="a surface names each tool once"):
        tool_surface_digest((SEARCH, SEARCH))
    assert SEARCH_LIMIT.maximum == 20
