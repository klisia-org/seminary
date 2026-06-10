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

    The general cap is Frappe's own `max_file_size` (System Settings → site
    config → 25 MB default), which is already enforced server-side for every
    upload. Recordings carry the tighter app-level sub-cap on top.
    """
    from frappe.core.api.file import get_max_file_size

    max_bytes = get_max_file_size()
    return {
        "max_upload_bytes": max_bytes,
        "max_upload_mb": round(max_bytes / (1024 * 1024)),
        "max_recording_mb": MAX_RECORDING_MB,
    }


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
