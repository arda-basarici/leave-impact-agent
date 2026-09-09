"""The authority table: the system of record's observation wins whatever the order, an
unresolvable set of observations is refused loudly, and the planted conflicts of a view are
derived from the facts — single-valued predicates only, differing values only, reachable
sources only."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    REGISTRY,
    AuthorityRule,
    ConflictFinding,
    FactBase,
    Observation,
    PredicateName,
    Resolution,
    RunCondition,
    Source,
    conflicts_in,
    employee_ref,
    resolve,
    work_item_ref,
)
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
BOB = employee_ref(w.BOB)
LIVE = Observation(Source.JIRA, ALICE)
STALE = Observation(Source.CORPUS, BOB)
STALE_SKILL = Observation(Source.CORPUS, "kafka")
NORMAL = RunCondition.all_reachable()


def test_the_system_of_record_wins_whatever_the_order() -> None:
    expected = Resolution(ALICE, AuthorityRule.SYSTEM_OF_RECORD_WINS, LIVE)
    assert resolve(PredicateName.OWNS_WORK_ITEM, (LIVE, STALE)) == expected
    assert resolve(PredicateName.OWNS_WORK_ITEM, (STALE, LIVE)) == expected


def test_observations_that_do_not_form_a_resolvable_conflict_are_refused() -> None:
    with pytest.raises(ValueError, match="at least two observations"):
        resolve(PredicateName.OWNS_WORK_ITEM, (LIVE,))
    with pytest.raises(ValueError, match="observes each source once"):
        resolve(PredicateName.OWNS_WORK_ITEM, (LIVE, Observation(Source.JIRA, BOB)))
    with pytest.raises(ValueError, match="calendar is outside the evidence domain"):
        resolve(PredicateName.OWNS_WORK_ITEM, (LIVE, Observation(Source.CALENDAR, BOB)))
    # No two-source domain can lack its record; a wider domain shows the table refusing to guess.
    wide = dict(REGISTRY)
    wide[PredicateName.HAS_SKILL] = replace(
        REGISTRY[PredicateName.HAS_SKILL], evidence_domain=frozenset(Source)
    )
    with pytest.raises(ValueError, match="no observation from the system of record frappe"):
        resolve(
            PredicateName.HAS_SKILL, (Observation(Source.JIRA, "kafka"), STALE_SKILL), registry=wide
        )


def test_the_planted_conflict_is_derived_from_the_facts() -> None:
    view = w.WORLD.at(w.NOW, NORMAL)
    assert conflicts_in(view) == (
        ConflictFinding(
            work_item_ref(w.TICKET),
            PredicateName.OWNS_WORK_ITEM,
            (w.STALE_OWNER, w.LIVE_OWNER),
            Resolution(ALICE, AuthorityRule.SYSTEM_OF_RECORD_WINS, LIVE),
        ),
    )
    assert conflicts_in(view)[0].observations == (STALE, LIVE)


def test_agreeing_sources_and_multi_valued_sets_are_not_conflicts() -> None:
    agreeing = FactBase((w.LIVE_OWNER, w.ticket_owner_in_corpus(ALICE)))
    assert conflicts_in(agreeing.at(w.NOW, NORMAL)) == ()
    # Deniz holds Kafka by a comment and nothing on the HR record: a set, not a disagreement.
    skills_only = FactBase(
        (w.DENIZ_KAFKA_IN_COMMENT, w.hr(w.DENIZ, PredicateName.HAS_SKILL, "postgres", "skills"))
    )
    assert conflicts_in(skills_only.at(w.NOW, NORMAL)) == ()


def test_a_conflict_needs_both_sources_visible() -> None:
    assert conflicts_in(w.WORLD.at(w.NOW, NORMAL.without(Source.CORPUS))) == ()
    assert conflicts_in(w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))) == ()
