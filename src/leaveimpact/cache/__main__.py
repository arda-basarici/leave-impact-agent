"""``python -m leaveimpact.cache``: fill the corpus cache from the world store.

The composition root: the world store from the ``LEAVE_IMPACT_*`` names (the bucket with
its region, or the local twin's root), the database from ``DATABASE_URL``, the schema
ensured, then the job over the reader and the loader. Exit 2 for a configuration the job
cannot start from, 1 for a refusal or an unreachable store or database, 0 when every
admitted version is loaded or found ready. Every line printed is a key=value line the
deploy log keeps; a version the serving rule declines is a line, not a failure, since a
world without an approved verdict is the normal state of a world mid-validation.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence

from leaveimpact.adapters.corpus.loader import CacheRefused, ensure_schema, load_world
from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.object_store.serving import ServingRefused
from leaveimpact.adapters.wiring import ConfigurationError, world_store_from_env, world_store_reader
from leaveimpact.cache.job import CacheJobRefused, fill_cache
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable

PROGRAM = "leaveimpact.cache"
DATABASE = "DATABASE_URL"


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    try:
        store = world_store_from_env(env)
        dsn = env.get(DATABASE, "").strip()
        if not dsn:
            raise ConfigurationError(f"{DATABASE} is not set and the cache job needs it")
    except ConfigurationError as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 2
    development = store.local_root is not None
    print(f"store={'local:' + str(store.local_root) if development else 's3:' + str(store.bucket)}")
    try:
        ensure_schema(dsn)
        report = fill_cache(
            world_store_reader(store),
            development=development,
            load=lambda world: load_world(dsn, world),
            emit=print,
        )
    except (
        CacheJobRefused,
        CacheRefused,
        ServingRefused,
        MalformedRecord,
        SourceUnreachable,
        AccessRefused,
        ObjectStoreUnreachable,
        ObjectStoreMisconfigured,
    ) as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 1
    print(
        f"loaded={len(report.loaded)} already_ready={len(report.already_ready)} "
        f"declined={len(report.declined)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
