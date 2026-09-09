"""Read-only verification that projection realized the declared world.

Re-reads the live systems through the adapters and re-derives each scenario's structured
expectations — who is on leave, which work items are open per person, which blocks are
busy — at two instants inside the stable-now interval, and compares them with the world
specification. It validates the projected systems rather than the generator's
intermediate objects on purpose: the projection seam is under test too, and a shared
generation bug cannot yield an evaluation that agrees with a wrong world. It reads the
world specification and the live systems, and never the truth manifest; the truth-level
construction invariants are ``world``'s, run before sealing.

Boundary: its own package so that read-only is enforceable by the import law — inside
``generator`` nothing could stop a validator module from importing a projector. Imports
``world``, ``adapters`` and ``core``; never ``generator``.
"""
