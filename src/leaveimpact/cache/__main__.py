"""``python -m leaveimpact.cache``: fill the corpus cache from the world store.

The composition root: the world store from the ``LEAVE_IMPACT_*`` names (the bucket with
its region, or the local twin's root), the database from ``DATABASE_URL``, the schema
ensured, then the job over the reader and the loader's three operations bound to the
database. Exit 2 for a configuration the job cannot start from, 1 for a refusal or an
unreachable store or database, 0 when every admitted version is loaded, found ready or
readmitted and every version the rule no longer serves is demoted. Every line printed is a
key=value line the deploy log keeps; a version the serving rule declines is a line, not a
failure, since a world without an approved verdict is the normal state of a world
mid-validation, and so is a demotion, which is the rule's current reading of a version an
earlier deploy served.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from leaveimpact.adapters.corpus.loader import (
    CacheRefused,
    CacheWorld,
    LoadOutcome,
    demote,
    ensure_schema,
    load_world,
    ready_versions,
)
from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.object_store.serving import ServingRefused
from leaveimpact.adapters.wiring import ConfigurationError, world_store_from_env, world_store_reader
from leaveimpact.cache.job import CacheJobRefused, fill_cache
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable

PROGRAM = "leaveimpact.cache"
DATABASE = "DATABASE_URL"


@dataclass(frozen=True, slots=True)
class PostgresCache:
    """The loader's three operations bound to the database at ``dsn``: the job's cache."""

    dsn: str

    def load(self, world: CacheWorld) -> LoadOutcome:
        return load_world(self.dsn, world)

    def ready_versions(self) -> frozenset[WorldVersion]:
        return ready_versions(self.dsn)

    def demote(self, version: WorldVersion) -> bool:
        return demote(self.dsn, version)


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
            cache=PostgresCache(dsn),
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
        f"readmitted={len(report.readmitted)} declined={len(report.declined)} "
        f"demoted={len(report.demoted)} unlisted={len(report.unlisted)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
