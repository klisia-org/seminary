# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Bounds, member-path rules and content types for a SCORM package archive.

privatedocs p009 §2.4. One copy, shared by the two places that look at a
package: `seminary.seminary.api._check_scorm_package`, which refuses a bad zip
at the moment a chapter accepts it, and `seminary.scorm.explode`, which re-runs
the same checks before it writes a byte. p008 F17e put these caps in `api.py`
when nothing opened a package; the explode job is the thing that opens it, and
two copies of a bounds check are two copies that drift.

Everything here is computed from the zip's **central directory**, so it costs no
decompression: a member that lies about its size cannot exceed the budget
anyway, because reading it is bounded separately and fails its CRC.

The caps are the Course Pack caps in shape and in reasoning
(`course_pack/constants.py`): a different artifact, an identical attack.
"""

from __future__ import annotations

import posixpath
import stat
import unicodedata

import frappe

#: Each raisable in site_config.json.
MAX_ENTRIES = 20000  # scorm_max_entries
MAX_UNCOMPRESSED_BYTES = 4 * 1024**3  # scorm_max_uncompressed_bytes
MAX_MEMBER_BYTES = 1024**3  # scorm_max_member_bytes
MAX_MANIFEST_BYTES = 8 * 1024**2  # scorm_max_manifest_bytes

#: A ratio check only means something on a payload big enough to hurt: a package
#: that is mostly HTML compresses very well and is no bomb.
RATIO_FLOOR_BYTES = 100 * 1024**2
MAX_RATIO = 200

#: A member served from our own origin rather than redirected to the object
#: store is streamed through a worker, so it carries a much tighter ceiling than
#: the general member cap -- and it is enforced here, at explode time, so the
#: instructor hears about it instead of the student (p009 §2.6).
MAX_PROXIED_MEMBER_BYTES = 16 * 1024**2  # scorm_proxy_member_max_bytes

MANIFEST_NAME = "imsmanifest.xml"

#: Path segments a package has no business containing. Junk from desktop zip
#: tools, skipped rather than refused: it is never referenced, and refusing it
#: would fail packages that are otherwise perfectly good.
JUNK_SEGMENTS = ("__MACOSX", ".DS_Store", "Thumbs.db")

#: The longest member path we will store. Frappe caps a Data column at 1000, and
#: `SCORM Package Item.href` is such a column -- so a path that validates here
#: can always be recorded there.
MAX_PATH_BYTES = 1000
MAX_SEGMENT_BYTES = 255


class PackageError(ValueError):
    """The archive is not a package we will accept. Safe to show to staff."""


def cap(key: str, default: int) -> int:
    return int(frappe.conf.get(key) or default)


# ------------------------------------------------------------------- bounds


def check_bounds(zf, compressed_size: int) -> None:
    """Refuse a bomb, an over-large package or a non-package, before any read."""
    infos = zf.infolist()

    if len(infos) > cap("scorm_max_entries", MAX_ENTRIES):
        raise PackageError(frappe._("This SCORM package has too many files."))

    total = sum(i.file_size for i in infos)
    if total > cap("scorm_max_uncompressed_bytes", MAX_UNCOMPRESSED_BYTES):
        raise PackageError(frappe._("This SCORM package is too large once unpacked."))

    member_cap = cap("scorm_max_member_bytes", MAX_MEMBER_BYTES)
    if any(i.file_size > member_cap for i in infos):
        raise PackageError(
            frappe._("This SCORM package contains a file that is too large.")
        )

    if total > RATIO_FLOOR_BYTES and compressed_size:
        if total / compressed_size > MAX_RATIO:
            raise PackageError(
                frappe._("This file does not look like a SCORM package.")
            )

    manifest = find_manifest(zf.namelist())
    if manifest is None:
        raise PackageError(frappe._("This SCORM package has no imsmanifest.xml."))

    if zf.getinfo(manifest).file_size > cap(
        "scorm_max_manifest_bytes", MAX_MANIFEST_BYTES
    ):
        raise PackageError(frappe._("This SCORM package's manifest is too large."))


def find_manifest(names) -> str | None:
    """The shallowest `imsmanifest.xml`, which defines the package root.

    The spec puts it at the archive root; zipping the containing folder is a
    common enough mistake that a nested one is accepted, and then everything the
    manifest says is relative to *its* directory -- which is why the root has to
    be established before any member path is recorded.
    """
    candidates = [
        n
        for n in names
        if n.replace("\\", "/").rsplit("/", 1)[-1].lower() == MANIFEST_NAME
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda n: (n.count("/"), len(n)))


def package_root(manifest_name: str) -> str:
    root = posixpath.dirname(manifest_name.replace("\\", "/"))
    return f"{root}/" if root else ""


# -------------------------------------------------------------- member paths


def is_symlink(info) -> bool:
    """`zipfile` stores symlinks happily; nothing downstream should see one."""
    return stat.S_ISLNK(info.external_attr >> 16)


def normalise_member_path(raw: str) -> str:
    """Normalise a zip member name, then validate it. Never repair it.

    Normalisation is the part that is safe to do: backslashes become slashes,
    repeated slashes collapse, and `.` segments drop. None of those turns a
    dangerous path into a safe one -- they only spell the same path one way.

    Validation refuses; it does not fix. A `..` segment is **rejected**, not
    resolved away, because a package that needs its paths repaired is a package
    we do not understand.

    Note what this is *not* load-bearing for. Delivery never resolves a client
    path against anything: it looks the path up in the inventory these rules
    produced, and a miss is a 404. Traversal is closed by that lookup, which is
    exactly why it is safe to be strict here and fail an odd-but-harmless
    package rather than accommodate it.
    """
    path = (raw or "").replace("\\", "/")

    if not path or path.endswith("/"):
        raise PackageError(frappe._("Directory entry"))  # caller skips these

    if "\x00" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise PackageError(
            frappe._("This SCORM package contains a file name with control characters.")
        )

    if path.startswith("/") or (len(path) > 1 and path[1] == ":" and path[0].isalpha()):
        raise PackageError(
            frappe._("This SCORM package contains an absolute file path.")
        )

    segments = [s for s in path.split("/") if s not in ("", ".")]
    if not segments:
        raise PackageError(frappe._("This SCORM package contains an empty file name."))

    for segment in segments:
        if segment == "..":
            raise PackageError(
                frappe._(
                    "This SCORM package contains a file path that climbs out of it."
                )
            )
        if segment != segment.rstrip(". "):
            # Windows silently trims these, so `a.` and `a` become the same file
            # on extraction -- a collision the archive does not admit to.
            raise PackageError(
                frappe._(
                    "This SCORM package contains a file name ending in a dot or space."
                )
            )
        if len(segment.encode("utf-8")) > MAX_SEGMENT_BYTES:
            raise PackageError(
                frappe._("This SCORM package contains a file name that is too long.")
            )

    normalised = "/".join(segments)
    if len(normalised.encode("utf-8")) > MAX_PATH_BYTES:
        raise PackageError(
            frappe._("This SCORM package contains a file path that is too long.")
        )
    return normalised


def collision_keys(path: str) -> tuple[str, str]:
    """The two forms a second member must not already have claimed.

    Two members differing only in case, or only in Unicode normal form, mean one
    of them is unreachable -- and *which* one depends on the filesystem, the
    object store and the browser. Refuse the package rather than pick.
    """
    return path.lower(), unicodedata.normalize("NFC", path)


def is_junk(path: str) -> bool:
    return any(segment in JUNK_SEGMENTS for segment in path.split("/"))


# ------------------------------------------------------------ content types


#: Explicit, not `mimetypes.guess_type`. That helper reads the host's
#: `/etc/mime.types`, so the same package would be typed differently on two
#: servers -- and the type decides whether a member is proxied from our origin
#: or redirected to the object store (§2.6). Deterministic beats complete.
#:
#: Nothing is **refused** for its type: real courseware carries every format
#: there is, and a type allow-list would reject legitimate packages to buy
#: protection the origin isolation already provides. An unknown extension is
#: served as `application/octet-stream` with `nosniff`, which on an isolated
#: origin is inert.
CONTENT_TYPES = {
    # documents and code -- these can carry relative references, so they are the
    # ones delivery must serve from its own origin
    "html": "text/html; charset=utf-8",
    "htm": "text/html; charset=utf-8",
    "xhtml": "application/xhtml+xml; charset=utf-8",
    "xml": "text/xml; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "mjs": "text/javascript; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "svg": "image/svg+xml",
    "txt": "text/plain; charset=utf-8",
    "vtt": "text/vtt; charset=utf-8",
    "srt": "application/x-subrip",
    # images
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
    "bmp": "image/bmp",
    "ico": "image/x-icon",
    # audio and video
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "wav": "audio/wav",
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    # fonts
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "otf": "font/otf",
    "eot": "application/vnd.ms-fontobject",
    # documents a package may link to
    "pdf": "application/pdf",
    "zip": "application/zip",
}

DEFAULT_CONTENT_TYPE = "application/octet-stream"

#: Served **through** the delivery origin rather than redirected to a presigned
#: URL. The rule is "can this contain a relative reference?", not "is it small?":
#: once a document is fetched via a redirect, the browser's base URL moves to the
#: object store and every relative reference in it resolves there, unsigned
#: (§2.6). Size is handled separately by MAX_PROXIED_MEMBER_BYTES.
#: Served *through* the delivery origin rather than redirected to the object
#: store. Two reasons, and the second was learned the hard way:
#:
#: 1. **It can carry a relative reference.** Once a document is fetched via a
#:    302 to a presigned URL its base URL is the object store, and every
#:    `assets/main.js` in it resolves there unsigned (p009 §1.2). Anything that
#:    can address other members has to stay on this origin.
#: 2. **Fonts need CORS, and a presigned URL has none.** A cross-origin
#:    `@font-face` is a CORS-checked fetch, so a font redirected to the object
#:    store is refused unless the bucket carries a CORS policy naming this
#:    delivery host -- infrastructure per deployment, which is exactly what
#:    §3 refused to depend on. Fonts are tens of kilobytes and there are a
#:    handful per package, so proxying them costs nothing the redirect was
#:    protecting: §2.6 redirects to keep *lecture video* off the worker pool.
PROXIED_EXTENSIONS = frozenset(
    {
        "html",
        "htm",
        "xhtml",
        "xml",
        "css",
        "js",
        "mjs",
        "json",
        "svg",
        "txt",
        "vtt",
        "srt",
        # Fonts: see (2) above. Not because they can reference anything.
        "woff",
        "woff2",
        "ttf",
        "otf",
        "eot",
    }
)


def extension_of(path: str) -> str:
    return (
        path.rsplit("/", 1)[-1].rsplit(".", 1)[-1].lower()
        if "." in path.rsplit("/", 1)[-1]
        else ""
    )


def content_type_for(path: str) -> str:
    return CONTENT_TYPES.get(extension_of(path), DEFAULT_CONTENT_TYPE)


def is_proxied(path: str) -> bool:
    return extension_of(path) in PROXIED_EXTENSIONS
