"""Registrations for tests: the draft, and versions of it with its choices made.

Test infrastructure. ``DRAFT`` is the registration as it stood before the freeze, a copy
of the committed draft kept under ``tests/fixtures`` so that what a draft means, which
values a pending one blocks and how a plan leaves cells out, stays testable after the
committed file froze (the freeze step); ``COMMITTED`` is the committed file itself,
whatever its status. The draft holds most of its choices pending, so a test of what a
resolved, a frozen or a bound registration does has to make those choices first. They are
made here once, with placeholder values that mean nothing: a role, an attribution table of
one row per kind of observation, a re-dispatch bound, an entry schema.

``named`` resolves what an execution of the agent and of full context needs, so their cells
can be built, and leaves the single-shot system's roles pending on purpose, so a plan built
from it has one system that cannot be built, the case the analysis tests need. The committed
draft names every variant, sets the single-shot's protocol and limit (the baselines step) and
the three model systems' roles (the first live run's step, to what the tree ships);
``pending_roles`` puts every model system's roles back to pending, the state a draft is in
before its systems are built, for tests of what a run records under a role nobody has
registered. ``frozen`` drops the single-shot system and everything that names it, a frozen
registration having nothing pending but its world.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from leaveimpact.core import (
    AgentSystem,
    AttributionKind,
    Basis,
    CallConfiguration,
    CallSetting,
    EntrySchema,
    FullContextSystem,
    GroupDecision,
    InputTokenRange,
    MeasuredWorld,
    MechanismMeasure,
    NotBuilt,
    Pending,
    RegisteredRole,
    RegisteredSystem,
    Registration,
    RegistrationStatus,
    SingleShotSystem,
    SystemKind,
    decode_registration_bytes,
)
from leaveimpact.core.attribution import (
    AttributionRow,
    AttributionTable,
    Match,
    ObservationKind,
    RedispatchPolicy,
)

_ROOT = Path(__file__).resolve().parents[2]
DRAFT_FILE = _ROOT / "tests" / "fixtures" / "registration-draft.json"
DRAFT = decode_registration_bytes(DRAFT_FILE.read_bytes())
COMMITTED_FILE = _ROOT / "preregistration" / "registration.json"
COMMITTED = decode_registration_bytes(COMMITTED_FILE.read_bytes())
DIGEST = "ab" * 32
COMMIT = "c" * 40
ROLE = RegisteredRole(
    "investigator",
    CallConfiguration("eu.some-model", (CallSetting("temperature", 0),)),
    (("system", DIGEST),),
    DIGEST,
    "some-model",
    200_000,
)
TABLE = AttributionTable(
    tuple(
        AttributionRow(f"any_{kind.value}", Match(kind), AttributionKind.INFRASTRUCTURE)
        for kind in ObservationKind
    )
)
MECHANISM = MechanismMeasure("needed_prose_facts", ("returned", "emitted", "admitted", "usable"))


def pending_roles(registration: Registration) -> Registration:
    """``registration`` with every model system's roles pending, as a draft holds them before
    its systems are built."""

    def unroled(system: RegisteredSystem) -> RegisteredSystem:
        if isinstance(system, AgentSystem | SingleShotSystem | FullContextSystem):
            return replace(system, roles=Pending("set when the system is built"))
        return system

    return replace(registration, systems=tuple(unroled(system) for system in registration.systems))


def light(registration: Registration, resamples: int = 200) -> Registration:
    """``registration`` with fewer resamples: the registered count buys precision a test
    of shape does not need."""
    return replace(registration, statistics=replace(registration.statistics, resamples=resamples))


def named(
    registration: Registration = DRAFT,
    *,
    agent: str = "graph",
    full_context: str = "all-documents",
    roles: tuple[RegisteredRole, ...] = (ROLE,),
) -> Registration:
    """``registration`` with the agent and full context named and given ``roles``, the
    single-shot system's roles pending, and the three values every model system's execution
    needs set: the attribution table, the re-dispatch policy and the entry schema."""

    def resolved(system: RegisteredSystem) -> RegisteredSystem:
        if isinstance(system, AgentSystem):
            return replace(system, variant=agent, roles=roles)
        if isinstance(system, FullContextSystem):
            return replace(system, variant=full_context, roles=roles)
        if isinstance(system, SingleShotSystem):
            return replace(system, roles=Pending("left pending by the fixture, one unbuilt system"))
        return system

    return replace(
        registration,
        systems=tuple(resolved(system) for system in registration.systems),
        run_accounting=replace(registration.run_accounting, redispatch=RedispatchPolicy(2, 1_000)),
        attribution=TABLE,
        stated_facts=replace(
            registration.stated_facts, entry_schema=EntrySchema("fact-entries-1", DIGEST)
        ),
    )


def decided(registration: Registration, run: bool) -> Registration:
    """``registration`` with every conditional group decided: run, or not run for a reason."""
    decision = GroupDecision(run, None if run else "the reforecast left no budget")
    return replace(
        registration,
        cell_groups=tuple(replace(group, decision=decision) for group in registration.cell_groups),
    )


def without_single_shot(registration: Registration) -> Registration:
    """``registration`` with the single-shot system and everything that names it removed."""
    kept = SystemKind.SINGLE_SHOT
    statistics = registration.statistics
    descriptive = statistics.descriptive
    return replace(
        registration,
        systems=tuple(s for s in registration.systems if not isinstance(s, SingleShotSystem)),
        cells=tuple(cell for cell in registration.cells if cell.system is not kept),
        statistics=replace(
            statistics,
            secondary=tuple(c for c in statistics.secondary if kept not in c.systems),
            descriptive=replace(
                descriptive, pairs=tuple(pair for pair in descriptive.pairs if kept not in pair)
            ),
            level_contrasts=tuple(c for c in statistics.level_contrasts if c.system is not kept),
        ),
    )


def frozen(registration: Registration = DRAFT, *, run_group: bool = True) -> Registration:
    """A frozen registration made from ``registration``: every choice made, the numbers
    calibrated, and nothing pending but the world's version."""
    resolved = decided(without_single_shot(named(registration)), run_group)
    calibrated = tuple(
        replace(system, caps=replace(system.caps, basis=Basis.CALIBRATED))
        for system in resolved.systems
    )
    return replace(
        resolved,
        status=RegistrationStatus.FROZEN,
        systems=calibrated,
        corpus_levels=tuple(
            replace(
                level,
                filler_documents=0 if level.name == "base" else 160,
                full_context_input_tokens=InputTokenRange(10_000, 11_000)
                if level.name == "base"
                else InputTokenRange(40_000, 43_000),
            )
            for level in resolved.corpus_levels
        ),
        statistics=replace(resolved.statistics, mechanism=MECHANISM),
        supporting=tuple(
            replace(
                entry,
                other_model=None,
                inclusion=NotBuilt("not built before the freeze, for time", None),
            )
            for entry in resolved.supporting
        ),
        budget=replace(resolved.budget, basis=Basis.CALIBRATED),
    )


def bound(
    version: str, registration: Registration | None = None, *, frozen_commit: str = COMMIT
) -> Registration:
    """The bound registration made from a frozen one: the world's version, the frozen commit
    it binds, and nothing else changed."""
    held = frozen() if registration is None else registration
    return replace(
        held, status=RegistrationStatus.BOUND, world=MeasuredWorld(version, frozen_commit, 0)
    )


__all__ = [
    "COMMIT",
    "COMMITTED",
    "COMMITTED_FILE",
    "DIGEST",
    "DRAFT",
    "pending_roles",
    "DRAFT_FILE",
    "MECHANISM",
    "ROLE",
    "TABLE",
    "bound",
    "decided",
    "frozen",
    "light",
    "named",
    "without_single_shot",
]
