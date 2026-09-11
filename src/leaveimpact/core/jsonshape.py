"""Shape helpers for the codecs: the JSON type of each field, nothing about its meaning.

Shared by the claim codec and the value codec so that "a missing field", "a wrong JSON
type" and "a surplus field" raise the same ``ValueError`` from one place. Meaning —
whether the string is a valid id, whether the value fits the predicate — is the domain
constructors' and is checked there, once.

The one byte rule lives here too. Every artifact the project hashes or compares — the
claims, the sealed world bundle, the world manifest — is canonical JSON in the same
sense: one object built field by field in a fixed order, compact separators, UTF-8
passed through, so the bytes are a property of the value and never of a serializer's
defaults. Defined once so that three codecs cannot drift apart by one keyword argument.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

JsonObject = dict[str, object]
"""A JSON object as Python builds it: string keys, values already JSON-ready."""


def canonical_json(value: object) -> str:
    """``value`` as canonical JSON text: insertion order kept, compact separators, UTF-8 through.

    >>> canonical_json({"b": 1, "a": ["ü", None]})
    '{"b":1,"a":["ü",null]}'
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_bytes(data: JsonObject) -> bytes:
    """The UTF-8 bytes of ``canonical_json(data)`` — what gets hashed and what gets written."""
    return canonical_json(data).encode("utf-8")


def expect_fields(data: Mapping[str, object], fields: tuple[str, ...], what: str) -> None:
    """Refuse ``data`` unless its keys are exactly ``fields``."""
    expected = set(fields)
    if set(data) != expected:
        missing = sorted(expected - set(data))
        surplus = sorted(set(data) - expected)
        raise ValueError(
            f"{what} has fields {sorted(expected)}; missing {missing}, surplus {surplus}"
        )


def as_object(value: object, what: str) -> Mapping[str, object]:
    """``value`` as a JSON object, or ``ValueError`` naming ``what`` was expected."""
    if not isinstance(value, dict):
        raise ValueError(f"{what} is a JSON object, got {type(value).__name__}")
    return cast(dict[str, object], value)


def field_of(data: Mapping[str, object], key: str) -> object:
    """The field ``key`` of ``data``; a missing field is a ``ValueError``, never a ``KeyError``."""
    if key not in data:
        raise ValueError(f"{key} is missing")
    return data[key]


def object_field(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    return as_object(field_of(data, key), key)


def string_field(data: Mapping[str, object], key: str) -> str:
    value = field_of(data, key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is a string, got {type(value).__name__}")
    return value


def optional_string_field(data: Mapping[str, object], key: str) -> str | None:
    value = field_of(data, key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} is a string or null, got {type(value).__name__}")
    return value


def integer_field(data: Mapping[str, object], key: str) -> int:
    value = field_of(data, key)
    # bool is an int in Python; JSON's true is not a count.
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} is an integer, got {type(value).__name__}")
    return value


def string_item(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"an item of {key} is a string, got {type(value).__name__}")
    return value


def array_field(data: Mapping[str, object], key: str) -> list[object]:
    value = field_of(data, key)
    if not isinstance(value, list):
        raise ValueError(f"{key} is a JSON array, got {type(value).__name__}")
    return cast(list[object], value)
