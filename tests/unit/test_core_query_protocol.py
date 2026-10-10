"""The single-shot query protocol: a literal renders as written; a template's parts render over
the prefetch's records for the leaver the leave names and join with the web-search
grammar's ``or``, blank parts dropped, the fallback sent when nothing rendered; a rendering
is clipped at the search argument's maximum on a word boundary; the codec round-trips both
shapes and refuses every other; the texts are held to the search argument's bounds at
construction."""

from datetime import date

import pytest

from leaveimpact.core import (
    JOIN,
    QUERY_MAX_LENGTH,
    Component,
    Employee,
    EmploymentType,
    Entity,
    Grade,
    Leave,
    LeaveKind,
    LeaveStatus,
    LiteralQuery,
    Observed,
    QueryInput,
    Source,
    TemplateQuery,
    WorkItem,
    WorkItemStatus,
    clip_query,
    decode_query_protocol,
    encode_query_protocol,
    input_values,
    render_query,
)
from leaveimpact.core.ids import (
    EmployeeId,
    component_id,
    employee_id,
    leave_id,
    team_id,
    work_item_id,
)

LEAVER = employee_id(1)
OTHER = employee_id(2)
LEAVE = Leave(
    leave_id(1), LEAVER, date(2026, 9, 7), date(2026, 9, 11), LeaveKind.ANNUAL, LeaveStatus.APPROVED
)


def _employee(id: EmployeeId, name: str) -> Observed[Entity]:
    return Observed(
        Employee(
            id=id,
            name=name,
            team_id=team_id(1),
            manager_id=None,
            skills=None,
            location="Istanbul",
            country="TR",
            timezone="Europe/Istanbul",
            grade=Grade.SENIOR,
            employment_type=EmploymentType.EMPLOYEE,
        ),
        Source.FRAPPE,
    )


def _component(number: int, name: str) -> Observed[Entity]:
    return Observed(Component(component_id(number), name, (LEAVER,)), Source.JIRA)


def _item(number: int, title: str, owner: EmployeeId, component: int) -> Observed[Entity]:
    return Observed(
        WorkItem(
            work_item_id(number),
            title,
            owner,
            WorkItemStatus.IN_PROGRESS,
            component_id(component),
            date(2026, 8, 1),
            None,
            None,
            (),
        ),
        Source.JIRA,
    )


RETURNED: tuple[Observed[Entity], ...] = (
    _employee(LEAVER, "Deniz Kaya"),
    _employee(OTHER, "Can Demir"),
    _component(1, "Kafka ingest"),
    _component(2, "Billing"),
    _component(3, "Mobile"),
    _item(1, "Rotate the Kafka certificates", LEAVER, 1),
    _item(2, "Invoice export", LEAVER, 2),
    _item(3, "Mobile  release   notes", OTHER, 3),
    _item(4, "Rotate the Kafka certificates", LEAVER, 1),
)


def test_a_literal_renders_as_written_whatever_was_read() -> None:
    assert render_query(LiteralQuery("handover or coverage"), RETURNED, LEAVE) == (
        "handover or coverage"
    )
    assert render_query(LiteralQuery("handover or coverage"), (), LEAVE) == "handover or coverage"


def test_inputs_are_read_from_the_leavers_records_distinct_and_in_returned_order() -> None:
    assert input_values(QueryInput.LEAVER_NAME, RETURNED, LEAVE) == ("Deniz Kaya",)
    assert input_values(QueryInput.COMPONENT_NAMES, RETURNED, LEAVE) == ("Kafka ingest", "Billing")
    assert input_values(QueryInput.WORK_ITEM_TITLES, RETURNED, LEAVE) == (
        "Rotate the Kafka certificates",
        "Invoice export",
    )
    # Another employee's items contribute nothing, and a leaver the reads never returned
    # has no name.
    assert input_values(QueryInput.LEAVER_NAME, RETURNED[2:], LEAVE) == ()


def test_a_template_joins_its_parts_with_or_and_drops_blank_ones() -> None:
    template = TemplateQuery(
        (QueryInput.COMPONENT_NAMES, "handover", QueryInput.LEAVER_NAME), "handover or coverage"
    )
    assert render_query(template, RETURNED, LEAVE) == JOIN.join(
        ("Kafka ingest", "Billing", "handover", "Deniz Kaya")
    )
    # No components returned: the part renders blank and is dropped, the rest stands.
    without_components = tuple(r for r in RETURNED if not isinstance(r.value, Component))
    assert render_query(template, without_components, LEAVE) == "handover or Deniz Kaya"


def test_a_template_that_renders_blank_sends_its_fallback() -> None:
    template = TemplateQuery((QueryInput.WORK_ITEM_TITLES,), "handover or coverage")
    assert render_query(template, (), LEAVE) == "handover or coverage"
    assert render_query(template, RETURNED, LEAVE) == (
        "Rotate the Kafka certificates or Invoice export"
    )


def test_a_rendering_is_clipped_at_the_arguments_maximum_on_a_word_boundary() -> None:
    long_titles = tuple(
        _item(10 + n, f"Title number {n} of the long backlog", LEAVER, 1) for n in range(20)
    )
    rendered = render_query(
        TemplateQuery((QueryInput.WORK_ITEM_TITLES,), "handover"), (*RETURNED, *long_titles), LEAVE
    )
    assert len(rendered) <= QUERY_MAX_LENGTH
    assert not rendered.endswith(" or") and not rendered.endswith(" ")
    assert rendered.startswith("Rotate the Kafka certificates or Invoice export or Title number")
    assert clip_query("x" * (QUERY_MAX_LENGTH + 5)) == "x" * QUERY_MAX_LENGTH
    assert clip_query("a or " + "b" * QUERY_MAX_LENGTH) == "a"


def test_the_codec_round_trips_both_shapes_and_refuses_every_other() -> None:
    literal = LiteralQuery("handover or coverage")
    template = TemplateQuery((QueryInput.COMPONENT_NAMES, "handover"), "handover or coverage")
    assert decode_query_protocol(encode_query_protocol(literal)) == literal
    assert decode_query_protocol(encode_query_protocol(template)) == template
    assert encode_query_protocol(template) == {
        "kind": "template",
        "parts": [{"input": "component_names"}, {"text": "handover"}],
        "fallback": "handover or coverage",
    }
    with pytest.raises(ValueError, match="kind is literal or template"):
        decode_query_protocol({"kind": "regex", "text": "x"})
    with pytest.raises(ValueError, match="a template part is one of input or text"):
        decode_query_protocol({"kind": "template", "parts": [{"both": 1}], "fallback": "x"})
    with pytest.raises(ValueError):
        decode_query_protocol(
            {"kind": "template", "parts": [{"input": "team_name"}], "fallback": "x"}
        )
    with pytest.raises(ValueError):
        decode_query_protocol({"kind": "literal", "text": "x", "extra": 1})


def test_texts_are_held_to_the_search_arguments_bounds_at_construction() -> None:
    with pytest.raises(ValueError, match="a literal query is non-blank"):
        LiteralQuery("  ")
    with pytest.raises(ValueError, match=f"at most {QUERY_MAX_LENGTH} characters"):
        LiteralQuery("k" * (QUERY_MAX_LENGTH + 1))
    with pytest.raises(ValueError, match="one form"):
        LiteralQuery(" handover")
    with pytest.raises(ValueError, match="at least one part"):
        TemplateQuery((), "handover")
    with pytest.raises(ValueError, match="names at least one input"):
        TemplateQuery(("handover",), "coverage")
    with pytest.raises(ValueError, match="a template's fallback is non-blank"):
        TemplateQuery((QueryInput.LEAVER_NAME,), "")
