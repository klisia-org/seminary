# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Frappe `write_file` / `delete_file_data_content` hook adapters.

These are the only two write-side seams Frappe offers, and both are called with
**two different signatures** depending on which API the caller used. Every
branch that does not offload delegates to the *exact* upstream default, so a
site with no storage backend runs Frappe's own code path plus one boolean.

## The two call forms

    frappe/core/doctype/file/file.py:810-813   write_file_method(self)
    frappe/utils/file_manager.py:164-165       write_file_method(fname, content,
                                                   content_type=…, is_private=…)

`get_hook_method` (`frappe/utils/__init__.py:619`) takes `hooks[name][0]` — the
*first* app wins, bench-globally. Seminary claims both hooks; that is only safe
because of the fall-through above.

## Two asymmetries worth knowing before editing this file

**The doc form must mutate, not return.** `File.before_insert` (file.py:134)
calls `self.save_file(...)` and *discards* the return value; upstream's
`save_file_on_filesystem` works purely because it assigns `self.file_url` in
place. The returned dict is consumed only by the legacy form
(`file_manager.py:165`, which then `.update()`s it into the new doc).

**Rollback compensation is free on the doc form and absent on the legacy one.**
file.py:134-135 sets `flags.new_file` and registers `after_rollback` regardless
of which backend ran, and `on_rollback` (249) → `_delete_file_on_disk` (603) →
refcount → `delete_file_data_content` → this module. The legacy path registers
nothing: it writes the bytes, then inserts a doc whose `file_url` is already set,
so `is_remote_file` is True and `before_insert` takes the `validate_remote_file`
branch instead. We register our own compensation there.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from seminary.storage.backend import (
    get_storage_backend,
    is_offloaded,
    key_from_url,
    object_key,
)
from seminary.storage.routing import should_offload


def write_file(*args, **kwargs):
    """Dispatch on the call form. See the module docstring."""
    if args and isinstance(args[0], Document):
        return _write_from_doc(args[0])
    return _write_from_args(*args, **kwargs)


def _write_from_doc(doc):
    """Modern form: `File.save_file` hands us the document.

    By the time this runs, `save_file` has already set `file_size` (file.py:780),
    `content_hash` (781), `content_type` (770) and a collision-suffixed
    `file_name` (803), and `_content` holds the (possibly EXIF-stripped) bytes.
    All of it is reusable as-is.
    """
    if not should_offload(doc.file_name, doc.file_size, doc.is_private):
        return doc.save_file_on_filesystem()

    key = object_key(doc.content_hash)
    get_storage_backend().put(key, doc._content, content_type=doc.content_type)

    # Mutate in place — the caller discards our return value.
    doc.file_url = _url(key)
    return {"file_name": doc.file_name, "file_url": doc.file_url}


def _write_from_args(fname, content, content_type=None, is_private=0):
    """Legacy form: `frappe.utils.file_manager.save_file` hands us raw values.

    Seminary's upload paths have moved to the document form (the legacy helper
    enforces a size ceiling that ignores System Settings), so the live callers left
    are `integrations/pexels.py` and anything outside this app. It stays supported
    because the hook is bench-global and any installed app may use either form.

    Note that upstream has *already* deduped by content hash before reaching us
    (`get_file_data_from_hash`, file_manager.py:160), so an existing blob never
    gets here.
    """
    from frappe.core.doctype.file.utils import get_content_hash
    from frappe.utils.file_manager import save_file_on_filesystem

    size = len(content or b"")
    if not should_offload(fname, size, is_private):
        return save_file_on_filesystem(
            fname, content, content_type=content_type, is_private=is_private
        )

    content_hash = get_content_hash(content)
    key = object_key(content_hash)
    get_storage_backend().put(key, content, content_type=content_type)

    # Upstream registers no rollback compensation on this path (see the module
    # docstring), so we do. The guard matters: a rolled-back *duplicate* upload
    # must not delete bytes a committed sibling row still points at.
    frappe.db.after_rollback.add(lambda: _delete_if_unreferenced(key, content_hash))

    return {"file_name": fname, "file_url": _url(key)}


def delete_file_data_content(doc, only_thumbnail: bool = False):
    """Remove an offloaded object once nothing references it.

    **There is no refcount to reimplement here.** Both call sites
    (file.py:840-846, file_manager.py:292-294) sit downstream of
    `_delete_file_on_disk` (file.py:603-618), which runs the `content_hash`-shared
    query itself and passes `only_thumbnail=True` when the blob is still shared.
    So this function is only ever reached with `only_thumbnail=False` when the row
    being deleted is genuinely the last one. The invariant to protect is simply:
    never bypass `_delete_file_on_disk`.

    The delete is deferred to `after_commit` rather than run inline. Upstream
    unlinks from disk during `on_trash`, so a later rollback in the same
    transaction leaves a live File row pointing at bytes that are already gone —
    an upstream bug we get to not inherit.
    """
    from frappe.utils.file_manager import delete_file, delete_file_from_filesystem

    key = key_from_url(doc.file_url)
    if not key:
        return delete_file_from_filesystem(doc, only_thumbnail=only_thumbnail)

    # Offloaded blob. Any thumbnail is still a local file (images never offload),
    # so mirror upstream's ordering: thumbnail always, the blob itself only when
    # this is not a thumbnail-only call.
    delete_file(doc.thumbnail_url)
    if only_thumbnail:
        return

    content_hash = doc.content_hash
    frappe.db.after_commit.add(
        lambda: _delete_if_unreferenced(key, content_hash, exclude=doc.name)
    )


def _delete_if_unreferenced(
    key: str, content_hash: str | None, exclude: str | None = None
):
    """Delete `key` unless some other File row still points at that blob.

    Runs outside the transaction (after commit or after rollback), so it must not
    assume the row it was called for still exists, and must never raise into the
    caller — a failed cleanup leaves a harmless orphan, which ADR 041 already
    accepts for disk; a raised exception here would be worse than the orphan.
    """
    try:
        if content_hash:
            filters = {"content_hash": content_hash}
            if exclude:
                filters["name"] = ["!=", exclude]
            if frappe.get_all("File", filters=filters, limit=1):
                return
        get_storage_backend().delete(key)
    except Exception:
        frappe.log_error(
            title="seminary.storage: orphaned object",
            message=f"Could not delete {key}:\n{frappe.get_traceback()}",
        )


def _url(key: str) -> str:
    from seminary.storage.backend import url_for_key

    return url_for_key(key)


__all__ = ["delete_file_data_content", "is_offloaded", "write_file"]
