"""The object store over one S3 bucket, both capabilities, the SDK's shapes mapped to the port's.

One store per bucket: keys are the bucket's prefix layout and the caller holds a world
store and a truth store as two instances of this class typed at the capability its role
is allowed. The credentials are ambient — the workflow's OIDC exchange exports them and
the SDK finds them — so this module takes a client and a bucket name and never a secret.

Every mapping here was observed before it was written (``probes/FINDINGS.md``, the
objectstore entry, 2026-09-13, under the generator role): a conditional put on an absent
key returns 200 with the version id; the same put on a present key raises ``ClientError``
with code ``PreconditionFailed`` and HTTP 412 whether the bytes match or not, so the
present-and-equal outcome is this store's read-back and comparison, never the SDK's; a
plain put under a final prefix raises the modeled ``AccessDenied`` with the bucket
policy's explicit deny in the message; a get of a missing key raises ``NoSuchKey`` on a
bucket that grants list, and reads as ``AccessDenied`` on one that does not, which is the
truth bucket for the validator and exactly the boundary that store's ``AccessRefused``
reports; an empty listing carries no ``Contents`` field at all; and every put, head and
get returns ``VersionId`` and ``ETag``. The type stubs mark those fields as not required,
and this store treats their absence as a fault rather than a value, since a versioned
bucket always returns them and an unversioned one cannot serve the immutability rule.

The vendor's exceptions never leave: an unreachable endpoint or a timeout is
``ObjectStoreUnreachable`` with the SDK's error chained, a refusal is ``AccessRefused``
with the message the policy wrote. The SDK's own retries (the standard mode) run first.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from leaveimpact.adapters.object_store.read import (
    AccessRefused,
    ObjectStoreUnreachable,
    StoredObject,
)
from leaveimpact.adapters.object_store.write import ObjectConflict, PutOutcome, PutReceipt

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class S3ObjectStore:
    """``ObjectWriter`` over ``bucket``; hand it to a reader as an ``ObjectReader``."""

    def __init__(self, client: S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def for_bucket(cls, bucket: str, region: str) -> S3ObjectStore:
        """A store on the ambient credentials for ``bucket`` in ``region``."""
        # The stubs type ``boto3.client`` as one overload per AWS service, and every
        # service whose stub is not installed returns Unknown; the S3 overload is typed.
        client = boto3.client("s3", region_name=region)  # pyright: ignore[reportUnknownMemberType]
        return cls(client, bucket)

    @property
    def bucket(self) -> str:
        return self._bucket

    def get(self, key: str) -> StoredObject | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if _code(error) == "NoSuchKey":
                return None
            raise _translated("get", key, error) from error
        except NoCredentialsError as error:
            raise AccessRefused("get", key, "no AWS credentials in the environment") from error
        except BotoCoreError as error:
            raise ObjectStoreUnreachable("get", key) from error
        content = response["Body"].read()
        return StoredObject(key, content, _version_id(response, "get", key))

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        keys: list[str] = []
        try:
            pages = self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix
            )
            for page in pages:
                for item in page.get("Contents", ()):
                    keys.append(_required(item.get("Key"), "list", prefix, "Key"))
        except ClientError as error:
            raise _translated("list", prefix, error) from error
        except NoCredentialsError as error:
            raise AccessRefused("list", prefix, "no AWS credentials in the environment") from error
        except BotoCoreError as error:
            raise ObjectStoreUnreachable("list", prefix) from error
        return tuple(sorted(keys))

    def put_if_absent(self, key: str, content: bytes) -> PutReceipt:
        try:
            response = self._client.put_object(
                Bucket=self._bucket, Key=key, Body=content, IfNoneMatch="*"
            )
        except ClientError as error:
            if _code(error) == "PreconditionFailed":
                return self._present_and_equal(key, content)
            raise _translated("put_if_absent", key, error) from error
        except NoCredentialsError as error:
            raise AccessRefused(
                "put_if_absent", key, "no AWS credentials in the environment"
            ) from error
        except BotoCoreError as error:
            raise ObjectStoreUnreachable("put_if_absent", key) from error
        return PutReceipt(key, _version_id(response, "put_if_absent", key), PutOutcome.CREATED)

    def overwrite(self, key: str, content: bytes) -> PutReceipt:
        try:
            response = self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        except ClientError as error:
            raise _translated("overwrite", key, error) from error
        except NoCredentialsError as error:
            raise AccessRefused(
                "overwrite", key, "no AWS credentials in the environment"
            ) from error
        except BotoCoreError as error:
            raise ObjectStoreUnreachable("overwrite", key) from error
        return PutReceipt(key, _version_id(response, "overwrite", key), PutOutcome.CREATED)

    def _present_and_equal(self, key: str, content: bytes) -> PutReceipt:
        # 412 says only "present"; the read-back decides between equal and conflicting. A
        # key that vanished between the two calls is a store no writer of this project
        # holds delete rights on, so it is reported as the fault it is.
        existing = self.get(key)
        if existing is None:
            raise ObjectStoreUnreachable("put_if_absent", key)
        if existing.content != content:
            raise ObjectConflict(key, _sha256(existing.content), _sha256(content))
        return PutReceipt(key, existing.version_id, PutOutcome.PRESENT_EQUAL)


def _code(error: ClientError) -> str:
    response = cast("dict[str, Any]", error.response)
    return str(response.get("Error", {}).get("Code", ""))


def _translated(operation: str, key: str, error: ClientError) -> Exception:
    response = cast("dict[str, Any]", error.response)
    code = _code(error)
    if code == "AccessDenied":
        message = str(response.get("Error", {}).get("Message", code))
        return AccessRefused(operation, key, message)
    status = int(response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
    if status >= 500:
        return ObjectStoreUnreachable(operation, key)
    return error


def _version_id(response: Any, operation: str, key: str) -> str:
    version = cast("dict[str, Any]", response).get("VersionId")
    if not version:
        raise ValueError(
            f"{operation} on {key!r} returned no VersionId: the bucket is not versioned, "
            "and the immutability rule needs the version of every write"
        )
    return str(version)


def _required(value: str | None, operation: str, key: str, field: str) -> str:
    # The stubs mark the field as not required; a listing without it is a fault.
    if value is None:
        raise ValueError(f"{operation} on {key!r} returned an entry without {field}")
    return value


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
