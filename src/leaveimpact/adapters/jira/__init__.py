"""Jira: issues as work items with their comments, project components as components.

Jira's own timestamps, keys and comment ids are vendor identity and vendor time, kept
inside the adapter. ``records`` holds the pure translation between Jira JSON and
domain entities; ``adapter`` holds the wire, the project scope, and the site
preparation whose result — the custom field ids — the adapter is configured with.
"""

from leaveimpact.adapters.jira.adapter import (
    JiraAdapter,
    JiraConfig,
    JiraCredential,
    JiraFields,
    JiraSite,
)

__all__ = ["JiraAdapter", "JiraConfig", "JiraCredential", "JiraFields", "JiraSite"]
