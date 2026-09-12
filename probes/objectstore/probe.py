"""The conditional-write mechanism boto3 exposes, observed live before the S3 store takes its shape.

The platform side proved the bucket policy with the CLI (2026-09-12: second conditional
put 412, plain put on a final prefix 403). What the store's code needs is the *SDK's*
shape of each outcome — the exception class, the error code string, the HTTP status,
which fields the success response carries — so the three-outcome contract of
``put_if_absent`` (created / present-and-equal / refused) maps to observed values and
not to a guess. Runs under the generator role from the throwaway benchmark workflow.

Pass criterion, stated before the run: every numbered step below prints the shape it
expects, and step 5 is refused with the AccessDenied code. The run touches the world
bucket only — ``preparing/`` expires in a day, and the refused put on ``worlds/``
creates nothing — so the truth bucket and the served prefixes stay untouched.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

WORLD_BUCKET = os.environ["WORLD_BUCKET"]
RUN = os.environ["GITHUB_RUN_ID"]
MUTABLE_KEY = f"preparing/probe/{RUN}/object.bin"
FINAL_KEY = f"worlds/probe-{RUN}/object.bin"

s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"])


def shape(error: ClientError) -> str:
    response: dict[str, Any] = error.response
    meta = response.get("ResponseMetadata", {})
    err = response.get("Error", {})
    return json.dumps(
        {
            "class": type(error).__name__,
            "code": err.get("Code"),
            "message": err.get("Message"),
            "http": meta.get("HTTPStatusCode"),
            "condition": err.get("Condition"),
        }
    )


def success(response: dict[str, Any]) -> str:
    keep = {k: response.get(k) for k in ("VersionId", "ETag") if k in response}
    keep["http"] = response["ResponseMetadata"]["HTTPStatusCode"]
    return json.dumps(keep)


def expect_error(step: str, **call: Any) -> ClientError:
    try:
        s3.put_object(**call)
    except ClientError as error:
        print(f"{step}: refused {shape(error)}")
        return error
    print(f"{step}: NOT refused — the mechanism is not what the design assumes")
    sys.exit(1)


def main() -> None:
    body_a, body_b = b"probe-a", b"probe-b"

    created = s3.put_object(Bucket=WORLD_BUCKET, Key=MUTABLE_KEY, Body=body_a, IfNoneMatch="*")
    print(f"1 conditional put, absent key: created {success(created)}")
    first_version = created["VersionId"]

    error = expect_error(
        "2 conditional put, same key, same bytes",
        Bucket=WORLD_BUCKET, Key=MUTABLE_KEY, Body=body_a, IfNoneMatch="*",
    )
    assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 412, "expected 412"

    expect_error(
        "3 conditional put, same key, different bytes",
        Bucket=WORLD_BUCKET, Key=MUTABLE_KEY, Body=body_b, IfNoneMatch="*",
    )

    head = s3.head_object(Bucket=WORLD_BUCKET, Key=MUTABLE_KEY)
    print(f"4a head after the refusals: {success(head)} length={head['ContentLength']}")
    got = s3.get_object(Bucket=WORLD_BUCKET, Key=MUTABLE_KEY, VersionId=first_version)
    print(f"4b get by version id: {success(got)} bytes_equal={got['Body'].read() == body_a}")

    overwritten = s3.put_object(Bucket=WORLD_BUCKET, Key=MUTABLE_KEY, Body=body_b)
    print(f"4c plain put on preparing/ (the overwrite path): {success(overwritten)}")
    latest = s3.get_object(Bucket=WORLD_BUCKET, Key=MUTABLE_KEY)
    print(f"4d get latest: {success(latest)} bytes_equal_b={latest['Body'].read() == body_b}")

    error = expect_error(
        "5 plain put on a final prefix (worlds/)",
        Bucket=WORLD_BUCKET, Key=FINAL_KEY, Body=body_a,
    )
    assert error.response["Error"]["Code"] == "AccessDenied", "expected AccessDenied"

    try:
        s3.get_object(Bucket=WORLD_BUCKET, Key=f"preparing/probe/{RUN}/missing.bin")
        print("6a get of a missing key: NOT refused")
        sys.exit(1)
    except ClientError as error:
        print(f"6a get of a missing key: {shape(error)}")
    try:
        s3.head_object(Bucket=WORLD_BUCKET, Key=f"preparing/probe/{RUN}/missing.bin")
        print("6b head of a missing key: NOT refused")
        sys.exit(1)
    except ClientError as error:
        print(f"6b head of a missing key: {shape(error)}")

    listed = s3.list_objects_v2(Bucket=WORLD_BUCKET, Prefix=f"preparing/probe/{RUN}/")
    keys = [item["Key"] for item in listed.get("Contents", [])]
    print(f"7a list under the probe prefix: KeyCount={listed['KeyCount']} keys={keys}")
    empty = s3.list_objects_v2(Bucket=WORLD_BUCKET, Prefix=f"preparing/probe/{RUN}/nothing/")
    print(f"7b list under an empty prefix: KeyCount={empty['KeyCount']} has_Contents={'Contents' in empty}")

    listed_final = s3.list_objects_v2(Bucket=WORLD_BUCKET, Prefix=f"worlds/probe-{RUN}/")
    print(f"8 nothing created under worlds/ by the refused put: KeyCount={listed_final['KeyCount']}")
    print("PASS")


if __name__ == "__main__":
    main()
