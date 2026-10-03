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
prefetch run over it. ``rules_only`` is the first system: the prefetch, the structured
projection as its whole view, ruling 4's preconditions (a defect at its operation, or an
abstention with no claims), the shared rules through ``core``'s composing pass, and
``report``, the one reporting policy that writes the rules' conclusions as claims;
``export`` writes a run as the artifact the evaluator grades, under the provenance the
harness around it supplies; ``registered`` builds that provenance from the preregistration
and refuses a run whose registration differs from what this code computes or declares.
"""
