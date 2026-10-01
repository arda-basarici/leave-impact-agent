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
each scenario's construction record rebuilt and every cross-file claim checked, and
loads them through the object-store reader. The oracle and the grading follow in the
same build step (the investigator milestone's third).
"""
