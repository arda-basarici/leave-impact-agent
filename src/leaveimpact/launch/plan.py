"""The launcher's pure half: the frozen inputs of a run from the registration, the price
table, the cell and the scenario; the work command's cell flags from the same plan; and
the next step of the lifecycle from an attempt's state.

*The plan.* A model system's role is filled from the registered role alone: its model
configuration, its counting model and its context allowance as the registration binds them,
priced under the committed table's key for that model in the region given. The registration
must name the roles; a draft holding them pending is refused here, since a launcher that
invented a filling would admit a run the registration does not describe. The provenance
functions are the work command's (``agent.registered``), so the admission's inputs and the
worker's effective configuration are one computation run twice, and the worker's comparison
at the claim passes by construction. The reservation is the caps' ceiling
(``core.pricing.run_reservation``), ``None`` for rules only, which calls no model.

*The cell flags.* The work command's line restates the cell and the role as flags, and the
worker refuses the claim where the line composes something other than the admission. The
flags are derived from the plan here, so a workflow passes them verbatim and never spells
a model id twice; a registered setting the line cannot state is refused by name.

*The next step.* Three ending states a work command leaves (the step's fork 1 as amended):
an attempt left open, recovered as the same attempt under a bound of the launcher's own;
an attempt awaiting a human's approval, where the job ends and nothing is re-sent; and a
closed attempt, published and inventoried. The decision reads the attempt's state from the
log and not the worker's printed ending, so it serves a completion the transport reported
uncertainly as well as a clean one; the caller establishes that no process still owns the
attempt before it acts on a recovery. The decision also takes the approval policy the run
was dispatched under, since the log alone cannot tell a pause from a death at the same
position: an approval requested and not given is a human's wait under the human policy and
a process gone under the automatic one, which a recovering worker completes with no new
send (the group's external read). ``RECOVERY_BOUND`` bounds recoveries on one attempt over
its whole history, the count the log's fold carries and the transition's ``next_claim``
defines (the step-14 review's finding: the count was the dispatching job's, so every
continuation granted the bound again); the registered re-dispatch policy bounds dispatches
of one call and the retry rule bounds attempts of one run, and none stands in for another.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.agent.log_transition import AttemptState, ClaimKind, next_claim
from leaveimpact.agent.registered import (
    RoleFilling,
    effective_rules,
    model_system_provenance,
    registered_filling,
    rules_only_configuration,
)
from leaveimpact.agent.worker import ApprovalPolicy
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.input_bound import output_maximum
from leaveimpact.core.pricing import PriceTable, basis_for, run_reservation
from leaveimpact.core.registration import Registration
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.worldtime import RunContext
from leaveimpact.world.scenario import ScenarioSpec

RECOVERY_BOUND = 2
"""How many recoveries an attempt may hold in its log before the launcher holds the run for
an operator instead of sending work again: a development value of the launcher's own,
stated in the development protocol and registered nowhere."""

STATED_SETTINGS = ("max_tokens", "temperature", "top_p")
"""The inference settings the work command's line can state, as flags of the same names."""


@dataclass(frozen=True, slots=True)
class RunCell:
    """The registered cell a run belongs to: its system, condition and corpus level."""

    system: SystemKind
    condition: str
    level: str


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    """What one admission records and the work command restates: the frozen inputs, the
    role the system runs (``None`` for rules only), the cell, the registration's commit and
    the region the clients call from."""

    inputs: FrozenInputs
    role: RoleFilling | None
    cell: RunCell
    registration_commit: str
    region: str


def plan_run(
    registration: Registration,
    *,
    registration_commit: str,
    prices: PriceTable,
    cell: RunCell,
    spec: ScenarioSpec,
    world_version: WorldVersion,
    run_id: str,
    attempt: int,
    region: str,
    billing_mode: str = "on_demand",
) -> LaunchPlan:
    """The plan of ``attempt`` of ``run_id``, a run of ``spec`` on ``world_version`` in
    ``cell``, under ``registration`` at ``registration_commit`` and ``prices``.

    ``ValueError`` names what refuses: a cell the registration does not run, roles the
    registration holds pending, a system registered with other than one role, a price
    table without the role's rates, and whatever the provenance functions refuse."""
    context = RunContext(spec.id, world_version, spec.leave_id, spec.now, spec.reference_timezone)
    if cell.system is SystemKind.RULES_ONLY:
        configuration = rules_only_configuration(
            registration,
            cell.condition,
            cell.level,
            preregistration_commit=registration_commit,
            pricing=basis_for(prices, ()),
        )
        return LaunchPlan(
            configuration.freeze(run_id, attempt, context, None),
            None,
            cell,
            registration_commit,
            region,
        )
    role = registered_filling(registration, cell.system, region, billing_mode)
    basis = basis_for(prices, (role.pricing,))
    configuration = model_system_provenance(
        registration,
        cell.system,
        cell.condition,
        cell.level,
        preregistration_commit=registration_commit,
        pricing=basis,
        role=role,
    )
    rules = effective_rules(registration)
    assert rules.redispatch is not None, "a model system is read under a re-dispatch policy"
    reservation = run_reservation(
        configuration.caps,
        rules.redispatch,
        [(output_maximum(role.configuration), role.pricing)],
        basis,
    )
    return LaunchPlan(
        configuration.freeze(run_id, attempt, context, reservation),
        role,
        cell,
        registration_commit,
        region,
    )


def work_arguments(plan: LaunchPlan) -> tuple[str, ...]:
    """The work command's flags for the cell and the role of ``plan``, in the line's own
    spelling: what a send appends after the execution's own flags (the attempt, the nonce,
    the launch identity, the registration and price files, the approval). ``ValueError``
    for a registered setting the line cannot state."""
    cell = plan.cell
    arguments = [
        "--system",
        cell.system.value,
        "--condition",
        cell.condition,
        "--level",
        cell.level,
        "--registration-commit",
        plan.registration_commit,
        "--region",
        plan.region,
    ]
    role = plan.role
    if role is None:
        return tuple(arguments)
    settings = {setting.name: setting.value for setting in role.configuration.settings}
    unstated = sorted(set(settings) - set(STATED_SETTINGS))
    if unstated:
        raise ValueError(
            f"the work line states {', '.join(STATED_SETTINGS)}; the registered role sets "
            f"{', '.join(unstated)}"
        )
    if "max_tokens" not in settings:
        raise ValueError("the registered role sets no max_tokens, and the work line requires it")
    arguments += [
        "--model",
        role.configuration.model_id,
        "--counting-model",
        role.counting_model_id,
        "--context-allowance",
        str(role.context_allowance_tokens),
        "--pricing-key",
        role.pricing.pricing_key,
        "--billing-mode",
        role.pricing.billing_mode,
    ]
    for name in STATED_SETTINGS:
        if name in settings:
            arguments += [f"--{name.replace('_', '-')}", _flag_value(settings[name])]
    return tuple(arguments)


def _flag_value(value: object) -> str:
    """A setting's value as the line spells it: an integer without a fraction, a number as
    Python prints it (the line parses ``--temperature`` as a float and ``0`` reads as 0.0,
    which the settings codec compares equal to 0)."""
    return str(value)


# --- The next step ---------------------------------------------------------------------------


class NextStep(StrEnum):
    """What the lifecycle sends next, from an attempt's state."""

    WORK = "work"
    """Never claimed, or an approval delivered after a pause: the work command."""
    RECOVER = "recover"
    """Left open by a process that is gone: the work command again, on the same attempt,
    counted against the recovery bound."""
    WAIT = "wait"
    """An approval is requested and not given: a human decides; nothing is sent."""
    PUBLISH = "publish"
    """Closed: publish the export, then the inventory."""
    HOLD = "hold"
    """Left open past the recovery bound: an operator decides; nothing is sent."""


def next_step(
    state: AttemptState, *, approval: ApprovalPolicy, bound: int = RECOVERY_BOUND
) -> NextStep:
    """The next step for an attempt in ``state`` dispatched under ``approval``, for a caller
    that has established no process owns the attempt; the recoveries so far are the
    state's own count."""
    if state.inputs is None:
        raise ValueError("an attempt with no admission has no next step")
    if state.closed is not None:
        return NextStep.PUBLISH
    if next_claim(state) is not ClaimKind.RECOVERY:
        return NextStep.WORK
    human_decides = approval.approver(state) is None
    if state.approval_requested is not None and state.approved is None and human_decides:
        return NextStep.WAIT
    return NextStep.RECOVER if state.recoveries < bound else NextStep.HOLD


__all__ = [
    "RECOVERY_BOUND",
    "STATED_SETTINGS",
    "LaunchPlan",
    "NextStep",
    "RunCell",
    "next_step",
    "plan_run",
    "work_arguments",
]
