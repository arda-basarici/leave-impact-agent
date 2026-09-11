"""The ports: what the domain needs from the four systems, stated below any vendor.

A port describes what the domain asks of a system — the people a leave affects, the
work they own, the meetings they attend, the documents that constrain a plan — and
never how a vendor answers it; an abstraction that describes how Jira works belongs
inside the Jira adapter (DESIGN, "Package boundaries and the import law"). A port is
declared here only when two consumers need it: the generator's projectors and the
validator today, the investigator at its milestone.

Ports return observed domain entities, an entity with the source it was read from
(``observed``), and never facts. Turning an entity into facts and gaps is the
domain's, in one derivation the rules can trust, so an adapter translates shape and
identity and does not decide what is true. The one exception is the corpus: the
``requires`` fact comes from the world's structured brief, never from document text,
so the document port searches and returns text and derives nothing.

The read side and the write side are two modules on purpose. The generator's
projectors write; the validator and the investigator only read; and the import law
lets only ``adapters`` and ``generator`` import ``write``, so read-only is a property
of the module graph rather than a promise about which methods get called. This
package therefore re-exports nothing: a writer is reachable only by the module path
the law can see, and the readers, the observed wrapper and the fault types are
re-exported from ``leaveimpact.core`` like every other domain name.

Faults keep three cases apart, because closure treats them differently (``errors``):
a record that is not there is a plain ``None`` or an empty tuple — missing data is
evidence; a source that cannot answer after the adapter's retries raises
``SourceUnreachable`` — an epistemic limit the run condition records; a record the
adapter cannot translate raises ``MalformedRecord`` — a defect, never an unknown. The
write side has a fourth: an identity the source already holds with other state raises
``IdentityConflict``, and the projector stops rather than adopt or overwrite it.
"""
