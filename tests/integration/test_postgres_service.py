"""The integration level's floor: the PostgreSQL the suite is configured against answers.

Proves the CI service wiring (and, locally, the Compose store) rather than declaring
it. Every store test that follows inherits this assumption; when this one fails the
cause is the environment, not the code under test. Skips — never fails — when no
``DATABASE_URL`` is set, so a plain ``pytest`` on a workstation without the service
stays green.
"""

import os

import psycopg
import pytest

pytestmark = pytest.mark.integration


def test_postgres_answers() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL unset — the PostgreSQL service is not running here")
    with psycopg.connect(url, connect_timeout=5) as conn:
        assert conn.execute("SELECT 1").fetchone() == (1,)
