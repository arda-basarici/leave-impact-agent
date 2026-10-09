"""A run's provenance read from the preregistration, so that nothing the registration fixes
reaches a run from a literal.

The harness executes under a committed registration (the investigator milestone's sixth
build step, rulings 1 and 5, and the contract step's rulings on the registration). What a
run records of it, the outage it was assigned with the schedule's digest, the corpus level,
the caps and the variant, is taken from the decoded registration here and from nowhere
else. Where the registration names something this code computes, the two are compared and
a difference refuses the run: the outage protocol and the frozen prefetch against
``core``'s, the composing policy against the one the composer computes, the anchor table's
digest against ``core``'s. Neither side is substituted for the other, since a run that
quietly used the current value would cite a registration it did not follow.

A run is of a registered cell: its system under a condition at a corpus level. A cell that
belongs to a conditional group is executed only once the group is decided as run. A pending
value blocks only an execution that needs it (``core.registration.blocking``): the
rules-only baseline runs while the model systems' entries are still pending, and under a
draft, whose runs the evaluator labels development. What only a composition root knows, the
harness revision, the commit the registration is read at and the price table, arrives as
arguments; nothing here reads a file or the repository.

The agent's provenance is every frozen input the admission does not copy, and under a draft
the registration holds some of them pending (the graph step, fork 14): the roles, the
attribution table, the re-dispatch policy and the entry schema. A draft run uses this code's
current value for each and records it, so the export says what the run ran under and the
evaluator labels it development as it does every draft run; the development table and
policy live here, since the graph asserts a table on the first model call and the fixtures
are no production home. A registration past its draft may hold nothing an agent run needs
pending, and every value it binds is compared as the baseline's are.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.composer import composing_policy
from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.fact_entries import refused_by
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.surface import surface_digest
from leaveimpact.agent.worker import WorkerConfiguration
from leaveimpact.core.anchors import anchor_table_digest
from leaveimpact.core.attribution import (
    AttributionRow,
    AttributionTable,
    Match,
    ObservationKind,
    RedispatchPolicy,
    attribution_table_digest,
)
from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.model_calls import AttributionKind, RefusedBy
from leaveimpact.core.prefetch import PREFETCH_PROTOCOL, prefetch_rule
from leaveimpact.core.registration import (
    OUTAGE_PROTOCOL,
    AgentSystem,
    Injection,
    Pending,
    RegisteredRole,
    Registration,
    Roles,
    RulesOnlySystem,
    blocking,
    schedule_digest,
)
from leaveimpact.core.run_ending import ClaimAuthor
from leaveimpact.core.run_record import (
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    PricingSelection,
    System,
    SystemKind,
)
from leaveimpact.core.run_timing import HarnessRevision
from leaveimpact.core.tools import Role


def rules_only_provenance(
    registration: Registration,
    condition: str,
    level: str,
    *,
    harness: HarnessRevision,
    preregistration_commit: str,
    pricing: PricingBasis,
) -> RunProvenance:
    """The provenance of a rules-only run under ``condition`` at the corpus level ``level``,
    each a registered name, as ``registration`` fixes it.

    The baseline reads no document, so it runs the same at every level; it is still run
    once per registered cell, so that each cell has its own exports.

    Raises ``ValueError`` when the registration cannot be executed as written: no
    rules-only system or a pending variant, a cell that is not registered or whose group is
    not decided as run, or an outage protocol, a prefetch, a composing policy or an anchor
    table that differs from this code's.
    """
    system = registration.system(SystemKind.RULES_ONLY)
    if not isinstance(system, RulesOnlySystem):
        raise ValueError("the registration names no rules-only system")
    pending = blocking(registration, SystemKind.RULES_ONLY)
    if pending or not isinstance(system.variant, str):
        raise ValueError(
            f"the rules-only system has a value pending ({', '.join(pending)}), and a run "
            "records it"
        )
    _require_registered_composing(registration)
    return RunProvenance(
        outage=_assignment(registration, SystemKind.RULES_ONLY, condition, level),
        corpus_level=level,
        harness=harness,
        preregistration_commit=preregistration_commit,
        caps=system.caps.caps,
        pricing=pricing,
        variant=system.variant,
    )


def _assignment(
    registration: Registration, system: SystemKind, condition: str, level: str
) -> OutageAssignment:
    """What ``system`` is assigned under ``condition`` at ``level``, once the registered
    schedule and prefetch are the ones this code executes and the cell is one to run."""
    _require_executable_outage(registration)
    _require_registered_prefetch(registration)
    registered = registration.outage.condition(condition)
    cell = registration.cell(system, condition, level)
    if registered is None or cell is None:
        raise ValueError(
            f"no cell is registered for {system.value} under {condition!r} at {level!r}"
        )
    if not registration.runs(cell):
        raise ValueError(
            f"the cell of {system.value} under {condition!r} at {level!r} belongs to the "
            f"group {cell.group}, which is not decided as run"
        )
    return OutageAssignment(registered.unreachable, schedule_digest(registration.outage))


def _require_registered_composing(registration: Registration) -> None:
    stated = registration.stated_facts
    computed = composing_policy()
    if stated.composing_policy != computed:
        raise ValueError(
            f"the registered composing policy is {stated.composing_policy}, this harness "
            f"composes under {computed}"
        )
    # The composing specification holds the same function's value, so this also holds the
    # specification's anchor entry to the registered field.
    if stated.anchor_table != anchor_table_digest():
        raise ValueError(
            f"the registered anchor table is {stated.anchor_table}, this harness guards "
            f"with {anchor_table_digest()}"
        )


def _require_executable_outage(registration: Registration) -> None:
    outage = registration.outage
    if outage.protocol != OUTAGE_PROTOCOL:
        raise ValueError(
            f"the registered outage protocol is {outage.protocol}, this harness injects "
            f"under {OUTAGE_PROTOCOL}"
        )
    if outage.injection is not Injection.WHOLE_RUN_AT_READ_PORT:
        raise ValueError(f"this harness injects whole-run at the read port, got {outage.injection}")


def _require_registered_prefetch(registration: Registration) -> None:
    registered = registration.prefetch
    rule = prefetch_rule()
    declared = (registered.identifier, registered.protocol_version, registered.digest)
    computed = (rule.identifier, PREFETCH_PROTOCOL[1], rule.digest)
    if declared != computed:
        raise ValueError(
            f"the registered prefetch is {declared}, this harness plans {computed} "
            "(identifier, protocol version, digest)"
        )


# --- The agent under a draft ---------------------------------------------------------------

NOVA_TOOL_USE_CUT = "Model produced invalid sequence as part of ToolUse"
"""The one evidenced message signature: a Nova tool call cut at the output limit, relayed as
a model error, read as the model's behaviour (the acceptance spike)."""

DEVELOPMENT_ATTRIBUTION_TABLE = AttributionTable(
    (
        AttributionRow(
            "registered-stop-reason",
            Match(ObservationKind.COMPLETE_RESPONSE),
            AttributionKind.BEHAVIOUR,
        ),
        AttributionRow(
            "stream", Match(ObservationKind.BROKEN_STREAM), AttributionKind.INFRASTRUCTURE
        ),
        AttributionRow(
            "nova-cut-tool-use",
            Match(ObservationKind.SERVICE_ERROR, message_signatures=frozenset({NOVA_TOOL_USE_CUT})),
            AttributionKind.BEHAVIOUR,
        ),
        AttributionRow(
            "unmatched",
            Match(ObservationKind.SERVICE_ERROR),
            AttributionKind.INFRASTRUCTURE,
            redispatch=True,
            unmatched=True,
        ),
        AttributionRow(
            "gave_up", Match(ObservationKind.CLIENT_ERROR), AttributionKind.INFRASTRUCTURE
        ),
        AttributionRow(
            "never_sent",
            Match(ObservationKind.REFUSED_BEFORE_SEND),
            AttributionKind.INFRASTRUCTURE,
        ),
    )
)
"""The harness's current reading of what a dispatch observes, the value a development run
records while the registration holds the table pending: a complete response is the
model's behaviour under any stop reason; a broken stream, a client that gave up and a
request never sent are infrastructure; a service error is infrastructure and re-dispatched
unless it carries the one evidenced signature of the model's own doing. The rows are the
fixtures' since the contract step, so every fixture record names this digest; the freeze
registers the table it measures under, which may differ."""

DEVELOPMENT_REDISPATCH_POLICY = RedispatchPolicy(3, 1_000)
"""At most three dispatches of a logical call, a second between them, while the registration
holds the policy pending. The values are a guess with no measured basis behind them (the
step-11 build notes), and the freeze sets the registered ones."""


@dataclass(frozen=True, slots=True)
class RoleFilling:
    """What the composition root supplies for the investigator role: the model and settings
    its calls run under, the rate they are priced under, and the base model its requests are
    counted against. Under a draft the registration holds the role pending and these are
    recorded; under a bound registration they are compared with the registered role."""

    name: str
    configuration: CallConfiguration
    pricing: PricingSelection
    counting_model_id: str


def effective_rules(registration: Registration) -> Rules:
    """The attribution table and re-dispatch policy a run of ``registration`` is read under:
    the registered ones, or the development values above where the registration holds
    them pending, which only a draft can (the registration type refuses a frozen one with
    anything pending but its world)."""
    table = registration.attribution
    policy = registration.run_accounting.redispatch
    return Rules(
        DEVELOPMENT_ATTRIBUTION_TABLE if isinstance(table, Pending) else table,
        DEVELOPMENT_REDISPATCH_POLICY if isinstance(policy, Pending) else policy,
    )


def agent_provenance(
    registration: Registration,
    condition: str,
    level: str,
    *,
    preregistration_commit: str,
    pricing: PricingBasis,
    role: RoleFilling,
) -> WorkerConfiguration:
    """Every frozen input of an investigator run under ``condition`` at ``level`` but the
    five the admission copies, as ``registration`` fixes them and this code supplies them:
    what a development export records (the graph step, fork 14).

    Where the registration binds a value it is compared with this code's or with ``role``
    and a difference refuses the run: the variant, the retrieval, the caps and the retry
    rule are taken as registered; the outage protocol, the prefetch, the composing policy
    and the anchor table must be the ones this code executes; a registered role must be
    the one ``role`` and the shipped assets give; a registered entry schema must be the
    fact parser's; a registered table and policy are the rules. Where the registration is
    a draft holding a value pending, this code's current value is used and recorded: the
    role from ``role``, the prompt assets and the investigator's tool surface; the
    attribution table and the re-dispatch policy from the development values; the entry
    schema from the fact parser. A pending value is a draft's by construction: the
    registration type refuses a frozen or bound registration holding anything pending but
    its world, so no check here asks the status.

    Raises ``ValueError`` naming what refuses: no agent system or a pending variant, a
    cell not registered or not decided as run, or any of the differences above.
    """
    system = registration.system(SystemKind.AGENT)
    if not isinstance(system, AgentSystem):
        raise ValueError("the registration names no agent system")
    if not isinstance(system.variant, str):
        raise ValueError("the agent's variant is pending, and a run records it")
    _require_registered_composing(registration)
    rules = effective_rules(registration)
    assert rules.table is not None and rules.redispatch is not None
    registered_role = _agent_role(system, role)
    parser = _entry_schema(registration)
    return WorkerConfiguration(
        preregistration_commit=preregistration_commit,
        system=System(SystemKind.AGENT, system.variant),
        retrieval=system.retrieval,
        caps=system.caps.caps,
        model_configurations=((registered_role.name, registered_role.configuration),),
        pricing_selections=((registered_role.name, role.pricing),),
        counting_identifiers=((registered_role.name, registered_role.counting_model_id),),
        pricing=pricing,
        prompt_digests=tuple(
            (registered_role.name, name, digest) for name, digest in registered_role.prompt_digests
        ),
        tool_surface_digests=((registered_role.name, registered_role.tool_surface_digest),),
        attribution_table=attribution_table_digest(rules.table),
        redispatch=rules.redispatch,
        retry=registration.run_accounting.retry,
        prefetch_rule=_registered_prefetch_rule(registration),
        composing_policy=composing_policy(),
        claim_author=ClaimAuthor.RULES,
        parser=parser,
        outage=_assignment(registration, SystemKind.AGENT, condition, level),
        corpus_level=level,
    )


def _agent_role(system: AgentSystem, filling: RoleFilling) -> RegisteredRole:
    """The one role the run records: the code's under a draft that holds the roles pending,
    else the registered one, which must equal the code's."""
    assets = load_prompt_assets()
    current = RegisteredRole(
        filling.name,
        filling.configuration,
        assets.digests(),
        surface_digest(Role.INVESTIGATOR),
        filling.counting_model_id,
    )
    if isinstance(system.roles, Pending):
        return current
    if [role.name for role in system.roles] != [current.name]:
        raise ValueError(
            f"the registered agent roles are {_role_names(system.roles)}, this harness runs "
            f"one, {current.name}"
        )
    (registered,) = system.roles
    differing = [
        f.name
        for f in fields(RegisteredRole)
        if getattr(registered, f.name) != getattr(current, f.name)
    ]
    if differing:
        raise ValueError(
            f"the registered {current.name} role differs from this harness's on "
            f"{', '.join(differing)}"
        )
    return current


def _entry_schema(registration: Registration) -> RefusedBy:
    current = refused_by()
    registered = registration.stated_facts.entry_schema
    if isinstance(registered, Pending):
        return current
    if (registered.parser, registered.digest) != (current.parser, current.schema_digest):
        raise ValueError(
            f"the registered entry schema is {registered.parser} at {registered.digest}, this "
            f"harness parses with {current.parser} at {current.schema_digest}"
        )
    return current


def _registered_prefetch_rule(registration: Registration) -> PrefetchRule:
    _require_registered_prefetch(registration)
    return PrefetchRule(registration.prefetch.identifier, registration.prefetch.digest)


def _role_names(roles: Roles) -> str:
    return ", ".join(role.name for role in roles) or "none"


__all__ = [
    "DEVELOPMENT_ATTRIBUTION_TABLE",
    "DEVELOPMENT_REDISPATCH_POLICY",
    "NOVA_TOOL_USE_CUT",
    "RoleFilling",
    "agent_provenance",
    "effective_rules",
    "rules_only_provenance",
]
