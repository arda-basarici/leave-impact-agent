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
can actually obtain, anchored on the sealed key under the normal condition, or states
that no answer exists there because the leave or the policy cannot be read.
``characterization`` measures, once per world, how far that view and the dated one
disagree, the count of graded items the choice of view rests on. ``rows`` is the grade's
plain data, one record per expected or reported claim with expectation, presence,
standing and payload kept apart, and ``matching`` writes those rows from a report's
claims and the oracle. ``plan_checks`` asks whether the plan is valid against the oracle,
whether the report hangs together with itself, and whether it assessed everyone where a
conclusion is about everyone, three questions with their results kept apart, one record
per omission. ``grading`` gives every export exactly one outcome: graded against the
oracle, limited to the checks that need no expected answer, or excluded and counted.

``world_index`` is the sealed world by identity: every record, every comment and section,
the facts each carries, and what each requirement clause is scoped to, with the proof that
the clause's own text states that scope. ``observed_view`` builds, from an export's
completed reads, the facts those reads support and what they covered, and reports every
difference between what was read and what was sealed. ``plan_reading`` is the one reading
of a plan that the coherence check and the replay share. ``replay`` asks of each claim
whether the rules, fed only what the run read, conclude what it says; ``grounded`` derives
from its records which claims are grounded end to end, under the operational and the
strict reading; ``citations`` judges each evidence reference on three axes.

``trace_metrics`` measures what a run did, beside its outcome and for every export that
decodes, and is the entry that returns both. Its parts are ``source_discipline`` (the
reads by source, outcome and origin, the refused calls, the model calls, the repeats, the
operations no conforming harness records), ``cost_check`` (usage and cost recomputed from
the trace in three layers), ``proof_contribution`` (which reads supplied something a proof
rests on), ``retrieval_targets`` (the statements a scenario's answer depends on under a
condition, by removal through the oracle) and ``retrieval`` (which of them a run's reads
returned, and through which search at what rank).

The aggregation of rows and metrics into tables is the next commit group's; the evaluation
artifact's codec and the job's entry point follow it.
"""
