"""JSON for the preregistration: one committed file, strict, in one written form.

The registration is read by the harness and the evaluator from the same committed bytes,
and a run is eligible for a table when the file at the commit it cites equals the
evaluator's byte for byte (the investigator milestone's sixth build step, rulings 1 and
7), so the codec sits here with the type and the file has exactly one spelling. Unlike
the run export, that spelling is indented: the file is edited by hand and reviewed as a
diff, and one line would make every change unreadable. The form is still fixed, one object
built field by field in the declared order, two-space indentation, UTF-8 passed through,
one trailing newline, and a decoder accepts bytes only when re-encoding what they decode
to reproduces them, so a reformatted, reordered or duplicate-keyed file is refused and
equal registrations are equal in bytes.

Strict in the export codec's manner, through the domain constructors: the format version
first, any version but this code's refused before anything else is read; exactly the
declared fields on every object, each of its declared type; enum members by value; a
system by its ``kind``; every invariant the types enforce. A pendable field is always an
object with exactly one key, ``{"value": ...}`` or ``{"pending": "<what resolves it>"}``,
so no string and no ``null`` doubles as a marker and a field not declared pendable cannot
be pending. ``null`` keeps its one meaning, that there is none of a thing (a first
registration amends nothing).

A condition is written as the sources it cannot reach; its identifier is derived and never
stored, so the two cannot disagree. The schedule digest is not stored either: it is a
function of the outage section, computed by ``registration.schedule_digest``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import assert_never, cast

from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.jsonshape import (
    JsonObject,
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
from leaveimpact.core.provenance import decode_model_configuration, encode_model_configuration
from leaveimpact.core.registration import (
    REGISTRATION_FORMAT_VERSION,
    AgentSystem,
    Amendment,
    Basis,
    Budget,
    CheckReading,
    CountedAttemptRule,
    DescriptiveComparisons,
    Injection,
    MissingRunRule,
    OutageSchedule,
    Pending,
    PrimaryComparison,
    RegisteredArm,
    RegisteredCaps,
    RegisteredCondition,
    RegisteredPrefetch,
    RegisteredSystem,
    Registration,
    RegistrationStatus,
    ReportingPolicy,
    ReportingScope,
    RetryRule,
    RulesOnlySystem,
    RunAccounting,
    ScenarioSetName,
    ScenarioSets,
    SingleShotSystem,
    Statistics,
    StratumLevel,
)
from leaveimpact.core.run_record import (
    Caps,
    FailureCategory,
    Retrieval,
    RetrievalKind,
    SystemKind,
)
from leaveimpact.core.run_trace import require_integer

_FIELDS = (
    "format_version",
    "status",
    "amendment",
    "systems",
    "outage",
    "arms",
    "run_accounting",
    "statistics",
    "prefetch",
    "caps",
    "budget",
    "scenario_sets",
)
_SYSTEM_FIELDS: dict[SystemKind, tuple[str, ...]] = {
    SystemKind.AGENT: (
        "kind",
        "variant",
        "retrieval",
        "model",
        "prompt_digests",
        "tool_surface_digest",
    ),
    SystemKind.RULES_ONLY: ("kind", "variant", "retrieval", "policy"),
    SystemKind.SINGLE_SHOT: (
        "kind",
        "variant",
        "retrieval",
        "model",
        "prompt_digests",
        "query_protocol",
        "search_limit",
    ),
}

# --- Encoding ---------------------------------------------------------------------------


def registration_bytes(registration: Registration) -> bytes:
    """The one written form of ``registration``: what is committed and compared."""
    text = json.dumps(encode_registration(registration), ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


def encode_registration(registration: Registration) -> JsonObject:
    """The JSON object of a registration, its sections in the declared order."""
    amendment = registration.amendment
    accounting = registration.run_accounting
    prefetch = registration.prefetch
    caps = registration.caps.caps
    budget = registration.budget
    sets = registration.scenario_sets
    return {
        "format_version": registration.format_version,
        "status": registration.status.value,
        "amendment": {
            "amends": amendment.amends,
            "prior_full_set_results": amendment.prior_full_set_results,
        },
        "systems": [_encode_system(system) for system in registration.systems],
        "outage": _encode_outage(registration.outage),
        "arms": [
            {"system": arm.system.value, "condition": arm.condition} for arm in registration.arms
        ],
        "run_accounting": {
            "repeats": accounting.repeats,
            "missing_run": accounting.missing_run.value,
            "retry": {
                "after": accounting.retry.after.value,
                "max_attempts": accounting.retry.max_attempts,
            },
            "counted_attempt": accounting.counted_attempt.value,
            "estimand": accounting.estimand,
        },
        "statistics": _encode_statistics(registration.statistics),
        "prefetch": {
            "identifier": prefetch.identifier,
            "protocol_version": prefetch.protocol_version,
            "digest": prefetch.digest,
        },
        "caps": {
            "basis": registration.caps.basis.value,
            "call_cap": caps.call_cap,
            "token_cap": caps.token_cap,
            "finalization_call_reserve": caps.finalization_call_reserve,
            "finalization_token_reserve": caps.finalization_token_reserve,
            "counting_rule": caps.counting_rule,
        },
        "budget": {
            "basis": budget.basis.value,
            "expected_usd": budget.expected_usd,
            "ceiling_usd": budget.ceiling_usd,
            "reforecast_after_runs": budget.reforecast_after_runs,
            "admission_threshold_usd": budget.admission_threshold_usd,
            "admission_threshold_limit_usd": budget.admission_threshold_limit_usd,
        },
        "scenario_sets": {
            "development_size": sets.development_size,
            "development_per_tier": sets.development_per_tier,
            "development": _encode_pendable(sets.development, list),
        },
    }


def _encode_pendable[T](value: T | Pending, encode: Callable[[T], object]) -> JsonObject:
    if isinstance(value, Pending):
        return {"pending": value.awaiting}
    return {"value": encode(value)}


def _same[T](value: T) -> T:
    return value


def _encode_prompts(prompts: tuple[tuple[str, str], ...]) -> list[JsonObject]:
    return [{"name": name, "digest": digest} for name, digest in prompts]


def _encode_retrieval(retrieval: Retrieval) -> JsonObject:
    return {"kind": retrieval.kind.value, "embedding_model": retrieval.embedding_model}


def _encode_system(system: RegisteredSystem) -> JsonObject:
    head: JsonObject = {
        "kind": system.kind.value,
        "variant": _encode_pendable(system.variant, _same),
        "retrieval": _encode_retrieval(system.retrieval),
    }
    match system:
        case AgentSystem():
            return head | {
                "model": _encode_pendable(system.model, encode_model_configuration),
                "prompt_digests": _encode_pendable(system.prompt_digests, _encode_prompts),
                "tool_surface_digest": _encode_pendable(system.tool_surface_digest, _same),
            }
        case RulesOnlySystem():
            policy = system.policy
            return head | {
                "policy": {
                    "identifier": policy.identifier,
                    "version": policy.version,
                    "tie_break": policy.tie_break,
                }
            }
        case SingleShotSystem():
            return head | {
                "model": _encode_pendable(system.model, encode_model_configuration),
                "prompt_digests": _encode_pendable(system.prompt_digests, _encode_prompts),
                "query_protocol": _encode_pendable(system.query_protocol, _same),
                "search_limit": _encode_pendable(system.search_limit, _same),
            }
        case _:
            assert_never(system)


def _encode_outage(outage: OutageSchedule) -> JsonObject:
    return {
        "protocol": {"id": outage.protocol[0], "version": outage.protocol[1]},
        "injection": outage.injection.value,
        "conditions": [
            {
                "unreachable": sorted(source.value for source in condition.unreachable),
                "reporting": condition.reporting.value,
            }
            for condition in outage.conditions
        ],
    }


def _encode_pair(pair: tuple[SystemKind, SystemKind]) -> list[str]:
    return [pair[0].value, pair[1].value]


def _encode_statistics(statistics: Statistics) -> JsonObject:
    descriptive = statistics.descriptive
    return {
        "confidence_percent": statistics.confidence_percent,
        "seed": statistics.seed,
        "resamples": statistics.resamples,
        "checks": list(statistics.checks),
        "measures": list(statistics.measures),
        "primary": [
            {
                "check": comparison.check,
                "reading": comparison.reading.value,
                "condition": comparison.condition,
                "stratum": comparison.stratum.value,
                "scenario_set": comparison.scenario_set.value,
                "systems": _encode_pair(comparison.systems),
            }
            for comparison in statistics.primary
        ],
        "descriptive": {
            "pairs": [_encode_pair(pair) for pair in descriptive.pairs],
            "conditions": list(descriptive.conditions),
            "strata": [level.value for level in descriptive.strata],
            "scenario_sets": [name.value for name in descriptive.scenario_sets],
            "checks": list(descriptive.checks),
            "readings": [reading.value for reading in descriptive.readings],
            "measures": list(descriptive.measures),
        },
    }


# --- Decoding ---------------------------------------------------------------------------


def decode_registration_bytes(content: bytes | str) -> Registration:
    """The registration ``content`` holds, accepted only if its re-encoding is ``content``
    byte for byte.

    >>> decode_registration_bytes(b'{"format_version": 2}')
    Traceback (most recent call last):
    ...
    ValueError: this code reads registration format 1, got 2
    """
    raw = content.encode("utf-8") if isinstance(content, str) else content
    registration = decode_registration(json.loads(raw))
    if registration_bytes(registration) != raw:
        raise ValueError(
            "the registration's bytes are not its one written form; a re-encoding of what "
            "they decode to differs (a reformatted, reordered or duplicate-keyed file)"
        )
    return registration


def decode_registration(value: object) -> Registration:
    """The registration ``value`` encodes; a format other than this code's refuses first."""
    data = as_object(value, "a registration")
    version = require_integer(field_of(data, "format_version"), "format_version")
    if version != REGISTRATION_FORMAT_VERSION:
        raise ValueError(
            f"this code reads registration format {REGISTRATION_FORMAT_VERSION}, got {version}"
        )
    expect_fields(data, _FIELDS, "a registration")
    amendment = object_field(data, "amendment")
    expect_fields(amendment, ("amends", "prior_full_set_results"), "the amendment")
    prefetch = object_field(data, "prefetch")
    expect_fields(prefetch, ("identifier", "protocol_version", "digest"), "the prefetch")
    return Registration(
        format_version=version,
        status=RegistrationStatus(string_field(data, "status")),
        amendment=Amendment(
            optional_string_field(amendment, "amends"),
            _boolean_field(amendment, "prior_full_set_results"),
        ),
        systems=tuple(_decode_system(item) for item in array_field(data, "systems")),
        outage=_decode_outage(object_field(data, "outage")),
        arms=tuple(_decode_arm(item) for item in array_field(data, "arms")),
        run_accounting=_decode_accounting(object_field(data, "run_accounting")),
        statistics=_decode_statistics(object_field(data, "statistics")),
        prefetch=RegisteredPrefetch(
            string_field(prefetch, "identifier"),
            integer_field(prefetch, "protocol_version"),
            string_field(prefetch, "digest"),
        ),
        caps=_decode_caps(object_field(data, "caps")),
        budget=_decode_budget(object_field(data, "budget")),
        scenario_sets=_decode_scenario_sets(object_field(data, "scenario_sets")),
    )


def _boolean_field(data: Mapping[str, object], key: str) -> bool:
    value = field_of(data, key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} is true or false, got {type(value).__name__}")
    return value


def _pendable[T](
    data: Mapping[str, object], key: str, decode: Callable[[object], T]
) -> T | Pending:
    """The pendable field ``key``: its value through ``decode``, or what it is pending on."""
    wrapper = object_field(data, key)
    if set(wrapper) == {"pending"}:
        return Pending(string_field(wrapper, "pending"))
    if set(wrapper) == {"value"}:
        return decode(wrapper["value"])
    raise ValueError(
        f"{key} is an object with exactly one of 'value' and 'pending', got {sorted(wrapper)}"
    )


def _only_pending(data: Mapping[str, object], key: str) -> Pending:
    value = _pendable(data, key, _same)
    if not isinstance(value, Pending):
        raise ValueError(f"{key} can only be pending in registration format 1")
    return value


def _string_of(key: str) -> Callable[[object], str]:
    return lambda value: string_item(value, key)


def _integer_of(key: str) -> Callable[[object], int]:
    return lambda value: require_integer(value, key, minimum=None)


def _strings(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    return tuple(string_item(item, key) for item in array_field(data, key))


def _as_array(value: object, key: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{key} is a JSON array, got {type(value).__name__}")
    return cast(list[object], value)


def _decode_prompts(value: object) -> tuple[tuple[str, str], ...]:
    prompts: list[tuple[str, str]] = []
    for item in _as_array(value, "prompt_digests"):
        prompt = as_object(item, "a prompt digest")
        expect_fields(prompt, ("name", "digest"), "a prompt digest")
        prompts.append((string_field(prompt, "name"), string_field(prompt, "digest")))
    return tuple(prompts)


def _decode_retrieval(data: Mapping[str, object]) -> Retrieval:
    expect_fields(data, ("kind", "embedding_model"), "the retrieval")
    return Retrieval(
        RetrievalKind(string_field(data, "kind")), optional_string_field(data, "embedding_model")
    )


def _decode_system(item: object) -> RegisteredSystem:
    data = as_object(item, "a system")
    kind = SystemKind(string_field(data, "kind"))
    expect_fields(data, _SYSTEM_FIELDS[kind], f"the {kind.value} system")
    variant = _pendable(data, "variant", _string_of("variant"))
    retrieval = _decode_retrieval(object_field(data, "retrieval"))
    match kind:
        case SystemKind.AGENT:
            return AgentSystem(
                variant,
                retrieval,
                _pendable(data, "model", decode_model_configuration),
                _pendable(data, "prompt_digests", _decode_prompts),
                _pendable(data, "tool_surface_digest", _string_of("tool_surface_digest")),
            )
        case SystemKind.RULES_ONLY:
            policy = object_field(data, "policy")
            expect_fields(policy, ("identifier", "version", "tie_break"), "the reporting policy")
            return RulesOnlySystem(
                variant,
                retrieval,
                ReportingPolicy(
                    string_field(policy, "identifier"),
                    integer_field(policy, "version"),
                    string_field(policy, "tie_break"),
                ),
            )
        case SystemKind.SINGLE_SHOT:
            return SingleShotSystem(
                variant,
                retrieval,
                _pendable(data, "model", decode_model_configuration),
                _pendable(data, "prompt_digests", _decode_prompts),
                _only_pending(data, "query_protocol"),
                _pendable(data, "search_limit", _integer_of("search_limit")),
            )
        case _:
            assert_never(kind)


def _decode_outage(data: Mapping[str, object]) -> OutageSchedule:
    expect_fields(data, ("protocol", "injection", "conditions"), "the outage")
    protocol = object_field(data, "protocol")
    expect_fields(protocol, ("id", "version"), "the outage protocol")
    return OutageSchedule(
        (string_field(protocol, "id"), integer_field(protocol, "version")),
        Injection(string_field(data, "injection")),
        tuple(_decode_condition(item) for item in array_field(data, "conditions")),
    )


def _decode_condition(item: object) -> RegisteredCondition:
    data = as_object(item, "a condition")
    expect_fields(data, ("unreachable", "reporting"), "a condition")
    return RegisteredCondition(
        frozenset(Source(name) for name in _strings(data, "unreachable")),
        ReportingScope(string_field(data, "reporting")),
    )


def _decode_arm(item: object) -> RegisteredArm:
    data = as_object(item, "an arm")
    expect_fields(data, ("system", "condition"), "an arm")
    return RegisteredArm(SystemKind(string_field(data, "system")), string_field(data, "condition"))


def _decode_accounting(data: Mapping[str, object]) -> RunAccounting:
    expect_fields(
        data, ("repeats", "missing_run", "retry", "counted_attempt", "estimand"), "run accounting"
    )
    retry = object_field(data, "retry")
    expect_fields(retry, ("after", "max_attempts"), "the retry rule")
    return RunAccounting(
        integer_field(data, "repeats"),
        MissingRunRule(string_field(data, "missing_run")),
        RetryRule(
            FailureCategory(string_field(retry, "after")), integer_field(retry, "max_attempts")
        ),
        CountedAttemptRule(string_field(data, "counted_attempt")),
        string_field(data, "estimand"),
    )


def _decode_pair(item: object, key: str) -> tuple[SystemKind, SystemKind]:
    names = _as_array(item, key)
    if len(names) != 2:
        raise ValueError(f"{key} names two systems, got {len(names)}")
    first, second = (SystemKind(string_item(name, key)) for name in names)
    return first, second


def _decode_statistics(data: Mapping[str, object]) -> Statistics:
    expect_fields(
        data,
        (
            "confidence_percent",
            "seed",
            "resamples",
            "checks",
            "measures",
            "primary",
            "descriptive",
        ),
        "the statistics",
    )
    descriptive = object_field(data, "descriptive")
    expect_fields(
        descriptive,
        ("pairs", "conditions", "strata", "scenario_sets", "checks", "readings", "measures"),
        "the descriptive comparisons",
    )
    return Statistics(
        integer_field(data, "confidence_percent"),
        integer_field(data, "seed"),
        integer_field(data, "resamples"),
        _strings(data, "checks"),
        _strings(data, "measures"),
        tuple(_decode_primary(item) for item in array_field(data, "primary")),
        DescriptiveComparisons(
            tuple(_decode_pair(item, "pairs") for item in array_field(descriptive, "pairs")),
            _strings(descriptive, "conditions"),
            tuple(StratumLevel(name) for name in _strings(descriptive, "strata")),
            tuple(ScenarioSetName(name) for name in _strings(descriptive, "scenario_sets")),
            _strings(descriptive, "checks"),
            tuple(CheckReading(name) for name in _strings(descriptive, "readings")),
            _strings(descriptive, "measures"),
        ),
    )


def _decode_primary(item: object) -> PrimaryComparison:
    data = as_object(item, "a primary comparison")
    expect_fields(
        data,
        ("check", "reading", "condition", "stratum", "scenario_set", "systems"),
        "a primary comparison",
    )
    return PrimaryComparison(
        string_field(data, "check"),
        CheckReading(string_field(data, "reading")),
        string_field(data, "condition"),
        StratumLevel(string_field(data, "stratum")),
        ScenarioSetName(string_field(data, "scenario_set")),
        _decode_pair(field_of(data, "systems"), "systems"),
    )


def _decode_caps(data: Mapping[str, object]) -> RegisteredCaps:
    expect_fields(
        data,
        (
            "basis",
            "call_cap",
            "token_cap",
            "finalization_call_reserve",
            "finalization_token_reserve",
            "counting_rule",
        ),
        "the caps",
    )
    return RegisteredCaps(
        Basis(string_field(data, "basis")),
        Caps(
            integer_field(data, "call_cap"),
            integer_field(data, "token_cap"),
            integer_field(data, "finalization_call_reserve"),
            integer_field(data, "finalization_token_reserve"),
            string_field(data, "counting_rule"),
        ),
    )


def _decode_budget(data: Mapping[str, object]) -> Budget:
    expect_fields(
        data,
        (
            "basis",
            "expected_usd",
            "ceiling_usd",
            "reforecast_after_runs",
            "admission_threshold_usd",
            "admission_threshold_limit_usd",
        ),
        "the budget",
    )
    return Budget(
        Basis(string_field(data, "basis")),
        integer_field(data, "expected_usd"),
        integer_field(data, "ceiling_usd"),
        integer_field(data, "reforecast_after_runs"),
        integer_field(data, "admission_threshold_usd"),
        integer_field(data, "admission_threshold_limit_usd"),
    )


def _decode_scenarios(value: object) -> tuple[ScenarioId, ...]:
    return tuple(
        ScenarioId(string_item(item, "development")) for item in _as_array(value, "development")
    )


def _decode_scenario_sets(data: Mapping[str, object]) -> ScenarioSets:
    expect_fields(
        data, ("development_size", "development_per_tier", "development"), "the scenario sets"
    )
    return ScenarioSets(
        integer_field(data, "development_size"),
        integer_field(data, "development_per_tier"),
        _pendable(data, "development", _decode_scenarios),
    )


__all__ = [
    "decode_registration",
    "decode_registration_bytes",
    "encode_registration",
    "registration_bytes",
]
