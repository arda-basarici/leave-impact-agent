"""Does a raising signal handler unwind a main thread blocked on a lock another thread
holds, on a future another thread never completes, and on a Condition wait?"""
import concurrent.futures
import signal
import sys
import threading
import time


def handler(signum, frame):
    raise SystemExit("signal")


signal.signal(signal.SIGALRM, handler)
mode = sys.argv[1]
t0 = time.monotonic()
try:
    if mode == "lock":
        lock = threading.Lock()
        lock.acquire()
        signal.setitimer(signal.ITIMER_REAL, 1)
        lock.acquire()
    elif mode == "future":
        ex = concurrent.futures.ThreadPoolExecutor(1)
        ev = threading.Event()
        fut = ex.submit(ev.wait)
        signal.setitimer(signal.ITIMER_REAL, 1)
        concurrent.futures.wait([fut])
    elif mode == "result":
        ex = concurrent.futures.ThreadPoolExecutor(1)
        ev = threading.Event()
        fut = ex.submit(ev.wait)
        signal.setitimer(signal.ITIMER_REAL, 1)
        fut.result()
    elif mode == "condition":
        cond = threading.Condition()
        signal.setitimer(signal.ITIMER_REAL, 1)
        with cond:
            cond.wait()
    print(mode, "NOT unwound after", round(time.monotonic() - t0, 2))
except SystemExit as exc:
    print(mode, "unwound after", round(time.monotonic() - t0, 2), "s:", exc, flush=True)
    import os
    os._exit(0)
