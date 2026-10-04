"""The reading of a raw usage object: counters present only when reported, every declared
name under its accepted shape, and anything else an anomaly that leaves the usage unfit to
price completely. The three whole shapes below are the ones the acceptance spike's saved
responses hold."""

from collections.abc import Mapping

import pytest

from leaveimpact.core.usage import (
    ReportedUsage,
    UsageAnomaly,
    UsageAnomalyKind,
    read_usage,
)

HAIKU_WHOLE: dict[str, object] = {
    "cacheReadInputTokenCount": 0,
    "cacheReadInputTokens": 0,
    "cacheWriteInputTokenCount": 0,
    "cacheWriteInputTokens": 0,
    "inputTokens": 2049,
    "outputTokens": 38,
    "serverToolUsage": {},
    "totalTokens": 2087,
}
NOVA_OR_STREAMED: dict[str, object] = {
    "inputTokens": 1672,
    "outputTokens": 18,
    "serverToolUsage": {},
    "totalTokens": 1690,
}
HAIKU_CACHE_WRITE: dict[str, object] = {
    "cacheDetails": [{"inputTokens": 7270, "ttl": "5m"}],
    "cacheReadInputTokenCount": 0,
    "cacheReadInputTokens": 0,
    "cacheWriteInputTokenCount": 7270,
    "cacheWriteInputTokens": 7270,
    "inputTokens": 13,
    "outputTokens": 4,
    "serverToolUsage": {},
    "totalTokens": 7287,
}


def _kinds(raw: Mapping[str, object]) -> list[tuple[str, str]]:
    return [(anomaly.kind.value, anomaly.field) for anomaly in read_usage(raw).anomalies]


def test_the_measured_shapes_read_clean_with_absent_kept_apart_from_zero() -> None:
    explicit = read_usage(HAIKU_WHOLE)
    assert explicit.anomalies == ()
    assert explicit.counters.counters == (
        ("input_tokens", 2049),
        ("output_tokens", 38),
        ("cache_read_input_tokens", 0),
        ("cache_write_input_tokens", 0),
    )
    omitted = read_usage(NOVA_OR_STREAMED)
    assert omitted.anomalies == ()
    assert omitted.counters.counters == (("input_tokens", 1672), ("output_tokens", 18))
    assert omitted.counters.value("cache_read_input_tokens") is None
    written = read_usage(HAIKU_CACHE_WRITE)
    assert written.anomalies == ()
    assert written.counters.value("cache_write_input_tokens") == 7270
    assert written.counters.value("input_tokens") == 13


def test_a_twin_that_disagrees_or_repeats_an_unreported_counter_is_an_anomaly() -> None:
    assert _kinds({**HAIKU_WHOLE, "cacheReadInputTokenCount": 5}) == [
        ("twin_disagrees", "cacheReadInputTokenCount")
    ]
    assert _kinds({"inputTokens": 1, "outputTokens": 1, "cacheWriteInputTokenCount": 0}) == [
        ("twin_disagrees", "cacheWriteInputTokenCount")
    ]


def test_a_total_that_is_not_the_sum_of_the_reported_counters_is_an_anomaly() -> None:
    assert _kinds({**NOVA_OR_STREAMED, "totalTokens": 1691}) == [("total_not_sum", "totalTokens")]
    cached = {"inputTokens": 8, "outputTokens": 2, "cacheReadInputTokens": 7421}
    assert _kinds({**cached, "totalTokens": 7431}) == []


@pytest.mark.parametrize("value", [True, -1, 1.0, "12", None])
def test_a_counter_that_is_not_a_count_is_unreported_and_an_anomaly(value: object) -> None:
    reading = read_usage({"inputTokens": value, "outputTokens": 3})
    assert reading.counters.counters == (("output_tokens", 3),)
    assert reading.anomalies == (UsageAnomaly(UsageAnomalyKind.NOT_A_COUNT, "inputTokens"),)


def test_a_declared_name_outside_its_accepted_shape_is_an_anomaly() -> None:
    assert _kinds({**NOVA_OR_STREAMED, "serverToolUsage": {"webSearchRequests": 1}}) == [
        ("unexpected_shape", "serverToolUsage")
    ]
    # Any key inside it is a nested name nobody declared, a zero included.
    assert _kinds({**NOVA_OR_STREAMED, "serverToolUsage": {"webSearchRequests": 0}}) == [
        ("unexpected_shape", "serverToolUsage")
    ]
    assert _kinds({**NOVA_OR_STREAMED, "serverToolUsage": []}) == [
        ("unexpected_shape", "serverToolUsage")
    ]
    hour = {**HAIKU_CACHE_WRITE, "cacheDetails": [{"inputTokens": 7270, "ttl": "1h"}]}
    assert _kinds(hour) == [("unexpected_shape", "cacheDetails")]
    short = {**HAIKU_CACHE_WRITE, "cacheDetails": [{"inputTokens": 7000, "ttl": "5m"}]}
    assert _kinds(short) == [("unexpected_shape", "cacheDetails")]
    nested = {**HAIKU_CACHE_WRITE, "cacheDetails": [{"inputTokens": 7270, "ttl": "5m", "x": 1}]}
    assert _kinds(nested) == [("unexpected_shape", "cacheDetails")]
    unwritten: dict[str, object] = {**NOVA_OR_STREAMED, "cacheDetails": []}
    assert _kinds(unwritten) == [("unexpected_shape", "cacheDetails")]


def test_an_undeclared_name_is_an_anomaly_and_nothing_raises() -> None:
    raw = {"reasoningTokens": 9, **NOVA_OR_STREAMED, "audio": {"seconds": 2}}
    assert _kinds(raw) == [("undeclared_field", "reasoningTokens"), ("undeclared_field", "audio")]
    assert read_usage({}).counters.counters == ()
    assert read_usage({}).anomalies == ()


def test_reported_usage_holds_the_raw_object_frozen_and_reads_it() -> None:
    raw: dict[str, object] = dict(HAIKU_CACHE_WRITE)
    reported = ReportedUsage(raw)
    raw["inputTokens"] = 99
    assert reported.counters.value("input_tokens") == 13
    assert reported.complete
    assert reported == ReportedUsage(dict(reversed(list(HAIKU_CACHE_WRITE.items()))))
    # Equality is the encoding's: JSON's true is not 1, and the two read differently.
    as_true, as_one = ReportedUsage({"inputTokens": True}), ReportedUsage({"inputTokens": 1})
    assert as_true != as_one and hash(as_true) != hash(as_one)
    assert (as_true.complete, as_one.complete) == (False, True)
    assert ReportedUsage({"inputTokens": 1.0}) != as_one
    assert not ReportedUsage({**NOVA_OR_STREAMED, "totalTokens": 1}).complete
    with pytest.raises(ValueError, match="a raw usage is a JSON object"):
        ReportedUsage([1])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-finite float"):
        ReportedUsage({"inputTokens": float("nan")})
