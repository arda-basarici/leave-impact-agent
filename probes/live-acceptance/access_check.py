"""The worker container's own Access pair, checked at the edge with no run spent (the
final smoke of the demo milestone's step 17). The smoke is the first attempt whose Frappe
reads leave the worker service itself: the instance probe proved the service token from a
one-off container that read Parameter Store, never from the environment the deploy script
hands the worker through Compose. Compose gives both names an empty default, so a name
being present says nothing, and a value being nonempty says nothing of whether the edge
accepts it; this asks the edge.

Run inside the worker container, its source piped to the interpreter there by the
acceptance sampler's host script (`host.sh`, the `check` action)::

    docker exec -i leaveimpact-worker-1 python - < access_check.py

It prints, and nothing else: for each of the two names, `nonempty` or `empty`; the host of
the Frappe base URL the container holds; and the Frappe login page read twice without
following a redirect, once with the pair as the two service-token headers and once without
them, each as its status and the host of its Location header. Expected: 200 with the pair,
and without it the edge's redirect to the Zero Trust organization (the runner probe's
reading of 2026-11-03), which is what makes the 200 the token's doing. No value, no body
and no Location query is printed: the redirect's query carries signed metadata about the
caller, and the output is filed in a public repository. Standard library only, since the
image carries no test dependency.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

NAMES = ("LEAVE_IMPACT_CF_ACCESS_CLIENT_ID", "LEAVE_IMPACT_CF_ACCESS_CLIENT_SECRET")
HEADERS = ("CF-Access-Client-Id", "CF-Access-Client-Secret")
"""The two headers the Frappe adapter's transport sends, in the names' order."""
BASE = "LEAVE_IMPACT_FRAPPE_BASE_URL"
USER_AGENT = "leave-impact-access-check/1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is the answer read, never followed."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def login_line(base: str, label: str, headers: Mapping[str, str]) -> str:
    """One read of the login page as a line: the status and the Location's host, or the
    error's type when no answer came."""
    request = urllib.request.Request(base + "/login", headers={"User-Agent": USER_AGENT, **headers})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=20) as response:
            status, location = response.status, response.headers.get("Location")
    except urllib.error.HTTPError as error:
        status, location = error.code, error.headers.get("Location")
    except OSError as error:
        return f"access login {label}: error {type(error).__name__}"
    host = urllib.parse.urlsplit(location).netloc if location else "-"
    return f"access login {label}: status {status}, location host {host}"


def lines(environ: Mapping[str, str]) -> list[str]:
    """Every line the check prints, from ``environ``."""
    out = [f"access {name} {'nonempty' if environ.get(name) else 'empty'}" for name in NAMES]
    base = environ.get(BASE, "").rstrip("/")
    out.append(f"frappe base host {urllib.parse.urlsplit(base).netloc or 'unset'}")
    if not base:
        return out
    pair = {header: environ.get(name, "") for header, name in zip(HEADERS, NAMES, strict=True)}
    out.append(login_line(base, "with the pair", pair))
    out.append(login_line(base, "without it", {}))
    return out


def main() -> int:
    for line in lines(os.environ):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
