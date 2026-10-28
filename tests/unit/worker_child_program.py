"""A child program for the supervisor's real-spawn tests, three behaviours by its first
argument: ``ending <line>`` prints the line and exits 0; ``die <code>`` writes a line to
stderr and exits with the code, no ending printed; ``hang`` ignores its terminate where
the platform lets a process do so (POSIX) and sleeps past any wall, so only the kill ends
it. Importing it does nothing; it acts under ``__main__`` alone."""

from __future__ import annotations

import signal
import sys
import time


def main(argv: list[str]) -> int:
    behaviour = argv[0]
    if behaviour == "ending":
        print(argv[1], flush=True)
        return 0
    if behaviour == "die":
        print("the child program died as asked", file=sys.stderr, flush=True)
        return int(argv[1])
    if behaviour == "hang":
        if hasattr(signal, "SIGTERM") and sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
        return 0
    raise SystemExit(f"unknown behaviour {behaviour}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
