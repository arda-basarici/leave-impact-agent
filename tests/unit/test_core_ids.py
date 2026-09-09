"""Ids: every numbered kind shares one shape, a negative number is refused, skills are keys."""

from collections.abc import Callable

import pytest

from leaveimpact.core import ids


@pytest.mark.parametrize(
    ("make", "prefix"),
    [
        (ids.employee_id, "emp"),
        (ids.team_id, "team"),
        (ids.component_id, "comp"),
        (ids.work_item_id, "ticket"),
        (ids.comment_id, "comment"),
        (ids.event_id, "event"),
        (ids.document_id, "doc"),
        (ids.clause_id, "clause"),
        (ids.leave_id, "leave"),
        (ids.scenario_id, "scenario"),
    ],
)
def test_numbered_kinds_share_the_prefixed_zero_padded_shape(
    make: Callable[[int], str], prefix: str
) -> None:
    assert make(7) == f"{prefix}_007"
    assert make(1234) == f"{prefix}_1234"
    assert ids.is_numbered_id(make(7))


def test_numbered_ids_sort_by_number_within_three_digits() -> None:
    assert sorted(ids.employee_id(n) for n in (30, 2, 17)) == ["emp_002", "emp_017", "emp_030"]


def test_a_negative_number_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="emp:-1"):
        ids.employee_id(-1)


@pytest.mark.parametrize("key", ["kafka", "postgres_15", "k8s"])
def test_skill_keys_are_lower_case_vocabulary(key: str) -> None:
    assert ids.skill_id(key) == key


@pytest.mark.parametrize("key", ["Kafka", "kafka streams", "", "1st"])
def test_a_malformed_skill_key_is_refused(key: str) -> None:
    with pytest.raises(ValueError, match="vocabulary key"):
        ids.skill_id(key)


@pytest.mark.parametrize("leaked", ["LIA-42", "emp-017", "emp_17", "10481"])
def test_a_vendor_key_does_not_pass_as_a_world_id(leaked: str) -> None:
    assert not ids.is_numbered_id(leaked)
