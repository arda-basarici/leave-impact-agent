"""The truth manifest read back from its sealed bytes: the one decoder of the evaluator-only file.

The truth manifest holds every key, the authored facts, the briefs, the dated fact base and
the record of the model-written texts; reading it is reading the answer key. Its types and
its encoder live in ``artifacts`` ungated, since an encoder needs an assembled world as
input and gives a reader nothing. The decoder is the capability, so it sits alone in this
module and the import law gates the module by path, to readers it names one by one: the
generator's resume, the evaluator's world loading, and the audit sheet, the operator's
script that renders a sealed world for the hand audit. Nothing else may import it, in
the package or among the scripts and probes beside it, the validator above all, whose
role reads the world spec and never the key. No ``__init__`` names this module, so the
package's own import surface cannot hand it on. That is the split the object store's
writers have, by capability and not by file kind.

Bytes in, the value out, and only for bytes that are the value's canonical encoding: the
decoded manifest is re-encoded and compared, so one manifest is one byte sequence and the
digest a reader cites names what it graded against. Input that decodes and re-encodes
differently (a reordered field, a pretty-printed spelling, a repeated JSON key) is refused
as not canonical. Strict in the sibling decoders' manner besides: exactly the declared
fields, an id of the kind the field names, an enumeration member by its value, a date in
its one spelling, and every check the domain constructors make, since each record is
built through them. A refusal names the field, never a ``KeyError`` from inside.

Three fields may be absent, each because it joined the format after worlds were sealed,
and absent is read back as unavailable, never as empty: a key's expected conflicts and
its expected unknowns, each on its own (``null`` is neither and is refused); the record's
counters; a refusal's reasons. A manifest sealed before the record itself existed lacks
the ``materialization`` field altogether and is refused at the top level, naming it: no
reader consumes such a world and the codec carries no branch for it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

from leaveimpact.core.claims import (
    AssessmentReason,
    AuthorityRule,
    ConstraintKey,
    CoverageActionKind,
    ImpactKey,
    ImpactSubtype,
    UnknownReason,
    Verdict,
)
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.facts import Fact, FactBase, Gap
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    DocumentId,
    EmployeeId,
    LeaveId,
    ScenarioId,
    WorkItemId,
    is_numbered_id,
)
from leaveimpact.core.jsonshape import (
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
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.provenance import decode_model_configuration
from leaveimpact.core.refs import EntityRef, EvidenceRef, require_id
from leaveimpact.core.values_json import decode_ref, decode_value
from leaveimpact.core.worldtime import date_at
from leaveimpact.world.artifacts import (
    TRUTH_MANIFEST,
    TruthKey,
    TruthManifest,
    TruthScenario,
    encode_truth_manifest,
)
from leaveimpact.world.briefs import (
    Brief,
    CommentTarget,
    FillerBrief,
    ProseTarget,
    Register,
    RequiredFact,
    SectionTarget,
)
from leaveimpact.world.prose import (
    AssertionMode,
    FactRole,
    GuardName,
    MaterializationMetrics,
    MaterializationRecord,
    Namespace,
    Polarity,
    Proposition,
    ReasonCount,
    Refusal,
    RefusalReason,
    SurfaceForm,
    TargetRecord,
)
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    DistractorReason,
    ExpectedConflict,
    ExpectedImpact,
    ExpectedUnknown,
    ModifierName,
    NamedDistractor,
    ScenarioClassName,
    Tier,
)

_KEY_FIELDS = (
    "scenario_id",
    "tier",
    "scenario_class",
    "modifiers",
    "impacts",
    "constraints",
    "distractors",
    "required_sources",
)
_DERIVED_SETS = ("expected_conflicts", "expected_unknowns")
"""The key fields that joined after the first worlds were sealed; a key holds each or not."""


def decode_truth_manifest(content: bytes | str) -> TruthManifest:
    """The truth manifest ``content`` holds, accepted only if its re-encoding is ``content``.

    ``ValueError`` names what is malformed: a wrong discriminator, a field missing or
    surplus at any level (the top level first), a value of the wrong shape or kind, a
    record its domain constructor refuses, or bytes that are not the canonical encoding
    of what they decode to.
    """
    raw = content.encode("utf-8") if isinstance(content, str) else content
    data = as_object(json.loads(raw), "the truth manifest")
    found = field_of(data, "artifact")
    if found != TRUTH_MANIFEST:
        raise ValueError(f"the truth manifest is sealed as {TRUTH_MANIFEST}, got {found!r}")
    # The pool's briefs are named only in a manifest whose world owes the pool prose; a
    # manifest without the name was sealed by a generator that built no pool.
    present = ("filler_briefs",) if "filler_briefs" in data else ()
    expect_fields(
        data,
        ("artifact", "scenarios", "facts", "materialization") + present,
        "the truth manifest",
    )
    record = field_of(data, "materialization")
    manifest = TruthManifest(
        scenarios=tuple(_scenario(item) for item in array_field(data, "scenarios")),
        facts=_fact_base(object_field(data, "facts")),
        materialization=(
            None if record is None else _record(as_object(record, "the materialization record"))
        ),
        filler_briefs=tuple(
            _brief(item)
            for item in (array_field(data, "filler_briefs") if present else ())
        ),
    )
    if canonical_bytes(encode_truth_manifest(manifest)) != raw:
        raise ValueError(
            "the truth manifest's bytes are not its canonical encoding; a re-encoding of what "
            "they decode to differs, so they are not what the one byte rule writes"
        )
    return manifest


# --- Scenario rows and keys ---------------------------------------------------------------


def _scenario(item: object) -> TruthScenario:
    data = as_object(item, "a truth scenario")
    expect_fields(data, ("key", "authored_facts", "briefs"), "a truth scenario")
    return TruthScenario(
        key=_key(object_field(data, "key")),
        authored_facts=tuple(_fact(fact) for fact in array_field(data, "authored_facts")),
        briefs=tuple(_brief(brief) for brief in array_field(data, "briefs")),
    )


def _key(data: Mapping[str, object]) -> TruthKey:
    present = tuple(name for name in _DERIVED_SETS if name in data)
    expect_fields(data, _KEY_FIELDS + present, "a key")
    return TruthKey(
        scenario_id=_scenario_id(string_field(data, "scenario_id")),
        tier=Tier(string_field(data, "tier")),
        scenario_class=ScenarioClassName(string_field(data, "scenario_class")),
        modifiers=tuple(
            ModifierName(string_item(item, "modifiers")) for item in array_field(data, "modifiers")
        ),
        impacts=tuple(_expected_impact(item) for item in array_field(data, "impacts")),
        constraints=tuple(_constraint(item) for item in array_field(data, "constraints")),
        distractors=tuple(_distractor(item) for item in array_field(data, "distractors")),
        required_sources=tuple(
            Source(string_item(item, "required_sources"))
            for item in array_field(data, "required_sources")
        ),
        expected_conflicts=_derived_set(data, "expected_conflicts", _expected_conflict),
        expected_unknowns=_derived_set(data, "expected_unknowns", _expected_unknown),
    )


def _derived_set[T](
    data: Mapping[str, object], name: str, read: Callable[[object], T]
) -> tuple[T, ...] | None:
    # No field is a key sealed before the set existed: unavailable, never "none expected".
    # ``null`` is neither absent nor empty, and the array check refuses it by name.
    if name not in data:
        return None
    return tuple(read(item) for item in array_field(data, name))


def _expected_impact(item: object) -> ExpectedImpact:
    data = as_object(item, "an expected impact")
    expect_fields(data, ("key", "outcome", "must_assess"), "an expected impact")
    return ExpectedImpact(
        key=_impact_key(object_field(data, "key")),
        outcome=CoverageActionKind(string_field(data, "outcome")),
        must_assess=tuple(_authored(verdict) for verdict in array_field(data, "must_assess")),
    )


def _impact_key(data: Mapping[str, object]) -> ImpactKey:
    expect_fields(data, ("leave_id", "subtype", "artifact"), "an impact key")
    return ImpactKey(
        LeaveId(string_field(data, "leave_id")),
        ImpactSubtype(string_field(data, "subtype")),
        decode_ref(object_field(data, "artifact")),
    )


def _authored(item: object) -> AuthoredVerdict:
    data = as_object(item, "an authored verdict")
    expect_fields(data, ("employee_id", "verdict", "reasons"), "an authored verdict")
    return AuthoredVerdict(
        _employee(data, "employee_id"),
        Verdict(string_field(data, "verdict")),
        tuple(
            AssessmentReason(string_item(item, "reasons")) for item in array_field(data, "reasons")
        ),
    )


def _constraint(item: object) -> ConstraintKey:
    data = as_object(item, "a constraint")
    expect_fields(data, ("clause_id", "applies_to"), "a constraint")
    return ConstraintKey(
        ClauseId(string_field(data, "clause_id")), decode_ref(object_field(data, "applies_to"))
    )


def _distractor(item: object) -> NamedDistractor:
    data = as_object(item, "a distractor")
    expect_fields(data, ("entity", "reason"), "a distractor")
    return NamedDistractor(
        decode_ref(object_field(data, "entity")), DistractorReason(string_field(data, "reason"))
    )


def _expected_conflict(item: object) -> ExpectedConflict:
    data = as_object(item, "an expected conflict")
    expect_fields(
        data, ("entity", "predicate", "resolved_value", "authority_rule"), "an expected conflict"
    )
    name = PredicateName(string_field(data, "predicate"))
    return ExpectedConflict(
        decode_ref(object_field(data, "entity")),
        name,
        decode_value(object_field(data, "resolved_value"), predicate(name).value_spec),
        AuthorityRule(string_field(data, "authority_rule")),
    )


def _expected_unknown(item: object) -> ExpectedUnknown:
    data = as_object(item, "an expected unknown")
    expect_fields(
        data, ("employee_id", "subject", "required_fact", "reason"), "an expected unknown"
    )
    return ExpectedUnknown(
        _employee(data, "employee_id"),
        decode_ref(object_field(data, "subject")),
        PredicateName(string_field(data, "required_fact")),
        UnknownReason(string_field(data, "reason")),
    )


# --- Facts --------------------------------------------------------------------------------


def _fact_base(data: Mapping[str, object]) -> FactBase:
    expect_fields(data, ("facts", "gaps"), "the fact base")
    return FactBase(
        tuple(_fact(item) for item in array_field(data, "facts")),
        tuple(_gap(item) for item in array_field(data, "gaps")),
    )


def _fact(item: object) -> Fact:
    data = as_object(item, "a fact")
    expect_fields(data, ("subject", "predicate", "value", "evidence", "observable_from"), "a fact")
    name = PredicateName(string_field(data, "predicate"))
    return Fact(
        decode_ref(object_field(data, "subject")),
        name,
        decode_value(object_field(data, "value"), predicate(name).value_spec),
        _evidence(object_field(data, "evidence")),
        date_at(string_field(data, "observable_from"), "observable_from"),
    )


def _gap(item: object) -> Gap:
    data = as_object(item, "a gap")
    expect_fields(data, ("subject", "predicate", "evidence", "observable_from"), "a gap")
    return Gap(
        decode_ref(object_field(data, "subject")),
        PredicateName(string_field(data, "predicate")),
        _evidence(object_field(data, "evidence")),
        date_at(string_field(data, "observable_from"), "observable_from"),
    )


def _evidence(data: Mapping[str, object]) -> EvidenceRef:
    expect_fields(data, ("source", "target", "field"), "an evidence reference")
    return EvidenceRef(
        Source(string_field(data, "source")),
        decode_ref(object_field(data, "target")),
        optional_string_field(data, "field"),
    )


# --- Briefs -------------------------------------------------------------------------------


def _brief(item: object) -> Brief:
    data = as_object(item, "a brief")
    filler = ("fictional",) if "fictional" in data else ()
    expect_fields(
        data, ("target", "register", "required", "allowed", "namespace") + filler, "a brief"
    )
    target = _target(object_field(data, "target"))
    required = tuple(_required(fact) for fact in array_field(data, "required"))
    allowed = tuple(_fact(fact) for fact in array_field(data, "allowed"))
    namespace = _namespace(object_field(data, "namespace"))
    register = Register(string_field(data, "register"))
    if not filler:
        return Brief(target, required, allowed, namespace, register)
    return FillerBrief(
        target,
        required,
        allowed,
        namespace,
        register,
        fictional=tuple(
            decode_ref(as_object(item, "a fictional entity"))
            for item in array_field(data, "fictional")
        ),
    )


def _required(item: object) -> RequiredFact:
    data = as_object(item, "a required fact")
    expect_fields(data, ("fact", "role"), "a required fact")
    return RequiredFact(_fact(field_of(data, "fact")), FactRole(string_field(data, "role")))


def _target(data: Mapping[str, object]) -> ProseTarget:
    kind = string_field(data, "kind")
    if kind == "comment":
        expect_fields(
            data,
            ("kind", "id", "work_item_id", "position", "world_date", "author_id"),
            "a comment target",
        )
        return CommentTarget(
            CommentId(_id(data, "id", EntityKind.COMMENT)),
            WorkItemId(_id(data, "work_item_id", EntityKind.WORK_ITEM)),
            integer_field(data, "position"),
            date_at(string_field(data, "world_date"), "world_date"),
            _employee(data, "author_id"),
        )
    if kind == "section":
        expect_fields(data, ("kind", "id", "document_id", "position"), "a section target")
        return SectionTarget(
            ClauseId(_id(data, "id", EntityKind.CLAUSE)),
            DocumentId(_id(data, "document_id", EntityKind.DOCUMENT)),
            integer_field(data, "position"),
        )
    raise ValueError(f"a prose target is a comment or a section, got kind {kind!r}")


def _namespace(data: Mapping[str, object]) -> Namespace:
    expect_fields(data, ("forms", "dates", "numbers"), "a namespace")
    return Namespace(
        forms=tuple(_form(item) for item in array_field(data, "forms")),
        dates=tuple(
            date_at(string_item(item, "dates"), "a date") for item in array_field(data, "dates")
        ),
        numbers=tuple(_integer_item(item, "numbers") for item in array_field(data, "numbers")),
    )


def _form(item: object) -> SurfaceForm:
    data = as_object(item, "a surface form")
    expect_fields(data, ("kind", "id", "form"), "a surface form")
    return SurfaceForm(
        string_field(data, "kind"), string_field(data, "id"), string_field(data, "form")
    )


# --- The materialization record -------------------------------------------------------------


def _record(data: Mapping[str, object]) -> MaterializationRecord:
    # The counters joined the record after the first prose worlds were sealed, so their
    # field is the one the decoder allows to be absent; present, it is read whole.
    counted = "metrics" in data
    expect_fields(
        data,
        ("writer", "checker", "prompt_digests", "attempt_cap", "targets")
        + (("metrics",) if counted else ()),
        "the materialization record",
    )
    return MaterializationRecord(
        writer=decode_model_configuration(object_field(data, "writer")),
        checker=decode_model_configuration(object_field(data, "checker")),
        prompt_digests=tuple(_prompt(item) for item in array_field(data, "prompt_digests")),
        attempt_cap=integer_field(data, "attempt_cap"),
        targets=tuple(_target_record(item) for item in array_field(data, "targets")),
        metrics=_metrics(object_field(data, "metrics")) if counted else None,
    )


def _metrics(data: Mapping[str, object]) -> MaterializationMetrics:
    # The counters a record holds are the ones its run had: the type refuses an unknown
    # name, a repeat or a departure from the declared order, and asks nothing of a name
    # a later stage added.
    return MaterializationMetrics(tuple((name, integer_field(data, name)) for name in data))


def _prompt(item: object) -> tuple[str, str]:
    data = as_object(item, "a prompt digest")
    expect_fields(data, ("name", "digest"), "a prompt digest")
    return (string_field(data, "name"), string_field(data, "digest"))


def _target_record(item: object) -> TargetRecord:
    data = as_object(item, "a target record")
    expect_fields(
        data,
        (
            "target_id",
            "attempts",
            "refusals",
            "request_digest",
            "accepted_body_digest",
            "propositions",
        ),
        "a target record",
    )
    return TargetRecord(
        target_id=string_field(data, "target_id"),
        attempts=integer_field(data, "attempts"),
        refusals=tuple(_refusal(entry) for entry in array_field(data, "refusals")),
        request_digest=string_field(data, "request_digest"),
        accepted_body_digest=string_field(data, "accepted_body_digest"),
        propositions=tuple(_proposition(entry) for entry in array_field(data, "propositions")),
    )


def _refusal(item: object) -> Refusal:
    data = as_object(item, "a refusal")
    # Reasons joined the refusal after the measurement world was sealed; their field is the
    # one allowed to be absent, and absent decodes as unavailable, never as no reasons.
    reasoned = "reasons" in data
    expect_fields(
        data, ("attempt", "guard", "count") + (("reasons",) if reasoned else ()), "a refusal"
    )
    return Refusal(
        integer_field(data, "attempt"),
        GuardName(string_field(data, "guard")),
        integer_field(data, "count"),
        tuple(_reason(entry) for entry in array_field(data, "reasons")) if reasoned else None,
    )


def _reason(item: object) -> ReasonCount:
    data = as_object(item, "a reason count")
    expect_fields(data, ("reason", "count"), "a reason count")
    return (RefusalReason(string_field(data, "reason")), integer_field(data, "count"))


def _proposition(item: object) -> Proposition:
    data = as_object(item, "a proposition")
    expect_fields(
        data, ("subject", "predicate", "value", "polarity", "assertion_mode"), "a proposition"
    )
    name = PredicateName(string_field(data, "predicate"))
    raw_subject = field_of(data, "subject")
    subject: EntityRef | None = None
    if raw_subject is not None:
        subject = decode_ref(as_object(raw_subject, "a proposition's subject"))
    return Proposition(
        subject,
        name,
        decode_value(object_field(data, "value"), predicate(name).value_spec),
        Polarity(string_field(data, "polarity")),
        AssertionMode(string_field(data, "assertion_mode")),
    )


# --- Ids and scalars ----------------------------------------------------------------------


def _id(data: Mapping[str, object], key: str, kind: EntityKind) -> str:
    return require_id(kind, string_field(data, key))


def _employee(data: Mapping[str, object], key: str) -> EmployeeId:
    return EmployeeId(_id(data, key, EntityKind.EMPLOYEE))


def _scenario_id(value: str) -> ScenarioId:
    # A scenario is not an entity kind, so its namespace is checked here, as the sibling
    # decoders check it.
    if not is_numbered_id(value) or not value.startswith("scenario_"):
        raise ValueError(f"{value!r} is not a scenario_ id")
    return ScenarioId(value)


def _integer_item(value: object, key: str) -> int:
    # bool is an int in Python; JSON's true is not a number a namespace admits.
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"an item of {key} is an integer, got {type(value).__name__}")
    return value


__all__ = ["decode_truth_manifest"]
