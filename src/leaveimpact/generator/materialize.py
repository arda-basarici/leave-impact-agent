"""The attempt loop: every pending brief written, gated, and either accepted with its record or
refused until the cap, the whole stage before any byte of the world is fixed.

One function, ``materialize``, walks the semantic world's briefs in order — scenario by
scenario, brief by brief, which is the execution order the record preserves — and for each
runs the loop the step 14 rulings fixed (DESIGN, "Materialization"): render the brief, ask the
writer, run the namespace scanner and the required-fact check, ask the checker, parse its
reading, run the containment check; accept on a clean pass, otherwise discard the draft
whole and try again from the same prompt, with nothing fed back, up to the cap. Each attempt
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
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields

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
from leaveimpact.generator.guards import (
    containment_findings,
    namespace_findings,
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
from leaveimpact.world.briefs import Brief, lexicon_of
from leaveimpact.world.prose import (
    GuardName,
    Lexicon,
    MaterializationRecord,
    ModelConfiguration,
    Refusal,
    SurfaceForm,
    TargetRecord,
)

CALL_RETRIES = 3
"""How many times one model call is retried on a transient fault before the stage aborts."""


@dataclass(slots=True)
class ProseMetrics:
    """One run's prose numbers, reported in the log and the findings and never sealed."""

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

    def lines(self) -> tuple[str, ...]:
        """The metrics as the run prints them, one number per line."""
        return tuple(f"prose_{f.name}={getattr(self, f.name)}" for f in fields(self))


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
    """The state one run of the loop carries: the models, the assets, the tallies, the log."""

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
) -> Materialized:
    """Every pending brief of ``semantic`` written and accepted, or the run's failures by name.

    Raises ``MaterializationFailed`` after the whole stage when any target exhausted the cap,
    ``MaterializationAborted`` at once when a model is unusable. Raises nothing and calls no
    model for a world with no pending prose.
    """
    if attempt_cap < 1:
        raise ValueError(f"the attempt cap is at least one, got {attempt_cap}")
    loop = _Loop(writer, checker, assets, attempt_cap, log)
    lexicon = lexicon_of(
        semantic.org,
        [p.entity for s in semantic.scenarios for p in s.owned.work_items],
        [p.entity for s in semantic.scenarios for p in s.owned.documents],
        [p.entity for s in semantic.scenarios for p in s.owned.events],
    )
    world_forms = lexicon.forms()
    prose: dict[str, str] = {}
    targets: list[TargetRecord] = []
    failed: dict[str, tuple[Refusal, ...]] = {}
    for scenario in semantic.scenarios:
        for brief in scenario.briefs:
            accepted = _materialize_one(loop, brief, lexicon, world_forms)
            if isinstance(accepted, _Accepted):
                prose[brief.id] = accepted.body
                targets.append(accepted.record)
            else:
                failed[brief.id] = accepted
    if failed:
        raise MaterializationFailed(failed, loop.metrics)
    record = MaterializationRecord(
        writer=ModelConfiguration(writer.model_id, WRITER_INFERENCE.settings()),
        checker=ModelConfiguration(checker.model_id, CHECKER_INFERENCE.settings()),
        prompt_digests=assets.digests(),
        attempt_cap=attempt_cap,
        targets=tuple(targets),
    )
    return Materialized(prose, record, loop.metrics)


@dataclass(frozen=True, slots=True)
class _Accepted:
    body: str
    record: TargetRecord


def _materialize_one(
    loop: _Loop, brief: Brief, lexicon: Lexicon, world_forms: tuple[SurfaceForm, ...]
) -> _Accepted | tuple[Refusal, ...]:
    """The loop for one brief: an accepted body with its record, or the refusals at the cap."""
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
    for attempt in range(1, loop.attempt_cap + 1):
        written = _write(loop, brief.id, request)
        loop.metrics.writer_attempts += 1
        body = written.text.strip()
        refused = _gate(loop, brief, body, lexicon, world_forms)
        if refused is not None:
            guard, count = refused
            refusals.append(Refusal(attempt, guard, count))
            _count_refusal(loop.metrics, guard)
            loop.log(f"{brief.id} attempt {attempt}: refused by {guard.value} ({count} findings)")
            continue
        extraction = _check(loop, brief, body)
        findings = containment_findings(brief, extraction)
        if findings:
            refusals.append(Refusal(attempt, GuardName.EXTRACTION, len(findings)))
            loop.metrics.extraction_refusals += 1
            loop.log(
                f"{brief.id} attempt {attempt}: refused by {GuardName.EXTRACTION.value} "
                f"({len(findings)} findings)"
            )
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
        return _Accepted(body, record)
    loop.metrics.targets_cap_exhausted += 1
    loop.log(f"{brief.id}: cap of {loop.attempt_cap} exhausted")
    return tuple(refusals)


def _gate(
    loop: _Loop, brief: Brief, body: str, lexicon: Lexicon, world_forms: tuple[SurfaceForm, ...]
) -> tuple[GuardName, int] | None:
    """The two free guards in order; the first that finds anything names itself and its count."""
    findings = namespace_findings(body, brief, world_forms)
    if findings:
        return (GuardName.NAMESPACE, len(findings))
    findings = required_fact_findings(body, brief, lexicon)
    if findings:
        return (GuardName.REQUIRED_FACT, len(findings))
    return None


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
            extraction = parse_extraction(call.input, brief.namespace)
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
