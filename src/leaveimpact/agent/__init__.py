"""The investigator and its baselines: the systems the benchmark measures.

The investigator gathers evidence about one leave across the organizational systems
through the read ports alone, emits claims in the frozen vocabulary and a coverage plan
for a human to approve, and never decides. Beside it stand the two preregistered
baselines it is measured against, rules-only and single-shot, sharing its ports, its
claim vocabulary and its run export. The loop's framework is contained inside this
package: the ports, the tool registry and the run record know nothing of it.

Boundary: the investigator is blind to the benchmark by the import law, not by
convention. Imports ``adapters`` and ``core``; never ``world``, ``generator``,
``validator`` or ``evaluator``, so the answer key is unreachable at source level and
the write ports are unreachable by module path.

``execution`` is the one path for a declared tool call, the frozen prefetch's now and
the model's when the registry arrives: validation, the port and the method, one
recorded operation with one of the six outcomes, the per-source stop state, and the
prefetch run over it. ``composer`` is the one path from a run's reads and the facts a
model stated to claims, shared by every system whose claims the rules write: the join, the
span binding and the scope rules from ``core``, the shared rules through ``core``'s
composing pass, and ``report``, the one reporting policy that writes the rules'
conclusions as claims, constraints among them; it carries the composing policy every such
export records. ``fact_entries`` parses a model's fact entries into stated facts, or keeps
an unreadable one whole beside its reason. ``rules_only`` is the first system: the
prefetch, the structured projection as its whole view, ruling 4's preconditions (a defect
at its operation, a source that contradicts itself among them, or an abstention with no
claims), and the composer given no statement;
``export`` writes a run as the artifact the evaluator grades, under the provenance the
harness around it supplies; ``registered`` builds that provenance from the preregistration
and refuses a run whose registration differs from what this code computes or declares.

The event log is the agent's own execution control, ownership and accounting, which the
evaluator never reads, and its pure half lives here beside one PostgreSQL module to come:
``log_events`` (the sixteen event kinds, their keys, bytes and codec), ``log_transition``
(the one function that decides what a log may hold next, and the state it folds to),
``log_ending`` (the ending and the status as functions of that state), ``answer_parse``
(the derived parse from a response as it arrived to what its answer carried) and
``log_reader`` (a closed log to its format 3 export, with no connection, worker or graph).
"""
