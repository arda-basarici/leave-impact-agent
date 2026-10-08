"""The corpus cache job: the application's own shell on the instance, filling PostgreSQL
from the served worlds in the world bucket.

The canonical documents leave the generator as sealed objects under ``worlds/<version>/``,
because the generator runs on a GitHub runner that cannot reach the instance's PostgreSQL
and holds no database credential (DESIGN, the corpus ruling of the step 12 interview); the
application's corpus is a cache the instance fills from those objects. This package is
that filling, run by the deploy script after PostgreSQL is healthy and before the
application is declared landed (the M2 step 9 build): it lists the versions under the
prefix with the instance role, admits each by the serving rule, reads the levels object
and every document the manifest receipts, verifies what it read against the manifest, and
loads the version in one transaction, ready last.

A rank-3 shell beside the validator and the evaluator, importing the adapters and the
world codecs and never a benchmark job: the generator writes what this reads, the
validator judges it, and the evaluator holds the answer key's reader (the import law's
denied edges). ``job`` is the orchestration over a store reader and a loading callable,
testable with neither a bucket nor a database; ``__main__`` is the composition root that
reads the environment and wires the real ones.
"""
