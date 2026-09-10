"""The two faults a port can raise, kept apart because the run treats them differently.

Missing data is evidence, unavailable infrastructure is an epistemic limit, malformed
data is a defect (ruled at step 5 of the world milestone's build). The first never
raises: a record that is not there is a ``None`` or an empty tuple, and what its
absence means — closed-world false, or unknown behind a gap — is closure's to decide.
The other two are exceptions with no common base, on purpose: a harness that could
catch "any port failure" in one clause would fold a defect into a legitimate unknown,
and the whole point of the split is that it cannot.

A vendor's own exception never leaves its adapter. The adapter retries connection
faults itself, and what it raises afterwards is one of these, with the vendor error
chained as the cause for the log and never as the type the caller sees. The
investigator's harness marks the source unreachable for the rest of the run at the
first ``SourceUnreachable`` and stops calling it; facts read before the fault stay
facts, because closure checks a positive fact before it checks reachability.
``MalformedRecord`` propagates: in the world milestone the generator and the
validator want the crash, since catching a malformed projection is the validator's
job; whether the investigator degrades instead is the investigator milestone's
runtime policy.
"""

from __future__ import annotations

from leaveimpact.core.enums import Source


class SourceUnreachable(Exception):
    """``source`` could not answer after the adapter's retries — a run condition, not a fact.

    >>> raise SourceUnreachable(Source.JIRA, "refused after 3 attempts")
    Traceback (most recent call last):
    ...
    leaveimpact.core.ports.errors.SourceUnreachable: jira unreachable: refused after 3 attempts
    """

    def __init__(self, source: Source, reason: str) -> None:
        super().__init__(f"{source.value} unreachable: {reason}")
        self.source = source
        self.reason = reason


class MalformedRecord(Exception):
    """``source`` answered, and the record at ``locator`` cannot be translated into a domain entity.

    The locator is the record's location as the source names it, an opaque string,
    because translation may fail before a domain identity exists — a payload with no
    usable id has no ``EntityRef`` to report. When identity did translate, the adapter
    puts the domain id in the locator too.

    >>> raise MalformedRecord(Source.FRAPPE, "Employee/HR-EMP-00017", "no world id")
    Traceback (most recent call last):
    ...
    leaveimpact.core.ports.errors.MalformedRecord: frappe record Employee/HR-EMP-00017: no world id
    """

    def __init__(self, source: Source, locator: str, reason: str) -> None:
        super().__init__(f"{source.value} record {locator}: {reason}")
        self.source = source
        self.locator = locator
        self.reason = reason
