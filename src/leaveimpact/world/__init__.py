"""The benchmark, pure: everything that exists only because the world is constructed.

The world specification (people, teams, skills, managers, tickets, meetings, leaves),
the scenario definitions (a fourteen-day slice, the leave inside it, ``now`` and the
stable-now interval, class and modifiers), the truth fact base with dated provenance,
the per-scenario keys (planted impacts, named distractors with their reason, the
``must_assess`` set, required sources, the completeness condition), the prose briefs and
templates, and the semantic generator that derives all of it from a seed, parameters and
a generator version. The construction invariants live here as well — the authored
``must_assess`` verdict must equal the rule's verdict over the fact base, and a scenario's
intended class must emerge from static org facts by selection — so a construction bug
fails generation instead of grading an agent wrong.

Boundary: imports ``core`` and nothing above it; performs no I/O, so semantic generation
can never quietly call a vendor or a model; is never imported by the investigator, which
is what keeps the answer key unreachable at source level and not only by credential.
Prose is not written here: this package emits briefs, the generator materializes them.
"""
