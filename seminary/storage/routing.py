# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""The single predicate deciding whether a file is offloaded to object storage.

## Why size and extension, and not "which doctype is this attached to?"

Frappe calls the `write_file` hook with two incompatible signatures. The modern
form (`file.py:812`) hands over the whole `File` doc; the legacy form
(`frappe/utils/file_manager.py:164`) hands over only
`(fname, content, content_type, is_private)` — no `attached_to_doctype`, no
folder, no doc, because the row does not exist yet.

Both live seminary paths that carry the most bytes use the *legacy* form:
`seminary/api/folder_upload.py` (Course Folder instructor materials) and
`seminary/seminary/course_pack/import_.py`. So a context-aware predicate
("is this a Course Folder file?") would silently fail exactly where it matters
most, and route those files to disk while appearing to work everywhere else.

Size and extension are available in both forms. They are also the honest
criteria: what makes a file worth offloading is that it is big and that it is
media, not which doctype happens to own it.

## Why the deny list beats the size threshold

Images are excluded *regardless of size*. This is what keeps the rest of the
system unaware that any of this exists: `comms.py` rewrites `/private/files/`
URLs inside stored HTML when publishing embedded images for outbound email,
`File.make_thumbnail` writes straight to the site's public directory, and the
desk renders avatars by path. None of those understand a remote URL. Images are
also cheap — they are not where the egress bill lives — so excluding them costs
nothing and removes a whole class of breakage.

Unknown extensions are denied by default, matching the allow-list discipline
`course_pack/constants.py` already uses (ADR 041).
"""

from __future__ import annotations

import os

import frappe

from seminary.storage.backend import get_storage_backend

#: Large, egress-heavy, and read as opaque bytes by everything that touches them.
OFFLOAD_EXTENSIONS = frozenset(
    {
        # video
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".mkv",
        # audio (includes Seminary Announcement voice_audio)
        ".mp3",
        ".m4a",
        ".wav",
        ".ogg",
        # instructor materials and submissions
        ".pptx",
        ".ppt",
        ".pdf",
        ".docx",
        ".doc",
        ".xlsx",
        # SCORM packages and course packs — these need StorageBackend.materialize()
        ".zip",
    }
)

#: Never offloaded at any size. See the module docstring.
NEVER_OFFLOAD_EXTENSIONS = frozenset(
    {
        # images: rewritten by comms.py, thumbnailed, rendered by path
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".bmp",
        # text formats: small, and read as content by importers
        ".csv",
        ".txt",
        ".json",
        ".xml",
        ".html",
        ".htm",
        ".md",
    }
)

#: Below this, offloading costs a redirect round-trip and saves nothing.
DEFAULT_MIN_BYTES = 8 * 1024 * 1024


def min_offload_bytes() -> int:
    return int(frappe.conf.get("storage_min_bytes") or DEFAULT_MIN_BYTES)


def _offload_unknown_types() -> bool:
    return bool(frappe.conf.get("storage_offload_unknown_types"))


def client_rule() -> dict:
    """The offload rule, serialised for the browser.

    The SPA has to know whether a given file will go direct to object storage,
    because that decides which ceiling applies to it — the large direct one or
    the much smaller worker one. Getting that wrong means either refusing an
    upload that would have worked, or accepting one the server will reject after
    the user has waited for it.

    Published from these same constants rather than restated in JavaScript, so
    the rule cannot drift between the two.
    """
    return {
        "min_bytes": min_offload_bytes(),
        "offload_extensions": sorted(OFFLOAD_EXTENSIONS),
        "never_offload_extensions": sorted(NEVER_OFFLOAD_EXTENSIONS),
        "offload_unknown_types": _offload_unknown_types(),
    }


def should_offload(file_name: str | None, size: int | None, is_private=None) -> bool:
    """True when this file should live in object storage rather than on disk.

    `is_private` is accepted because both hook signatures carry it and a future
    policy may need it; it is deliberately not consulted today — access control
    is enforced at read time by the download endpoint, so where the bytes live is
    independent of who may see them.
    """
    # The single kill switch. A site with no storage backend behaves exactly as
    # it did before this module existed.
    if not get_storage_backend().is_configured():
        return False

    if not size or int(size) < min_offload_bytes():
        return False

    extension = os.path.splitext(file_name or "")[1].lower()

    if extension in NEVER_OFFLOAD_EXTENSIONS:
        return False

    if extension in OFFLOAD_EXTENSIONS:
        return True

    return _offload_unknown_types()
