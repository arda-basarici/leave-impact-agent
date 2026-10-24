"""The memory baseline's sampler (the demo milestone's step 10): one reading of the host
and the stack's containers as a compact JSON line on stdout, run on the instance with the
system Python between the loader's levels by the host script.

It reads cgroup v2 files directly rather than `docker stats`, whose usage column folds
the page cache in and reports no peak: per container, `memory.current` (what the limit is
enforced on), `memory.peak` where the kernel has it, and the anonymous, file and shared
pages of `memory.stat`; the host's `/proc/meminfo`; the app process's thread count, so
whether the thread pool binds reads off the same samples; and, when asked, the host's
largest resident processes, which make the host's own baseline a read number. A container
that is absent is recorded as absent, never skipped, so the reading shows which
residents the host had. Written for the instance's Python 3.9, so no syntax newer than it.
"""

import glob
import json
import os
import subprocess
import sys
import time

CONTAINERS = ("leaveimpact-app-1", "leaveimpact-postgres-1", "proxy-caddy-1")
STAT_KEYS = {"anon": "anon", "file": "file", "shmem": "shm", "kernel": "kern", "slab": "slab"}
MEMINFO_KEYS = {
    "MemTotal": "total",
    "MemFree": "free",
    "MemAvailable": "avail",
    "Buffers": "buffers",
    "Cached": "cached",
    "Shmem": "shm",
    "SwapTotal": "swap",
}


def read_int(path):
    try:
        with open(path) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return None


def read_stat(path):
    stat = {}
    try:
        with open(path) as handle:
            for line in handle:
                key, _, value = line.partition(" ")
                stat[key] = int(value)
    except OSError:
        pass
    return stat


def threads_of(pid):
    try:
        with open("/proc/%d/status" % pid) as handle:
            for line in handle:
                if line.startswith("Threads:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


def container(name):
    inspected = subprocess.run(
        ["docker", "inspect", "-f", "{{.Id}} {{.State.Pid}}", name],
        capture_output=True,
        text=True,
    )
    if inspected.returncode != 0:
        return {"absent": inspected.stderr.strip()[:100]}
    cid, pid = inspected.stdout.split()
    dirs = [
        path
        for path in glob.glob("/sys/fs/cgroup/**/*" + cid + "*", recursive=True)
        if os.path.isdir(path)
    ]
    if not dirs:
        return {"absent": "no cgroup directory for " + cid[:12]}
    cgroup = dirs[0]
    reading = {
        "cur": read_int(cgroup + "/memory.current"),
        "peak": read_int(cgroup + "/memory.peak"),
        "thr": threads_of(int(pid)),
    }
    stat = read_stat(cgroup + "/memory.stat")
    for key, short in STAT_KEYS.items():
        reading[short] = stat.get(key)
    return reading


def meminfo():
    info = {}
    with open("/proc/meminfo") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            if key in MEMINFO_KEYS:
                info[MEMINFO_KEYS[key]] = int(rest.split()[0]) * 1024
    return info


def largest_processes(count=10):
    listed = subprocess.run(
        ["ps", "-eo", "rss=,comm=", "--sort=-rss"], capture_output=True, text=True
    )
    rows = []
    for line in listed.stdout.splitlines()[:count]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            rows.append([int(parts[0]) * 1024, parts[1].strip()])
    return rows


def main(argv):
    label = argv[1] if len(argv) > 1 else "sample"
    reading = {
        "label": label,
        "t": time.strftime("%H:%M:%S", time.gmtime()),
        "host": meminfo(),
        "containers": {name: container(name) for name in CONTAINERS},
    }
    if "--processes" in argv:
        reading["processes"] = largest_processes()
    print(json.dumps(reading, separators=(",", ":")))


if __name__ == "__main__":
    main(sys.argv)
