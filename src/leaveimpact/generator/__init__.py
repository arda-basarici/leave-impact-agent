"""The generation job: causes world state, then seals it.

Composes the pure semantic generator in ``world`` with the adapters: materializes the
prose briefs through the writer and gates the result with the containment guards
(namespace, required facts, the independent extraction check) under the attempt loop of
``materialize``, with the prompt policy of ``prose`` and the guards of ``guards``; projects
the frozen world into Frappe, Jira and Calendar idempotently — find-or-create against the
identity map, so a rerun adds nothing — and the documents into the world bucket as sealed
objects, the application's corpus being a cache filled elsewhere; and seals the artifacts
in the ruled order: the world spec and the truth manifest to the truth bucket, the scenario
specs and the documents to the world bucket, the world version as the content hash of the
frozen bundle. Runs as an approval-gated job under the generator role, never inside the
application process, because it knows both halves of the benchmark.

Boundary: imports ``world``, ``adapters`` and ``core``; never the validator, the evaluator
or the investigator. Generation followed by validation is composed at the entry point, not
by one package importing the other.
"""
