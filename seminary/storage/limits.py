# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Per-audience upload size limits.

Frappe has exactly one upload ceiling, `max_file_size`, applied to everyone. That
is the wrong shape for a seminary: an instructor publishing a lecture recording and
a student submitting a term paper do not belong under the same cap, and an alumnus
updating a profile photo needs less room than either.

## How this nests under Frappe's cap

`File.check_max_file_size` (`frappe/core/doctype/file/file.py:780`) runs inside
`save_file`, *before* any app hook, and throws at the global value. So the global
cap is a hard ceiling we cannot raise from here, only tighten beneath. The rule is
therefore:

    System Settings → Max File Size  =  the MOST permissive role's limit
    Seminary's per-role caps         =  tighter limits underneath it

This is the same arrangement ADR 040 already uses for in-platform recordings, where
`MAX_RECORDING_MB` is a sub-cap beneath the global. That ADR's "one knob, surfaced
everywhere" rule is deliberately amended here; see
`privatedocs/p004-object-storage-for-large-media.md`.

## Resolving a user's cap

Configured in Seminary Settings: a **Default Max Upload** that applies to everyone,
plus a table of **Per-Role Exceptions** for the roles that differ. Configuring the
default once and listing only exceptions is far less work than naming all seven
ADR 034 roles, and it means a role added later is covered automatically instead of
silently uncapped.

Resolution, in order:

1. Administrator is never capped.
2. If any of the user's roles appears in the exceptions table, the cap is the **most
   permissive** of those. A Program Chair who is also a Student must not be narrowed
   to the student cap.
3. Otherwise the default applies.
4. If neither is configured, there is no seminary limit and only Frappe's global cap
   applies — which is what makes an unconfigured site behave exactly as it does today.

An explicit role row **overrides** the default rather than competing with it. If it
competed under "most permissive wins", a deliberately tight row (Alumni at 5 MB under
a 25 MB default) would lose to the default and could only ever loosen, never tighten.
"""

from __future__ import annotations

import frappe

MB = 1024 * 1024


def _policy() -> dict:
    """The configured policy as `{"default": bytes|None, "roles": {role: bytes}}`.

    Cached, and fetched as one unit, because this is consulted on every single
    upload and on `get_upload_limits()` for every page that mounts an uploader.
    """

    def _load():
        default_mb = frappe.db.get_single_value(
            "Seminary Settings", "default_max_upload_mb"
        )
        rows = frappe.get_all(
            "Upload Limit",
            filters={"parenttype": "Seminary Settings"},
            fields=["role", "max_file_size_mb"],
        )
        return {
            "default": (
                int(default_mb) * MB if default_mb and int(default_mb) > 0 else None
            ),
            "roles": {
                row.role: int(row.max_file_size_mb) * MB
                for row in rows
                if row.role and row.max_file_size_mb and int(row.max_file_size_mb) > 0
            },
        }

    return frappe.cache.get_value("seminary_upload_limits", _load)


def role_limits() -> dict[str, int]:
    """The per-role exceptions table, as `{role: max bytes}`."""
    return _policy()["roles"]


def default_limit() -> int | None:
    """The catch-all cap in bytes, or None when unset."""
    return _policy()["default"]


def clear_cache():
    """Drop the cached table. Called from Seminary Settings `on_update`."""
    frappe.cache.delete_value("seminary_upload_limits")


def limit_for_user(user: str | None = None) -> int | None:
    """Effective seminary upload cap in bytes, or None when unlimited.

    None means "no seminary-level limit" — Frappe's global `max_file_size` still
    applies on top, and always did.
    """
    user = user or frappe.session.user

    if user == "Administrator":
        return None

    policy = _policy()
    exceptions = policy["roles"]

    if exceptions:
        applicable = [
            exceptions[role] for role in frappe.get_roles(user) if role in exceptions
        ]
        if applicable:
            # Most permissive of the user's listed roles, and it overrides the
            # default outright — see the module docstring.
            return max(applicable)

    return policy["default"]


#: Ceiling for a direct browser upload when no per-role cap is configured. This is
#: the second knob ADR 040 said not to have, added deliberately: the direct path
#: never reaches Frappe's `check_max_file_size` (the File row is created with
#: `file_url` already set, so `save_file` no-ops), so it is bounded only by what we
#: enforce, and a site with no role policy still needs an upper bound.
DEFAULT_MAX_DIRECT_BYTES = 2 * 1024 * 1024 * 1024


def direct_limit_for_user(user: str | None = None) -> int:
    """Ceiling in bytes for a direct-to-object-storage upload.

    Deliberately *not* bounded by `global_max_bytes()`: escaping Frappe's global
    ceiling — and nginx's `client_max_body_size` — is the entire point of the
    direct path. Per-role policy still governs, so an instructor capped at 400 MB
    is capped at 400 MB here too; the fallback only applies where no role policy
    exists at all.
    """
    ceiling = int(
        frappe.conf.get("storage_max_direct_bytes") or DEFAULT_MAX_DIRECT_BYTES
    )
    role_cap = limit_for_user(user)
    return min(role_cap, ceiling) if role_cap else ceiling


def global_max_bytes() -> int:
    """The size Frappe itself will accept, across *both* of its ceilings.

    Frappe ships two unrelated `get_max_file_size()` functions and which one
    applies depends on how a file was created:

    - `frappe.core.api.file.get_max_file_size` — used by `File.check_max_file_size`
      on the document path. System Settings (MB) → `conf` → 25 MB.
    - `frappe.utils.file_manager.get_max_file_size` — used by the legacy
      `save_file()` path. **`conf.max_file_size` only → 10 MB**, ignoring System
      Settings completely.

    Seminary uses both paths: `api/folder_upload.py` (Course Folder instructor
    materials) and `course_pack/import_.py` go through the legacy one. So a site
    that raises System Settings to 100 MB still has its folder uploads rejected at
    10 MB, with a message naming a limit nobody configured.

    We report the **lower** of the two, because ADR 040's promise is that the
    number shown to the user is the number enforced, and a hint that over-promises
    is worse than one that is conservative. To make the two agree, set
    `max_file_size` (in *bytes*) in `site_config.json` and leave System Settings →
    Max File Size at 0: the modern path then falls through to `conf` and both read
    the same value.
    """
    from frappe.core.api.file import get_max_file_size as doc_path_max
    from frappe.utils.file_manager import get_max_file_size as legacy_path_max

    return min(doc_path_max(), legacy_path_max())


def enforce_upload_limits(doc, method=None):
    """Reject an upload above the uploader's per-role cap (`File` validate hook).

    Only on insert: a cap governs *uploading*, so tightening policy must not make
    existing files unsaveable. Frappe's global cap has already been applied by
    `check_max_file_size` inside `save_file`, so anything reaching here is within
    it and only the tighter role cap can still bite.
    """
    if getattr(doc, "is_folder", 0) or not doc.is_new():
        return

    if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
        return

    cap = limit_for_user()
    if not cap:
        return

    size = doc.file_size or 0
    if size <= cap:
        return

    frappe.throw(
        frappe._(
            "This file is too large ({0} MB). Your account may upload files up to {1} MB."
        ).format(round(size / MB), round(cap / MB)),
        title=frappe._("File too large"),
    )


def effective_limit(user: str | None = None) -> tuple[int, str | None]:
    """Return `(max_bytes, source)` actually enforced for `user`.

    `source` is "role" when a seminary per-role cap is the binding constraint and
    None when the global cap is, which lets callers phrase an accurate message
    instead of blaming the wrong setting.
    """
    global_bytes = global_max_bytes()
    role_bytes = limit_for_user(user)

    if role_bytes is None or role_bytes >= global_bytes:
        return global_bytes, None
    return role_bytes, "role"
