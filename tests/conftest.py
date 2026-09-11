"""Suite-wide fixtures: the cassette configuration every recorded test inherits.

pytest-recording looks a ``vcr_config`` fixture up by name; the content lives in
``recording`` so the safety test and the fixture read one definition.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import recording


@pytest.fixture(scope="session")
def vcr_config() -> dict[str, Any]:
    return recording.vcr_config()
