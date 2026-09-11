"""Server-side guard rails for in-platform lesson video recordings.

The lesson editor's "Record Video" block (frontend RecorderPlugin) caps clip
length in the browser, but that limit can be bypassed by a crafted upload. This
hook enforces a hard size ceiling on the server for recorder output so a long or
tampered recording cannot bloat storage / egress.

The check is deliberately scoped to recorder files (identified by the
`lesson-recording-` filename prefix the recorder assigns) so ordinary uploads —
PDFs, images, instructor-supplied videos via the Upload block — are untouched and
remain governed only by Frappe's global `max_file_size`.
"""

import frappe
from frappe import _

# Keep this aligned with the recorder's client-side cap (RecorderPlugin.vue
# `maxSeconds` + `videoBitsPerSecond`). At ~1.6 Mbps a 3-minute clip is ~36 MB;
# the ceiling leaves headroom for VBR spikes while still blocking abuse.
RECORDING_FILENAME_PREFIX = "lesson-recording-"
MAX_RECORDING_MB = 75
MAX_RECORDING_BYTES = MAX_RECORDING_MB * 1024 * 1024


@frappe.whitelist()
def get_upload_limits():
    """Expose upload size limits to the frontend so it can validate files before
    uploading and tell the user the maximum allowed size.

    The values are **per user**: the general cap is the tighter of Frappe's own
    `max_file_size` and whatever per-role cap Seminary Settings → Upload Limits
    gives this user (privatedocs/p004). Recordings carry a tighter app-level
    sub-cap on top of that.

    The keys are unchanged from ADR 040 on purpose. `uploadLimits` +
    `validateFileSize` in `frontend/src/utils/index.js` are already wired into
    every `FileUploader`, so per-audience limits reach the whole SPA — including
    each "Max N MB" hint — without touching a single component.
    """
    from seminary.storage import get_storage_backend
    from seminary.storage.limits import MB, direct_limit_for_user, effective_limit

    max_bytes, _source = effective_limit()
    limits = {
        "max_upload_bytes": max_bytes,
        "max_upload_mb": round(max_bytes / MB),
        # Never advertise a recording cap above the general one, or the recorder
        # would offer a length the upload path then refuses.
        "max_recording_mb": min(MAX_RECORDING_MB, round(max_bytes / MB)),
    }

    # With object storage the browser can upload straight to it, which escapes both
    # Frappe's max_file_size and nginx's body cap — so the ceiling there is much
    # higher and is a separate number. Absent, the SPA uses the general cap alone.
    if get_storage_backend().is_configured():
        from seminary.storage.routing import client_rule

        direct_bytes = direct_limit_for_user()
        limits["max_direct_upload_bytes"] = direct_bytes
        limits["max_direct_upload_mb"] = round(direct_bytes / MB)
        # Which ceiling applies depends on whether *this* file goes direct, so the
        # SPA needs the routing rule to pick the right one. Published from the
        # routing constants rather than restated in JS, so it cannot drift.
        limits["direct_rule"] = client_rule()

    return limits


def enforce_recording_limits(doc, method=None):
    """Reject oversized in-platform recordings (File `validate` hook)."""
    if getattr(doc, "is_folder", 0):
        return

    file_name = doc.file_name or ""
    if not file_name.startswith(RECORDING_FILENAME_PREFIX):
        return

    # `save_file()` runs in before_insert and sets file_size; fall back to the
    # raw content length just in case it is not yet populated.
    size = doc.file_size or len(doc.get_content() or b"")
    if size > MAX_RECORDING_BYTES:
        frappe.throw(
            _(
                "This recording is too large ({0} MB). In-platform recordings are "
                "limited to {1} MB — please record a shorter clip."
            ).format(round(size / (1024 * 1024)), MAX_RECORDING_MB),
            title=_("Recording too large"),
        )
