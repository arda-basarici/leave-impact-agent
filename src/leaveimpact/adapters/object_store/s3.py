"""The reader over one S3 bucket, and the SDK-to-port translation the writer shares with it.

One reader per bucket: keys are the bucket's prefix layout and a consumer holds a world
reader and, if its role allows, a truth reader as two instances. The credentials are
ambient — the workflow's OIDC exchange exports them and the SDK finds them — so this
module takes a client and a bucket name and never a secret. The class here has the two
read operations and nothing else, so an instance handed to the validator is an object
with no write method on it at runtime, not only in its type; the writer is a subclass in
``s3_write``, which the import law admits to ``adapters`` and ``generator`` alone.

Every mapping here was observed before it was written (``probes/FINDINGS.md``, the
objectstore entry, 2026-09-13, under the generator role): a get of a missing key raises
``NoSuchKey`` on a bucket that grants list, and reads as ``AccessDenied`` on one that
does not, which is the truth bucket for the validator and exactly the boundary this
store's ``AccessRefused`` reports; an empty listing carries no ``Contents`` field at
all; every put, head and get returns ``VersionId`` and ``ETag``. The type stubs mark
those fields as not required, and the store treats their absence as a fault rather than
a value, since a versioned bucket always returns them and an unversioned one cannot
serve the immutability rule.

The vendor's exceptions never leave, on the request or on the body: the SDK's own
retries (the standard mode) run first, and what remains is translated by ``translated``
into the closed vocabulary of ``read`` — ``AccessDenied`` to ``AccessRefused``; a
connection or timeout fault, a 5xx, or a body that breaks off mid-stream to
``ObjectStoreUnreachable``; every other rejection the store answers with (a 4xx that is
not authorization, a bucket that does not exist, missing credentials) to
``ObjectStoreMisconfigured`` — with the SDK's error chained as the cause for the log.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
    StoredObject,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def s3_client(region: str) -> S3Client:
    """The SDK client on the ambient credentials; one per process is enough."""
    # The stubs type ``boto3.client`` as one overload per AWS service, and every service
    # whose stub is not installed returns Unknown; the S3 overload itself is typed.
    return boto3.client("s3", region_name=region)  # pyright: ignore[reportUnknownMemberType]


class S3ObjectReader:
    """``ObjectReader`` over ``bucket``: get and list, no write method exists on it."""

    def __init__(self, client: S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    def get(self, key: str) -> StoredObject | None:
        def fetch() -> StoredObject | None:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as error:
                if code(error) == "NoSuchKey":
                    return None
                raise
            content = response["Body"].read()
            return StoredObject(key, content, version_id(response, "get", key))

        return translated("get", key, fetch)

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        def enumerate_keys() -> tuple[str, ...]:
            keys: list[str] = []
            pages = self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix
            )
            for page in pages:
                for item in page.get("Contents", ()):
                    entry = item.get("Key")
                    if entry is None:
                        raise ObjectStoreMisconfigured("list", prefix, "a listing entry has no Key")
                    keys.append(entry)
            return tuple(sorted(keys))

        return translated("list", prefix, enumerate_keys)


def translated[T](operation: str, key: str, call: Callable[[], T]) -> T:
    """Run ``call`` with every SDK and transport fault mapped into the port's three.

    The boundary covers the response body too, which is why a whole call is wrapped and
    not only the request: a streaming body that breaks off raises from ``read``, after
    the request has already succeeded.
    """
    try:
        return call()
    except ClientError as error:
        raise _client_fault(operation, key, error) from error
    except NoCredentialsError as error:
        raise ObjectStoreMisconfigured(
            operation, key, "no AWS credentials in the environment"
        ) from error
    except BotoCoreError as error:
        raise ObjectStoreUnreachable(operation, key) from error
    except OSError as error:
        # The body's stream is a socket under the SDK; a reset or a timeout while it is
        # consumed arrives as the interpreter's own error, not the SDK's.
        raise ObjectStoreUnreachable(operation, key) from error


def code(error: ClientError) -> str:
    """The service error code the SDK parsed, empty when the response carried none."""
    response = cast("dict[str, Any]", error.response)
    return str(response.get("Error", {}).get("Code", ""))


def version_id(response: Any, operation: str, key: str) -> str:
    """The ``VersionId`` of a put, head or get; its absence means an unversioned bucket."""
    version = cast("dict[str, Any]", response).get("VersionId")
    if not version:
        raise ObjectStoreMisconfigured(
            operation,
            key,
            "the response carries no VersionId: the bucket is not versioned, and the "
            "immutability rule needs the version of every write",
        )
    return str(version)


def _client_fault(operation: str, key: str, error: ClientError) -> Exception:
    response = cast("dict[str, Any]", error.response)
    error_code = code(error)
    message = str(response.get("Error", {}).get("Message", error_code))
    if error_code == "AccessDenied":
        return AccessRefused(operation, key, message)
    status = int(response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
    if status >= 500:
        return ObjectStoreUnreachable(operation, key)
    return ObjectStoreMisconfigured(operation, key, f"{error_code}: {message}")
