"""The object store's contract, held by every implementation: absent is ``None`` and an empty
prefix is empty; a first conditional put creates, a second with the same bytes is accepted
as present-and-equal on the same version without a write, a second with different bytes
is a conflict naming both digests and adopting neither; an overwrite makes a new version;
a listing is by string prefix, not by directory, and never fetches contents. The S3 store's
mapping of the SDK's observed shapes onto that contract is tested against botocore's
stubber, one response per shape the probe recorded; the in-memory double's emulated
policy refuses a plain put under a final prefix."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import boto3
import pytest
from botocore.exceptions import (
    EndpointConnectionError,
    FlexibleChecksumError,
    IncompleteReadError,
    ParamValidationError,
)
from botocore.response import StreamingBody
from botocore.stub import Stubber

from leaveimpact.adapters.object_store import (
    AccessRefused,
    ObjectStoreMisconfigured,
    ObjectStoreUnreachable,
)
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.object_store.s3 import S3ObjectReader, translated
from leaveimpact.adapters.object_store.s3_write import S3ObjectWriter
from leaveimpact.adapters.object_store.write import ObjectConflict, ObjectWriter, PutOutcome
from tests.unit.in_memory_object_store import InMemoryObjectStore

FINAL = "worlds/abc/world-manifest.json"
MUTABLE = "preparing/abc/world-manifest.json"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@pytest.fixture(params=["memory", "local"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> ObjectWriter:
    if request.param == "memory":
        return InMemoryObjectStore()
    return LocalObjectWriter(tmp_path / "bucket")


def test_absent_is_none_and_an_empty_prefix_is_empty(store: ObjectWriter) -> None:
    assert store.get(FINAL) is None
    assert store.list_keys("worlds/") == ()


def test_a_first_conditional_put_creates_and_reads_back(store: ObjectWriter) -> None:
    receipt = store.put_if_absent(FINAL, b"sealed")
    assert receipt.outcome is PutOutcome.CREATED
    read = store.get(FINAL)
    assert read is not None
    assert read.content == b"sealed"
    assert read.version_id == receipt.version_id


def test_the_same_bytes_again_are_present_and_equal_without_a_write(store: ObjectWriter) -> None:
    first = store.put_if_absent(FINAL, b"sealed")
    again = store.put_if_absent(FINAL, b"sealed")
    assert again.outcome is PutOutcome.PRESENT_EQUAL
    assert again.version_id == first.version_id


def test_different_bytes_are_a_conflict_naming_both_digests(store: ObjectWriter) -> None:
    store.put_if_absent(FINAL, b"sealed")
    with pytest.raises(ObjectConflict) as raised:
        store.put_if_absent(FINAL, b"tampered")
    assert raised.value.existing_digest == _sha256(b"sealed")
    assert raised.value.offered_digest == _sha256(b"tampered")
    read = store.get(FINAL)
    assert read is not None and read.content == b"sealed", "neither side is adopted"


def test_an_overwrite_replaces_and_makes_a_new_version(store: ObjectWriter) -> None:
    first = store.overwrite(MUTABLE, b'{"stage":"preparing","receipts":1}')
    second = store.overwrite(MUTABLE, b'{"stage":"preparing","receipts":2}')
    read = store.get(MUTABLE)
    assert read is not None
    assert read.content.endswith(b'"receipts":2}')
    assert read.version_id == second.version_id != first.version_id


def test_listing_is_by_string_prefix_not_by_directory(store: ObjectWriter) -> None:
    store.put_if_absent("worlds/abc/documents/doc_1.json", b"1")
    store.put_if_absent("worlds/abc/documents/doc_2.json", b"2")
    store.put_if_absent("worlds/abd/world-manifest.json", b"m")
    store.overwrite("preparing/abc/world-manifest.json", b"p")
    assert store.list_keys("worlds/abc/documents/") == (
        "worlds/abc/documents/doc_1.json",
        "worlds/abc/documents/doc_2.json",
    )
    assert store.list_keys("worlds/ab") == (
        "worlds/abc/documents/doc_1.json",
        "worlds/abc/documents/doc_2.json",
        "worlds/abd/world-manifest.json",
    )
    assert store.list_keys("worlds/abc/documents/doc_1") == ("worlds/abc/documents/doc_1.json",)


def test_the_local_twin_refuses_a_key_outside_the_grammar_on_every_platform(
    tmp_path: Path,
) -> None:
    local = LocalObjectWriter(tmp_path / "bucket")
    for key in ("", "worlds//x", "../x", "worlds/../x", "worlds\\..\\..\\x", "C:/x", "a b"):
        with pytest.raises(ValueError):
            local.put_if_absent(key, b"x")
        with pytest.raises(ValueError):
            local.get(key)
    assert not (tmp_path / "bucket").exists(), "nothing was written anywhere"


def test_the_readers_carry_no_write_method_at_runtime(tmp_path: Path) -> None:
    local = LocalObjectReader(tmp_path / "bucket")
    s3, _ = _stubbed_reader()
    for reader in (local, s3):
        assert not hasattr(reader, "put_if_absent") and not hasattr(reader, "overwrite")


def test_the_local_twin_ignores_a_staged_temporary_in_listings(tmp_path: Path) -> None:
    local = LocalObjectWriter(tmp_path / "bucket")
    local.overwrite(MUTABLE, b"p")
    (tmp_path / "bucket" / "preparing" / "abc" / "world-manifest.json.tmp").write_bytes(b"half")
    assert local.list_keys("preparing/") == (MUTABLE,)


def test_the_memory_double_emulates_the_bucket_policy() -> None:
    memory = InMemoryObjectStore()
    with pytest.raises(AccessRefused):
        memory.overwrite(FINAL, b"sealed")
    assert memory.get(FINAL) is None
    memory.put_if_absent(FINAL, b"sealed")
    memory.overwrite(MUTABLE, b"checkpoint")
    memory.reachable = False
    with pytest.raises(ObjectStoreUnreachable):
        memory.get(FINAL)


# --- the S3 mapping, one stubbed response per observed shape ---------------------------

BUCKET = "leave-impact-world-test"
CONTENT = b"sealed"


def _body(content: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(content), len(content))


def _client() -> Any:
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3",
        region_name="eu-central-1",
        aws_access_key_id="stub",
        aws_secret_access_key="stub",
    )


def _stubbed() -> tuple[S3ObjectWriter, Stubber]:
    client = _client()
    return S3ObjectWriter(client, BUCKET), Stubber(client)


def _stubbed_reader() -> tuple[S3ObjectReader, Stubber]:
    client = _client()
    return S3ObjectReader(client, BUCKET), Stubber(client)


def _get_response(content: bytes, version: str) -> dict[str, Any]:
    return {
        "Body": _body(content),
        "VersionId": version,
        "ETag": '"etag"',
        "ContentLength": len(content),
        "LastModified": datetime(2026, 9, 13, tzinfo=UTC),
    }


def _with[T](stub: Stubber, action: Callable[[], T]) -> T:
    with stub:
        result = action()
        stub.assert_no_pending_responses()
    return result


def test_s3_created_carries_the_minted_version_id() -> None:
    store, stub = _stubbed()
    stub.add_response(
        "put_object",
        {"VersionId": "v-created", "ETag": '"e"'},
        {"Bucket": BUCKET, "Key": FINAL, "Body": CONTENT, "IfNoneMatch": "*"},
    )
    receipt = _with(stub, lambda: store.put_if_absent(FINAL, CONTENT))
    assert receipt.outcome is PutOutcome.CREATED
    assert receipt.version_id == "v-created"


def test_s3_412_with_equal_bytes_is_present_and_equal_on_the_existing_version() -> None:
    store, stub = _stubbed()
    stub.add_client_error(
        "put_object",
        service_error_code="PreconditionFailed",
        service_message="At least one of the pre-conditions you specified did not hold",
        http_status_code=412,
    )
    stub.add_response(
        "get_object", _get_response(CONTENT, "v-existing"), {"Bucket": BUCKET, "Key": FINAL}
    )
    receipt = _with(stub, lambda: store.put_if_absent(FINAL, CONTENT))
    assert receipt.outcome is PutOutcome.PRESENT_EQUAL
    assert receipt.version_id == "v-existing"


def test_s3_412_with_different_bytes_is_a_conflict() -> None:
    store, stub = _stubbed()
    stub.add_client_error(
        "put_object", service_error_code="PreconditionFailed", http_status_code=412
    )
    stub.add_response(
        "get_object", _get_response(b"other", "v-existing"), {"Bucket": BUCKET, "Key": FINAL}
    )
    with stub, pytest.raises(ObjectConflict) as raised:
        store.put_if_absent(FINAL, CONTENT)
    assert raised.value.existing_digest == _sha256(b"other")
    assert raised.value.offered_digest == _sha256(CONTENT)


def test_s3_access_denied_is_refused_with_the_policy_message() -> None:
    store, stub = _stubbed()
    stub.add_client_error(
        "put_object",
        service_error_code="AccessDenied",
        service_message="explicit deny in a resource-based policy",
        http_status_code=403,
    )
    with stub, pytest.raises(AccessRefused) as raised:
        store.overwrite(FINAL, CONTENT)
    assert "explicit deny" in str(raised.value)


def test_s3_a_missing_key_is_none_on_get_and_refused_where_list_is_denied() -> None:
    store, stub = _stubbed()
    stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    assert _with(stub, lambda: store.get(FINAL)) is None
    store, stub = _stubbed()
    stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
    with stub, pytest.raises(AccessRefused):
        store.get("world-spec/abc.json")


def test_s3_an_empty_listing_has_no_contents_field_and_pages_are_joined() -> None:
    store, stub = _stubbed()
    stub.add_response(
        "list_objects_v2",
        {"KeyCount": 0, "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": "worlds/none/"},
    )
    assert _with(stub, lambda: store.list_keys("worlds/none/")) == ()
    store, stub = _stubbed()
    stub.add_response(
        "list_objects_v2",
        {
            "KeyCount": 1,
            "IsTruncated": True,
            "NextContinuationToken": "t",
            "Contents": [{"Key": "worlds/abc/b.json"}],
        },
        {"Bucket": BUCKET, "Prefix": "worlds/abc/"},
    )
    stub.add_response(
        "list_objects_v2",
        {"KeyCount": 1, "IsTruncated": False, "Contents": [{"Key": "worlds/abc/a.json"}]},
        {"Bucket": BUCKET, "Prefix": "worlds/abc/", "ContinuationToken": "t"},
    )
    assert _with(stub, lambda: store.list_keys("worlds/abc/")) == (
        "worlds/abc/a.json",
        "worlds/abc/b.json",
    )


def test_s3_a_put_without_a_version_id_is_misconfiguration_not_a_receipt() -> None:
    store, stub = _stubbed()
    stub.add_response(
        "put_object", {"ETag": '"e"'}, {"Bucket": BUCKET, "Key": MUTABLE, "Body": CONTENT}
    )
    with stub, pytest.raises(ObjectStoreMisconfigured, match="not versioned"):
        store.overwrite(MUTABLE, CONTENT)


def test_s3_an_unclassified_rejection_is_misconfiguration_never_the_vendor_class() -> None:
    store, stub = _stubbed_reader()
    stub.add_client_error(
        "get_object",
        service_error_code="InvalidRequest",
        service_message="the request is not valid",
        http_status_code=400,
    )
    with stub, pytest.raises(ObjectStoreMisconfigured, match="InvalidRequest") as raised:
        store.get(FINAL)
    assert raised.value.__cause__ is not None


def test_s3_unreachable_is_an_allowlist_and_a_local_sdk_fault_is_misconfiguration() -> None:
    def raising(error: Exception) -> Callable[[], None]:
        def call() -> None:
            raise error

        return call

    for transport in (
        EndpointConnectionError(endpoint_url="https://s3.eu-central-1.amazonaws.com"),
        IncompleteReadError(actual_bytes=3, expected_bytes=7),
    ):
        with pytest.raises(ObjectStoreUnreachable) as raised:
            translated("get", FINAL, raising(transport))
        assert raised.value.__cause__ is transport
    local = ParamValidationError(report="Invalid type for parameter Key")
    with pytest.raises(ObjectStoreMisconfigured, match="ParamValidationError") as raised:
        translated("get", FINAL, raising(local))
    assert raised.value.__cause__ is local


def test_s3_a_checksum_mismatch_is_unreachable_at_the_body_and_misconfiguration_at_setup() -> None:
    class Corrupt(io.RawIOBase):
        def read(self, size: int = -1) -> bytes:
            raise FlexibleChecksumError(error_msg="Expected checksum X did not match calculated Y")

    store, stub = _stubbed_reader()
    response = _get_response(CONTENT, "v")
    response["Body"] = StreamingBody(cast("Any", Corrupt()), len(CONTENT))
    stub.add_response("get_object", response, {"Bucket": BUCKET, "Key": FINAL})
    with stub, pytest.raises(ObjectStoreUnreachable) as raised:
        store.get(FINAL)
    assert isinstance(raised.value.__cause__, FlexibleChecksumError)

    def at_setup() -> None:
        raise FlexibleChecksumError(error_msg="Unsupported checksum algorithm: crc64")

    with pytest.raises(ObjectStoreMisconfigured, match="FlexibleChecksumError"):
        translated("put_if_absent", FINAL, at_setup)


def test_s3_a_body_that_breaks_off_is_unreachable_not_a_builtin_error() -> None:
    class Broken(io.RawIOBase):
        def read(self, size: int = -1) -> bytes:
            raise ConnectionResetError("reset mid-stream")

    store, stub = _stubbed_reader()
    response = _get_response(CONTENT, "v")
    response["Body"] = StreamingBody(cast("Any", Broken()), len(CONTENT))
    stub.add_response("get_object", response, {"Bucket": BUCKET, "Key": FINAL})
    with stub, pytest.raises(ObjectStoreUnreachable):
        store.get(FINAL)


def test_s3_a_server_fault_is_unreachable_and_a_vendor_error_never_leaves() -> None:
    store, stub = _stubbed()
    stub.add_client_error("get_object", service_error_code="InternalError", http_status_code=500)
    with stub, pytest.raises(ObjectStoreUnreachable) as raised:
        store.get(FINAL)
    assert raised.value.__cause__ is not None
