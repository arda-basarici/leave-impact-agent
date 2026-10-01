"""Grading of recorded runs against the sealed truth, in the frozen claim vocabulary.

The evaluator reads a world's three sealed files (the world spec, the scenario specs,
the truth manifest) and a run's export, and grades what the run observed: which claims
matched the key and whether their payloads were correct, reported apart; whether the
plan is valid for the run's condition; and whether each claim is grounded, meaning the
pure rules in ``core`` replayed over the run's own reads reproduce its payload. It
never re-reads a vendor, which is what
separates it from the validator: the validator proves the live systems realize the
sealed spec before any run, the evaluator judges a run from its record alone, so an
evaluation is reproducible from the export and the truth it names.

Boundary: its own package so that the answer key stays out of the investigator's reach
by the import law and not by credential alone. Imports ``world``, ``adapters`` and
``core``; never ``agent``, ``generator`` or ``validator`` (the lateral ban), and
``agent`` never imports it, so the grader and the graded share only ``core``'s rules.

``sealed_world`` joins the three sealed files into the world a run is graded against,
each scenario's construction record rebuilt, every cross-file claim checked and every
sealed key reproduced by today's rules, and loads them through the object-store reader.
``condition`` reads the condition a run was observed under off its trace. ``oracle``
derives what the rules conclude about a scenario under a condition, over the facts a run
can actually obtain, anchored on the sealed key under the normal condition.
``characterization`` measures, once per world, how far that view and the dated one
disagree, the count of graded items the choice of view rests on. ``rows`` is the grade's
plain data, one record per expected or reported claim with expectation, presence,
standing and payload kept apart, and ``matching`` writes those rows from a report's
claims and the oracle. ``plan_checks`` asks whether the plan is valid against the oracle
and whether the report hangs together with itself, two questions with their findings
kept apart. The outcome of a whole run follows in the same build step (the investigator
milestone's third).
"""
