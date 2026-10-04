"""The run-side call configuration: any JSON setting in one spelling, a boolean apart from a
number, and a codec that returns the bytes it was given only when they were canonical."""

import json

import pytest

from leaveimpact.core.call_settings import (
    CallConfiguration,
    CallSetting,
    decode_call_configuration,
    encode_call_configuration,
    normalized_setting_value,
)
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.provenance import ModelConfiguration, Setting, encode_model_configuration


def test_an_integer_valued_float_is_the_integer_at_every_depth() -> None:
    setting = CallSetting("tool_choice", {"limits": [1.0, 2.5, {"k": 40.0}], "t": -0.0})
    assert canonical_json(encode_call_configuration(CallConfiguration("eu.model", (setting,)))) == (
        '{"model_id":"eu.model","settings":[{"name":"tool_choice",'
        '"value":{"limits":[1,2.5,{"k":40}],"t":0}}]}'
    )
    assert CallSetting("temperature", 1.0) == CallSetting("temperature", 1)
    assert hash(CallSetting("temperature", 1.0)) == hash(CallSetting("temperature", 1))
    assert type(CallSetting("temperature", 1.0).value) is int
    assert CallSetting("temperature", 0.7).value == 0.7


def test_a_boolean_is_never_equal_to_a_number() -> None:
    assert CallSetting("stream", True) != CallSetting("stream", 1)
    assert CallSetting("stream", False) != CallSetting("stream", 0)
    assert CallSetting("stream", False) != CallSetting("stream", 0.0)
    assert CallSetting("flags", [True]) != CallSetting("flags", [1])
    assert len({CallSetting("stream", True), CallSetting("stream", 1)}) == 2
    assert CallConfiguration("m", (CallSetting("stream", True),)) != CallConfiguration(
        "m", (CallSetting("stream", 1),)
    )


def test_a_value_json_cannot_carry_is_refused() -> None:
    for value in (float("nan"), float("inf"), [-float("inf")], {"a": {"b": float("nan")}}):
        with pytest.raises(ValueError, match="non-finite number"):
            CallSetting("top_p", value)
    with pytest.raises(ValueError, match="holds set, which JSON cannot carry"):
        CallSetting("stop", {"END"})
    with pytest.raises(ValueError, match="non-string key 1"):
        CallSetting("bias", {1: 2})
    with pytest.raises(ValueError, match="a setting is named"):
        CallSetting(" ", 1)


def test_a_setting_is_frozen_and_keeps_none_and_nesting() -> None:
    held = {"b": [1, 2], "a": None}
    setting = CallSetting("extra", held)
    held["b"].append(3)  # type: ignore[union-attr]
    assert normalized_setting_value(setting.value, "x") == setting.value
    assert canonical_json(encode_call_configuration(CallConfiguration("m", (setting,)))).endswith(
        '"value":{"a":null,"b":[1,2]}}]}'
    )
    with pytest.raises(TypeError):
        setting.value["a"] = 1  # type: ignore[index]


def test_a_configuration_orders_its_settings_names_each_once_and_round_trips() -> None:
    configured = CallConfiguration(
        "eu.model",
        (CallSetting("top_p", 0.9), CallSetting("stream", False), CallSetting("stop", ["END"])),
    )
    assert [setting.name for setting in configured.settings] == ["stop", "stream", "top_p"]
    text = canonical_json(encode_call_configuration(configured))
    decoded = decode_call_configuration(json.loads(text))
    assert decoded == configured
    assert canonical_json(encode_call_configuration(decoded)) == text
    with pytest.raises(ValueError, match="a setting is given once"):
        CallConfiguration("eu.model", (CallSetting("stream", True), CallSetting("stream", 1)))
    with pytest.raises(ValueError, match="names its model"):
        CallConfiguration(" ", ())
    with pytest.raises(ValueError, match=r"a setting has fields .*surplus \['unit'\]"):
        decode_call_configuration(
            {"model_id": "m", "settings": [{"name": "t", "value": 1, "unit": "x"}]}
        )


def test_a_second_spelling_decodes_to_the_one_spelling_so_its_bytes_are_not_canonical() -> None:
    spelled = '{"model_id":"m","settings":[{"name":"temperature","value":1.0}]}'
    decoded = decode_call_configuration(json.loads(spelled))
    assert canonical_json(encode_call_configuration(decoded)) != spelled
    assert decoded == CallConfiguration("m", (CallSetting("temperature", 1),))


def test_the_generators_type_still_keeps_a_float_as_written() -> None:
    """Why there are two types: the sealed checker configuration holds ``0.0``, and the
    provenance codec must return it as written."""
    sealed = ModelConfiguration("eu.model", (Setting("temperature", 0.0),))
    assert '"value":0.0' in canonical_json(encode_model_configuration(sealed))
    assert '"value":0}' in canonical_json(
        encode_call_configuration(CallConfiguration("eu.model", (CallSetting("temperature", 0.0),)))
    )
