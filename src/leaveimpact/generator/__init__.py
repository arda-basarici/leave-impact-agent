"""The generation job: causes world state, then seals it.

Composes the pure semantic generator in ``world`` with the adapters: materializes the
prose briefs through the writer and gates the result with the containment guards
(namespace, required facts, the independent extraction check), projects the frozen world
into Frappe, Jira, Calendar and the corpus idempotently — find-or-create against the
identity map, so a rerun adds nothing — and seals the artifacts: world and scenario
specifications to the world bucket, the truth manifest to the truth bucket, the world
version as the content hash of the frozen bundle. Runs as a separate job under an assumed
generator role, never inside the application process, because it knows both halves of the
benchmark.

Boundary: imports ``world``, ``adapters`` and ``core``; never the validator, the evaluator
or the investigator. Generation followed by validation is composed at the entry point, not
by one package importing the other.
"""
