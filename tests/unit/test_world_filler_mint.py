"""The generator's own filler pool: minted after the whole assembly from the world's book and a
derived generator, so the planted part is what the seed produces without filler; shaped and
titled from the name book, a release and a client in turn, briefed for decoys and nothing of
the world; described by the plan it was asked for and sealed with it. Five seeds in the suite,
twenty under the slow mark (the generator step's ruling 9 as amended)."""

from __future__ import annotations

import json
from datetime import date
from random import Random

import pytest

from leaveimpact.core.anchors import SKILL_KIND, SurfaceForm
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import DocumentKind, EntityKind, Source
from leaveimpact.core.facts import EvidenceRef, Fact
from leaveimpact.core.ids import clause_id, document_id, employee_id, work_item_id
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref, employee_ref
from leaveimpact.world import (
    BASE_LEVELS,
    DEFAULT_PARAMS,
    FICTIONAL_ID_BASE,
    FillerBrief,
    FillerExhausted,
    FillerNamesTheWorld,
    FillerPlan,
    Namespace,
    ProseContractError,
    Register,
    SealedLevel,
    SectionTarget,
    SemanticWorld,
    assemble_semantic_world,
    bundle,
    compose,
    decode_world_spec,
    encode_semantic_world,
    filler_brief_for,
    filler_mint,
    lexicon_of,
    strip_filler,
)
from leaveimpact.world.construction import Minting
from leaveimpact.world.filler_mint import mint_filler
from leaveimpact.world.truth_decoder import decode_truth_manifest
from tests.unit.filler_fixture import stand_in_bodies
from tests.unit.prose_fixture import record_for

WORLD_START = date(2026, 1, 1)
SEEDS = (7, 11, 23, 42, 101)
PLAN = FillerPlan(12, 2, (SealedLevel("padded", 6),))


def pooled(seed: int, plan: FillerPlan = PLAN) -> SemanticWorld:
    return assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, "golden", plan)


def plain(seed: int) -> SemanticWorld:
    return assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, "golden")


def invariants(world: SemanticWorld) -> None:
    """Every statement the mint makes about its pool, checked on one world."""
    pool = world.filler
    assert len(pool) == world.filler_plan.documents
    assert world.levels == (*BASE_LEVELS, *world.filler_plan.levels)
    planted_documents = [p.entity for s in world.scenarios for p in s.owned.documents]
    last_planted = max(int(d.id.rsplit("_", 1)[-1]) for d in planted_documents)
    assert all(int(p.entity.id.rsplit("_", 1)[-1]) > last_planted for p in pool)
    titles = [p.entity.title for p in pool]
    assert len(set(titles)) == len(titles)
    forms = lexicon_of(
        world.org,
        [p.entity for s in world.scenarios for p in s.owned.work_items],
        planted_documents,
        [p.entity for s in world.scenarios for p in s.owned.events],
    ).forms()
    spelled = {form.form.casefold() for form in forms}
    titled = {
        form.form.casefold()
        for form in forms
        if form.kind
        in {k.value for k in (EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.DOCUMENT)}
    }
    for title in titles:
        folded = title.casefold()
        assert folded not in spelled
        assert not any(folded in other or other in folded for other in titled)
    briefs_by_document: dict[str, list[FillerBrief]] = {p.entity.id: [] for p in pool}
    for brief in world.filler_briefs:
        assert isinstance(brief, FillerBrief)
        assert isinstance(brief.target, SectionTarget)
        briefs_by_document[brief.target.document_id].append(brief)
    for position, planted in enumerate(pool):
        assert planted.observable_from == WORLD_START
        assert planted.entity.sections == ()
        owed = briefs_by_document[planted.entity.id]
        assert sorted(b.target.position for b in owed) == list(
            range(world.filler_plan.sections_per_document)
        )
        # Releases at the even positions, clients at the odd, so every prefix holds both.
        expected_kind = EntityKind.WORK_ITEM.value if position % 2 == 0 else "client"
        for brief in owed:
            own = (EntityKind.DOCUMENT.value, planted.entity.id)
            kinds = {(f.kind, f.id) for f in brief.namespace.forms}
            assert own in kinds
            assert brief.register is Register.FILLER_REQUIREMENT
            skills = [f for f in brief.namespace.forms if f.kind == SKILL_KIND]
            assert len(skills) == filler_mint.SKILLS_PER_BRIEF
            artifacts = [
                f
                for f in brief.namespace.forms
                if f.kind not in (SKILL_KIND, EntityKind.DOCUMENT.value)
            ]
            [artifact] = artifacts
            assert artifact.kind == expected_kind
            assert artifact.form in planted.entity.title
            if artifact.kind == EntityKind.WORK_ITEM.value:
                assert brief.fictional == (EntityRef(EntityKind.WORK_ITEM, artifact.id),)
                assert int(artifact.id.rsplit("_", 1)[-1]) >= FICTIONAL_ID_BASE
            else:
                assert brief.fictional == ()



# --- The pool over five seeds ---------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_the_planted_world_is_what_the_seed_produces_without_filler(seed: int) -> None:
    assert strip_filler(pooled(seed)) == plain(seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_pool_holds_the_mint_s_invariants(seed: int) -> None:
    invariants(pooled(seed))


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(1, 21))
def test_twenty_seeds_hold_the_mint_s_invariants_and_the_stripped_equality(seed: int) -> None:
    world = pooled(seed)
    invariants(world)
    assert strip_filler(world) == plain(seed)


def test_the_same_seed_mints_the_same_pool_and_another_seed_another() -> None:
    assert pooled(7) == pooled(7)
    assert [p.entity.title for p in pooled(7).filler] != [p.entity.title for p in pooled(11).filler]


def test_a_plan_with_no_documents_seals_no_level_beyond_the_base() -> None:
    # The provenance writes a plan only when it has documents; a level over an empty pool
    # would seal and never decode (the group 2 review), so the plan refuses it first.
    with pytest.raises(ValueError, match="seals no level beyond the base"):
        FillerPlan(0, 0, (SealedLevel("padded", 0),))


def test_a_plan_past_the_book_s_capacity_fails_loud() -> None:
    with pytest.raises(FillerExhausted, match="book is exhausted after"):
        pooled(7, FillerPlan(10_000, 1))


def test_a_fictional_name_the_world_spells_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    world = plain(7)
    real_client = world.org.employees[0].name  # a real spelling the lexicon holds
    monkeypatch.setattr(filler_mint, "FICTIONAL_CLIENTS", (real_client,))
    ids = Minting()
    for _ in range(40):
        ids.document()
    with pytest.raises(FillerNamesTheWorld, match="is the"):
        mint_filler(ids, Random(1), FillerPlan(2, 1), world.org, world.scenarios, WORLD_START)


def test_a_filler_title_around_a_planted_one_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    world = plain(7)
    planted_title = next(p.entity.title for s in world.scenarios for p in s.owned.documents)
    monkeypatch.setattr(filler_mint, "RELEASE_TITLES", (("runbook", planted_title + " ({name})"),))
    ids = Minting()
    for _ in range(40):
        ids.document()
    with pytest.raises(FillerNamesTheWorld, match="contain one another"):
        mint_filler(ids, Random(1), FillerPlan(1, 1), world.org, world.scenarios, WORLD_START)


# --- The filler brief's contract -----------------------------------------------------------


DOCUMENT = Document(
    document_id(9001), "Release runbook: Kelp release", DocumentKind.RUNBOOK, WORLD_START, ()
)
RELEASE = SurfaceForm(EntityKind.WORK_ITEM.value, work_item_id(FICTIONAL_ID_BASE), "Kelp release")
SKILL = SurfaceForm(SKILL_KIND, "kafka", "Kafka")


def test_a_filler_brief_declares_its_fictional_entities_and_admits_a_client_as_a_name() -> None:
    brief = filler_brief_for(
        DOCUMENT, clause_id(9001), 0, Register.FILLER_REQUIREMENT, (RELEASE,), (SKILL,)
    )
    assert brief.fictional == (EntityRef(EntityKind.WORK_ITEM, RELEASE.id),)
    assert brief.required == () and brief.allowed == () and brief.target.position == 0
    assert [(f.kind, f.id) for f in brief.namespace.forms] == sorted(
        (f.kind, f.id) for f in brief.namespace.forms
    )
    assert {(f.kind, f.id) for f in brief.namespace.forms} == {
        (EntityKind.DOCUMENT.value, DOCUMENT.id),
        (RELEASE.kind, RELEASE.id),
        (SKILL.kind, SKILL.id),
    }
    client = SurfaceForm("client", "halcyon", "Halcyon")
    noted = filler_brief_for(
        DOCUMENT, clause_id(9002), 1, Register.FILLER_REQUIREMENT, (client,), (SKILL,)
    )
    assert noted.fictional == () and ("client", "halcyon") in {
        (f.kind, f.id) for f in noted.namespace.forms
    }


def test_a_filler_brief_refuses_facts_a_planted_register_a_comment_and_an_undeclared_entity() -> (
    None
):
    namespace = Namespace(
        (SurfaceForm(EntityKind.DOCUMENT.value, DOCUMENT.id, DOCUMENT.title), RELEASE), (), ()
    )
    target = SectionTarget(clause_id(9001), DOCUMENT.id, 0)
    # An allowed fact of the carrier's own source, the one shape the brief contract admits,
    # which the filler contract then refuses on its own rule.
    fact = Fact(
        employee_ref(employee_id(1)),
        PredicateName.HAS_SKILL,
        "kafka",
        EvidenceRef(Source.CORPUS, clause_ref(clause_id(8999))),
        WORLD_START,
    )
    with pytest.raises(ProseContractError, match="carries no required or allowed fact"):
        FillerBrief(target, (), (fact,), namespace, Register.FILLER_REQUIREMENT)
    with pytest.raises(ProseContractError, match="written in a filler register"):
        FillerBrief(target, (), (), namespace, Register.RUNBOOK)
    with pytest.raises(ProseContractError, match="a form of the namespace"):
        FillerBrief(
            target,
            (),
            (),
            namespace,
            Register.FILLER_REQUIREMENT,
            fictional=(EntityRef(EntityKind.WORK_ITEM, work_item_id(9500)),),
        )
    low = SurfaceForm(EntityKind.WORK_ITEM.value, work_item_id(12), "Low release")
    with pytest.raises(ProseContractError, match=f"numbered from {FICTIONAL_ID_BASE}"):
        filler_brief_for(DOCUMENT, clause_id(9001), 0, Register.FILLER_REQUIREMENT, (low,), ())


# --- Sealing: the plan in the provenance, the brief's declared entities in the manifest -------


def test_a_pooled_world_seals_its_plan_and_its_briefs_and_a_plain_one_seals_neither_name() -> None:
    world = pooled(7)
    bodies = stand_in_bodies(world)
    sealed = bundle(compose(world, bodies, record_for(bodies)))
    spec = json.loads(sealed.world_spec.content)
    assert spec["provenance"]["filler_plan"] == {"documents": 12, "sections_per_document": 2}
    decoded = decode_world_spec(sealed.world_spec.content)
    assert decoded.filler_plan == PLAN
    assert decoded.levels == (*BASE_LEVELS, SealedLevel("padded", 6))
    manifest = decode_truth_manifest(sealed.truth_manifest.content)
    assert manifest.filler_briefs == world.filler_briefs
    assert all(isinstance(brief, FillerBrief) for brief in manifest.filler_briefs)
    provenance = encode_semantic_world(plain(7))["provenance"]
    assert isinstance(provenance, dict) and "filler_plan" not in provenance
    assert "fictional" not in json.dumps(encode_semantic_world(plain(7)))
