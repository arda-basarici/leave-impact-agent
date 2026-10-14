"""The attempt loop: every pending brief written, gated, and either accepted with its record or
refused until the cap, the whole stage before any byte of the world is fixed.

One function, ``materialize``, takes the semantic world's briefs in order — scenario by
scenario, brief by brief, which is the order the record preserves whatever ran first — and
for each runs the loop the step 14 rulings fixed (DESIGN, "Truth before prose"): render the
brief, ask the writer, run the namespace scanner and the required-fact check, ask the
checker, parse its reading, run the containment check; accept on a clean pass, otherwise
discard the draft whole and try again from the same prompt, with nothing fed back, up to the
cap. Each attempt
is a fresh sample from the same configuration: the orchestration creates no dependence
between attempts, which is the property claimed.

Two kinds of failure are kept apart on purpose. A cap exhausted is a *semantic* failure of
one target: the target is marked, the stage goes on, and at the end every failed target is
reported together in ``MaterializationFailed``, so a doomed run yields the whole diagnostic
and not the first miss. A model that cannot be used — the writer or the checker unreachable
after the bounded retries, or a checker whose answers keep breaking the tool's contract — is
*infrastructure*: the stage aborts at once in ``MaterializationAborted``, since further
writer calls could never be accepted. A refused grant or a rejected request aborts without
a retry, since neither is a condition a retry changes; the adapter's fault stays chained as
the cause. A checker fault therefore never counts as a refusal, and the record distinguishes
the two. A retry is counted only when another call follows it: four failed calls under a
budget of three are three retries and one terminal failure.

What leaves this module is plain data: the accepted bodies by target, the materialization
record with each target's attempts and refusals by guard, and the run's metrics — the ten
numbers the step reports (attempts, first-attempt and eventual passes, caps exhausted,
refusals per guard, checker retries and unusable checkers) with tokens and latency beside
them. The log receives ids, attempt numbers, guard names and counts and never a sentence,
since the job log is public; the private detail of a refusal exists only inside this
function and is dropped.

Briefs are independent by the property claimed above, so ``workers`` of them run at once on
a thread pool (the freeze step's ruling on the pool's generation time: a 100,000-token
filler pool is about 2,500 attempts, about eighty minutes sequentially at the 1.9 seconds
an attempt the first development world measured, a quarter of that at four workers, and a
world regenerated on a defect pays it again). Each brief's loop keeps its own tally and
the tallies are merged in brief order, so the record and the metrics are the same sums at
any worker count; the log is serialized so lines never interleave mid-line. Nothing the
world seals changes with the count, which is why it is a run control and no generator
version moves with it. Throttling is the SDK's adaptive retry with backoff first and the
bounded retry here after it.

A ``checkpoint`` (its module) is a private file of the bodies this seed's briefs were
accepted with. A brief whose kept entry carries the current request digest, whose body
still has the recorded digest, and whose body passes the two free guards again is accepted
from the file with the record its acceptance made, no model called, counted as reused; any
other brief is written as usual and kept as it passes. The checker is not re-run on a kept
body: the request digest fixes the brief the containment check was made against, and the
free guards are re-run because they are free and may have changed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, fields
from threading import Lock

from leaveimpact.adapters.prose.seam import (
    ModelAccessRefused,
    ModelMisconfigured,
    ModelProtocolFault,
    ModelUnreachable,
    ProseChecker,
    ProseWriter,
    ToolCall,
    WriterRequest,
    WrittenText,
)
from leaveimpact.core.jsonshape import canonical_bytes
from leaveimpact.core.provenance import ModelConfiguration
from leaveimpact.generator.checkpoint import Checkpointed, ProseCheckpoint
from leaveimpact.generator.guards import (
    Finding,
    containment_findings,
    namespace_findings,
    reason_counts,
    required_fact_findings,
)
from leaveimpact.generator.prose.assets import PromptAssets
from leaveimpact.generator.prose.render import (
    CHECKER_INFERENCE,
    WRITER_INFERENCE,
    checker_request,
    writer_request,
)
from leaveimpact.generator.prose.schema import Extraction, ExtractionMalformed, parse_extraction
from leaveimpact.world.artifacts import digest
from leaveimpact.world.assembly import SemanticWorld
from leaveimpact.world.briefs import Brief, lexicon_of, target_ref
from leaveimpact.world.filler import world_documents
from leaveimpact.world.prose import (
    GuardName,
    Lexicon,
    MaterializationMetrics,
    MaterializationRecord,
    Refusal,
    SurfaceForm,
    TargetRecord,
)

CALL_RETRIES = 3
"""How many times one model call is retried on a transient fault before the stage aborts."""


@dataclass(slots=True)
class ProseMetrics:
    """One run's prose numbers, reported in the log and the findings; ``sealed`` freezes the
    counters into the materialization record the truth manifest carries (the step 15
    ruling on sealed counters), never the costs."""

    writer_attempts: int = 0
    targets_first_attempt_pass: int = 0
    targets_eventual_pass: int = 0
    targets_cap_exhausted: int = 0
    namespace_refusals: int = 0
    required_fact_refusals: int = 0
    extraction_refusals: int = 0
    checker_retries: int = 0
    checker_unusable: int = 0
    writer_retries: int = 0
    writer_input_tokens: int = 0
    writer_output_tokens: int = 0
    checker_input_tokens: int = 0
    checker_output_tokens: int = 0
    writer_latency_ms: int = 0
    checker_latency_ms: int = 0
    canonicalized_pairs: int = 0
    targets_reused_from_checkpoint: int = 0

    def lines(self) -> tuple[str, ...]:
        """The metrics as the run prints them, one number per line."""
        return tuple(f"prose_{f.name}={getattr(self, f.name)}" for f in fields(self))

    def sealed(self) -> MaterializationMetrics:
        """The counters frozen for the record, every field in its declared order."""
        return MaterializationMetrics(tuple((f.name, getattr(self, f.name)) for f in fields(self)))

    def absorb(self, other: ProseMetrics) -> None:
        """Adds ``other``'s counters into these, field by field: a brief's tally into the run's."""
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


@dataclass(frozen=True, slots=True)
class Materialized:
    """The stage's output: accepted bodies by target, their record, the run's metrics."""

    prose: Mapping[str, str]
    record: MaterializationRecord
    metrics: ProseMetrics


class MaterializationFailed(Exception):
    """At least one target exhausted the cap; every such target is named with its refusals."""

    def __init__(self, failed: Mapping[str, tuple[Refusal, ...]], metrics: ProseMetrics) -> None:
        summary = ", ".join(
            f"{target} ({len(refusals)} refusals)" for target, refusals in failed.items()
        )
        super().__init__(f"materialization failed for {len(failed)} target(s): {summary}")
        self.failed = dict(failed)
        self.metrics = metrics


class MaterializationAborted(Exception):
    """A model could not be used: infrastructure, not a refusal; the stage stopped at once."""

    def __init__(self, which: str, target: str, metrics: ProseMetrics) -> None:
        super().__init__(f"{which} unusable while materializing {target}; the stage stopped")
        self.which = which
        self.target = target
        self.metrics = metrics


@dataclass(slots=True)
class _Loop:
    """What one brief's loop carries: the shared models, assets and log, and its own tally."""

    writer: ProseWriter
    checker: ProseChecker
    assets: PromptAssets
    attempt_cap: int
    log: Callable[[str], None]
    metrics: ProseMetrics = field(default_factory=ProseMetrics)


def materialize(
    semantic: SemanticWorld,
    writer: ProseWriter,
    checker: ProseChecker,
    assets: PromptAssets,
    attempt_cap: int,
    log: Callable[[str], None],
    workers: int = 1,
    checkpoint: ProseCheckpoint | None = None,
) -> Materialized:
    """Every pending brief of ``semantic`` written and accepted, or the run's failures by name.

    ``workers`` briefs are in flight at once; one is the sequential loop. The record lists
    the targets in brief order and the metrics are the same sums at any count. A
    ``checkpoint`` supplies bodies accepted by an earlier run of the seed on the module's
    terms and receives each body accepted by this one. Raises
    ``MaterializationFailed`` after the whole stage when any target exhausted the cap,
    ``MaterializationAborted`` at once when a model is unusable, the briefs not yet started
    cancelled and the ones in flight finished first, the adapter's fault chained as the
    cause. Raises nothing and calls no model for a world with no pending prose.
    """
    if attempt_cap < 1:
        raise ValueError(f"the attempt cap is at least one, got {attempt_cap}")
    if workers < 1:
        raise ValueError(f"the worker count is at least one, got {workers}")
    template = _Loop(writer, checker, assets, attempt_cap, _serialized(log))
    lexicon = lexicon_of(
        semantic.org,
        [p.entity for s in semantic.scenarios for p in s.owned.work_items],
        [p.entity for p in world_documents(semantic)],
        [p.entity for s in semantic.scenarios for p in s.owned.events],
    )
    world_forms = lexicon.forms()
    briefs = [brief for scenario in semantic.scenarios for brief in scenario.briefs]
    ordered = (*briefs, *semantic.filler_briefs)
    kept = {} if checkpoint is None else checkpoint.load()
    keep = None if checkpoint is None else checkpoint.keep
    outcomes = _run_all(template, ordered, lexicon, world_forms, workers, kept, keep)
    metrics = ProseMetrics()
    prose: dict[str, str] = {}
    targets: list[TargetRecord] = []
    failed: dict[str, tuple[Refusal, ...]] = {}
    for brief, outcome in zip(ordered, outcomes, strict=True):
        metrics.absorb(outcome.tally)
        if isinstance(outcome.result, _Accepted):
            prose[brief.id] = outcome.result.body
            targets.append(outcome.result.record)
        else:
            failed[brief.id] = outcome.result
    if failed:
        raise MaterializationFailed(failed, metrics)
    record = MaterializationRecord(
        writer=ModelConfiguration(writer.model_id, WRITER_INFERENCE.settings()),
        checker=ModelConfiguration(checker.model_id, CHECKER_INFERENCE.settings()),
        prompt_digests=assets.digests(),
        attempt_cap=attempt_cap,
        targets=tuple(targets),
        metrics=metrics.sealed(),
    )
    return Materialized(prose, record, metrics)


@dataclass(frozen=True, slots=True)
class _Outcome:
    """One brief's result with the tally its loop kept."""

    result: _Accepted | tuple[Refusal, ...]
    tally: ProseMetrics


def _run_all(
    template: _Loop,
    ordered: Sequence[Brief],
    lexicon: Lexicon,
    world_forms: tuple[SurfaceForm, ...],
    workers: int,
    kept: Mapping[str, Checkpointed],
    keep: Callable[[str, TargetRecord], None] | None,
) -> list[_Outcome]:
    """Every brief's outcome in brief order, ``workers`` at a time. The first abort cancels
    the briefs not yet started, lets the ones in flight finish, and is re-raised carrying
    every finished brief's tally merged with the aborted ones', the adapter's fault still
    the cause."""

    def one(brief: Brief) -> _Outcome:
        loop = _Loop(
            template.writer, template.checker, template.assets, template.attempt_cap, template.log
        )
        accepted = _materialize_one(loop, brief, lexicon, world_forms, kept.get(brief.id), keep)
        return _Outcome(accepted, loop.metrics)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, brief) for brief in ordered]
        done, _ = wait(futures, return_when=FIRST_EXCEPTION)
        if any(future.exception() is not None for future in done):
            for future in futures:
                future.cancel()
    outcomes: list[_Outcome] = []
    merged = ProseMetrics()
    first: MaterializationAborted | None = None
    for future in futures:
        if future.cancelled():
            continue
        error = future.exception()
        if error is None:
            outcomes.append(future.result())
            merged.absorb(future.result().tally)
        elif isinstance(error, MaterializationAborted):
            merged.absorb(error.metrics)
            first = first or error
        else:
            raise error
    if first is not None:
        raise MaterializationAborted(first.which, first.target, merged) from first.__cause__
    return outcomes


def _serialized(log: Callable[[str], None]) -> Callable[[str], None]:
    """``log`` under a lock, so lines from concurrent briefs never interleave mid-line."""
    lock = Lock()

    def write(line: str) -> None:
        with lock:
            log(line)

    return write


@dataclass(frozen=True, slots=True)
class _Accepted:
    body: str
    record: TargetRecord


def _materialize_one(
    loop: _Loop,
    brief: Brief,
    lexicon: Lexicon,
    world_forms: tuple[SurfaceForm, ...],
    kept: Checkpointed | None = None,
    keep: Callable[[str, TargetRecord], None] | None = None,
) -> _Accepted | tuple[Refusal, ...]:
    """The loop for one brief: an accepted body with its record, or the refusals at the cap;
    ``kept`` is reused on the module's terms and ``keep`` receives a fresh acceptance."""
    refusals: list[Refusal] = []
    request = writer_request(brief, lexicon, loop.assets)
    request_digest = digest(
        canonical_bytes(
            {
                "system": request.system,
                "message": request.message,
                "settings": [[s.name, s.value] for s in request.inference.settings()],
            }
        )
    )
    if kept is not None and _reusable(loop, brief, kept, request_digest, lexicon, world_forms):
        loop.metrics.targets_reused_from_checkpoint += 1
        loop.log(f"{brief.id}: reused from the checkpoint (attempt {kept.record.attempts})")
        return _Accepted(kept.body, kept.record)
    for attempt in range(1, loop.attempt_cap + 1):
        written = _write(loop, brief.id, request)
        loop.metrics.writer_attempts += 1
        body = written.text.strip()
        refused = _gate(loop, brief, body, lexicon, world_forms)
        if refused is not None:
            guard, findings = refused
            refusals.append(_refusal(attempt, guard, findings))
            _count_refusal(loop.metrics, guard)
            loop.log(_refused_line(brief.id, attempt, guard, findings))
            continue
        extraction = _check(loop, brief, body)
        loop.metrics.canonicalized_pairs += extraction.canonicalized
        findings = containment_findings(brief, extraction)
        if findings:
            refusals.append(_refusal(attempt, GuardName.EXTRACTION, findings))
            loop.metrics.extraction_refusals += 1
            loop.log(_refused_line(brief.id, attempt, GuardName.EXTRACTION, findings))
            continue
        loop.metrics.targets_eventual_pass += 1
        if attempt == 1:
            loop.metrics.targets_first_attempt_pass += 1
        loop.log(f"{brief.id}: accepted on attempt {attempt}")
        record = TargetRecord(
            brief.id,
            attempt,
            tuple(refusals),
            request_digest,
            digest(body.encode("utf-8")),
            extraction.propositions,
        )
        if keep is not None:
            keep(body, record)
        return _Accepted(body, record)
    loop.metrics.targets_cap_exhausted += 1
    loop.log(f"{brief.id}: cap of {loop.attempt_cap} exhausted")
    return tuple(refusals)


def _reusable(
    loop: _Loop,
    brief: Brief,
    kept: Checkpointed,
    request_digest: str,
    lexicon: Lexicon,
    world_forms: tuple[SurfaceForm, ...],
) -> bool:
    """Whether a kept body stands for this brief today: the same request, the recorded body,
    the free guards passing again."""
    if kept.record.request_digest != request_digest:
        return False
    if kept.record.accepted_body_digest != digest(kept.body.encode("utf-8")):
        return False
    return _gate(loop, brief, kept.body, lexicon, world_forms) is None


def _gate(
    loop: _Loop, brief: Brief, body: str, lexicon: Lexicon, world_forms: tuple[SurfaceForm, ...]
) -> tuple[GuardName, tuple[Finding, ...]] | None:
    """The two free guards in order; the first that finds anything names itself and its findings."""
    findings = namespace_findings(body, brief, world_forms)
    if findings:
        return (GuardName.NAMESPACE, findings)
    findings = required_fact_findings(body, brief, lexicon)
    if findings:
        return (GuardName.REQUIRED_FACT, findings)
    return None


def _refusal(attempt: int, guard: GuardName, findings: Sequence[Finding]) -> Refusal:
    return Refusal(attempt, guard, len(findings), reason_counts(findings))


def _refused_line(target: str, attempt: int, guard: GuardName, findings: Sequence[Finding]) -> str:
    """The log line of a refusal: counts by reason and nothing a finding's message names."""
    by_reason = ", ".join(f"{count} {reason.value}" for reason, count in reason_counts(findings))
    return (
        f"{target} attempt {attempt}: refused by {guard.value} "
        f"({len(findings)} findings: {by_reason})"
    )


def _write(loop: _Loop, target: str, request: WriterRequest) -> WrittenText:
    """One writer call, retried on a transient fault; unusable after the retries aborts."""
    for call in range(CALL_RETRIES + 1):
        try:
            written = loop.writer.write(request)
        except (ModelAccessRefused, ModelMisconfigured) as fault:
            loop.log(f"{target}: writer unusable ({type(fault).__name__})")
            raise MaterializationAborted("writer", target, loop.metrics) from fault
        except (ModelUnreachable, ModelProtocolFault) as fault:
            if call == CALL_RETRIES:
                loop.log(f"{target}: writer call failed ({type(fault).__name__}), giving up")
                raise MaterializationAborted("writer", target, loop.metrics) from fault
            loop.metrics.writer_retries += 1
            loop.log(f"{target}: writer call failed ({type(fault).__name__}), retry {call + 1}")
            continue
        loop.metrics.writer_input_tokens += written.usage.input_tokens
        loop.metrics.writer_output_tokens += written.usage.output_tokens
        loop.metrics.writer_latency_ms += written.usage.latency_ms
        return written
    raise MaterializationAborted("writer", target, loop.metrics)


def _check(loop: _Loop, brief: Brief, body: str) -> Extraction:
    """One checker call parsed, retried on a transient or protocol fault; unusable aborts."""
    request = checker_request(body, brief, loop.assets)
    for attempt in range(CALL_RETRIES + 1):
        try:
            call: ToolCall = loop.checker.extract(request)
            extraction = parse_extraction(call.input, brief.namespace, target_ref(brief.target))
        except (ModelAccessRefused, ModelMisconfigured) as fault:
            loop.metrics.checker_unusable += 1
            loop.log(f"{brief.id}: checker unusable ({type(fault).__name__})")
            raise MaterializationAborted("checker", brief.id, loop.metrics) from fault
        except (ModelUnreachable, ModelProtocolFault, ExtractionMalformed) as fault:
            if attempt == CALL_RETRIES:
                loop.metrics.checker_unusable += 1
                loop.log(f"{brief.id}: checker call failed ({type(fault).__name__}), giving up")
                raise MaterializationAborted("checker", brief.id, loop.metrics) from fault
            loop.metrics.checker_retries += 1
            loop.log(
                f"{brief.id}: checker call failed ({type(fault).__name__}), retry {attempt + 1}"
            )
            continue
        loop.metrics.checker_input_tokens += call.usage.input_tokens
        loop.metrics.checker_output_tokens += call.usage.output_tokens
        loop.metrics.checker_latency_ms += call.usage.latency_ms
        return extraction
    raise MaterializationAborted("checker", brief.id, loop.metrics)


def _count_refusal(metrics: ProseMetrics, guard: GuardName) -> None:
    match guard:
        case GuardName.NAMESPACE:
            metrics.namespace_refusals += 1
        case GuardName.REQUIRED_FACT:
            metrics.required_fact_refusals += 1
        case GuardName.EXTRACTION:
            metrics.extraction_refusals += 1


__all__ = [
    "CALL_RETRIES",
    "MaterializationAborted",
    "MaterializationFailed",
    "Materialized",
    "ProseMetrics",
    "materialize",
]
