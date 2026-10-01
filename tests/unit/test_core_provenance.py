"""The model configuration: settings held in name order and named once, and the codec
round-trips a configuration while refusing a boolean where a parameter value belongs."""

import json

import pytest

from leaveimpact.core import (
    ModelConfiguration,
    Setting,
    decode_model_configuration,
    encode_model_configuration,
)
from leaveimpact.core.jsonshape import canonical_json


def test_a_model_configuration_orders_its_settings_and_names_each_once() -> None:
    configured = ModelConfiguration(
        "eu.model", (Setting("top_p", 0.9), Setting("temperature", 0.7))
    )
    assert [setting.name for setting in configured.settings] == ["temperature", "top_p"]
    with pytest.raises(ValueError, match="a setting is given once"):
        ModelConfiguration("eu.model", (Setting("temperature", 0.7), Setting("temperature", 0)))
    with pytest.raises(ValueError, match="names its model"):
        ModelConfiguration(" ", ())


def test_a_configuration_round_trips_with_its_settings_in_name_order() -> None:
    configured = ModelConfiguration(
        "eu.model", (Setting("top_p", 0.9), Setting("max_tokens", 1024), Setting("stop", "END"))
    )
    encoded = encode_model_configuration(configured)
    assert [s["name"] for s in encoded["settings"]] == ["max_tokens", "stop", "top_p"]  # type: ignore[index]
    decoded = decode_model_configuration(json.loads(canonical_json(encoded)))
    assert decoded == configured
    assert canonical_json(encode_model_configuration(decoded)) == canonical_json(encoded)


def test_a_setting_constructs_only_with_a_value_that_round_trips() -> None:
    """A boolean is an ``int`` to Python and a non-finite float has no JSON token, so each
    would encode and then decode as nothing; the constructor refuses what the decoder would."""
    for value in (True, False, float("nan"), float("inf"), -float("inf"), None, [1]):
        with pytest.raises(ValueError, match="a setting's value is"):
            Setting("stream", value)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a setting is named"):
        Setting(" ", 1)
    assert Setting("temperature", 0.0).value == 0.0


def test_a_boolean_or_a_surplus_field_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="a setting's value is finite, got nan"):
        decode_model_configuration(
            {"model_id": "eu.model", "settings": [{"name": "top_p", "value": float("nan")}]}
        )
    with pytest.raises(ValueError, match="a setting's value is a number or a string, got True"):
        decode_model_configuration(
            {"model_id": "eu.model", "settings": [{"name": "stream", "value": True}]}
        )
    with pytest.raises(
        ValueError, match=r"a model configuration has fields .*surplus \['region'\]"
    ):
        decode_model_configuration({"model_id": "eu.model", "settings": [], "region": "eu"})
