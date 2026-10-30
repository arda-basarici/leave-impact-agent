"""The authority of a closure as a public page words it: by role, never by identity.

A page names people exactly when the run read their record (the report step), and a
producer identity is not a person's record: ``demo-sweeper`` or ``workflow:investigate``
on a public page is an implementation name a stranger cannot read. The ending view and
the narration both word an abandonment's authority through this one mapping, so the two
pages say the same thing of the same closure (the live pages step, group 3's design pass,
fork 4): the demo's own sweeper when it closed a wait or gave up on an unclaimed attempt,
the operator's workflow when the launcher's dispatch closed it, and an operator for any
other identity, the hand-run commands included. The audit trail keeps the identity itself
beside the role, since the trail is where the record is shown whole.

The identities are the producers' own: the sweeper's is its module's constant and the
workflow's is the launcher's admitter prefix, and a unit test holds this module's spellings
to both, so a renamed producer fails a test instead of silently reading as an operator.
"""

from __future__ import annotations

SWEEPER_IDENTITY = "demo-sweeper"
"""The demo sweeper's producer identity, as its module declares it."""

WORKFLOW_PREFIX = "workflow:"
"""The prefix of the launcher's admitter identities (``workflow:investigate``)."""


def role_of(authority: str) -> str:
    """The role a public page names ``authority`` by.

    >>> role_of("demo-sweeper")
    "the demo's sweeper"
    >>> role_of("workflow:investigate")
    "the operator's workflow"
    >>> role_of("operator")
    'an operator'
    """
    if authority == SWEEPER_IDENTITY:
        return "the demo's sweeper"
    if authority.startswith(WORKFLOW_PREFIX):
        return "the operator's workflow"
    return "an operator"


__all__ = ["SWEEPER_IDENTITY", "WORKFLOW_PREFIX", "role_of"]
