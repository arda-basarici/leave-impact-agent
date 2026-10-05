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

The agent and the single-shot baseline get their own functions with their systems, their
provenance holding what a model system records.
"""

from __future__ import annotations

from leaveimpact.agent.composer import composing_policy
from leaveimpact.agent.export import RunProvenance
from leaveimpact.core.anchors import anchor_table_digest
from leaveimpact.core.prefetch import PREFETCH_PROTOCOL, prefetch_rule
from leaveimpact.core.registration import (
    OUTAGE_PROTOCOL,
    Injection,
    Registration,
    RulesOnlySystem,
    blocking,
    schedule_digest,
)
from leaveimpact.core.run_record import OutageAssignment, PricingBasis, SystemKind
from leaveimpact.core.run_timing import HarnessRevision


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


__all__ = ["rules_only_provenance"]
