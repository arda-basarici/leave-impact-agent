"""Step 14's probe from the instance: the production client's own path. Prints status
words and counts; never a parameter's value. Run inside the deployed image."""

import json
import os
import sys
import traceback
from datetime import UTC, datetime

import boto3

out: dict[str, object] = {}


def step(name, fn):
    try:
        out[name] = fn()
    except Exception as error:  # noqa: BLE001 - a probe records every failure kind
        text = str(error)
        out[name] = {"error": type(error).__name__, "detail": text[:240]}


def env(name):
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} not given to the probe")
    return value


out["code_version"] = os.environ.get("LEAVEIMPACT_CODE_VERSION", "")
out["python"] = sys.version.split()[0]

from leaveimpact.adapters.calendar.adapter import CalendarCredential  # noqa: E402
from leaveimpact.adapters.frappe.adapter import FrappeCredential  # noqa: E402
from leaveimpact.adapters.inference import CountingClient, inference_client  # noqa: E402
from leaveimpact.adapters.jira.adapter import JiraCredential  # noqa: E402
from leaveimpact.adapters.manifest import ManifestStage, decode_manifest  # noqa: E402
from leaveimpact.adapters.object_store.layout import world_manifest_key  # noqa: E402
from leaveimpact.adapters.wiring import (  # noqa: E402
    Hosts,
    build_readers,
    jira_gateway_root,
    world_store_from_env,
    world_store_reader,
)
from leaveimpact.core.ids import WorldVersion  # noqa: E402
from leaveimpact.core.worldtime import InstantSpan  # noqa: E402

version = WorldVersion(env("P_WORLD_VERSION"))
key = world_manifest_key(version)
manifest = None


def read_manifest():
    global manifest
    reader = world_store_reader(world_store_from_env(os.environ))
    stored = reader.get(key)
    if stored is None:
        return {"found": False, "key": key}
    manifest = decode_manifest(stored.content, stage=ManifestStage.PROJECTED)
    return {
        "found": True,
        "stage": str(manifest.stage),
        "observed_sites": {str(k): v for k, v in manifest.observed_sites.items()},
        "artifacts": len(manifest.artifacts),
    }


step("P0_manifest", read_manifest)

readers = None


def build():
    global readers
    hosts = Hosts(
        frappe_base_url=env("P_FRAPPE_BASE_URL").rstrip("/"),
        frappe_credential=FrappeCredential(
            api_key=env("P_FRAPPE_API_KEY"), api_secret=env("P_FRAPPE_API_SECRET")
        ),
        jira_base_url=jira_gateway_root(env("P_JIRA_BASE_URL")),
        jira_credential=JiraCredential(email=env("P_JIRA_EMAIL"), api_token=env("P_JIRA_TOKEN")),
        calendar_credential=CalendarCredential.from_authorized_user_info(
            json.loads(env("P_GOOGLE_JSON"))
        ),
    )
    reader = world_store_reader(world_store_from_env(os.environ))
    readers = build_readers(hosts, manifest, reader)
    return "built"


if manifest is not None:
    step("P0_readers", build)

if readers is not None:

    def frappe():
        people = readers.people.employees()
        first = people[0].value.id if people else None
        one = readers.people.employee(first) if first is not None else None
        return {"employees": len(people), "by_id": one is not None}

    def jira():
        items = readers.work.work_items()
        first = items[0].value.id if items else None
        one = readers.work.work_item(first) if first is not None else None
        return {"work_items": len(items), "by_id": one is not None}

    def calendar():
        span = InstantSpan(
            datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 12, 31, tzinfo=UTC)
        )
        events = readers.calendar.events_within(span)
        return {"events": len(events)}

    step("P3_frappe", frappe)
    step("P4_jira", jira)
    step("P5_calendar", calendar)
    try:
        readers.close()
    except Exception:  # noqa: BLE001
        pass

region = env("LEAVE_IMPACT_AWS_REGION")
model = env("P_MODEL")
counting_model = env("P_COUNT_MODEL")
messages = [{"role": "user", "content": [{"text": "Reply with the single word ok."}]}]
runtime = inference_client(region)


def invoke():
    response = runtime.converse(
        modelId=model, messages=messages, inferenceConfig={"maxTokens": 5, "temperature": 0}
    )
    return {
        "stop": response.get("stopReason"),
        "usage": response.get("usage"),
        "request_id": response["ResponseMetadata"].get("RequestId"),
    }


def count(identifier):
    def run():
        outcome = CountingClient(runtime).count(identifier, {"messages": messages})
        return {"outcome": type(outcome).__name__, "fields": repr(outcome)[:240]}

    return run


step("P6_invoke", invoke)
step("P7_count_profile", count(model))
step("P7_count_base_model", count(counting_model))

bucket = env("LEAVE_IMPACT_WORLD_BUCKET")
probe_key = f"runs/probe-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}/instance-create-only.txt"
s3 = boto3.client("s3", region_name=region)


def put(with_header):
    def run():
        kwargs = {"Bucket": bucket, "Key": probe_key, "Body": b"step 14 instance probe\n"}
        if with_header:
            kwargs["IfNoneMatch"] = "*"
        response = s3.put_object(**kwargs)
        return {"status": response["ResponseMetadata"]["HTTPStatusCode"]}

    return run


step("P8_put_create_only", put(True))
step("P8_put_again_create_only", put(True))
step("P8_put_without_header", put(False))
out["probe_key"] = probe_key

print(json.dumps(out, indent=1, default=str))
