"""A run's provenance read from the preregistration, so that nothing the registration fixes
reaches a run from a literal.

The harness executes under a committed registration (the investigator milestone's sixth
build step, rulings 1 and 5). What a run records of it, the outage it was assigned with the
schedule's digest, the caps and the variant, is taken from the decoded registration here
and from nowhere else. Where the registration names something this code computes or
declares, the two are compared and a difference refuses the run: the outage protocol and
the frozen prefetch against ``core``'s, the rules-only reporting policy against the one
declared beside the policy. Neither side is substituted for the other, since a run that
quietly used the current value would cite a registration it did not follow.

A pending value blocks only an execution that needs it: the rules-only baseline runs while
the model systems' entries are still pending, and under a draft, whose runs the evaluator
labels development. What only a composition root knows, the harness revision, the commit
the registration is read at and the price table, arrives as arguments; nothing here reads
a file or the repository.

The agent and the single-shot baseline get their own functions with their systems, their
provenance holding what a model system records.
"""

from __future__ import annotations

from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.report import REPORTING_POLICY
from leaveimpact.core.prefetch import PREFETCH_PROTOCOL, prefetch_rule
from leaveimpact.core.registration import (
    OUTAGE_PROTOCOL,
    Injection,
    Pending,
    RegisteredArm,
    Registration,
    RulesOnlySystem,
    schedule_digest,
)
from leaveimpact.core.run_record import (
    BASE_CORPUS_LEVEL,
    OutageAssignment,
    PricingBasis,
    SystemKind,
)
from leaveimpact.core.run_timing import HarnessRevision


def rules_only_provenance(
    registration: Registration,
    condition: str,
    *,
    harness: HarnessRevision,
    preregistration_commit: str,
    pricing: PricingBasis,
) -> RunProvenance:
    """The provenance of a rules-only run under ``condition``, a registered condition's
    identifier, as ``registration`` fixes it.

    Raises ``ValueError`` when the registration cannot be executed as written: no
    rules-only system or a pending variant, an arm that is not registered, or an outage
    protocol, a prefetch or a reporting policy that differs from this code's.
    """
    system = registration.system(SystemKind.RULES_ONLY)
    if not isinstance(system, RulesOnlySystem):
        raise ValueError("the registration names no rules-only system")
    if isinstance(system.variant, Pending):
        raise ValueError(
            f"the rules-only variant is pending ({system.variant.awaiting}), and a run records it"
        )
    if system.policy != REPORTING_POLICY:
        raise ValueError(
            f"the registered reporting policy is {system.policy}, this harness reports under "
            f"{REPORTING_POLICY}"
        )
    return RunProvenance(
        outage=_assignment(registration, SystemKind.RULES_ONLY, condition),
        # The baseline reads no document, so it runs the same at every corpus level; the
        # registration names the levels once it holds them, and until then this is the one.
        corpus_level=BASE_CORPUS_LEVEL,
        harness=harness,
        preregistration_commit=preregistration_commit,
        caps=registration.caps.caps,
        pricing=pricing,
        variant=system.variant,
    )


def _assignment(registration: Registration, system: SystemKind, condition: str) -> OutageAssignment:
    """What ``system`` is assigned under ``condition``, once the registered schedule and
    prefetch are the ones this code executes."""
    _require_executable_outage(registration)
    _require_registered_prefetch(registration)
    registered = registration.outage.condition(condition)
    if registered is None or RegisteredArm(system, condition) not in registration.arms:
        raise ValueError(f"no arm is registered for {system.value} under {condition!r}")
    return OutageAssignment(registered.unreachable, schedule_digest(registration.outage))


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


__all__ = ["rules_only_provenance"]
