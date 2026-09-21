# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""When a package's objects are removed, and when they are swept (p009 §2.13).

A package tree sits **outside** the `File` refcount model on purpose. p004 keys
media by content hash because `_delete_file_on_disk` counts File rows sharing a
`content_hash` and nothing else; a thousand objects under one prefix are not
File rows and never will be. So the refcount here is ours: a `SCORM Package` is
alive while any `Course Schedule Chapter` points at it, and its objects go when
the last one stops.

Two things that are deliberately *not* symmetric with deletion:

* **Attempts are retained.** They are student records and they outlive the
  content they were recorded against.
* **The source zip is retained.** It is a `File` attached to its chapter, and
  frappe's own refcount owns it. It is also the artifact a re-upload or a Course
  Pack starts from.
"""

from __future__ import annotations

import frappe

#: An unpack that died between its first `put` and its `SCORM Package` row
#: leaves objects nothing references. Younger than this they may belong to an
#: unpack still running, so the sweep leaves them alone.
ORPHAN_MIN_AGE_HOURS = 24

KEY_PREFIX = "scorm/"


def release(package_name: str | None, exclude_chapter: str | None = None) -> bool:
    """Drop `package_name` if no chapter points at it any more.

    Called from every path that stops a chapter referencing a package --
    deletion, re-upload, re-pointing. `exclude_chapter` is for the caller that
    has already decided a chapter is going but has not deleted its row yet.

    Returns True when the package was removed.
    """
    if not package_name or not frappe.db.exists("SCORM Package", package_name):
        return False

    filters = {"scorm_package_ref": package_name}
    if exclude_chapter:
        filters["name"] = ["!=", exclude_chapter]
    if frappe.db.exists("Course Schedule Chapter", filters):
        return False

    delete_objects(package_name)
    frappe.delete_doc(
        "SCORM Package", package_name, ignore_permissions=True, force=True
    )
    return True


def delete_objects(package_name: str) -> int:
    """Remove every object under this package's prefix. Best effort, counted.

    A failure to delete is logged rather than raised: the row must still go, or
    the next `release` finds a package whose chapters are gone and whose objects
    it will never try again. What is left behind is picked up by the sweep.
    """
    from seminary.storage.backend import get_storage_backend

    package_id = frappe.db.get_value("SCORM Package", package_name, "package_id")
    if not package_id:
        return 0

    backend = get_storage_backend()
    if not backend.is_configured():
        return 0

    removed = 0
    try:
        keys = [
            entry["key"] for entry in backend.list_keys(f"{KEY_PREFIX}{package_id}/")
        ]
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"scorm: could not list {package_name} to delete it"
        )
        return 0

    for key in keys:
        try:
            backend.delete(key)
            removed += 1
        except Exception:
            frappe.log_error(
                f"{key}\n{frappe.get_traceback()}",
                "scorm: could not delete a package object",
            )
    return removed


def sweep_orphaned_packages():
    """Daily. Remove `scorm/<id>/` trees that no `SCORM Package` row claims.

    The counterpart of `storage.direct.sweep_pending_uploads`, and for the same
    reason: an unpack that is killed between writing objects and committing its
    row leaves bytes nobody will ever ask for. An object-store lifecycle rule on
    the prefix cannot do this one -- the prefix is live for packages that *are*
    claimed, and age alone does not distinguish them.
    """
    from frappe.utils import add_to_date, get_datetime, now_datetime

    from seminary.storage.backend import get_storage_backend

    backend = get_storage_backend()
    if not backend.is_configured():
        return

    known = set(
        frappe.get_all(
            "SCORM Package", pluck="package_id", filters={"package_id": ["is", "set"]}
        )
    )
    cutoff = add_to_date(now_datetime(), hours=-ORPHAN_MIN_AGE_HOURS)

    stale: dict[str, list[str]] = {}
    for entry in backend.list_keys(KEY_PREFIX):
        key = entry["key"]
        rest = key[len(KEY_PREFIX) :]
        package_id = rest.split("/", 1)[0] if "/" in rest else None
        if not package_id or package_id in known:
            continue
        modified = entry.get("last_modified")
        if modified and get_datetime(modified) > cutoff:
            # Possibly an unpack still in flight.
            continue
        stale.setdefault(package_id, []).append(key)

    for package_id, keys in stale.items():
        for key in keys:
            try:
                backend.delete(key)
            except Exception:
                frappe.log_error(
                    f"{key}\n{frappe.get_traceback()}",
                    "scorm: could not sweep an orphaned package object",
                )
        frappe.logger("seminary").info(
            f"scorm: swept {len(keys)} orphaned objects under {KEY_PREFIX}{package_id}/"
        )
