"""One external boundary per subpackage: vendor shape and identity translated to ``core`` types.

``frappe`` (HR: people, leave, balances), ``jira`` (work items), ``calendar`` (events and
free/busy), ``corpus`` (the document store over PostgreSQL), ``prose`` (the writer and
checker models behind the materializer). Each owns its credentials, HTTP, pagination,
identity mapping and connection-fault retries, and stays thin: shape and identity are
translated, every world fact passes through as the system reports it, contradictions
included, because an adapter that normalized a planted inconsistency away would destroy
the evidence the evaluation grades (DESIGN, "adapters that translate but never launder").

Two rules hold across the subpackages. A credential is supplied at composition and never
embodied — one ``JiraAdapter`` taking a credential, never a generator flavour beside an
agent flavour — so the generator's principal and the investigator's read principal differ
in authority and share transport. And siblings never import one another: cross-system
orchestration lives above the adapters; a helper shared by all of them lives at this
level, not inside one sibling — ``transport``, the HTTP session under the retry rule,
where every request declares whether it is replayable; ``manifest``, the world
manifest that aggregates the four configurations with the projection's receipts, written
by the generator and decoded by every reader that builds adapters for a projected world;
and ``filestore``, the whole-or-nothing file replacement under every local artifact,
typed as bytes so the generator's manifest and the validator's verdict share it without
either importing the other.
"""
