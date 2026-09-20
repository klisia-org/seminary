# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course folder downloads as cached, content-addressed artifacts (p008 F17a).

`download_folder` used to assemble the zip inside the request, in worker memory:
`copy_into_zip` streamed each *file*, but into an `io.BytesIO()` whose
`getvalue()` then copied the whole archive again. No cap on folder size, entry
count or depth, no rate limit -- and `course_folder.user_may_read` admits a
student to the folders of their own sections, so any enrolled student could ask a
worker to assemble a multi-gigabyte zip in RAM, repeatedly.

**Not fixed with a folder-size cap.** Per-file upload caps (`storage/limits.py`)
already bound the unit; a folder ceiling would only teach instructors to split
folders -- the same bytes in a worse structure, and the worker still builds
whatever the largest folder happens to be. The fix is to stop holding the archive
at all.

## The shape

- **Manifest hash.** One walk of the tree reading no bytes: `(arcname,
  content identity, size)` per entry, sorted, sha256. It moves on add, delete,
  rename, move and replace, so it *is* the cache key.
- **The artifact.** A private File named `<folder>-<hash16>.zip` under
  `Home/Course Folder Archives`, attached to the **Course Folder document**. That
  attachment is the whole authorization story: `hooks.py` registers
  `course_folder.has_permission`, whose docstring names "a File read that
  resolves through its host folder", so reading the archive resolves to
  `user_may_read(course_folder)` -- the same rule that gates the folder itself,
  not a second parallel path.
- **Assembly never holds the archive.** Written to a temporary file, each member
  streamed in by `copy_into_zip`, then either streamed to object storage or moved
  into place on disk. Worker memory is flat whatever the folder holds, and with
  no object store configured this is an ordinary private file -- object storage
  is an optimisation here, never a requirement.
- **Generation is write-side.** Folder mutations enqueue a build. Lesson save is
  deliberately *not* the trigger: files can only be added from inside Edit
  Lesson, but the instructor may navigate away without ever saving, so a
  save-driven build would miss uploads. It is kept as a cheap re-check.
- **Download never builds.** The endpoint hashes, and either hands back the
  artifact's URL or enqueues a build and says "preparing". The build enqueued
  from a reader's miss carries an aggressive per-user cooldown; it exists so a
  student is never blocked waiting on staff, not as a routine path.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import zipfile
from typing import Optional, Set

import frappe
from frappe import _

from seminary.storage.files import copy_into_zip

#: Where generated archives live, mirroring `Home/Course Packs`.
ARCHIVE_FOLDER = "Course Folder Archives"

#: A folder tree deeper than this is a cycle the `visited` set did not catch, or
#: a mistake. Bounded so the recursive walk cannot exhaust the stack.
MAX_TREE_DEPTH = 32

#: How long one manifest hash is considered "already being built", so that a
#: burst of uploads -- or several students clicking at once -- produces one job.
BUILD_LOCK_SECONDS = 15 * 60

#: A reader whose download missed the cache may trigger at most one build per
#: this many seconds. Write-side builds are not subject to it: those callers have
#: already passed a write check on the folder.
READER_BUILD_COOLDOWN_SECONDS = 300

#: Generated artifacts are reproducible, not records (the `cleanup_old_packs`
#: rule). Superseded ones go as soon as they are noticed.
ARCHIVE_RETENTION_DAYS = 30


def _conf(key, default):
    return int(frappe.conf.get(key) or default)


# --- names -------------------------------------------------------------------


def arc_segment(name: str) -> str:
    """One path segment of an arcname, safe for whoever extracts the archive.

    Frappe strips `/` from `File.file_name` but not `\\`, so a file named
    `..\\..\\x.exe` reached the arcname intact. `zipfile.extractall` sanitizes,
    but several Windows extractors treat a backslash as a separator and would
    write outside the destination -- a zip slip we ship to someone else
    (p008 F17d). Separators become underscores, and a segment that is only dots
    cannot climb.
    """
    segment = re.sub(r"[\\/]", "_", (name or "").strip()) or "unnamed"
    if set(segment) <= {"."}:
        segment = "_" * len(segment)
    return segment


def root_name_of(folder_id: str) -> str:
    return arc_segment(frappe.db.get_value("File", folder_id, "file_name") or "folder")


def folder_key(folder_id: str) -> str:
    """A short, stable tag for the folder an archive was built from.

    `attached_to_name` is the *Course Folder*, because that is what makes the
    archive readable by the right people -- but a Course Folder has many
    subfolders and each can be downloaded on its own, so the row alone does not
    say which one an archive covers. Without that, retention cannot tell a
    subfolder's current archive from the root's stale one.
    """
    return hashlib.sha256(folder_id.encode()).hexdigest()[:8]


def archive_file_name(root_name: str, folder_id: str, manifest_hash: str) -> str:
    return f"{root_name}-{folder_key(folder_id)}-{manifest_hash[:16]}.zip"


# --- the manifest ------------------------------------------------------------


def _entries_in(folder_id: str) -> list:
    return frappe.get_all(
        "File",
        filters={"folder": folder_id},
        fields=[
            "name",
            "file_name",
            "is_folder",
            "content_hash",
            "file_size",
            "modified",
        ],
        order_by="is_folder desc, file_name asc",
        ignore_permissions=True,
    )


def _walk(folder_id: str, base_path: str, visited: Set[str], depth: int, out: list):
    if folder_id in visited or depth > MAX_TREE_DEPTH:
        return
    visited.add(folder_id)

    entries = _entries_in(folder_id)
    if not entries and base_path:
        out.append((f"{base_path}/", "", 0))
        return

    for entry in entries:
        path = (
            f"{base_path}/{arc_segment(entry.file_name)}"
            if base_path
            else arc_segment(entry.file_name)
        )
        if entry.is_folder:
            _walk(entry.name, path, visited, depth + 1, out)
            continue
        # `content_hash` is the identity when it is there. When it is not (older
        # rows, some remote files) fall back to size *and* mtime together: size
        # alone would miss a same-size replacement.
        identity = entry.content_hash or f"{entry.file_size or 0}:{entry.modified}"
        out.append((path, identity, int(entry.file_size or 0)))


def has_files(entries: list) -> bool:
    """True when a manifest holds an actual file, not only empty directories.

    `_walk` records an empty subfolder as a `dir/` placeholder, because adding
    one must move the hash -- the archive gains an entry. But a folder whose
    whole tree is empty directories has nothing to download, and counting those
    placeholders as content produced a 126-byte zip that the endpoint happily
    reported as ready (caught on the potestas smoke, not by a unit test).
    """
    return any(not path.endswith("/") for path, _identity, _size in entries)


def folder_manifest(folder_id: str) -> tuple[str, list]:
    """`(hash, entries)` for a folder tree. Reads no file bytes.

    The hash is the cache key, so it must move whenever the archive's bytes
    would: add, delete, rename, move and replace all change an entry tuple.
    """
    out: list = []
    _walk(folder_id, root_name_of(folder_id), set(), 0, out)
    out.sort()
    digest = hashlib.sha256()
    for path, identity, size in out:
        digest.update(f"{path}\0{identity}\0{size}\n".encode())
    return digest.hexdigest(), out


# --- assembly ----------------------------------------------------------------


def _add_folder_to_zip(
    archive: zipfile.ZipFile,
    folder_id: str,
    base_path: str,
    visited: Set[str],
    depth: int = 0,
) -> None:
    """Recursively write the contents of a folder into the zip archive."""
    if folder_id in visited or depth > MAX_TREE_DEPTH:
        return
    visited.add(folder_id)

    entries = _entries_in(folder_id)

    if not entries and base_path:
        # Preserve empty folders in the archive.
        archive.writestr(f"{base_path}/", b"")
        return

    for entry in entries:
        segment = arc_segment(entry.file_name)
        entry_path = f"{base_path}/{segment}" if base_path else segment
        if entry.is_folder:
            _add_folder_to_zip(archive, entry.name, entry_path, visited, depth + 1)
            continue
        # Streamed rather than read whole: a course folder of lecture video would
        # otherwise sit in worker memory in its entirety. Works the same whether
        # the file is on disk or offloaded to object storage (privatedocs/p004).
        copy_into_zip(archive, entry.name, entry_path)


def _archive_folder() -> str:
    """`Home/Course Folder Archives`, created on first use."""
    name = f"Home/{ARCHIVE_FOLDER}"
    if frappe.db.exists("File", name):
        return name
    folder = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": ARCHIVE_FOLDER,
            "is_folder": 1,
            "folder": "Home",
        }
    )
    folder.flags.ignore_permissions = True
    folder.insert(ignore_if_duplicate=True)
    return folder.name


def find_archive(course_folder: str, file_name: str) -> Optional[str]:
    """The File docname of an existing artifact for this manifest, or None."""
    return frappe.db.get_value(
        "File",
        {
            "attached_to_doctype": "Course Folder",
            "attached_to_name": course_folder,
            "file_name": file_name,
        },
        "name",
    )


def _store(
    tmp_path: str, file_name: str, size: int, content_hash: str, course_folder: str
):
    """Create the artifact's File row from a finished temporary file.

    Neither branch ever holds the archive as a `bytes`: with object storage it is
    streamed to the store, and without it the temporary file is *moved* into the
    private files directory and the row is created pointing at it. Passing
    `content=` instead would reintroduce exactly the memory profile this module
    exists to remove.
    """
    from seminary.storage import get_storage_backend
    from seminary.storage.backend import object_key, url_for_key

    backend = get_storage_backend()

    if backend.is_configured():
        key = object_key(content_hash)
        with open(tmp_path, "rb") as handle:
            backend.put_fileobj(key, handle, content_type="application/zip")
        file_url = url_for_key(key)
    else:
        from frappe.core.doctype.file.utils import get_file_name

        disk_name = file_name
        target = frappe.get_site_path("private", "files", disk_name)
        if os.path.exists(target):
            disk_name = get_file_name(file_name, content_hash[-6:])
            target = frappe.get_site_path("private", "files", disk_name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(tmp_path, target)
        file_url = f"/private/files/{disk_name}"

    doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "file_url": file_url,
            "is_private": 1,
            "file_size": size,
            "content_hash": content_hash,
            "folder": _archive_folder(),
            # The attachment *is* the permission rule -- see the module
            # docstring. Never attach this to the folder's File row instead:
            # that resolves through File's own owner branch, not through
            # `user_may_read`, and would be a second authorization path.
            "attached_to_doctype": "Course Folder",
            "attached_to_name": course_folder,
        }
    )
    doc.flags.ignore_permissions = True
    # Frappe's `File.before_insert` treats a *local* `file_url` as something it
    # must still ingest: it calls `save_file(content=self.get_content())`, which
    # reads the file back through a text-decoding `get_content()` and rewrites it
    # under a `content_hash[-6:]` name, orphaning ours. On a zip that produced a
    # file with a garbage central directory. `copy_from_existing_file` is the
    # flag frappe provides for precisely this -- "the blob is already at
    # `file_url`" -- and it keeps the rest of the insert lifecycle. The object
    # storage branch never hit this because `is_remote_file` short-circuits
    # first, which is why it has to be said here and not in both.
    doc.flags.copy_from_existing_file = True
    doc.insert()
    return doc


def build_archive(folder_id: str, course_folder: str) -> Optional[str]:
    """Assemble the archive for `folder_id` and return its File docname.

    Runs no permission check of its own: every caller gates before enqueueing,
    and the artifact's own readability comes from what it is attached to. Safe to
    run twice -- a manifest that already has an artifact returns it untouched.
    """
    if not frappe.db.exists("File", folder_id):
        return None

    manifest_hash, entries = folder_manifest(folder_id)
    if not has_files(entries):
        return None

    file_name = archive_file_name(root_name_of(folder_id), folder_id, manifest_hash)
    existing = find_archive(course_folder, file_name)
    if existing:
        return existing

    handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp_path = handle.name
    try:
        with handle:
            with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
                _add_folder_to_zip(archive, folder_id, root_name_of(folder_id), set())

        size = os.path.getsize(tmp_path)
        # Not a security hash: MD5 is what frappe's own `get_content_hash` uses,
        # and the delete refcount compares against that value.
        digest = hashlib.md5(usedforsecurity=False)
        with open(tmp_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)

        doc = _store(tmp_path, file_name, size, digest.hexdigest(), course_folder)
        _retire_superseded(course_folder, folder_id, keep=doc.name)
        return doc.name
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --- scheduling --------------------------------------------------------------


def _lock_key(course_folder: str, manifest_hash: str) -> str:
    return f"seminary_folder_archive:{course_folder}:{manifest_hash[:16]}"


def enqueue_archive_build(
    folder_id: str, course_folder: str | None, reader_triggered: bool = False
) -> str:
    """Queue a build, unless one for this exact manifest is already in flight.

    Returns "queued", "in-flight", "rate-limited" or "skipped" -- callers on the
    write side ignore it; the download endpoint reports it.
    """
    if not course_folder or not folder_id:
        return "skipped"

    manifest_hash, entries = folder_manifest(folder_id)
    if not has_files(entries):
        return "skipped"

    name = archive_file_name(root_name_of(folder_id), folder_id, manifest_hash)
    if find_archive(course_folder, name):
        return "skipped"

    if reader_triggered:
        cooldown = _conf("folder_archive_build_cooldown", READER_BUILD_COOLDOWN_SECONDS)
        user_key = f"seminary_folder_archive_user:{frappe.session.user}"
        if frappe.cache.get_value(user_key):
            return "rate-limited"
        frappe.cache.set_value(user_key, 1, expires_in_sec=cooldown)

    lock = _lock_key(course_folder, manifest_hash)
    if frappe.cache.get_value(lock):
        return "in-flight"
    frappe.cache.set_value(
        lock, 1, expires_in_sec=_conf("folder_archive_lock_seconds", BUILD_LOCK_SECONDS)
    )

    frappe.enqueue(
        "seminary.api.folder_archive.run_build",
        queue="long",
        timeout=3600,
        folder_id=folder_id,
        course_folder=course_folder,
        lock=lock,
    )
    return "queued"


def run_build(folder_id: str, course_folder: str, lock: str | None = None):
    """Background entry point. Releases the lock whatever happens, so a failed
    build does not wedge the folder for the lock's whole lifetime."""
    try:
        build_archive(folder_id, course_folder)
    finally:
        if lock:
            frappe.cache.delete_value(lock)


def refresh(folder_id: str | None, course_folder: str | None):
    """Write-side trigger. Called after any mutation of a folder's contents.

    Deliberately tolerant: a failure here must never take down the upload or
    delete that prompted it. The reader's fallback covers a missed refresh.
    """
    if not folder_id or not course_folder:
        return
    try:
        enqueue_archive_build(folder_id, course_folder)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), "folder_archive: could not queue a rebuild"
        )


# --- retention ---------------------------------------------------------------


def _retire_superseded(course_folder: str, folder_id: str, keep: str):
    """Delete this folder's older archives as soon as a newer one exists.

    Matched on the folder tag rather than the whole name, so only archives of
    *this* folder are touched -- a sibling subfolder's current archive is not a
    stale copy of ours.
    """
    tag = f"-{folder_key(folder_id)}-"
    for row in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Course Folder",
            "attached_to_name": course_folder,
            "file_name": ["like", f"%{tag}%"],
            "name": ["!=", keep],
        },
        pluck="name",
    ):
        _drop(row)


def _drop(name: str):
    try:
        frappe.delete_doc("File", name, ignore_permissions=True, force=True)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"folder_archive: could not delete {name}"
        )


def cleanup_stale_archives():
    """Daily sweep: drop archives past the retention window.

    Superseded archives are already retired at build time (`_retire_superseded`),
    so this only has to expire the ones nobody has rebuilt over -- a folder that
    stopped changing, or a Course Folder that is gone. Generated archives are
    reproducible artifacts, not records, which is the rule `cleanup_old_packs`
    follows; deleting the File row is enough, because the storage delete hook
    removes the object once no row references that content.
    """
    days = int(
        frappe.conf.get("folder_archive_retention_days") or ARCHIVE_RETENTION_DAYS
    )
    if not days:
        return

    cutoff = frappe.utils.add_days(frappe.utils.nowdate(), -days)
    for row in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Course Folder",
            "folder": f"Home/{ARCHIVE_FOLDER}",
            "creation": ["<", cutoff],
        },
        pluck="name",
    ):
        _drop(row)
