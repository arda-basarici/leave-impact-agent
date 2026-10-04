"""The model a role's calls ran under, as a run records it: any JSON setting, in one spelling.

A run record and a registration are compared setting by setting, and the comparison is
only sound when equal settings are equal in bytes. The generator's provenance type
(``provenance.Setting``) holds a number or a string and keeps a float as written, which a
run's settings outgrow twice: a model is called with booleans and nested values (whether
the call streams, a tool choice), and ``temperature`` 1 and 1.0 are one setting with two
encodings (the contract step's ruling on settings). So a run's configuration is its own
type. A value is any JSON value, held frozen; a non-finite number is refused, since JSON
has no token for it; a float that holds an integer is normalized to the integer at every
depth, so one setting has one encoding; and a boolean is never equal to a number, which
Python's ``True == 1`` would otherwise make it.

The generator's type is left as it is on purpose. Its records are sealed, and one of them
holds ``0.0``: normalizing there would decode a sealed record to a value that encodes to
other bytes than the ones it was sealed with.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import cast

from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_json,
    expect_fields,
    field_of,
    string_field,
)


def normalized_setting_value(value: object, what: str) -> object:
    """``value`` as a frozen JSON value in its one spelling, refused if JSON cannot carry it.

    Objects become read-only mappings in key order and arrays tuples, all the way down; a
    float holding an integer becomes that integer wherever it sits.

    >>> normalized_setting_value({"top_k": 40.0, "stop": ["END", 2.5]}, "a setting")["top_k"]
    40
    >>> normalized_setting_value(float("inf"), "a setting")
    Traceback (most recent call last):
    ...
    ValueError: a setting holds a non-finite number, which JSON cannot carry
    """
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            if not isfinite(value):
                raise ValueError(f"{what} holds a non-finite number, which JSON cannot carry")
            return int(value) if value.is_integer() else value
        case list() | tuple():
            items = cast("list[object] | tuple[object, ...]", value)
            return tuple(normalized_setting_value(item, what) for item in items)
        case Mapping():
            normalized: dict[str, object] = {}
            for key, item in cast("Mapping[object, object]", value).items():
                if not isinstance(key, str):
                    raise ValueError(f"{what} has a non-string key {key!r}")
                normalized[key] = normalized_setting_value(item, what)
            return MappingProxyType(dict(sorted(normalized.items())))
        case _:
            raise ValueError(f"{what} holds {type(value).__name__}, which JSON cannot carry")


def _thawed(value: object) -> object:
    match value:
        case Mapping():
            items = cast("Mapping[str, object]", value).items()
            return {key: _thawed(item) for key, item in items}
        case tuple():
            return [_thawed(item) for item in cast("tuple[object, ...]", value)]
        case _:
            return value


@dataclass(frozen=True, slots=True, eq=False)
class CallSetting:
    """One inference parameter by name, as the model was called with it.

    Two settings are equal exactly when their encodings are, so a boolean and a number
    never are and an integer-valued float and its integer always are.

    >>> CallSetting("temperature", 1.0) == CallSetting("temperature", 1)
    True
    >>> CallSetting("stream", True) == CallSetting("stream", 1)
    False
    """

    name: str
    value: object

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("a setting is named")
        object.__setattr__(
            self, "value", normalized_setting_value(self.value, f"the setting {self.name}")
        )

    @property
    def encoded(self) -> str:
        """The setting's canonical JSON text: its identity for equality and hashing."""
        return canonical_json({"name": self.name, "value": _thawed(self.value)})

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CallSetting) and self.encoded == other.encoded

    def __hash__(self) -> int:
        return hash(self.encoded)


@dataclass(frozen=True, slots=True)
class CallConfiguration:
    """A model and every explicit inference setting a role's calls ran under, in name order.

    >>> configured = CallConfiguration(
    ...     "eu.model", (CallSetting("top_p", 0.9), CallSetting("stream", False))
    ... )
    >>> [setting.name for setting in configured.settings]
    ['stream', 'top_p']
    """

    model_id: str
    settings: tuple[CallSetting, ...]

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("a call configuration names its model")
        names = [setting.name for setting in self.settings]
        if len(set(names)) != len(names):
            raise ValueError(f"a setting is given once, got {names}")
        object.__setattr__(self, "settings", tuple(sorted(self.settings, key=lambda s: s.name)))


def encode_call_configuration(configured: CallConfiguration) -> JsonObject:
    """The JSON object of a configuration: the model id, then name-value settings in name order."""
    return {
        "model_id": configured.model_id,
        "settings": [
            {"name": setting.name, "value": _thawed(setting.value)}
            for setting in configured.settings
        ],
    }


def decode_call_configuration(value: object) -> CallConfiguration:
    """The configuration ``value`` encodes; ``ValueError`` names what is malformed.

    A value spelled another way than its one spelling (``1.0`` for 1) decodes to the
    normalized setting, so bytes holding it are not canonical and a byte decoder that
    re-encodes refuses them.
    """
    data = as_object(value, "a call configuration")
    expect_fields(data, ("model_id", "settings"), "a call configuration")
    return CallConfiguration(
        string_field(data, "model_id"),
        tuple(_decode_setting(item) for item in array_field(data, "settings")),
    )


def _decode_setting(item: object) -> CallSetting:
    data = as_object(item, "a setting")
    expect_fields(data, ("name", "value"), "a setting")
    return CallSetting(string_field(data, "name"), field_of(data, "value"))


__all__ = [
    "CallConfiguration",
    "CallSetting",
    "decode_call_configuration",
    "encode_call_configuration",
    "normalized_setting_value",
]
