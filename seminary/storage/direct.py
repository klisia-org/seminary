# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Direct browser-to-object-storage upload.

Frappe's `upload_file` reads the entire request body into worker memory
(`frappe/handler.py:179`) before a byte reaches storage, and nginx caps the body at
`client_max_body_size` (50m on this bench). Between them, a lecture recording is
not uploadable at all, no matter how large the configured limits are.

This module hands the browser a short-lived URL and gets out of the way: the bytes
travel browser → object storage, never through a worker, and neither Frappe's
`max_file_size` nor nginx's body cap applies. That freedom is exactly why the
server-side checks here have to be complete — see below.

## Two calls, and why the second re-derives everything

    presign_upload(...)  -> {key, upload_url, ...}      # authorise
    ...browser PUTs straight to object storage...
    register_upload(key) -> the File row                # verify and record

**The key is always chosen here.** A presigned PUT authorises a write to exactly
one key, so letting a client name it would be an arbitrary-write primitive over the
whole bucket — overwriting any existing object, including another school's media on
a shared bucket.

**Nothing the client says at register time is trusted.** The doctype, docname,
fieldname and privacy flag are recorded in the cache at presign time (after the
permission check) and replayed at register time, so a caller cannot presign an
upload against a document they may write and then attach the result to one they may
not. The size comes from the store itself via `stat()`, never from the client, and
the limit is re-enforced against it.

**The pending entry is bound to the uploading user** and expires with the URL, so a
leaked key cannot be registered by someone else or reused later.

## Why the object moves after upload

It lands under a nonce key, then is copied to `media/<content hash>`. The
content-addressed key is what makes dedup work and, more importantly, what keeps
`_delete_file_on_disk`'s refcount correct — that refcount compares `content_hash`
across File rows, so two rows over identical bytes must resolve to one object (see
`backend.object_key`). The hash cannot come from the upload's ETag for anything
large: R2 returns `<hash>-<partcount>` for a multipart upload, which is not a
content hash. So a single-part ETag is used directly (it is the MD5, verified
against live R2) and anything else is hashed by streaming the object once — free in
egress, and it costs one pass of worker CPU rather than worker memory.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re

import frappe
from frappe import _

from seminary.storage.backend import get_storage_backend, object_key, url_for_key
from seminary.storage.limits import direct_limit_for_user
from seminary.storage.routing import should_offload

#: Temporary home for uploads that have not been registered yet. Swept on a
#: schedule, so an abandoned upload costs storage for at most a day.
DIRECT_PREFIX = "media/direct"

_PENDING_CACHE = "seminary_direct_upload"

#: How long a presigned PUT (and its pending record) stays valid. Long enough to
#: upload a large file on a slow connection, short enough that a leaked URL is of
#: little use.
DEFAULT_UPLOAD_TTL = 3600

#: Abandoned uploads older than this are swept.
PENDING_MAX_AGE_HOURS = 24


def upload_ttl() -> int:
    return int(frappe.conf.get("storage_upload_ttl") or DEFAULT_UPLOAD_TTL)


def _pending_key(nonce: str) -> str:
    return f"{_PENDING_CACHE}:{nonce}"


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_name(file_name: str) -> str:
    """Reduce a filename to URL-safe characters for the temporary key.

    Stricter than `frappe`'s `get_safe_file_name` (which leaves spaces and
    non-ASCII) because this string round-trips through a presigned URL and back:
    the browser PUTs to the encoded form, then hands the raw key to
    `register_upload`, which must resolve to the same object. Purely cosmetic
    anyway — the real name lives on `File.file_name`, and the object is renamed to
    its content hash on registration.
    """
    return (
        _UNSAFE.sub("_", os.path.basename(file_name or "upload")).strip("._-")
        or "upload"
    )


@frappe.whitelist()
def presign_upload(
    file_name: str,
    file_size: int,
    content_type: str | None = None,
    doctype: str | None = None,
    docname: str | None = None,
    fieldname: str | None = None,
    is_private: int | str = 1,
    folder: str | None = None,
):
    """Authorise one direct upload and return a URL to PUT it to.

    Returns `{"direct": False, ...}` when this upload should not go direct — no
    object storage configured, or the file is small enough that the ordinary
    upload path is simpler. Callers are expected to fall back rather than fail.
    """
    backend = get_storage_backend()
    file_size = int(file_size or 0)
    is_private = frappe.utils.cint(is_private)

    if not backend.is_configured() or not should_offload(
        file_name, file_size, is_private
    ):
        return {"direct": False, "reason": "not_eligible"}

    # Exactly the check `frappe.handler.upload_file` performs, so the direct path
    # cannot be used to attach a file to a document the user may not write.
    from frappe.handler import check_write_permission

    check_write_permission(doctype, docname)

    ceiling = direct_limit_for_user()
    if file_size > ceiling:
        frappe.throw(
            _(
                "This file is too large ({0} MB). You may upload files up to {1} MB."
            ).format(round(file_size / (1024 * 1024)), round(ceiling / (1024 * 1024))),
            title=_("File too large"),
        )

    content_type = (
        content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    )

    nonce = frappe.generate_hash(length=32)
    key = f"{DIRECT_PREFIX}/{nonce}/{_safe_name(file_name)}"
    ttl = upload_ttl()

    # Everything the register step will need, decided *now* while the caller's
    # permissions have just been checked. register_upload replays this and ignores
    # whatever the client sends.
    frappe.cache.set_value(
        _pending_key(nonce),
        {
            "key": key,
            "user": frappe.session.user,
            "file_name": file_name,
            "content_type": content_type,
            "doctype": doctype,
            "docname": docname,
            "fieldname": fieldname,
            "is_private": is_private,
            "folder": folder,
            "max_bytes": ceiling,
        },
        expires_in_sec=ttl + 300,
    )

    return {
        "direct": True,
        "key": key,
        "upload_url": backend.presigned_put(key, ttl=ttl, content_type=content_type),
        "method": "PUT",
        # The signature covers the content type, so the browser must send exactly
        # this or R2 rejects the PUT with a signature mismatch.
        "headers": {"Content-Type": content_type},
        "expires_in": ttl,
    }


@frappe.whitelist(methods=["POST"])
def register_upload(key: str):
    """Verify a completed direct upload and create its `File` row.

    Takes only the key: every other fact is replayed from what was authorised at
    presign time, or read from the object itself.
    """
    backend = get_storage_backend()
    if not backend.is_configured():
        frappe.throw(_("Object storage is not configured for this site."))

    pending, nonce = _load_pending(key)

    stat = backend.stat(key)
    if not stat:
        frappe.throw(
            _("The upload did not complete — nothing was stored. Please try again."),
            title=_("Upload not found"),
        )

    size = int(stat["size"])
    _enforce_size(size, pending)

    content_hash = _content_hash(backend, key, stat)
    final_key = object_key(content_hash)

    # Promote to the content-addressed key, unless identical bytes are already
    # there — in which case the upload deduplicated itself.
    if final_key != key and not backend.stat(final_key):
        backend.copy(key, final_key)

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": pending["file_name"],
            "file_url": url_for_key(final_key),
            "is_private": pending["is_private"],
            "file_size": size,
            "content_hash": content_hash,
            "folder": pending.get("folder") or None,
            "attached_to_doctype": pending.get("doctype"),
            "attached_to_name": pending.get("docname"),
            "attached_to_field": pending.get("fieldname"),
        }
    )
    file_doc.insert()

    # The temporary object is redundant now. Deferred to after_commit so a
    # rollback does not leave the row pointing at bytes we already removed.
    frappe.db.after_commit.add(lambda: _discard(key, final_key))
    frappe.cache.delete_value(_pending_key(nonce))

    return {
        "name": file_doc.name,
        "file_name": file_doc.file_name,
        "file_url": file_doc.file_url,
        "file_size": file_doc.file_size,
        "is_private": file_doc.is_private,
        "file_type": (os.path.splitext(file_doc.file_name or "")[1] or "")
        .lstrip(".")
        .upper(),
    }


def _load_pending(key: str):
    """Resolve `key` to the record written at presign time, or refuse."""
    if not key or not key.startswith(f"{DIRECT_PREFIX}/"):
        frappe.throw(_("Not an upload key."), frappe.PermissionError)

    parts = key.split("/")
    if len(parts) < 4:
        frappe.throw(_("Not an upload key."), frappe.PermissionError)
    nonce = parts[2]

    pending = frappe.cache.get_value(_pending_key(nonce))
    if not pending or pending.get("key") != key:
        frappe.throw(
            _("This upload has expired. Please upload the file again."),
            title=_("Upload expired"),
        )

    # A key is only ever handed to one user; binding it means a leaked key cannot
    # be redeemed by anyone else.
    if pending.get("user") != frappe.session.user:
        frappe.throw(_("This upload belongs to another user."), frappe.PermissionError)

    # Re-check the target, in case the user's access changed between the two calls.
    from frappe.handler import check_write_permission

    check_write_permission(pending.get("doctype"), pending.get("docname"))

    return pending, nonce


def _enforce_size(size: int, pending: dict):
    """Apply the limits to the size the *store* reports, not the client's claim."""
    ceiling = min(
        int(pending.get("max_bytes") or 0) or direct_limit_for_user(),
        direct_limit_for_user(),
    )
    if size > ceiling:
        frappe.throw(
            _(
                "This file is too large ({0} MB). You may upload files up to {1} MB."
            ).format(round(size / (1024 * 1024)), round(ceiling / (1024 * 1024))),
            title=_("File too large"),
        )

    # The in-platform recorder's cap is bypassable from the client (ADR 040), and
    # doubly so here where no worker ever sees the bytes.
    from seminary.seminary.lesson_media import (
        MAX_RECORDING_BYTES,
        MAX_RECORDING_MB,
        RECORDING_FILENAME_PREFIX,
    )

    if (pending.get("file_name") or "").startswith(RECORDING_FILENAME_PREFIX):
        if size > MAX_RECORDING_BYTES:
            frappe.throw(
                _(
                    "This recording is too large ({0} MB). In-platform recordings are "
                    "limited to {1} MB — please record a shorter clip."
                ).format(round(size / (1024 * 1024)), MAX_RECORDING_MB),
                title=_("Recording too large"),
            )


def _content_hash(backend, key: str, stat: dict) -> str:
    """MD5 of the uploaded object, matching `frappe`'s own `content_hash`.

    A single-part upload's ETag *is* the MD5 (verified against live R2), so the
    common case costs nothing. A multipart ETag is `<hash>-<partcount>` and is not
    a content hash, so those are hashed by streaming the object once.
    """
    etag = (stat.get("etag") or "").strip('"')
    if etag and "-" not in etag and len(etag) == 32:
        return etag

    # Not a security hash: MD5 is what frappe's own `get_content_hash` uses,
    # and the delete refcount compares against that value.
    digest = hashlib.md5(usedforsecurity=False)
    for chunk in backend.stream(key):
        digest.update(chunk)
    return digest.hexdigest()


def _discard(temp_key: str, final_key: str):
    """Remove the temporary object once its content-addressed copy is committed."""
    if temp_key == final_key:
        return
    try:
        get_storage_backend().delete(temp_key)
    except Exception:
        frappe.log_error(
            title="seminary.storage: could not remove temporary upload",
            message=f"{temp_key}\n{frappe.get_traceback()}",
        )


def sweep_pending_uploads():
    """Delete uploads that were presigned but never registered (daily scheduler).

    A presign the user abandoned — closed the tab, lost their connection — leaves
    an object nobody will ever reference. Without this they accumulate silently,
    and unlike a File row there is nothing in the database to notice.

    An object-store lifecycle rule on the `media/direct/` prefix would do the same
    job more cheaply; this exists so correctness does not depend on remembering to
    configure one.
    """
    backend = get_storage_backend()
    if not backend.is_configured():
        return

    from frappe.utils import add_to_date, get_datetime, now_datetime

    cutoff = add_to_date(now_datetime(), hours=-PENDING_MAX_AGE_HOURS)
    removed = 0
    for obj in backend.list_keys(f"{DIRECT_PREFIX}/"):
        last_modified = obj.get("last_modified")
        if not last_modified:
            continue
        if get_datetime(last_modified.replace(tzinfo=None)) < get_datetime(cutoff):
            try:
                backend.delete(obj["key"])
                removed += 1
            except Exception:
                frappe.log_error(
                    title="seminary.storage: could not sweep abandoned upload",
                    message=f"{obj['key']}\n{frappe.get_traceback()}",
                )
    return removed
