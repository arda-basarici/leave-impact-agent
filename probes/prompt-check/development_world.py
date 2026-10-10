"""What the prompt check's scripts share: the first development world read from the local
object store, its six live-iteration scenarios by the registration's seeded draw, and the
investigator's configuration under the draft registration as the production work command
would compose it.

The world is the generator step's, seed 101, sealed unprojected under
``data/object-store`` (the generator-step findings); the probe reads it as the evaluator
does, from the truth root and the world root, and never from a bucket. The six scenarios
are drawn by the rule the registration step built and the contract step retired with the
scenario sets (``development_selection``, commit ``281ac3f``): the registered number from
each tier, two, sampled by a stream derived from the registration's statistics seed under
the name ``development-scenarios`` and the tier's name, reading each scenario's tier and
nothing else of its key. The development protocol lists the first world's six as bare ids
because a scenario's tier is sealed and the repository is public; this module prints
nothing, and the scripts over it write ids alone to the files they leave beside themselves.

The configuration is what ``agent/__main__.py``'s work command composes from its line: the
role filled with Haiku 4.5 on the ``eu.`` profile at temperature 0 and an output maximum of
8,192 tokens, priced from ``prices.json`` beside this file (the Frankfurt on-demand rates
the bedrock probe captured, the four classes the worst case needs) and counted against the
base model id, the one identifier of four the input-bound probe found served. The draft
registration holds the roles, the attribution table, the re-dispatch policy and the entry
schema pending, so ``agent_provenance`` records this code's current values, as a
development run does.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from random import Random

from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import RoleFilling, agent_provenance, effective_rules
from leaveimpact.agent.worker import WorkerConfiguration
from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.pricing import PriceTable, basis_for, decode_price_table, worst_case_cost
from leaveimpact.core.registration import Registration
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_record import PricingSelection
from leaveimpact.core.run_timing import HarnessRevision, TreeState
from leaveimpact.core.tools import Role
from leaveimpact.core.worldtime import RunContext
from leaveimpact.evaluator.intervals import derived_seed
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.world.scenario import Scenario, Tier
from tests.unit import worker_support as support

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
STORE_ROOT = REPOSITORY / "data" / "object-store"
REGISTRATION_FILE = REPOSITORY / "preregistration" / "registration.json"
PRICES_FILE = HERE / "prices.json"

WORLD = WorldVersion("b7ec45636101ffd29acacef70a57f13e5b5d1da8ff7a0fe77f0f36394bde3c01")
"""The first development world: seed 101, the golden plan, sealed unprojected."""

CONDITION, LEVEL = "normal", "base"
MODEL = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
COUNTING_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-central-1"
OUTPUT_MAXIMUM = 8_192
"""Room for a finalization call that states every fact of a scenario in one batch; the
span probe's 4,096 held its per-section answers, and a whole run's facts are several
sections' worth. Inside the registered finalization token reserve of 20,000."""

PER_TIER = 2
DRAW_NAME = "development-scenarios"


@cache
def registration() -> Registration:
    return decode_registration_bytes(REGISTRATION_FILE.read_bytes())


def registration_commit() -> str:
    """The commit the registration file was last changed at: what a work line passes as the
    registration's commit."""
    return subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(REGISTRATION_FILE)],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()


@cache
def price_table() -> PriceTable:
    return decode_price_table(json.loads(PRICES_FILE.read_text(encoding="utf-8")))


@cache
def development_world() -> SealedWorld:
    """The development world joined and proven from the local store's two roots."""
    return load_sealed_world(
        WORLD, LocalObjectReader(STORE_ROOT / "truth"), LocalObjectReader(STORE_ROOT / "world")
    )


def live_iteration_scenarios(world: SealedWorld) -> tuple[Scenario, ...]:
    """The six live-iteration scenarios of ``world`` by the retired registration rule: two
    per tier, each tier's ids sorted and sampled by the stream derived from the
    registration's seed, the name and the tier; returned in id order."""
    seed = registration().statistics.seed
    selected: list[ScenarioId] = []
    for tier in Tier:
        ids = sorted(s.spec.id for s in world.scenarios if s.key.tier is tier)
        if len(ids) < PER_TIER:
            raise ValueError(f"a tier of {len(ids)} scenarios cannot give {PER_TIER}")
        selected.extend(Random(derived_seed(seed, DRAW_NAME, tier.value)).sample(ids, PER_TIER))
    by_id = {s.spec.id: s for s in world.scenarios}
    return tuple(by_id[scenario_id] for scenario_id in sorted(selected))


@dataclass(frozen=True)
class ProbeConfiguration:
    """The investigator's configuration under the draft, the rules a run is read by, and
    the reservation one run is admitted with."""

    role: RoleFilling
    rules: Rules
    worker: WorkerConfiguration
    harness: HarnessRevision
    reservation_pico_usd: int

    def frozen_inputs(self, context: RunContext) -> FrozenInputs:
        """What an admission of a run of ``context`` records: the five copied fields from
        the fixtures' admitted inputs, the reservation this probe makes, the rest from the
        configuration (the production path's ``frozen_for``)."""
        admitted = replace(
            support.admitted_inputs(context), reservation_pico_usd=self.reservation_pico_usd
        )
        return self.worker.frozen_for(admitted)


def probe_configuration(*, tree_state: TreeState) -> ProbeConfiguration:
    """The configuration the work command would compose from this probe's line."""
    role = RoleFilling(
        Role.INVESTIGATOR.value,
        CallConfiguration(
            MODEL, (CallSetting("max_tokens", OUTPUT_MAXIMUM), CallSetting("temperature", 0))
        ),
        PricingSelection(MODEL, REGION, "on_demand"),
        COUNTING_MODEL,
    )
    table = price_table()
    basis = basis_for(table, (role.pricing,))
    worker = agent_provenance(
        registration(),
        CONDITION,
        LEVEL,
        preregistration_commit=registration_commit(),
        pricing=basis,
        role=role,
    )
    caps = worker.caps
    # Every token of the run's cap at the dearest input rate and every call's whole output
    # maximum: more than a run can spend, so the ledger never ends one early.
    reservation = worst_case_cost(
        caps.token_cap, caps.call_cap * OUTPUT_MAXIMUM, role.pricing, basis
    )
    return ProbeConfiguration(
        role,
        effective_rules(registration()),
        worker,
        HarnessRevision(head_commit(), tree_state),
        reservation,
    )


__all__ = [
    "CONDITION",
    "COUNTING_MODEL",
    "LEVEL",
    "MODEL",
    "OUTPUT_MAXIMUM",
    "REGION",
    "WORLD",
    "ProbeConfiguration",
    "development_world",
    "live_iteration_scenarios",
    "probe_configuration",
    "registration",
]
