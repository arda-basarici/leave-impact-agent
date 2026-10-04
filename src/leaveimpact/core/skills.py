"""The public skill vocabulary: the closed list of skills an organization can hold, each with
the name a text writes it by.

A skill is a vocabulary term and not a record: no system returns one, so nothing a run reads
gives it a display form. Two parties need that form and may not import each other. The
world's generator writes a skill into prose by its name and draws every employee's skills
from this list. A harness needs the same names to check that the quote a model gives for a
fact about a skill names that skill (the anchor guard), and to tell a model which skill ids
exist. The table was the world's until a harness needed it, and ``agent`` may not import
``world``; ``world.vocabulary`` names it from here, and its digest covers these entries
exactly as before.

The list is public configuration, on the allowed side of the boundary the anchor guard is
held to (the contract step's ruling on the guard's lexicon): skill vocabularies as
configuration, names and titles from returned records, never the generator's organization
and never anything sealed. Which employee holds which skill is not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.ids import SkillId, skill_id


@dataclass(frozen=True, slots=True)
class Skill:
    """A skill in the closed vocabulary: the id the domain keys on and a display name for prose."""

    id: SkillId
    name: str


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
"""The skills, in declared order: the order the vocabulary's digest and a world's seed read."""

__all__ = ["SKILLS", "Skill"]
