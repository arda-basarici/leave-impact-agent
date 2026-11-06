"""Frappe HR: employees by employee number, departments as teams, leave applications as leaves.

Frappe's own record names and timestamps are vendor identity and vendor time, kept
inside the adapter and never exposed as world facts. ``records`` holds the pure
translation between Frappe documents and domain entities; ``adapter`` holds the wire,
the company scope and the site preparation. The public surface is the three names
below.
"""

from leaveimpact.adapters.frappe.adapter import (
    AccessServiceToken,
    FrappeAdapter,
    FrappeConfig,
    FrappeCredential,
)

__all__ = ["AccessServiceToken", "FrappeAdapter", "FrappeConfig", "FrappeCredential"]
