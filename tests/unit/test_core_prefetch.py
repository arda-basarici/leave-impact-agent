"""The frozen prefetch plans a leave as six calls in one order with the leave's exact span, every
call accepted by its tool's own validation; a span past a tool's bound is chunked by that
bound, days inclusive and disjoint, instants half-open and adjacent by elapsed time, so a
clock change never yields a chunk the validator refuses; and the rule's digest moves with the
protocol version, the steps and the named tools' contracts, and with nothing else."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core import (
    PREFETCH_IDENTIFIER,
    PREFETCH_PROTOCOL,
    PREFETCH_STEPS,
    TOOL_SPECIFICATIONS,
    ArgumentSource,
    DateSpan,
    InstantSpan,
    Leave,
    LeaveKind,
    LeaveStatus,
    PlannedCall,
    PortMethod,
    PrefetchStep,
    RunContext,
    ToolSpecification,
    calls_after_leave,
    day_chunks,
    instant_chunks,
    opening_call,
    prefetch_digest,
    prefetch_rule,
    specification_named,
    tools,
    validate_arguments,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, employee_id, leave_id
from leaveimpact.core.tools import DateSpanArgument, InstantSpanArgument

ISTANBUL = "Europe/Istanbul"
BERLIN = "Europe/Berlin"
CONTEXT = RunContext(
    ScenarioId("scenario_003"),
    WorldVersion("4f2c"),
    LeaveId("leave_005"),
    datetime(2026, 9, 14, 22, 30, tzinfo=UTC),
    ISTANBUL,
)


def leave(start: date, end: date) -> Leave:
    return Leave(leave_id(5), employee_id(17), start, end, LeaveKind.ANNUAL, LeaveStatus.APPROVED)


def bound_of(tool: str) -> int:
    specification = specification_named(tool)
    assert specification is not None
    (argument,) = specification.arguments
    assert isinstance(argument, DateSpanArgument | InstantSpanArgument)
    return argument.max_days


def accepted(call: PlannedCall) -> dict[str, object]:
    """``call``'s arguments as its tool's validation accepts them."""
    specification = specification_named(call.tool)
    assert specification is not None
    return dict(validate_arguments(specification, call.arguments))


def accepted_days(call: PlannedCall) -> DateSpan:
    span = accepted(call)["span"]
    assert isinstance(span, DateSpan)
    return span


def accepted_instants(call: PlannedCall) -> InstantSpan:
    span = accepted(call)["span"]
    assert isinstance(span, InstantSpan)
    return span


# --- The plan for a leave ----------------------------------------------------------------------


def test_the_plan_opens_with_the_contexts_leave_and_goes_on_with_five_calls_in_order() -> None:
    first = opening_call(CONTEXT)
    assert (first.step, first.tool) == (0, "leave")
    assert accepted(first) == {"id": "leave_005"}
    span = DateSpan(date(2026, 9, 14), date(2026, 9, 17))
    rest = calls_after_leave(leave(span.start, span.end), ISTANBUL)
    assert [(call.step, call.tool) for call in rest] == [
        (1, "employees"),
        (2, "leaves_within"),
        (3, "components"),
        (4, "work_items"),
        (5, "events_within"),
    ]
    assert [step.tool for step in PREFETCH_STEPS] == ["leave", *(call.tool for call in rest)]


def test_the_windowed_calls_carry_the_leaves_exact_span_and_validate_unchanged() -> None:
    span = DateSpan(date(2026, 9, 14), date(2026, 9, 17))
    rest = calls_after_leave(leave(span.start, span.end), ISTANBUL)
    by_tool = {call.tool: call for call in rest}
    assert accepted(by_tool["leaves_within"]) == {"span": span}
    assert accepted(by_tool["events_within"]) == {"span": span.instants_in(ISTANBUL)}
    assert accepted(by_tool["employees"]) == {}
    for call in rest:
        accepted(call)


def test_a_short_leave_is_one_call_per_step() -> None:
    rest = calls_after_leave(leave(date(2026, 9, 14), date(2026, 9, 15)), ISTANBUL)
    assert len(rest) == len(PREFETCH_STEPS) - 1


# --- Chunking by the tool's own bound ------------------------------------------------------------


def test_a_long_leave_is_chunked_by_each_tools_bound_and_every_chunk_validates() -> None:
    long = leave(date(2026, 1, 1), date(2027, 2, 10))  # 406 days
    rest = calls_after_leave(long, ISTANBUL)
    days = [accepted_days(call) for call in rest if call.tool == "leaves_within"]
    instants = [accepted_instants(call) for call in rest if call.tool == "events_within"]
    assert len(days) == 2 and len(instants) == 14
    assert all(call.step == 2 for call in rest if call.tool == "leaves_within")
    assert days[0].start == long.start and days[-1].end == long.end
    for earlier, later in zip(days, days[1:], strict=False):
        assert later.start == earlier.end + timedelta(days=1)
    whole = long.span.instants_in(ISTANBUL)
    assert instants[0].start == whole.start and instants[-1].end == whole.end
    for earlier, later in zip(instants, instants[1:], strict=False):
        assert later.start == earlier.end


def test_day_chunks_are_inclusive_disjoint_and_cover_the_span() -> None:
    span = DateSpan(date(2026, 1, 1), date(2026, 1, 10))
    chunks = day_chunks(span, 4)
    assert [(c.start.day, c.end.day) for c in chunks] == [(1, 4), (5, 8), (9, 10)]
    assert sum(c.days for c in chunks) == span.days
    assert day_chunks(span, 10) == (span,)
    assert day_chunks(span, 366) == (span,)


def test_instant_chunks_across_a_clock_change_are_cut_by_elapsed_time() -> None:
    # Berlin falls back on 2026-10-25: thirty-one wall-clock days across it are thirty-one
    # days and one hour of elapsed time, which the validator refuses.
    span = DateSpan(date(2026, 10, 1), date(2026, 11, 9)).instants_in(BERLIN)
    wall = InstantSpan(span.start, span.start + timedelta(days=31))
    assert wall.duration == timedelta(days=31, hours=1)
    specification = specification_named("events_within")
    assert specification is not None
    with pytest.raises(ValueError, match="at most 31 days"):
        validate_arguments(
            specification, {"span": {"start": _enc(wall.start), "end": _enc(wall.end)}}
        )
    chunks = instant_chunks(span, 31)
    assert len(chunks) == 2
    assert chunks[0].duration == timedelta(days=31)
    assert chunks[0].end.tzinfo == ZoneInfo(BERLIN)
    assert chunks[1].start == chunks[0].end and chunks[1].end == span.end
    assert chunks[0].start == span.start
    for chunk in chunks:
        validate_arguments(
            specification, {"span": {"start": _enc(chunk.start), "end": _enc(chunk.end)}}
        )


def test_a_leave_across_the_clock_change_plans_calls_the_validator_accepts() -> None:
    rest = calls_after_leave(leave(date(2026, 10, 1), date(2026, 11, 9)), BERLIN)
    events = [accepted_instants(call) for call in rest if call.tool == "events_within"]
    assert len(events) == 2
    assert (
        events[0].start == DateSpan(date(2026, 10, 1), date(2026, 11, 9)).instants_in(BERLIN).start
    )
    assert events[1].end == DateSpan(date(2026, 10, 1), date(2026, 11, 9)).instants_in(BERLIN).end


def _enc(instant: datetime) -> dict[str, object]:
    from leaveimpact.core.timeshape import encode_instant

    return encode_instant(instant)


# --- The digest --------------------------------------------------------------------------------


def test_the_rule_is_the_identifier_and_a_stable_digest() -> None:
    rule = prefetch_rule()
    assert rule.identifier == PREFETCH_IDENTIFIER
    assert rule == prefetch_rule()
    assert rule.digest == prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)


def test_the_digest_moves_with_the_protocol_the_steps_and_the_named_tools_contracts() -> None:
    base = prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    moved = {
        "protocol version": prefetch_digest(
            (PREFETCH_PROTOCOL[0], 2), PREFETCH_STEPS, TOOL_SPECIFICATIONS
        ),
        "a step reordered": prefetch_digest(
            PREFETCH_PROTOCOL,
            (PREFETCH_STEPS[0], *PREFETCH_STEPS[2:], PREFETCH_STEPS[1]),
            TOOL_SPECIFICATIONS,
        ),
        "a step added": prefetch_digest(
            PREFETCH_PROTOCOL,
            (*PREFETCH_STEPS, PrefetchStep("team", ArgumentSource.NONE)),
            TOOL_SPECIFICATIONS,
        ),
        "a named tool's description": prefetch_digest(
            PREFETCH_PROTOCOL, PREFETCH_STEPS, _with("employees", description="Everyone.")
        ),
        "a named tool's bound": prefetch_digest(
            PREFETCH_PROTOCOL,
            PREFETCH_STEPS,
            _with("events_within", arguments=(InstantSpanArgument("span", 30),)),
        ),
        "a named tool's method facts": prefetch_digest(
            PREFETCH_PROTOCOL, PREFETCH_STEPS, _with("components", method=PortMethod.WORK_ITEMS)
        ),
    }
    assert all(digest != base for digest in moved.values()), moved
    assert len(set(moved.values())) == len(moved)


def test_the_digest_moves_with_the_validation_protocol_and_the_result_codec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Neither is in a tool's definition or its method facts; both reach the digest through
    # the surface digest of the named tools, so a changed acceptance rule or a changed
    # rendering of a result is a changed prefetch rule.
    base = prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    assert tools.VALIDATION_PROTOCOL != ("exact-json-object", 3)
    assert tools.RESULT_CODEC != ("observed-envelope", 2)
    monkeypatch.setattr(tools, "VALIDATION_PROTOCOL", ("exact-json-object", 3))
    protocol_moved = prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    monkeypatch.undo()
    monkeypatch.setattr(tools, "RESULT_CODEC", ("observed-envelope", 2))
    codec_moved = prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    assert len({base, protocol_moved, codec_moved}) == 3


def test_the_digest_ignores_a_tool_the_plan_never_names() -> None:
    base = prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    assert (
        prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, _with("search", description="Any."))
        == base
    )
    assert (
        prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, tuple(reversed(TOOL_SPECIFICATIONS)))
        == base
    )


def test_the_digest_refuses_a_step_the_surface_does_not_declare() -> None:
    with pytest.raises(ValueError, match="does not declare"):
        prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS[:1])
    with pytest.raises(ValueError, match="declared tool"):
        PrefetchStep("teams", ArgumentSource.NONE)


def _with(tool: str, **fields: object) -> tuple[ToolSpecification, ...]:
    """The fourteen with ``tool``'s specification changed in ``fields``."""
    return tuple(
        replace(specification, **fields) if specification.name == tool else specification
        for specification in TOOL_SPECIFICATIONS
    )
