"""What a provider reported a call used: the raw object as it arrived, and one reading of it.

A cost is exact only if the usage behind it is what the provider said, and the chat client
between the two is not a faithful witness: it maps a counter the response omitted to zero,
and whether a cache counter is omitted follows the model family and the streaming mode,
not the caching state (the acceptance spike's measurement). So usage is filled from the raw
response, the raw object is kept verbatim, and the four canonical counters are read from
it by the one function here, each present only when the response reported it (the contract
step's ruling on usage). The harness that prices a call and the evaluator that verifies
the price both run this function over the same raw object, so the counters are never a
second copy that could disagree with their source.

The raw object holds more names than the four, and the reading says what it makes of each.
A *declared* name is read under its accepted shape: ``totalTokens`` is the sum of the
reported counters, the input counter being the non-cached part; the two ``...Count`` names
are twins of the cache counters and equal them; ``serverToolUsage`` is the empty object,
the only shape measured, since any key inside it is a nested name nobody declared;
``cacheDetails`` lists the cache writes by lifetime, all at the five-minute lifetime the
price table's one cache-write rate is for, summing to the cache-write counter. Anything
else is an *anomaly*: a counter that is not a count, a twin that disagrees, a total that is
not the sum, a declared name outside its accepted shape, a name nobody declared. An anomaly
raises nothing and removes nothing. It makes the usage unfit to price completely, since a
field this code does not understand may be a token class that was billed, so the cost over
it is a floor.

The declared names are what the supported configurations returned when measured (the
``eu.`` Haiku 4.5 and Nova Pro profiles, non-streamed and streamed). A new name from a
provider is an anomaly until it is declared here with a shape, which is the point: the list
does not chase the provider silently.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from leaveimpact.core.enums import require_member
from leaveimpact.core.run_trace import Usage, frozen_json

RAW_COUNTER_NAMES: tuple[tuple[str, str], ...] = (
    ("inputTokens", "input_tokens"),
    ("outputTokens", "output_tokens"),
    ("cacheReadInputTokens", "cache_read_input_tokens"),
    ("cacheWriteInputTokens", "cache_write_input_tokens"),
)
"""The raw name of each canonical counter, in the canonical order."""

RAW_TWINS: tuple[tuple[str, str], ...] = (
    ("cacheReadInputTokenCount", "cacheReadInputTokens"),
    ("cacheWriteInputTokenCount", "cacheWriteInputTokens"),
)
"""Each duplicate name with the counter it repeats."""

RAW_TOTAL = "totalTokens"
RAW_SERVER_TOOL_USAGE = "serverToolUsage"
RAW_CACHE_DETAILS = "cacheDetails"

PRICED_CACHE_LIFETIME = "5m"
"""The cache-write lifetime the price table's one cache-write rate prices; a write at
another lifetime is billed at another rate and is not priced here."""


class UsageAnomalyKind(StrEnum):
    """What the reading could not take as declared; a member is the wire format."""

    NOT_A_COUNT = "not_a_count"
    """A counter, a twin or the total holds something other than a non-negative integer."""
    TWIN_DISAGREES = "twin_disagrees"
    """A ``...Count`` name differs from the counter it repeats, or repeats one not reported."""
    TOTAL_NOT_SUM = "total_not_sum"
    """The reported total is not the sum of the reported counters."""
    UNEXPECTED_SHAPE = "unexpected_shape"
    """A declared name outside its accepted shape: a nonzero server tool usage, a cache
    detail with another field or lifetime, details that do not sum to the cache writes."""
    UNDECLARED_FIELD = "undeclared_field"
    """A name the reading has no declaration for."""


@dataclass(frozen=True, slots=True)
class UsageAnomaly:
    """One thing in a raw usage object the reading could not take as declared, by its name."""

    kind: UsageAnomalyKind
    field: str

    def __post_init__(self) -> None:
        require_member(self.kind, UsageAnomalyKind, "a usage anomaly's kind")


@dataclass(frozen=True, slots=True)
class UsageReading:
    """The counters a raw usage object reports and what in it was not as declared, the
    anomalies in the raw object's key order."""

    counters: Usage
    anomalies: tuple[UsageAnomaly, ...]


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def read_usage(raw: Mapping[str, object]) -> UsageReading:
    """The reading of one raw usage object; raises nothing for what a provider returned.

    >>> reading = read_usage({"inputTokens": 13, "outputTokens": 4, "totalTokens": 17})
    >>> reading.counters.counters, reading.anomalies
    ((('input_tokens', 13), ('output_tokens', 4)), ())
    >>> [a.kind.value for a in read_usage({"inputTokens": 13, "reasoningTokens": 9}).anomalies]
    ['undeclared_field']
    """
    anomalies: dict[str, UsageAnomalyKind] = {}
    counts: dict[str, int] = {}
    for raw_name, _ in RAW_COUNTER_NAMES:
        if raw_name not in raw:
            continue
        count = _count(raw[raw_name])
        if count is None:
            anomalies[raw_name] = UsageAnomalyKind.NOT_A_COUNT
        else:
            counts[raw_name] = count
    for twin, counter in RAW_TWINS:
        if twin not in raw:
            continue
        count = _count(raw[twin])
        if count is None:
            anomalies[twin] = UsageAnomalyKind.NOT_A_COUNT
        elif counts.get(counter) != count:
            anomalies[twin] = UsageAnomalyKind.TWIN_DISAGREES
    if RAW_TOTAL in raw:
        total = _count(raw[RAW_TOTAL])
        if total is None:
            anomalies[RAW_TOTAL] = UsageAnomalyKind.NOT_A_COUNT
        elif total != sum(counts.values()):
            anomalies[RAW_TOTAL] = UsageAnomalyKind.TOTAL_NOT_SUM
    if RAW_SERVER_TOOL_USAGE in raw and not _bills_nothing(raw[RAW_SERVER_TOOL_USAGE]):
        anomalies[RAW_SERVER_TOOL_USAGE] = UsageAnomalyKind.UNEXPECTED_SHAPE
    if RAW_CACHE_DETAILS in raw and not _details_are_the_writes(
        raw[RAW_CACHE_DETAILS], counts.get("cacheWriteInputTokens")
    ):
        anomalies[RAW_CACHE_DETAILS] = UsageAnomalyKind.UNEXPECTED_SHAPE
    declared = {
        *(raw_name for raw_name, _ in RAW_COUNTER_NAMES),
        *(twin for twin, _ in RAW_TWINS),
        RAW_TOTAL,
        RAW_SERVER_TOOL_USAGE,
        RAW_CACHE_DETAILS,
    }
    for name in raw:
        if name not in declared:
            anomalies[name] = UsageAnomalyKind.UNDECLARED_FIELD
    counters = Usage(
        tuple(
            (name, counts[raw_name]) for raw_name, name in RAW_COUNTER_NAMES if raw_name in counts
        )
    )
    return UsageReading(
        counters, tuple(UsageAnomaly(anomalies[name], name) for name in raw if name in anomalies)
    )


def _bills_nothing(value: object) -> bool:
    """Whether a server tool usage object is the empty object: no nested name, so nothing
    this reading would have to understand."""
    return isinstance(value, Mapping) and not value


def _details_are_the_writes(value: object, cache_writes: int | None) -> bool:
    """Whether cache details are entries of exactly a count and the priced lifetime that sum
    to the reported cache writes."""
    if not isinstance(value, list | tuple) or cache_writes is None:
        return False
    written = 0
    for entry in cast("list[object] | tuple[object, ...]", value):
        if not isinstance(entry, Mapping):
            return False
        detail = cast("Mapping[object, object]", entry)
        count = _count(detail.get("inputTokens"))
        if set(detail) != {"inputTokens", "ttl"} or count is None:
            return False
        if detail["ttl"] != PRICED_CACHE_LIFETIME:
            return False
        written += count
    return written == cache_writes


@dataclass(frozen=True, slots=True, eq=False)
class ReportedUsage:
    """The usage one send's response carried: the raw object, frozen, and its one reading.

    Only the raw object is held; the counters and the anomalies are read from it each time
    by ``read_usage``, so they cannot drift from it. ``complete`` is whether the reading
    took everything as declared, which a complete cost needs before the rates are asked.
    Two usages are equal exactly when their raw objects encode alike: ``true`` is not 1
    there, and the two read differently.

    >>> ReportedUsage({"inputTokens": True}) == ReportedUsage({"inputTokens": 1})
    False

    >>> reported = ReportedUsage({"inputTokens": 8, "outputTokens": 2, "totalTokens": 11})
    >>> reported.counters.value("input_tokens"), reported.complete
    (8, False)
    """

    raw: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.raw), Mapping):
            raise ValueError(f"a raw usage is a JSON object, got {type(self.raw).__name__}")
        object.__setattr__(self, "raw", frozen_json(dict(self.raw), "a raw usage"))

    @property
    def encoded(self) -> str:
        """The raw object's JSON text, keys in order: the usage's identity."""
        return json.dumps(self.raw, default=dict, sort_keys=True)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReportedUsage) and self.encoded == other.encoded

    def __hash__(self) -> int:
        return hash(self.encoded)

    @property
    def reading(self) -> UsageReading:
        return read_usage(self.raw)

    @property
    def counters(self) -> Usage:
        """The canonical counters the raw object reported, each only if reported."""
        return self.reading.counters

    @property
    def anomalies(self) -> tuple[UsageAnomaly, ...]:
        return self.reading.anomalies

    @property
    def complete(self) -> bool:
        """Whether nothing in the raw object was outside its declaration."""
        return not self.reading.anomalies


__all__ = [
    "PRICED_CACHE_LIFETIME",
    "RAW_COUNTER_NAMES",
    "RAW_TWINS",
    "ReportedUsage",
    "UsageAnomaly",
    "UsageAnomalyKind",
    "UsageReading",
    "read_usage",
]
