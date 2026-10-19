"""The public results' one written form: canonical JSON read and written from the types.

The schema is the types in ``public``, so the codec is a walk over their declared fields
rather than a hand-written reader per type: a dataclass is an object with exactly its
fields, a tuple an array, an optional a null or the value, a number a number of its
declared kind. Reading refuses a missing field, a surplus field, a wrong JSON type, a
boolean where a count is declared and a non-finite number, each named by its path, so a
file a page shows is exactly a value of the declared types and the types learn nothing
when a field is added. The byte rule is the core's: insertion order kept, compact
separators, UTF-8 through, so the committed file's bytes are a property of the value and
the acceptance command compares bytes.
"""

from __future__ import annotations

import json
import types
from dataclasses import fields, is_dataclass
from math import isfinite
from typing import cast, get_args, get_origin, get_type_hints

from leaveimpact.core.jsonshape import JsonObject, as_object, canonical_bytes, expect_fields
from leaveimpact.results.public import PUBLIC_RESULTS_FORMAT, PublicResults

__all__ = ["decode_public_results", "encode_public_results", "public_results_bytes"]


def encode_public_results(results: PublicResults) -> JsonObject:
    """``results`` as the JSON object it is written as."""
    return cast(JsonObject, _written(results))


def public_results_bytes(results: PublicResults) -> bytes:
    """The canonical bytes of ``results``, what is committed and what is compared."""
    return canonical_bytes(encode_public_results(results))


def decode_public_results(content: bytes | str) -> PublicResults:
    """The results ``content`` holds, or ``ValueError`` naming the first thing that is not
    of the declared types; a format other than this code's is refused first."""
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    data = as_object(json.loads(text), "the public results")
    version = data.get("format_version")
    if version != PUBLIC_RESULTS_FORMAT:
        raise ValueError(
            f"the public results are format {PUBLIC_RESULTS_FORMAT}, got {version!r}"
        )
    return cast(PublicResults, _read(data, PublicResults, "the public results"))


def _written(value: object) -> object:
    """``value`` as JSON-ready data: enumerations are not among the types, so a dataclass,
    a tuple, a string, a number, a boolean or a null is all there is."""
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            if not isfinite(value):
                raise ValueError(f"the public results hold finite numbers, got {value!r}")
            return value
        case tuple():
            return [_written(item) for item in cast("tuple[object, ...]", value)]
        case _ if is_dataclass(value) and not isinstance(value, type):
            return {field.name: _written(getattr(value, field.name)) for field in fields(value)}
        case _:
            raise TypeError(f"the public results' written form has no rule for {type(value)}")


def _read(value: object, annotation: object, at: str) -> object:
    """``value`` as a value of ``annotation``, or ``ValueError`` naming ``at``."""
    if isinstance(annotation, type) and is_dataclass(annotation):
        data = as_object(value, at)
        hints = get_type_hints(annotation)
        names = tuple(field.name for field in fields(annotation))
        expect_fields(data, names, at)
        read = {name: _read(data[name], hints[name], f"{at}.{name}") for name in names}
        return annotation(**read)
    origin = get_origin(annotation)
    if origin is types.UnionType:
        members = [member for member in get_args(annotation) if member is not type(None)]
        if len(members) != len(get_args(annotation)) and value is None:
            return None
        if len(members) != 1:
            raise TypeError(f"{at}: the schema declares one type or null, got {annotation}")
        return _read(value, members[0], at)
    if origin is tuple:
        if not isinstance(value, list):
            raise ValueError(f"{at} is a JSON array, got {type(value).__name__}")
        items = cast("list[object]", value)
        members = get_args(annotation)
        if len(members) == 2 and members[1] is Ellipsis:
            return tuple(_read(item, members[0], f"{at}[{i}]") for i, item in enumerate(items))
        if len(items) != len(members):
            raise ValueError(f"{at} has {len(members)} items, got {len(items)}")
        return tuple(
            _read(item, member, f"{at}[{i}]")
            for i, (item, member) in enumerate(zip(items, members, strict=True))
        )
    if annotation is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{at} is a boolean, got {type(value).__name__}")
        return value
    if annotation is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{at} is an integer, got {type(value).__name__}")
        return value
    if annotation is float:
        if not isinstance(value, float):
            raise ValueError(f"{at} is a number with a fraction, got {type(value).__name__}")
        if not isfinite(value):
            raise ValueError(f"{at} is finite, got {value!r}")
        return value
    if annotation is str:
        if not isinstance(value, str):
            raise ValueError(f"{at} is a string, got {type(value).__name__}")
        return value
    raise TypeError(f"{at}: the schema declares no rule for {annotation}")
