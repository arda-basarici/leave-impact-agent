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
the write ports are unreachable by module path. The first arrival is the rules-only
baseline at the investigator milestone's build step 5; until then the package holds
this contract and nothing else.
"""
