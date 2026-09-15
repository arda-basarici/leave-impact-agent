"""The closed vocabularies a generated organization is drawn from: names, cities, skills, labels.

The vocabulary is generator semantics, not decoration. Every employee, city, skill, team
and component label a world can contain comes from these tables, which is what makes
two properties hold at once: the same seed yields the same organization, and the
namespace guard on materialized prose (DESIGN, "The generator: pure specification,
materialized prose, frozen world") has a finite, known set of words to check against.
A change here that can alter a generated world therefore bumps ``GENERATOR_VERSION``;
``vocabulary_digest`` against the value recorded in ``world.version`` makes any edit fail
a test until that file is touched, so the version bump is visible in the same diff
instead of every world built from an old seed being silently re-cut.

Curated tables replaced a faker library on purpose. The tables are a few dozen entries,
a library's seeded output has changed across its releases (which would put the
reproducibility claim at the mercy of a pin), and benchmark vocabulary should be small,
closed and the project's own. Names are ASCII so that a synthetic person's name survives
every vendor's option label, JQL string and calendar summary without an encoding
question; the world is synthetic and does not claim demographic realism.

A city is one structured constant rather than three parallel tuples so that a person's
``location``, ``country`` and ``timezone`` are consistent by construction — the three
stay separate facts on the ``Employee`` record so a planted disagreement between the HR
record and a calendar remains expressible, but the organization's baseline is coherent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from leaveimpact.core.ids import SkillId, skill_id


@dataclass(frozen=True, slots=True)
class City:
    """An office city with the country and IANA zone a person working there is recorded under."""

    name: str
    country: str
    timezone: str


@dataclass(frozen=True, slots=True)
class Skill:
    """A skill in the closed vocabulary: the id the domain keys on and a display name for prose."""

    id: SkillId
    name: str


GIVEN_NAMES: tuple[str, ...] = (
    "Alice", "Bob", "Deniz", "Can", "Elif", "Mert", "Zeynep", "Emre", "Selin", "Kerem",
    "Lena", "Jonas", "Marta", "Tomasz", "Priya", "Arjun", "Noor", "Omar", "Sofia", "Mateus",
    "Ines", "Felix", "Hanna", "Liam", "Chloe", "Yusuf", "Aylin", "Baran", "Nadia", "Ravi",
)

FAMILY_NAMES: tuple[str, ...] = (
    "Demir", "Kaya", "Yilmaz", "Schmidt", "Novak", "Kowalski", "Fernandes", "Costa", "Patel",
    "Sharma", "Haddad", "Okafor", "Muller", "Jansen", "Visser", "Rossi", "Moreau", "Byrne",
    "Nakamura", "Chen",
)

# Distinct offsets on purpose: a timezone-boundary distractor needs two offices whose
# calendar days disagree, and Lisbon against London shows that two zones can share an
# offset and still be different provenance.
CITIES: tuple[City, ...] = (
    City("Istanbul", "TR", "Europe/Istanbul"),
    City("Berlin", "DE", "Europe/Berlin"),
    City("Amsterdam", "NL", "Europe/Amsterdam"),
    City("Warsaw", "PL", "Europe/Warsaw"),
    City("London", "GB", "Europe/London"),
    City("Lisbon", "PT", "Europe/Lisbon"),
    City("Toronto", "CA", "America/Toronto"),
    City("Bangalore", "IN", "Asia/Kolkata"),
)

SKILLS: tuple[Skill, ...] = (
    Skill(skill_id("kafka"), "Kafka"),
    Skill(skill_id("postgresql"), "PostgreSQL"),
    Skill(skill_id("kubernetes"), "Kubernetes"),
    Skill(skill_id("terraform"), "Terraform"),
    Skill(skill_id("aws"), "AWS"),
    Skill(skill_id("gcp"), "Google Cloud"),
    Skill(skill_id("python"), "Python"),
    Skill(skill_id("go"), "Go"),
    Skill(skill_id("java"), "Java"),
    Skill(skill_id("typescript"), "TypeScript"),
    Skill(skill_id("react"), "React"),
    Skill(skill_id("graphql"), "GraphQL"),
    Skill(skill_id("redis"), "Redis"),
    Skill(skill_id("elasticsearch"), "Elasticsearch"),
    Skill(skill_id("grafana"), "Grafana"),
    Skill(skill_id("airflow"), "Airflow"),
    Skill(skill_id("spark"), "Spark"),
    Skill(skill_id("dbt"), "dbt"),
    Skill(skill_id("ios"), "iOS"),
    Skill(skill_id("android"), "Android"),
)

TEAM_NAMES: tuple[str, ...] = ("Payments", "Platform", "Data", "Mobile", "Growth", "Identity")

# Deliberately not the team names: component membership is work-domain association and
# must be able to disagree with team membership (the ``Component`` docstring in ``core``).
COMPONENT_NAMES: tuple[str, ...] = (
    "Payments API",
    "Billing",
    "Auth",
    "Event Ingestion",
    "Notifications",
    "Mobile Release",
)

# A client is a name and nothing more: the responsibility class titles a client note by it
# and its procedure clause names that title, so the constraint's scope and the text's agree
# without a client entity (the 15.2 rulings). One name per scenario number, sized to the
# golden set's thirty, so no two notes in a golden world share a title.
CLIENT_NAMES: tuple[str, ...] = (
    "Northwind",
    "Contoso",
    "Fabrikam",
    "Tailwind",
    "Lakeshore",
    "Bluecrest",
    "Ironvale",
    "Meridian",
    "Harborline",
    "Stonebridge",
    "Copperfield",
    "Ashgrove",
    "Redfern",
    "Silverpine",
    "Oakhaven",
    "Brightwater",
    "Greystone",
    "Kestrel",
    "Larkspur",
    "Maplecroft",
    "Northgate",
    "Pinnacle",
    "Quarry Hill",
    "Riverbend",
    "Saltmarsh",
    "Thornfield",
    "Umberline",
    "Vantage",
    "Westbrook",
    "Yellowtail",
)


# --- Artifact titles: the scope handles a policy names an artifact by ----------------------
#
# A ticket title is a component name, a phrase and a qualifier; a meeting title a team name,
# a phrase and a qualifier. The product of phrases and qualifiers is the supply one context
# (a component, a team) can mint without replacement, and it must cover the largest plan's
# row count, since a policy scopes itself by the title it names and a title naming two
# artifacts of one kind is a scope the prose cannot resolve (the 15.3 rulings). Look-alike
# titles use their own phrases, disjoint from these, so a distractor never shares a real
# artifact's title. Qualifiers never begin with a comma: the modifiers' suffixes do, and
# a derived title (", phase one", ", groundwork", ", follow-up") stays distinct by that.

TICKET_PHRASES: tuple[str, ...] = (
    "upgrade the client library",
    "rotate the signing keys",
    "migrate the retry queue",
    "close the audit findings",
    "cut over to the new gateway",
    "retire the legacy endpoint",
)
TICKET_QUALIFIERS: tuple[str, ...] = (
    "",
    " for the EU region",
    " ahead of the freeze",
    " for the mobile clients",
    " behind the flag",
    " for the new tenant",
)
MEETING_PHRASES: tuple[str, ...] = (
    "release go/no-go",
    "sprint review",
    "customer escalation sync",
    "quarterly planning",
    "incident retrospective",
    "roadmap check-in",
)
MEETING_QUALIFIERS: tuple[str, ...] = (
    "",
    " with product",
    " with the platform leads",
    " for the next release",
    " (deep dive)",
    " (part two)",
)
LOOK_ALIKE_TICKET_PHRASES: tuple[str, ...] = (
    "triage the backlog",
    "refresh the dashboards",
    "review the alert thresholds",
    "tune the autoscaling",
    "document the runbook",
    "clean up stale branches",
)
LOOK_ALIKE_MEETING_PHRASES: tuple[str, ...] = (
    "weekly sync",
    "design review",
    "on-call handover",
    "stand-up",
    "estimation session",
    "demo prep",
)


def titles(context: str, phrases: tuple[str, ...], qualifiers: tuple[str, ...]) -> tuple[str, ...]:
    """Every title a context can carry from ``phrases`` by ``qualifiers``, in canonical order:
    plain phrases first, then each qualifier over the phrases.

    >>> titles("Auth", ("rotate keys", "add a key"), ("", " (EU)"))
    ('Auth: rotate keys', 'Auth: add a key', 'Auth: rotate keys (EU)', 'Auth: add a key (EU)')
    """
    return tuple(
        f"{context}: {phrase}{qualifier}" for qualifier in qualifiers for phrase in phrases
    )


def vocabulary_digest() -> str:
    """The SHA-256 of every table above in canonical JSON — the fingerprint ``version`` records.

    Tables in a fixed order, entries in declared order, compact separators, UTF-8 passed
    through — the same canonical-JSON convention the claim encoding uses, so a digest is a
    property of the vocabulary and not of a serializer's defaults.

    >>> len(vocabulary_digest())
    64
    """
    tables: dict[str, object] = {
        "given_names": list(GIVEN_NAMES),
        "family_names": list(FAMILY_NAMES),
        "cities": [[city.name, city.country, city.timezone] for city in CITIES],
        "skills": [[skill.id, skill.name] for skill in SKILLS],
        "team_names": list(TEAM_NAMES),
        "component_names": list(COMPONENT_NAMES),
        "client_names": list(CLIENT_NAMES),
        "ticket_phrases": list(TICKET_PHRASES),
        "ticket_qualifiers": list(TICKET_QUALIFIERS),
        "meeting_phrases": list(MEETING_PHRASES),
        "meeting_qualifiers": list(MEETING_QUALIFIERS),
        "look_alike_ticket_phrases": list(LOOK_ALIKE_TICKET_PHRASES),
        "look_alike_meeting_phrases": list(LOOK_ALIKE_MEETING_PHRASES),
    }
    canonical = json.dumps(tables, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
