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

The skill table is ``core``'s since a harness needed it for the anchor guard and may not
import this package; it is named here from there, and the digest reads it as before.

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

from leaveimpact.core.skills import SKILLS, Skill


@dataclass(frozen=True, slots=True)
class City:
    """An office city with the country and IANA zone a person working there is recorded under."""

    name: str
    country: str
    timezone: str


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


# --- The filler name book: fictional artifacts no planted record names --------------------
#
# Filler documents are shaped like the planted kinds and titled over fictional releases and
# clients, so a text about one can state a requirement that reads like a planted clause
# while naming nothing a planted record names (the generator step's ruling 2; the handbook
# book ruling 2 also planned was dropped on 2026-10-08, when four probe rounds found no
# such text passing the checker).
# Every name here is disjoint from every table above, casefolded, and every filler title is
# disjoint from every title the ticket and meeting products and the classes' templates can
# make, as a substring either way, which a vocabulary test holds: the scope matcher resolves
# by substring, so a filler title that contained a planted one would steal that clause's
# resolution. The group 0 probe's own "Northwind release" wore a client's name and passed
# only because the longer admitted form masked the client's; the table rule removes the luck.
# A template names its document kind beside it, since a filler document takes the shape of
# the planted kind it imitates.

FICTIONAL_RELEASES: tuple[str, ...] = (
    "Aurora", "Basalt", "Cobalt", "Dunlin", "Ember", "Falcon", "Granite", "Heron", "Iris",
    "Juniper", "Kelp", "Lantern", "Marlin", "Nimbus", "Orchid", "Peregrine", "Quartz", "Rowan",
    "Sable", "Tundra", "Onyx", "Vesper", "Willow", "Xenon", "Yarrow", "Zephyr", "Alder",
    "Bramble", "Cinder", "Dusk", "Elm", "Fjord", "Gale", "Harrier", "Ivory", "Jade",
)

FICTIONAL_CLIENTS: tuple[str, ...] = (
    "Halcyon", "Veridian", "Castellan", "Ambergate", "Fennwick", "Lowmere", "Kingsreach",
    "Dorrance", "Pellham", "Tarrow", "Hollins", "Marchbank", "Averill", "Caldwater", "Brennock",
    "Ellery", "Farrowmoor", "Glenridge", "Haverly", "Innsworth", "Jessop", "Kirkwell",
    "Langmoor", "Morrow", "Nethercott", "Oldcastle", "Penrose", "Quill", "Rutherglen", "Selwyn",
    "Thistlewood", "Underhill", "Varley", "Wexcombe", "Yardley", "Ashworth",
)

RELEASE_TITLES: tuple[tuple[str, str], ...] = (
    ("runbook", "Release runbook: {name} release"),
    ("policy", "Release policy: {name} release"),
    ("procedure", "Rollback procedure: {name} release"),
    ("runbook", "Cutover checklist: {name} release"),
    ("policy", "Freeze policy: {name} release"),
    ("procedure", "Smoke test procedure: {name} release"),
)
"""(document kind, title template) per fictional release; one filler document per pair."""

CLIENT_TITLES: tuple[tuple[str, str], ...] = (
    ("client_note", "{name} account notes"),
    ("procedure", "Account handover procedure: {name}"),
    ("client_note", "{name} onboarding notes"),
    ("procedure", "Escalation procedure: {name}"),
    ("client_note", "{name} renewal notes"),
    ("policy", "Data retention policy: {name}"),
)
"""(document kind, title template) per fictional client; one filler document per pair."""

def filler_titles() -> tuple[tuple[str, str], ...]:
    """Every (document kind, title) the two filler books can mint, in table order.

    >>> len(filler_titles()) == 36 * 6 + 36 * 6
    True
    """
    return tuple(
        (kind, template.format(name=name))
        for names, templates in (
            (FICTIONAL_RELEASES, RELEASE_TITLES),
            (FICTIONAL_CLIENTS, CLIENT_TITLES),
        )
        for kind, template in templates
        for name in names
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
        "fictional_releases": list(FICTIONAL_RELEASES),
        "fictional_clients": list(FICTIONAL_CLIENTS),
        "release_titles": [list(row) for row in RELEASE_TITLES],
        "client_titles": [list(row) for row in CLIENT_TITLES],
    }
    canonical = json.dumps(tables, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "CITIES",
    "CLIENT_NAMES",
    "CLIENT_TITLES",
    "FICTIONAL_CLIENTS",
    "FICTIONAL_RELEASES",
    "RELEASE_TITLES",
    "filler_titles",
    "COMPONENT_NAMES",
    "FAMILY_NAMES",
    "GIVEN_NAMES",
    "LOOK_ALIKE_MEETING_PHRASES",
    "LOOK_ALIKE_TICKET_PHRASES",
    "MEETING_PHRASES",
    "MEETING_QUALIFIERS",
    "SKILLS",
    "TEAM_NAMES",
    "TICKET_PHRASES",
    "TICKET_QUALIFIERS",
    "City",
    "Skill",
    "titles",
    "vocabulary_digest",
]
