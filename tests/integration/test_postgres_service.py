"""The integration level's floor: the PostgreSQL the suite is configured against answers.

Proves the CI service wiring (and, locally, the Compose store) rather than declaring
it. Every store test that follows inherits this assumption; when this one fails the
cause is the environment, not the code under test. Without ``DATABASE_URL`` it skips
on a workstation (no service running is normal there) but fails under ``CI`` — in the
pipeline a missing URL means the service wiring broke, and a skip would hide it.
"""

import os

import psycopg
import pytest

pytestmark = pytest.mark.integration


def test_postgres_answers() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("DATABASE_URL unset in CI — the PostgreSQL service wiring is broken")
        pytest.skip("DATABASE_URL unset — the PostgreSQL service is not running here")
    with psycopg.connect(url, connect_timeout=5) as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)
