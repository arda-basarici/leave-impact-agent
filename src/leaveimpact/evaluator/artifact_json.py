"""The evaluation artifact's written form: one encoder, no decoder.

An artifact is written once per evaluation and read by people and by the report built from
it; nothing in this code reads one back (the investigator milestone's sixth build step,
ruling 7). So the written form is derived from the types instead of spelled out per type
as the run export's and the registration's are: those two are decoded strictly by a second
party, and a codec written field by field is what keeps their encoder and decoder honest
with each other. Here there is one side, and thirty-odd hand-written encoders with nothing
to mirror would be transcription.

The rule of the walk. A dataclass is an object with one key per field, in the fields'
declared order, a field holding ``None`` written as null and never left out, so absent and
empty stay different statements. An enumeration member is its value. A tuple is an array
in its own order; a set is an array in the sorted order of its written members. A day and
an instant are ISO 8601 text. Integers, strings and booleans are themselves; a float is
written as Python's shortest round-trip form and a non-finite one is refused. Anything
else is refused by type, loudly: a value the walk does not know is a change to the format
somebody has to decide.

Three things are written differently from their type, each on purpose:

- *A condition* is written as the sources it cannot reach, the way the registration names
  one, not as the ones it can.
- *A run* is written as its outcome and its findings, not as its whole evaluation: the
  condition and the corpus level it was assigned, the header, how it ended and why, the
  claim rows, the plan findings and coverage gaps, each claim's replay standing, the
  integrity, operation and prefetch findings, the disagreements between record and
  trace, what the rerun of admission and composition disputes, the documents outside its
  level, whether it met a contradiction without failing by defect, what its record states
  of its ending with where the export does not bear it out, its dispatches' readings held
  to the registered table, and the sends an SDK retried. Proofs, premises,
  citations, retrieval rows, the per-operation rows, the fact stages with every emission's
  class and the contradictions among its reads are left out: each is recomputed from the
  stored export,
  which the inventory names by key, version id and digest; the contradictions reach the
  artifact through the analysis's incidents.
- *An inventory entry* holds that run under ``run`` and its recomputed cost beside it,
  since an export of another world has a cost and no run.

What holds the format still is the format version and a test that pins every key path the
walk produces from a set of runs chosen to reach every type. A renamed or added field
changes those paths, the test fails, and the change is made with the version in hand.

When this stops being the right shape: the day something decodes an artifact, a report
view or a comparison across evaluations, the format needs a decoder that refuses what it
does not know, and a decoder wants the explicit per-type codec the export has, written
against the pinned paths. The same holds if artifacts from two versions of this code must
ever be read side by side, or if bytes must be equal across platforms, which a float's
written form here does not promise.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite
from typing import cast

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.evaluator.artifact import EvaluationArtifact, InventoryEntry
from leaveimpact.evaluator.grading import Excluded, Graded, Grounding, Limited, RunOutcome
from leaveimpact.evaluator.trace_metrics import Evaluation


def artifact_bytes(artifact: EvaluationArtifact) -> bytes:
    """The bytes an evaluation is stored as: compact JSON in UTF-8, keys in declared order."""
    text = json.dumps(
        encode_artifact(artifact), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return text.encode("utf-8")


def encode_artifact(artifact: EvaluationArtifact) -> JsonObject:
    """``artifact`` as the JSON object it is written as."""
    return cast("JsonObject", _written(artifact))


def _written(value: object) -> object:
    """``value`` as JSON-ready data, by the rule of the walk."""
    match value:
        case Enum():
            return _written(value.value)
        case None | bool() | int() | str():
            return value
        case float():
            if not isfinite(value):
                raise ValueError(f"an artifact holds finite numbers, got {value!r}")
            return value
        case datetime() | date():
            return value.isoformat()
        case RunCondition():
            return {"unreachable": sorted(s.value for s in Source if s not in value.reachable)}
        case InventoryEntry():
            return _entry(value)
        case tuple() | list():
            return [_written(item) for item in cast("tuple[object, ...]", value)]
        case frozenset() | set():
            members = [_written(item) for item in cast("frozenset[object]", value)]
            return sorted(members, key=lambda member: json.dumps(member, sort_keys=True))
        case _ if is_dataclass(value) and not isinstance(value, type):
            return {field.name: _written(getattr(value, field.name)) for field in fields(value)}
        case _:
            raise TypeError(f"the artifact's written form has no rule for {type(value).__name__}")


def _entry(entry: InventoryEntry) -> JsonObject:
    return {
        "key": entry.key,
        "version_id": entry.version_id,
        "digest": entry.digest,
        "disposition": entry.disposition.value,
        "differing": _written(entry.differing),
        "label": _written(entry.label),
        "run": None if entry.evaluation is None else _run(entry.evaluation),
        "cost": _written(entry.cost),
    }


def _run(evaluation: Evaluation) -> JsonObject:
    metrics = evaluation.metrics
    return {
        "assigned": _written(evaluation.assigned),
        "level": evaluation.level,
        "outcome": _outcome(evaluation.outcome),
        "operation_findings": _written(metrics.discipline.findings),
        "prefetch": _written(metrics.prefetch),
        "fact_recheck": _written(metrics.recheck),
        "level_check": _written(metrics.level),
        "contradiction_not_failed": evaluation.contradiction_not_failed,
        "ending": _written(metrics.ending),
        "attribution": _written(metrics.attribution),
        "retried_sends": _written(metrics.discipline.retried_sends),
    }


def _outcome(outcome: RunOutcome) -> JsonObject:
    match outcome:
        case Excluded():
            return {
                "kind": "excluded",
                "header": _written(outcome.header),
                "reason": outcome.reason.value,
            }
        case Graded():
            return {
                "kind": "graded",
                "header": _written(outcome.header),
                "condition": _written(outcome.condition),
                "rows": _written(outcome.rows),
                "oracle_findings": _written(outcome.oracle_findings),
                "report_findings": _written(outcome.report_findings),
                "coverage": _written(outcome.coverage),
                "standings": _standings(outcome.grounding),
                "integrity": _written(outcome.integrity),
                "record_disagreements": _written(outcome.harness_findings),
            }
        case Limited():
            return {
                "kind": "limited",
                "header": _written(outcome.header),
                "condition": _written(outcome.condition),
                "reason": outcome.reason.value,
                "mixed": _written(outcome.mixed),
                "structural_problems": _written(outcome.structural_problems),
                "report_findings": _written(outcome.report_findings),
                "coverage": _written(outcome.coverage),
                "standings": _standings(outcome.grounding),
                "integrity": _written(outcome.integrity),
                "record_disagreements": _written(outcome.harness_findings),
            }


def _standings(grounding: Grounding | None) -> list[JsonObject] | None:
    """Each claim's replay standing with its reason, in claim order; null when the claim set
    could not be replayed, which is not the same as an empty report's empty list."""
    if grounding is None:
        return None
    return [
        {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type.value,
            "standing": claim.standing.value,
            "reason": None if claim.reason is None else claim.reason.value,
        }
        for claim in grounding.claims
    ]


__all__ = ["artifact_bytes", "encode_artifact"]
