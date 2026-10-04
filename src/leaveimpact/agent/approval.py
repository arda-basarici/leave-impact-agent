"""The automatic approval of an evaluation run: the decision, made before the export exists.

An investigation ends with a plan for a human to approve, and an evaluation has no human in
it: a run that completes is approved by the registered automatic policy before it
terminalizes (the contract step's ruling on approval). The decision is made here, in the
run path, and handed to the exporter, which projects it and decides nothing. An export
that computed its own approval would be asserting after the fact that one happened.

The policy approves the frozen review payload of any run that reached one, an abstention's
empty payload included, and records the payload's digest so the approval names exactly
what it was given. A failed run reached no payload and requested no approval. An automatic
approval is a measurement convention, never authorization: nothing is executed on it.

The baseline's decision is a function of its run. The graph's is an event in the log, made
by the same policy at the approval interrupt, and reaches the exporter the same way.
"""

from __future__ import annotations

from leaveimpact.agent.report import rules_only_composition
from leaveimpact.agent.rules_only import RulesOnlyRun
from leaveimpact.core.run_ending import Approval, ApprovalState, Approver
from leaveimpact.core.run_parts_json import review_payload_digest


def approve_rules_only_run(run: RulesOnlyRun) -> Approval:
    """The automatic policy's decision on ``run``: approved over its review payload, or not
    requested when the run failed before it had one."""
    if run.failure is not None:
        return Approval(ApprovalState.NOT_REQUESTED, None, None)
    digest = review_payload_digest(run.claims, rules_only_composition())
    return Approval(ApprovalState.APPROVED, Approver.AUTOMATIC, digest)


__all__ = ["approve_rules_only_run"]
