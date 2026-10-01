"""The model a run called and how: the inference configuration every model-written record carries.

A model-written artifact is reproducible only with the model and the settings it was
produced under, so the configuration is recorded whole beside the artifact: the
generator's materialization record carries the writer's and the checker's, and the
investigator's run record carries one per role (the investigator milestone's second
build step, where the types moved here from the world's prose vocabulary). ``core``
owns them because both the benchmark and the application record the same thing and
neither may import the other; a provenance type knows nothing of a benchmark.

Serialized whole so a parameter added later joins the record unasked (the world
milestone's step 14 ruling on provenance), settings held in name order so two equal
configurations are equal in bytes. The codec is strict in the sealed codecs' manner:
exactly the declared fields, a setting's value a number or a string and never a
boolean, since JSON's ``true`` is not a parameter value this project sends.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    field_of,
    string_field,
)


@dataclass(frozen=True, slots=True)
class Setting:
    """One inference parameter by name, as the model was called with it."""

    name: str
    value: int | float | str


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    """A model and every explicit inference setting it ran under, settings in name order.

    >>> configured = ModelConfiguration(
    ...     "eu.model", (Setting("top_p", 0.9), Setting("temperature", 0.7))
    ... )
    >>> [setting.name for setting in configured.settings]
    ['temperature', 'top_p']
    """

    model_id: str
    settings: tuple[Setting, ...]

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("a model configuration names its model")
        names = [setting.name for setting in self.settings]
        if len(set(names)) != len(names):
            raise ValueError(f"a setting is given once, got {names}")
        object.__setattr__(self, "settings", tuple(sorted(self.settings, key=lambda s: s.name)))


def encode_model_configuration(configured: ModelConfiguration) -> JsonObject:
    """The JSON object of a configuration: the model id, then name-value settings in name order."""
    return {
        "model_id": configured.model_id,
        "settings": [
            {"name": setting.name, "value": setting.value} for setting in configured.settings
        ],
    }


def decode_model_configuration(value: object) -> ModelConfiguration:
    """The configuration ``value`` encodes; ``ValueError`` names what is malformed."""
    data = as_object(value, "a model configuration")
    expect_fields(data, ("model_id", "settings"), "a model configuration")
    return ModelConfiguration(
        string_field(data, "model_id"),
        tuple(_decode_setting(item) for item in array_field(data, "settings")),
    )


def _decode_setting(item: object) -> Setting:
    data = as_object(item, "a setting")
    expect_fields(data, ("name", "value"), "a setting")
    value = field_of(data, "value")
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"a setting's value is a number or a string, got {value!r}")
    return Setting(string_field(data, "name"), value)
