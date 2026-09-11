# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The read endpoint for offloaded files.

Every offloaded `File.file_url` points here. The endpoint checks permission
exactly as Frappe would, then **redirects** to a short-lived presigned URL so the
bytes travel object-store→browser and never through a worker. That redirect is
the whole point: it is what removes both the egress bill and the worker occupancy
that ADR 040 flagged as the scaling caveat.

Modelled on `frappe.utils.response.download_private_file` (response.py:293-306),
with two deliberate differences, both recorded in `privatedocs/p004`:

**Guests are not rejected outright.** Upstream's private-file route refuses
`Guest` before it looks at anything. We cannot, because this one endpoint serves
public files too: `File.has_permission` (file.py:950-951) short-circuits with
`if not doc.is_private and ptype in ("read", "select"): return True`, and that is
what lets a telephony carrier fetch `Seminary Announcement.voice_audio` with no
session. Authorisation is delegated wholly to `is_downloadable()`, so a private
file is still refused to Guest — just one layer further in.

**Access logging is not per-request.** Today nginx serves byte ranges via
`X-Accel-Redirect` without ever entering Python, so a video playback produces one
Access Log row. Logging every request here would produce one row per seek, so we
log only the opening request of a playback.
"""

from __future__ import annotations

import mimetypes
import os

import frappe
from frappe import _
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response

from seminary.storage.backend import (
    DOWNLOAD_ENDPOINT,
    get_storage_backend,
    key_from_url,
    url_for_key,
)

#: Extensions Frappe refuses to render inline, because a browser would execute
#: them in the site's origin. Mirrors `response.FORCE_DOWNLOAD_EXTENSIONS`.
FORCE_DOWNLOAD_EXTENSIONS = (".svg", ".html", ".htm", ".xml")

DEFAULT_PRESIGN_TTL = 900

#: How far short of the signature's own lifetime the browser is allowed to cache
#: the redirect. Without a positive gap a cached 302 can outlive the URL it
#: points at, and the next range request after a long pause fails with a 403 the
#: player surfaces as a broken video.
_CACHE_SAFETY_MARGIN = 120


def presign_ttl() -> int:
    return int(frappe.conf.get("storage_presign_ttl") or DEFAULT_PRESIGN_TTL)


@frappe.whitelist(allow_guest=True, methods=["GET", "HEAD"])
def download_file(key: str, fid: str | None = None, download: int | str = 0):
    """Resolve `key` to a File, check read permission, redirect to a presigned URL."""
    key = key_from_url(url_for_key(key))
    if not key:
        raise NotFound

    file = _resolve_readable_file(key, fid)
    if not file:
        # Same response for "no such file" and "not allowed to see it", so this
        # endpoint cannot be used to probe which objects exist.
        raise Forbidden(_("You don't have permission to access this file"))

    if _is_initial_request():
        from frappe.core.doctype.access_log.access_log import make_access_log

        make_access_log(
            doctype="File",
            document=file.name,
            file_type=os.path.splitext(file.file_name or "")[-1][1:],
        )

    file_name = file.file_name or os.path.basename(key)
    extension = os.path.splitext(file_name)[1].lower()
    as_attachment = (
        bool(frappe.utils.cint(download)) or extension in FORCE_DOWNLOAD_EXTENSIONS
    )

    ttl = presign_ttl()
    url = get_storage_backend().presigned_get(
        key,
        ttl=ttl,
        file_name=file_name,
        content_type=mimetypes.guess_type(file_name)[0],
        as_attachment=as_attachment,
    )

    response = Response(status=302)
    response.headers["Location"] = url
    # Let the browser reuse one redirect for every range request of a playback.
    # Without this a scrub costs a worker round-trip per seek.
    response.headers["Cache-Control"] = (
        f"private, max-age={max(ttl - _CACHE_SAFETY_MARGIN, 0)}"
    )
    response.headers["Vary"] = "Cookie"
    return response


def _resolve_readable_file(key: str, fid: str | None):
    """Find a File row for `key` that the current user may read.

    Uses `find_file_by_url`, the same helper the upstream private-file route
    uses. It walks *every* row sharing the URL and returns the first that passes
    `is_downloadable()` — which is exactly the semantics we need, because content
    -hash keying means several File rows (`create_attachment_copy`, the
    per-recipient copies in `comms.py`) legitimately share one blob and one URL.

    Resolving through a File row is also what keeps this endpoint from being an
    open proxy onto the bucket: a key with no readable row is refused, so a
    client cannot ask us to sign arbitrary objects.
    """
    from frappe.core.doctype.file.utils import find_file_by_url

    return find_file_by_url(url_for_key(key), name=fid)


def _is_initial_request() -> bool:
    """True for a plain request or the opening range of one. See the docstring.

    `frappe.local.request` *raises* AttributeError when unset rather than being
    falsy (`frappe/utils/local.py:28`), so it must be reached with `getattr` —
    this endpoint is callable from a background job or `bench execute`, where
    there is no request at all.
    """
    request = getattr(frappe.local, "request", None)
    range_header = request.headers.get("Range") if request else None
    return not range_header or range_header.replace(" ", "").startswith("bytes=0-")


@frappe.whitelist()
def selftest():
    """Round-trip a small object so misconfiguration surfaces at setup time.

    Without this the first sign that credentials are wrong is a registrar losing
    a 400 MB lecture upload. Run with:

        bench --site <site> execute seminary.storage.api.selftest
    """
    frappe.only_for("System Manager")

    backend = get_storage_backend()
    if not backend.is_configured():
        return {
            "ok": False,
            "backend": type(backend).__name__,
            "detail": "No object storage configured; all files stay on disk.",
        }

    key = f"media/_selftest/{frappe.generate_hash(length=16)}/probe.txt"
    payload = b"seminary storage selftest"
    try:
        backend.put(key, payload, content_type="text/plain")
        roundtripped = backend.read(key)
        if roundtripped != payload:
            return {
                "ok": False,
                "backend": type(backend).__name__,
                "detail": "Object read back did not match what was written.",
            }
        url = backend.presigned_get(key, ttl=60, file_name="probe.txt")
    finally:
        # Best effort: a probe object left behind is harmless, and losing the
        # selftest's actual verdict to a cleanup failure would not be.
        try:
            backend.delete(key)
        except Exception:
            frappe.log_error(
                title="seminary.storage: selftest probe not cleaned up",
                message=f"{key}\n{frappe.get_traceback()}",
            )

    return {
        "ok": True,
        "backend": type(backend).__name__,
        "endpoint": DOWNLOAD_ENDPOINT,
        "presigned_sample": url.split("?")[0] + "?…",
    }
