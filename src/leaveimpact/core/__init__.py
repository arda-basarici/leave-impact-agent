"""The domain, pure: what the real system believes, with no knowledge that a benchmark exists.

Holds the types every other package speaks (employee, team, work item, calendar event,
document, leave, and their ids), the predicate registry, the claim vocabulary with its
per-type grading keys, ``RunContext`` and world time, and the deterministic rules —
viability of a person for a need, the system-of-record authority table that resolves
conflicting observations, closed-world evaluation per declared evidence domain,
constraint checks. The investigator's deterministic core and the evaluator call the same
rule functions from here, which makes that sharing visible instead of duplicated (the
answer-key contract in DESIGN says why sharing rules is safe and sharing code between
generator and evaluator is not). Vendor-neutral ports that both the generator and the
investigator consume sit here too; an abstraction that describes how one vendor works
stays inside that vendor's adapter.

Boundary: never imports ``world`` — the production investigator depends on the domain
without depending on the benchmark that grades it; performs no I/O; reads no clock —
world time arrives in ``RunContext``, and the wall clock is read only at a composition
root. Populated step by step through the world milestone; the layout is the decision.
"""
