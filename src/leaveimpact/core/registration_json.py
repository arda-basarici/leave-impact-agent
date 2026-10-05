"""JSON for the preregistration: one committed file, strict, in one written form.

The registration is read by the harness and the evaluator from the same committed bytes,
and a run is eligible for a table when the file at the commit it cites equals the
evaluator's byte for byte, so the codec sits here with the type and the file has exactly
one spelling. Unlike the run export, that spelling is indented: the file is edited by hand
and reviewed as a diff, and one line would make every change unreadable. The form is still
fixed, one object built field by field in the declared order, two-space indentation, UTF-8
passed through, one trailing newline, and a decoder accepts bytes only when re-encoding
what they decode to reproduces them, so a reformatted, reordered or duplicate-keyed file is
refused and equal registrations are equal in bytes.

Strict in the export codec's manner, through the domain constructors: the format version
first, any version but this code's refused before anything else is read; exactly the
declared fields on every object, each of its declared type; enum members by value; a
system by its ``kind``; every invariant the types enforce. A pendable field is always an
object with exactly one key, ``{"value": ...}`` or ``{"pending": "<what resolves it>"}``,
so no string and no ``null`` doubles as a marker and a field not declared pendable cannot
be pending. ``null`` keeps its one meaning, that there is none of a thing: a first
registration amends nothing, a cell belongs to no group, a comparison runs under no model
but the registered one.

A condition is written as the sources it cannot reach; its identifier is derived and never
stored, so the two cannot disagree. The schedule digest and the attribution table's digest
are not stored either: each is a function of its section.

``procedure_projection`` is the registration without the three values binding a world
changes: its status, the world's version, and the frozen commit a bound file names. A
frozen registration and the bound one made from it project to the same object, and a
reader that holds both compares the two. Everything else stays in, the amendment and the
declared count of tuned scenarios included, since both are part of what was frozen.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import assert_never, cast

from leaveimpact.core.attribution import (
    decode_attribution_table,
    decode_redispatch_policy,
    encode_attribution_table,
    encode_redispatch_policy,
)
from leaveimpact.core.call_settings import decode_call_configuration, encode_call_configuration
from leaveimpact.core.enums import Source
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.registration import (
    REGISTRATION_FORMAT_VERSION,
    AgentSystem,
    Amendment,
    Basis,
    Budget,
    CheckReading,
    Comparison,
    ConditionalGroup,
    CorpusLevel,
    CountedAttemptRule,
    DescriptiveComparisons,
    EntrySchema,
    FullContextSystem,
    GroupDecision,
    HeadroomProcedure,
    Injection,
    LevelContrast,
    MeasuredWorld,
    MechanismMeasure,
    MissingRunRule,
    NotBuilt,
    OutageSchedule,
    Pending,
    Place,
    RegisteredCaps,
    RegisteredCell,
    RegisteredCondition,
    RegisteredPrefetch,
    RegisteredRole,
    RegisteredSystem,
    Registration,
    RegistrationStatus,
    ReportingScope,
    RetryRule,
    Roles,
    RulesOnlySystem,
    RunAccounting,
    SingleShotSystem,
    StatedFactContract,
    Statistics,
    StratumLevel,
    SupportingComparison,
    SupportingSystem,
)
from leaveimpact.core.run_ending import ComposingPolicy
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
    "world",
    "systems",
    "corpus_levels",
    "outage",
    "cell_groups",
    "cells",
    "run_accounting",
    "attribution",
    "stated_facts",
    "statistics",
    "supporting",
    "prefetch",
    "budget",
)
_SYSTEM_FIELDS: dict[SystemKind, tuple[str, ...]] = {
    SystemKind.AGENT: ("kind", "variant", "retrieval", "roles", "caps"),
    SystemKind.RULES_ONLY: ("kind", "variant", "retrieval", "caps"),
    SystemKind.SINGLE_SHOT: (
        "kind",
        "variant",
        "retrieval",
        "roles",
        "query_protocol",
        "search_limit",
        "caps",
    ),
    SystemKind.FULL_CONTEXT: ("kind", "variant", "retrieval", "roles", "caps"),
}
_CAPS_FIELDS = (
    "basis",
    "call_cap",
    "token_cap",
    "finalization_call_reserve",
    "finalization_token_reserve",
    "counting_rule",
)
_COMPARISON_FIELDS = ("check", "reading", "condition", "level", "systems", "breakdowns")

# --- Encoding ---------------------------------------------------------------------------


def registration_bytes(registration: Registration) -> bytes:
    """The one written form of ``registration``: what is committed and compared."""
    text = json.dumps(encode_registration(registration), ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


def encode_registration(registration: Registration) -> JsonObject:
    """The JSON object of a registration, its sections in the declared order."""
    amendment = registration.amendment
    world = registration.world
    accounting = registration.run_accounting
    stated = registration.stated_facts
    prefetch = registration.prefetch
    budget = registration.budget
    return {
        "format_version": registration.format_version,
        "status": registration.status.value,
        "amendment": {
            "amends": amendment.amends,
            "prior_full_set_results": amendment.prior_full_set_results,
        },
        "world": {
            "version": _encode_pendable(world.version, _same),
            "frozen_commit": world.frozen_commit,
            "tuned_scenarios": world.tuned_scenarios,
        },
        "systems": [_encode_system(system) for system in registration.systems],
        "corpus_levels": [
            {"name": level.name, "filler_tokens": _encode_pendable(level.filler_tokens, _same)}
            for level in registration.corpus_levels
        ],
        "outage": _encode_outage(registration.outage),
        "cell_groups": [
            {
                "name": group.name,
                "rule": group.rule,
                "decision": _encode_pendable(group.decision, _encode_decision),
            }
            for group in registration.cell_groups
        ],
        "cells": [
            {
                "system": cell.system.value,
                "condition": cell.condition,
                "level": cell.level,
                "group": cell.group,
            }
            for cell in registration.cells
        ],
        "run_accounting": {
            "repeats": accounting.repeats,
            "missing_run": accounting.missing_run.value,
            "retry": {
                "after": accounting.retry.after.value,
                "max_attempts": accounting.retry.max_attempts,
            },
            "counted_attempt": accounting.counted_attempt.value,
            "redispatch": _encode_pendable(accounting.redispatch, encode_redispatch_policy),
            "estimand": accounting.estimand,
        },
        "attribution": _encode_pendable(registration.attribution, encode_attribution_table),
        "stated_facts": {
            "composing_policy": {
                "identifier": stated.composing_policy.identifier,
                "digest": stated.composing_policy.digest,
            },
            "anchor_table": stated.anchor_table,
            "entry_schema": _encode_pendable(
                stated.entry_schema,
                lambda schema: {"parser": schema.parser, "digest": schema.digest},
            ),
        },
        "statistics": _encode_statistics(registration.statistics),
        "supporting": [_encode_supporting(entry) for entry in registration.supporting],
        "prefetch": {
            "identifier": prefetch.identifier,
            "protocol_version": prefetch.protocol_version,
            "digest": prefetch.digest,
        },
        "budget": {
            "basis": budget.basis.value,
            "expected_usd": budget.expected_usd,
            "ceiling_usd": budget.ceiling_usd,
            "reforecast_after_runs": budget.reforecast_after_runs,
            "admission_threshold_usd": budget.admission_threshold_usd,
            "admission_threshold_limit_usd": budget.admission_threshold_limit_usd,
        },
    }


def procedure_projection(registration: Registration) -> JsonObject:
    """``registration`` as its procedure: the encoded object without its status, its world's
    version and the frozen commit a bound file names, the three values binding a world
    changes."""
    encoded = encode_registration(registration)
    world = cast("JsonObject", encoded["world"])
    return {
        **{key: value for key, value in encoded.items() if key != "status"},
        "world": {"tuned_scenarios": world["tuned_scenarios"]},
    }


def procedure_digest(registration: Registration) -> str:
    """SHA-256 of the procedure projection in canonical JSON: equal for a frozen
    registration and every bound one that changed nothing in it."""
    return hashlib.sha256(canonical_bytes(procedure_projection(registration))).hexdigest()


def _encode_pendable[T](value: T | Pending, encode: Callable[[T], object]) -> JsonObject:
    if isinstance(value, Pending):
        return {"pending": value.awaiting}
    return {"value": encode(value)}


def _same[T](value: T) -> T:
    return value


def _encode_decision(decision: GroupDecision) -> JsonObject:
    return {"run": decision.run, "reason": decision.reason}


def _encode_retrieval(retrieval: Retrieval) -> JsonObject:
    return {"kind": retrieval.kind.value, "embedding_model": retrieval.embedding_model}


def _encode_caps(registered: RegisteredCaps) -> JsonObject:
    caps = registered.caps
    return {
        "basis": registered.basis.value,
        "call_cap": caps.call_cap,
        "token_cap": caps.token_cap,
        "finalization_call_reserve": caps.finalization_call_reserve,
        "finalization_token_reserve": caps.finalization_token_reserve,
        "counting_rule": caps.counting_rule,
    }


def _encode_roles(roles: Roles) -> list[JsonObject]:
    return [
        {
            "name": role.name,
            "configuration": encode_call_configuration(role.configuration),
            "prompt_digests": [
                {"name": name, "digest": digest} for name, digest in role.prompt_digests
            ],
            "tool_surface_digest": role.tool_surface_digest,
        }
        for role in roles
    ]


def _encode_system(system: RegisteredSystem) -> JsonObject:
    head: JsonObject = {
        "kind": system.kind.value,
        "variant": _encode_pendable(system.variant, _same),
        "retrieval": _encode_retrieval(system.retrieval),
    }
    caps: JsonObject = {"caps": _encode_caps(system.caps)}
    match system:
        case AgentSystem() | FullContextSystem():
            return head | {"roles": _encode_pendable(system.roles, _encode_roles)} | caps
        case RulesOnlySystem():
            return head | caps
        case SingleShotSystem():
            return (
                head
                | {
                    "roles": _encode_pendable(system.roles, _encode_roles),
                    "query_protocol": _encode_pendable(system.query_protocol, _same),
                    "search_limit": _encode_pendable(system.search_limit, _same),
                }
                | caps
            )
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


def _encode_comparison(comparison: Comparison) -> JsonObject:
    return {
        "check": comparison.check,
        "reading": comparison.reading.value,
        "condition": comparison.condition,
        "level": comparison.level,
        "systems": _encode_pair(comparison.systems),
        "breakdowns": [level.value for level in comparison.breakdowns],
    }


def _encode_statistics(statistics: Statistics) -> JsonObject:
    descriptive = statistics.descriptive
    headroom = statistics.headroom
    return {
        "confidence_percent": statistics.confidence_percent,
        "seed": statistics.seed,
        "resamples": statistics.resamples,
        "interval_method": statistics.interval_method,
        "checks": list(statistics.checks),
        "measures": list(statistics.measures),
        "primary": _encode_comparison(statistics.primary),
        "secondary": [_encode_comparison(comparison) for comparison in statistics.secondary],
        "descriptive": {
            "places": [
                {"condition": place.condition, "level": place.level}
                for place in descriptive.places
            ],
            "pairs": [_encode_pair(pair) for pair in descriptive.pairs],
            "strata": [level.value for level in descriptive.strata],
            "checks": list(descriptive.checks),
            "readings": [reading.value for reading in descriptive.readings],
            "measures": list(descriptive.measures),
        },
        "level_contrasts": [
            {
                "system": contrast.system.value,
                "check": contrast.check,
                "reading": contrast.reading.value,
                "condition": contrast.condition,
                "levels": list(contrast.levels),
                "breakdowns": [level.value for level in contrast.breakdowns],
            }
            for contrast in statistics.level_contrasts
        ],
        "mechanism": _encode_pendable(
            statistics.mechanism,
            lambda measure: {"name": measure.name, "stages": list(measure.stages)},
        ),
        "headroom": {
            "reference": headroom.reference.value,
            "check": headroom.check,
            "reading": headroom.reading.value,
        },
    }


def _encode_supporting(entry: SupportingComparison) -> JsonObject:
    return {
        "identifier": entry.identifier,
        "condition": entry.condition,
        "level": entry.level,
        "systems": [
            {"kind": system.kind.value, "variant": system.variant} for system in entry.systems
        ],
        "other_model": _encode_pendable(entry.other_model, _same),
        "endpoint": entry.endpoint,
        "analysis": entry.analysis,
        "inclusion": _encode_pendable(
            entry.inclusion,
            lambda state: {
                "not_built": {
                    "reason": state.reason,
                    "development_number": state.development_number,
                }
            },
        ),
    }


# --- Decoding ---------------------------------------------------------------------------


def decode_registration_bytes(content: bytes | str) -> Registration:
    """The registration ``content`` holds, accepted only if its re-encoding is ``content``
    byte for byte.

    >>> decode_registration_bytes(b'{"format_version": 1}')
    Traceback (most recent call last):
    ...
    ValueError: this code reads registration format 2, got 1
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
    world = object_field(data, "world")
    expect_fields(world, ("version", "frozen_commit", "tuned_scenarios"), "the world")
    prefetch = object_field(data, "prefetch")
    expect_fields(prefetch, ("identifier", "protocol_version", "digest"), "the prefetch")
    return Registration(
        format_version=version,
        status=RegistrationStatus(string_field(data, "status")),
        amendment=Amendment(
            optional_string_field(amendment, "amends"),
            _boolean_field(amendment, "prior_full_set_results"),
        ),
        world=MeasuredWorld(
            _pendable(world, "version", _string_of("version")),
            optional_string_field(world, "frozen_commit"),
            integer_field(world, "tuned_scenarios"),
        ),
        systems=tuple(_decode_system(item) for item in array_field(data, "systems")),
        corpus_levels=tuple(_decode_level(item) for item in array_field(data, "corpus_levels")),
        outage=_decode_outage(object_field(data, "outage")),
        cell_groups=tuple(_decode_group(item) for item in array_field(data, "cell_groups")),
        cells=tuple(_decode_cell(item) for item in array_field(data, "cells")),
        run_accounting=_decode_accounting(object_field(data, "run_accounting")),
        attribution=_pendable(data, "attribution", decode_attribution_table),
        stated_facts=_decode_stated_facts(object_field(data, "stated_facts")),
        statistics=_decode_statistics(object_field(data, "statistics")),
        supporting=tuple(_decode_supporting(item) for item in array_field(data, "supporting")),
        prefetch=RegisteredPrefetch(
            string_field(prefetch, "identifier"),
            integer_field(prefetch, "protocol_version"),
            string_field(prefetch, "digest"),
        ),
        budget=_decode_budget(object_field(data, "budget")),
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
        raise ValueError(
            f"{key} can only be pending in registration format {REGISTRATION_FORMAT_VERSION}"
        )
    return value


def _string_of(key: str) -> Callable[[object], str]:
    return lambda value: string_item(value, key)


def _integer_of(key: str) -> Callable[[object], int]:
    return lambda value: require_integer(value, key, minimum=None)


def _optional_string_of(key: str) -> Callable[[object], str | None]:
    return lambda value: None if value is None else string_item(value, key)


def _strings(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    return tuple(string_item(item, key) for item in array_field(data, key))


def _as_array(value: object, key: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{key} is a JSON array, got {type(value).__name__}")
    return cast("list[object]", value)


def _decode_retrieval(data: Mapping[str, object]) -> Retrieval:
    expect_fields(data, ("kind", "embedding_model"), "the retrieval")
    return Retrieval(
        RetrievalKind(string_field(data, "kind")), optional_string_field(data, "embedding_model")
    )


def _decode_caps(data: Mapping[str, object]) -> RegisteredCaps:
    expect_fields(data, _CAPS_FIELDS, "the caps")
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


def _decode_roles(value: object) -> Roles:
    roles: list[RegisteredRole] = []
    for item in _as_array(value, "roles"):
        role = as_object(item, "a role")
        expect_fields(
            role, ("name", "configuration", "prompt_digests", "tool_surface_digest"), "a role"
        )
        prompts: list[tuple[str, str]] = []
        for entry in array_field(role, "prompt_digests"):
            prompt = as_object(entry, "a prompt digest")
            expect_fields(prompt, ("name", "digest"), "a prompt digest")
            prompts.append((string_field(prompt, "name"), string_field(prompt, "digest")))
        roles.append(
            RegisteredRole(
                string_field(role, "name"),
                decode_call_configuration(field_of(role, "configuration")),
                tuple(prompts),
                string_field(role, "tool_surface_digest"),
            )
        )
    return tuple(roles)


def _decode_system(item: object) -> RegisteredSystem:
    data = as_object(item, "a system")
    kind = SystemKind(string_field(data, "kind"))
    expect_fields(data, _SYSTEM_FIELDS[kind], f"the {kind.value} system")
    variant = _pendable(data, "variant", _string_of("variant"))
    retrieval = _decode_retrieval(object_field(data, "retrieval"))
    caps = _decode_caps(object_field(data, "caps"))
    match kind:
        case SystemKind.AGENT:
            return AgentSystem(variant, retrieval, _pendable(data, "roles", _decode_roles), caps)
        case SystemKind.RULES_ONLY:
            return RulesOnlySystem(variant, retrieval, caps)
        case SystemKind.SINGLE_SHOT:
            return SingleShotSystem(
                variant,
                retrieval,
                _pendable(data, "roles", _decode_roles),
                _only_pending(data, "query_protocol"),
                _pendable(data, "search_limit", _integer_of("search_limit")),
                caps,
            )
        case SystemKind.FULL_CONTEXT:
            return FullContextSystem(
                variant, retrieval, _pendable(data, "roles", _decode_roles), caps
            )
        case _:
            assert_never(kind)


def _decode_level(item: object) -> CorpusLevel:
    data = as_object(item, "a corpus level")
    expect_fields(data, ("name", "filler_tokens"), "a corpus level")
    return CorpusLevel(
        string_field(data, "name"),
        _pendable(data, "filler_tokens", _integer_of("filler_tokens")),
    )


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


def _decode_decision(value: object) -> GroupDecision:
    data = as_object(value, "a group's decision")
    expect_fields(data, ("run", "reason"), "a group's decision")
    return GroupDecision(_boolean_field(data, "run"), optional_string_field(data, "reason"))


def _decode_group(item: object) -> ConditionalGroup:
    data = as_object(item, "a conditional group")
    expect_fields(data, ("name", "rule", "decision"), "a conditional group")
    return ConditionalGroup(
        string_field(data, "name"),
        string_field(data, "rule"),
        _pendable(data, "decision", _decode_decision),
    )


def _decode_cell(item: object) -> RegisteredCell:
    data = as_object(item, "a cell")
    expect_fields(data, ("system", "condition", "level", "group"), "a cell")
    return RegisteredCell(
        SystemKind(string_field(data, "system")),
        string_field(data, "condition"),
        string_field(data, "level"),
        optional_string_field(data, "group"),
    )


def _decode_accounting(data: Mapping[str, object]) -> RunAccounting:
    expect_fields(
        data,
        ("repeats", "missing_run", "retry", "counted_attempt", "redispatch", "estimand"),
        "run accounting",
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
        _pendable(data, "redispatch", decode_redispatch_policy),
        string_field(data, "estimand"),
    )


def _decode_entry_schema(value: object) -> EntrySchema:
    data = as_object(value, "the entry schema")
    expect_fields(data, ("parser", "digest"), "the entry schema")
    return EntrySchema(string_field(data, "parser"), string_field(data, "digest"))


def _decode_stated_facts(data: Mapping[str, object]) -> StatedFactContract:
    expect_fields(
        data, ("composing_policy", "anchor_table", "entry_schema"), "the stated-fact contract"
    )
    policy = object_field(data, "composing_policy")
    expect_fields(policy, ("identifier", "digest"), "the composing policy")
    return StatedFactContract(
        ComposingPolicy(string_field(policy, "identifier"), string_field(policy, "digest")),
        string_field(data, "anchor_table"),
        _pendable(data, "entry_schema", _decode_entry_schema),
    )


def _decode_pair(item: object, key: str) -> tuple[SystemKind, SystemKind]:
    names = _as_array(item, key)
    if len(names) != 2:
        raise ValueError(f"{key} names two systems, got {len(names)}")
    first, second = (SystemKind(string_item(name, key)) for name in names)
    return first, second


def _strata(data: Mapping[str, object], key: str) -> tuple[StratumLevel, ...]:
    return tuple(StratumLevel(name) for name in _strings(data, key))


def _decode_comparison(item: object, what: str) -> Comparison:
    data = as_object(item, what)
    expect_fields(data, _COMPARISON_FIELDS, what)
    return Comparison(
        string_field(data, "check"),
        CheckReading(string_field(data, "reading")),
        string_field(data, "condition"),
        string_field(data, "level"),
        _decode_pair(field_of(data, "systems"), "systems"),
        _strata(data, "breakdowns"),
    )


def _decode_place(item: object) -> Place:
    data = as_object(item, "a place")
    expect_fields(data, ("condition", "level"), "a place")
    return Place(string_field(data, "condition"), string_field(data, "level"))


def _decode_level_contrast(item: object) -> LevelContrast:
    data = as_object(item, "a level contrast")
    expect_fields(
        data,
        ("system", "check", "reading", "condition", "levels", "breakdowns"),
        "a level contrast",
    )
    levels = _strings(data, "levels")
    if len(levels) != 2:
        raise ValueError(f"levels names two corpus levels, got {len(levels)}")
    return LevelContrast(
        SystemKind(string_field(data, "system")),
        string_field(data, "check"),
        CheckReading(string_field(data, "reading")),
        string_field(data, "condition"),
        (levels[0], levels[1]),
        _strata(data, "breakdowns"),
    )


def _decode_mechanism(value: object) -> MechanismMeasure:
    data = as_object(value, "the mechanism measure")
    expect_fields(data, ("name", "stages"), "the mechanism measure")
    return MechanismMeasure(string_field(data, "name"), _strings(data, "stages"))


def _decode_statistics(data: Mapping[str, object]) -> Statistics:
    expect_fields(
        data,
        (
            "confidence_percent",
            "seed",
            "resamples",
            "interval_method",
            "checks",
            "measures",
            "primary",
            "secondary",
            "descriptive",
            "level_contrasts",
            "mechanism",
            "headroom",
        ),
        "the statistics",
    )
    descriptive = object_field(data, "descriptive")
    expect_fields(
        descriptive,
        ("places", "pairs", "strata", "checks", "readings", "measures"),
        "the descriptive comparisons",
    )
    headroom = object_field(data, "headroom")
    expect_fields(headroom, ("reference", "check", "reading"), "the headroom procedure")
    return Statistics(
        integer_field(data, "confidence_percent"),
        integer_field(data, "seed"),
        integer_field(data, "resamples"),
        string_field(data, "interval_method"),
        _strings(data, "checks"),
        _strings(data, "measures"),
        _decode_comparison(field_of(data, "primary"), "the primary comparison"),
        tuple(
            _decode_comparison(item, "a secondary comparison")
            for item in array_field(data, "secondary")
        ),
        DescriptiveComparisons(
            tuple(_decode_place(item) for item in array_field(descriptive, "places")),
            tuple(_decode_pair(item, "pairs") for item in array_field(descriptive, "pairs")),
            _strata(descriptive, "strata"),
            _strings(descriptive, "checks"),
            tuple(CheckReading(name) for name in _strings(descriptive, "readings")),
            _strings(descriptive, "measures"),
        ),
        tuple(_decode_level_contrast(item) for item in array_field(data, "level_contrasts")),
        _pendable(data, "mechanism", _decode_mechanism),
        HeadroomProcedure(
            SystemKind(string_field(headroom, "reference")),
            string_field(headroom, "check"),
            CheckReading(string_field(headroom, "reading")),
        ),
    )


def _decode_inclusion(value: object) -> NotBuilt:
    data = as_object(value, "an inclusion state")
    expect_fields(data, ("not_built",), "an inclusion state")
    state = object_field(data, "not_built")
    expect_fields(state, ("reason", "development_number"), "a comparison that is not built")
    return NotBuilt(
        string_field(state, "reason"), optional_string_field(state, "development_number")
    )


def _decode_supporting(item: object) -> SupportingComparison:
    data = as_object(item, "a supporting comparison")
    expect_fields(
        data,
        (
            "identifier",
            "condition",
            "level",
            "systems",
            "other_model",
            "endpoint",
            "analysis",
            "inclusion",
        ),
        "a supporting comparison",
    )
    sides: list[SupportingSystem] = []
    for entry in array_field(data, "systems"):
        side = as_object(entry, "a supporting system")
        expect_fields(side, ("kind", "variant"), "a supporting system")
        sides.append(
            SupportingSystem(SystemKind(string_field(side, "kind")), string_field(side, "variant"))
        )
    if len(sides) != 2:
        raise ValueError(f"a supporting comparison names two systems, got {len(sides)}")
    return SupportingComparison(
        string_field(data, "identifier"),
        string_field(data, "condition"),
        string_field(data, "level"),
        (sides[0], sides[1]),
        _pendable(data, "other_model", _optional_string_of("other_model")),
        string_field(data, "endpoint"),
        string_field(data, "analysis"),
        _pendable(data, "inclusion", _decode_inclusion),
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


__all__ = [
    "decode_registration",
    "decode_registration_bytes",
    "encode_registration",
    "procedure_digest",
    "procedure_projection",
    "registration_bytes",
]
