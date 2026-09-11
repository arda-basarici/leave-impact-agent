"""Recording-time support for the Jira cassettes: the cassette project emptied.

A recording writes real issues into the cassette project, and a re-recording would
write them again — including the orphan an aborted write leaves without an id — so the
reset deletes every issue and every component and leaves the project, the custom fields
and the owner options, which are find-or-create and append-only. The project is never
dropped: a permanently deleted project's key can be reused, but the search index kept
mapping the reused keys to the dead issues (found at the second recording). Deleting an
issue needs a project role the permission scheme trusts, and the kanban template gives
the creating account none, so the reset first puts the account into the project's
Administrators role. It runs through the same transport, inside the cassette, so a
replay replays it too. Test support, not adapter capability: the adapter never deletes.
"""

from __future__ import annotations

from typing import Any

from leaveimpact.adapters.transport import Transport

_API = "/rest/api/3"


def _json(transport: Transport, method: str, path: str, **kwargs: Any) -> Any:
    return transport.request(method, f"{_API}{path}", **kwargs).json()


def ensure_deleter(transport: Transport, project_key: str) -> None:
    """The account joins the project's Administrators role, which may delete issues."""
    roles: dict[str, str] = _json(transport, "GET", f"/project/{project_key}/role", replayable=True)
    role_id = roles["Administrators"].rsplit("/", 1)[-1]
    role: dict[str, Any] = _json(
        transport, "GET", f"/project/{project_key}/role/{role_id}", replayable=True
    )
    me: dict[str, Any] = _json(transport, "GET", "/myself", replayable=True)
    actors: list[dict[str, Any]] = role.get("actors", [])
    if any(actor.get("actorUser", {}).get("accountId") == me["accountId"] for actor in actors):
        return
    transport.request(
        "POST",
        f"{_API}/project/{project_key}/role/{role_id}",
        replayable=False,
        ok=(200,),
        json={"user": [me["accountId"]]},
    )


def reset_project(transport: Transport, project_key: str) -> None:
    """Delete every issue and component of the cassette project; the project itself stays."""
    ensure_deleter(transport, project_key)
    while True:
        page: dict[str, Any] = _json(
            transport,
            "POST",
            "/search/jql",
            replayable=True,
            ok=(200,),
            json={"jql": f'project = "{project_key}"', "fields": ["key"], "maxResults": 100},
        )
        issues: list[dict[str, Any]] = page.get("issues", [])
        if not issues:
            break
        for issue in issues:
            transport.request(
                "DELETE",
                f"{_API}/issue/{issue['key']}",
                replayable=False,
                ok=(204, 404),
                params={"deleteSubtasks": "true"},
            )
    components: list[dict[str, Any]] = _json(
        transport, "GET", f"/project/{project_key}/components", replayable=True
    )
    for component in components:
        transport.request(
            "DELETE", f"{_API}/component/{component['id']}", replayable=False, ok=(204, 404)
        )
