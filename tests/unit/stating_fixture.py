"""A run that states facts, exported: the reads of a full investigation, one model call whose
answer carries one batch of statements, and the claims the composer makes of them.

Test infrastructure. No system states a fact yet, so the tests of what the evaluator reads
of stated facts build the export a stating harness would write, from the real parts: the
reads through the executor, each admission ``admit``'s own over those reads, the claims and
the composition ``compose``'s. Every read is logged before the one call, as a full-context
system's are. A test that wants a record at odds with those functions replaces the part it
wants wrong.

``truthful_statements`` is the truthful stater: every sealed prose fact of a carrier the
reads returned, stated with the carrier's whole text.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from functools import cache

from leaveimpact.agent.composer import compose
from leaveimpact.core import (
    Claim,
    Composition,
    Leave,
    Operation,
    OutageAssignment,
    PredicateName,
    RunExport,
    RunTrace,
    Source,
    review_payload_digest,
)
from leaveimpact.core.admission import admit, carriers_read, run_lexicon
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClauseId, EmployeeId
from leaveimpact.core.model_calls import Answer, BatchEntry, FactBatch, ParsedBatch
from leaveimpact.core.read_projection import StructuredReads, project_reads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.stated import Admitted, StatedFact
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import DIGEST, NORMAL, agent_export, answered_call, approval
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.throwaway_world import loaded_world

ANSWERED_AT = 1_103
"""Where the fixture's one call logs its answer: every read sits below it."""


def title_of(world: SealedWorld, target: EntityRef) -> str:
    """The title prose names ``target`` by: its own, or its document's for a section."""
    index = world.index
    named = index.parts[target].parent if target.kind is EntityKind.CLAUSE else target
    return index.records[named].title  # type: ignore[union-attr]


def truthful_statements(world: SealedWorld, reads: StructuredReads) -> tuple[StatedFact, ...]:
    """Every sealed prose fact of a carrier ``reads`` returned, stated as a truthful model
    would: quoting the carrier's whole text, a requirement's span the title of what the
    sealed world scopes its clause to."""
    stated: list[StatedFact] = []
    for carrier, read in carriers_read(reads).items():
        for fact in world.index.carried.get(carrier, ()):
            span = None
            if fact.predicate is PredicateName.REQUIRES:
                span = title_of(world, world.index.scope[ClauseId(fact.subject.id)])
            stated.append(
                StatedFact(fact.predicate, fact.subject, fact.value, carrier, read.text, span)
            )
    return tuple(stated)


def read_everything(
    world: SealedWorld, scenario: Scenario, down: tuple[Source, ...]
) -> tuple[list[Operation], StructuredReads, Leave, tuple[EmployeeId, ...]]:
    """A full investigation's operations with ``down`` unreachable, their projection, the
    leave under investigation as read and the candidates read."""
    operations = reads_of_everything(world, scenario, *down)
    context = world.context_of(scenario)
    reads = project_reads(operations, context.today)
    leave = next(
        record.value
        for record in reads.returned
        if isinstance(record.value, Leave) and record.value.id == context.leave_id
    )
    universe = tuple(
        sorted(EmployeeId(r.ref.id) for r in reads.returned if r.ref.kind is EntityKind.EMPLOYEE)
    )
    return operations, reads, leave, universe


def stating_export(
    world: SealedWorld,
    scenario: Scenario,
    *,
    down: tuple[Source, ...] = (),
    statements: Sequence[StatedFact] | None = None,
    gated: bool = True,
    entries: Sequence[BatchEntry] | None = None,
    batches: Sequence[FactBatch] | None = None,
) -> RunExport:
    """An agent's export of a run of ``scenario`` that read everything it could with ``down``
    scheduled out and unreachable, then stated facts in one answer.

    The statements are the truthful stater's unless ``statements`` is given; each is
    admitted or refused as the gates decide, or every one recorded as admitted when
    ``gated`` is false; ``entries`` gives the batch's entries outright and ``batches`` the
    answer's batches whole. The claims and the composition are the composer's over the
    admitted statements.

    The throwaway world's model-written prose is stand-in text that names nobody, so the
    gates admit a truthful stater's requirements, whose clauses a class writes, and refuse
    the rest for a missing anchor. The ungated layer is the composer alone, and its record
    is then one the gates dispute.
    """
    made, reads, leave, universe = read_everything(world, scenario, down)
    assert len(made) < 1_000, "the fixture's reads must sit below its one call"
    operations = tuple(
        replace(operation, position=number) for number, operation in enumerate(made, start=1)
    )
    if batches is None:
        if entries is None:
            said = truthful_statements(world, reads) if statements is None else statements
            lexicon = run_lexicon(reads)
            entries = [
                admit(stated, reads, lexicon) if gated else Admitted(stated) for stated in said
            ]
        batches = (ParsedBatch(tuple(entries)),)
    admitted = [
        entry.fact
        for batch in batches
        if isinstance(batch, ParsedBatch)
        for entry in batch.entries
        if isinstance(entry, Admitted)
    ]
    composed = compose(reads, admitted, world.context_of(scenario), leave, universe)
    call = answered_call(1, None, None, answer=Answer(False, (), tuple(batches)))
    return restated(
        agent_export(world, scenario, (call,)),
        operations,
        composed.claims,
        composed.composition,
        down,
    )


@cache
def truthful_stater_runs(
    down: tuple[Source, ...] = (), gated: bool = True
) -> tuple[Evaluation, ...]:
    """The truthful stater's run of every scenario of the golden throwaway world, in the
    plan's order, evaluated once per layer and condition and shared between test modules."""
    world = loaded_world("golden")
    return tuple(
        evaluate_run(world, stating_export(world, scenario, down=down, gated=gated))
        for scenario in world.scenarios
    )


def restated(
    export: RunExport,
    operations: Sequence[Operation],
    claims: Sequence[Claim],
    composition: Composition,
    down: tuple[Source, ...] = (),
) -> RunExport:
    """``export`` with these reads, claims and composition in its trace, approved over them,
    and ``down`` as the outage both scheduled and observed."""
    trace = RunTrace(export.trace.model_calls, tuple(operations), tuple(claims), composition)
    approved = approval(claims, failed=export.record.failure is not None)
    if approved.payload_digest is not None:
        approved = replace(approved, payload_digest=review_payload_digest(claims, composition))
    record = replace(
        export.record,
        observed_condition=NORMAL.without(*down),
        outage=OutageAssignment(frozenset(down), DIGEST),
        approval=approved,
    )
    return replace(export, record=record, trace=trace)


__all__ = [
    "ANSWERED_AT",
    "read_everything",
    "restated",
    "stating_export",
    "title_of",
    "truthful_statements",
    "truthful_stater_runs",
]
