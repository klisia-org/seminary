"""Course Folder file API (p006 F2, ADR §2.2c).

A folder is addressed in exactly two ways:

* `course_folder` — a **Course Folder docname**. The root File folder is its
  `file_reference`, after `resolve_latest` so an embed of a superseded School
  folder lands on the newest one.
* `folder_id` — a **File docname**, for navigating below the root.

There is deliberately no name-based lookup. A bare foldername resolved
site-wide was the p005 A01-5 hole, and with scopes "Readings" can legitimately
exist once per professor and once for the course.

Authorisation is one function, `_ensure_folder_permission`: walk up to the
owning Course Folder and apply `course_folder.user_may_read` / `user_may_write`;
a File folder that is not under any Course Folder is reachable only by its
owner or a System Manager. Not-found and not-permitted are the same message,
"Folder not available", so the API does not confirm which folders exist.

Listing and streaming keep `ignore_permissions=True` — children are private and
owned by whoever uploaded them — but only after the root check passed.

Every mutation writes a `Course Folder Activity` row: this log is the
term-to-term record of what changed in a folder.
"""

from __future__ import annotations

import io
import zipfile
from typing import Optional, Set

import frappe
from frappe import _

from seminary.seminary.doctype.course_folder.course_folder import (
    log_activity,
    resolve_latest,
    user_may_read,
    user_may_write,
)
from seminary.storage.backend import normalize_file_url
from seminary.storage.files import copy_into_zip

NOT_AVAILABLE = "Folder not available"


def _not_available():
    frappe.throw(_(NOT_AVAILABLE), frappe.PermissionError)


def _resolve_folder(
    course_folder: str | None = None,
    folder_id: str | None = None,
    **_ignored,
) -> str:
    """Return the File docname for a Course Folder root or a File subfolder.

    A caller that only knows a foldername gets "Folder not available": names
    are not identifiers here.
    """
    if folder_id:
        if frappe.db.exists("File", folder_id):
            return folder_id
        _not_available()

    if course_folder:
        latest = resolve_latest(course_folder)
        root = frappe.db.get_value("Course Folder", latest, "file_reference")
        if root and frappe.db.exists("File", root):
            return root
        _not_available()

    _not_available()


def _get_course_folder_context(folder_id: str) -> Optional[dict[str, str]]:
    """Return the Course Folder (and Course) owning the provided File folder."""
    visited: Set[str] = set()
    current = folder_id
    while current and current not in visited:
        course_folder = frappe.db.get_value(
            "Course Folder",
            {"file_reference": current},
            ["name", "course", "scope"],
            as_dict=True,
        )
        if course_folder:
            return {
                "course_folder": course_folder.name,
                "course": course_folder.course,
                "scope": course_folder.scope,
            }
        visited.add(current)
        parent = frappe.db.get_value("File", current, "folder")
        if not parent or parent in visited:
            break
        current = parent
    return None


def _link_file_to_course_folder(file_name: str, course_folder_name: str) -> None:
    if not file_name or not course_folder_name:
        return
    current = frappe.db.get_value(
        "File",
        file_name,
        ["attached_to_doctype", "attached_to_name"],
        as_dict=True,
    )
    if (
        current
        and current.attached_to_doctype == "Course Folder"
        and current.attached_to_name == course_folder_name
    ):
        return
    frappe.db.set_value(
        "File",
        file_name,
        "attached_to_doctype",
        "Course Folder",
        update_modified=False,
    )
    frappe.db.set_value(
        "File",
        file_name,
        "attached_to_name",
        course_folder_name,
        update_modified=False,
    )


def _ensure_folder_permission(folder_id: str, perm: str = "read") -> Optional[dict]:
    """Authorise `perm` on a File folder; returns the Course Folder context.

    Under a Course Folder the scope rule decides, nothing else. Outside one
    (an instructor's personal folder, `Home`, `Home/Attachments`) only the
    File row's owner or a System Manager gets through — the non-private
    `File.has_permission("read")` shortcut that opened `Home` is gone.
    """
    row = frappe.db.get_value(
        "File", folder_id, ["name", "owner", "is_folder"], as_dict=True
    )
    if not row:
        _not_available()

    context = _get_course_folder_context(row.name)
    if context:
        check = user_may_read if perm == "read" else user_may_write
        if check(context["course_folder"]):
            return context
        _not_available()

    user = frappe.session.user
    if user == "Administrator" or row.owner == user:
        return None
    if "System Manager" in frappe.get_roles(user):
        return None
    _not_available()


def _log(context: Optional[dict], action: str, file_name: str | None, section):
    if not context:
        return
    section = section or frappe.form_dict.get("course_schedule")
    log_activity(context["course_folder"], action, file_name=file_name, section=section)


def _store_file(folder: str, file_name: str, content: bytes, context) -> dict:
    """Write one uploaded file into `folder` as a File **document**.

    Deliberately not `frappe.utils.file_manager.save_file`. Frappe ships two
    unrelated size ceilings and that legacy helper reads the wrong one: its
    `check_max_file_size` consults `conf.max_file_size` alone and falls back to a
    hardcoded 10 MB, ignoring System Settings → Max File Size entirely. The
    document path runs `File.check_max_file_size` instead, which honours the Desk
    setting — so an administrator can raise the cap from the UI, and the
    per-audience limits in `seminary/storage/limits.py` (which hang off the File
    `validate` hook, after the legacy helper would already have thrown) get the
    final say.

    The document path also registers rollback compensation for the stored bytes
    (`frappe/core/doctype/file/file.py:135`), which the legacy path does not.

    Permission is the caller's `_ensure_folder_permission(folder, "write")`; the
    insert itself ignores permissions, exactly as the legacy helper did, so an
    instructor without a File-level role permission is unaffected by the switch.
    """
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "content": content,
            "folder": folder,
            "is_private": 1,
        }
    ).insert(ignore_permissions=True)

    if context:
        _link_file_to_course_folder(file_doc.name, context["course_folder"])

    return {
        "name": file_doc.name,
        "file_name": file_doc.file_name,
        "file_url": file_doc.file_url,
        "is_private": file_doc.is_private,
    }


@frappe.whitelist()
def upload_to_folder(**kwargs):
    """Store one uploaded file in a course folder.

    Reached as the `method=` callback of Frappe's own `/api/method/upload_file`
    (`frappe/handler.py:200`) rather than being posted to directly, and that
    indirection is load-bearing. The ceiling on the *request body* is chosen in
    `frappe/app.py:198` from the URL path, before any app code runs: only a path
    beginning `/api/method/upload_file` gets the ceiling that honours System
    Settings. Every other endpoint — including this app's own — gets
    `conf.max_file_size` or a hardcoded 25 MB, which no Desk setting can raise and
    no handler can override, since `make_form_dict` has already read the body by
    the time the handler is called.

    So posting through Frappe's endpoint is what makes Max File Size mean
    something for instructor materials.

    One constraint comes with it: `upload_file` applies an allow-list of mimetypes
    (`frappe/handler.py:28`) to any user *without desk access*, and `.pptx`,
    `.zip`, `.webm` and `.mp3` are not on it. Every role that can write to a course
    folder today — Instructor, Program Chair, Registrar, Seminary Manager — has
    desk access, so the branch never runs. Clearing `desk_access` on one of them
    would start rejecting PowerPoints with a message about JPGs; that is the thing
    to remember if this ever reports a baffling file-type error.

    Request fields: `folder_id` (File docname of the target folder) or
    `course_folder` (Course Folder docname, for its root); optional
    `course_schedule` — the section the lesson was open in, for the activity log.
    """
    folder = _resolve_folder(
        course_folder=frappe.form_dict.get("course_folder"),
        folder_id=frappe.form_dict.get("folder_id"),
    )
    context = _ensure_folder_permission(folder, perm="write")

    content = frappe.local.uploaded_file
    file_name = frappe.local.uploaded_filename
    if content is None or not file_name:
        frappe.throw(_("No file was provided for upload."))

    stored = _store_file(folder, file_name, content, context)
    _log(context, "added", stored["file_name"], frappe.form_dict.get("course_schedule"))

    return {
        "folder_id": folder,
        "folder_name": frappe.db.get_value("File", folder, "file_name"),
        "files": [stored],
    }


@frappe.whitelist()
def upload_folder(**kwargs):
    """Handle multi-file uploads posted directly to this endpoint.

    Superseded by `upload_to_folder` for the folder tool, which routes through
    Frappe's own upload endpoint to get a Desk-configurable request ceiling. This
    entry point is kept for any caller that posts here directly, but note that its
    request body is capped at `conf.max_file_size` (default 25 MB) for the *whole*
    request regardless of how many files it carries.
    """
    uploaded_files = frappe.request.files.getlist("files")
    if not uploaded_files:
        frappe.throw(_("No files were provided for upload."))

    folder = _resolve_folder(
        course_folder=frappe.form_dict.get("course_folder"),
        folder_id=frappe.form_dict.get("folder_id"),
    )
    context = _ensure_folder_permission(folder, perm="write")
    section = frappe.form_dict.get("course_schedule")

    saved = []
    for file in uploaded_files:
        stored = _store_file(folder, file.filename, file.stream.read(), context)
        _log(context, "added", stored["file_name"], section)
        saved.append(stored)

    return {
        "folder_id": folder,
        "folder_name": frappe.db.get_value("File", folder, "file_name"),
        "files": saved,
    }


@frappe.whitelist()
def get_files_in_folder(
    course_folder: str | None = None, folder_id: str | None = None, **kwargs
):
    """Retrieve files and sub-folders of a Course Folder root or a subfolder."""
    folder = _resolve_folder(course_folder=course_folder, folder_id=folder_id)
    _ensure_folder_permission(folder, perm="read")

    fields = [
        "name",
        "file_name",
        "file_url",
        "folder",
        "is_folder",
        "is_private",
        "modified",
        "creation",
        "file_size",
    ]

    entries = frappe.get_all(
        "File",
        filters={"folder": folder},
        fields=fields,
        order_by="is_folder desc, file_name asc",
        ignore_permissions=True,
    )

    return {
        "entries": entries,
        "folder_id": folder,
        "folder_name": frappe.db.get_value("File", folder, "file_name"),
    }


def _resolve_file(
    file_id: str | None = None,
    file_url: str | None = None,
    folder_id: str | None = None,
) -> str:
    """Resolve a single non-folder File row from the identifiers the caller has."""
    if file_id:
        if frappe.db.exists("File", file_id):
            return file_id
        _not_available()

    if not file_url:
        frappe.throw(_("File identifier is required."))

    filters = {"file_url": normalize_file_url(file_url), "is_folder": 0}
    if folder_id:
        filters["folder"] = _resolve_folder(folder_id=folder_id)

    matches = frappe.get_all(
        "File",
        filters=filters,
        pluck="name",
        limit=2,
        ignore_permissions=True,
    )
    if not matches:
        _not_available()
    if len(matches) > 1:
        # Guessing here would delete somebody else's row. The caller has the
        # document name in the folder listing; ask for it rather than pick one.
        frappe.throw(
            _(
                "More than one file shares this URL. Retry the delete from a "
                "refreshed folder listing."
            )
        )
    return matches[0]


def _file_in_folder(name: str):
    doc = frappe.get_doc("File", name)
    if doc.is_folder:
        frappe.throw(_("This is a folder, not a file."))
    if not doc.folder:
        frappe.throw(_("This file does not belong to a folder."))
    return doc


@frappe.whitelist()
def delete_file(
    file_id: str | None = None,
    file_url: str | None = None,
    folder_id: str | None = None,
    course_schedule: str | None = None,
    **kwargs,
):
    """Delete one file from a course folder.

    `file_url` is accepted so older clients keep working, but it is **not** a
    unique key: Frappe lets several File rows share one URL — an attachment copied
    between documents, and, now that large media is offloaded, any two uploads of
    identical bytes, since the object key is the content hash (privatedocs/p004).
    So a URL is resolved within the folder that owns it and an ambiguous match is
    refused. `file_id` is exact and is what the folder tool sends.

    Deletion goes through `frappe.delete_doc` rather than a direct DB delete, so
    File's own `on_trash` runs: that is what refcounts the stored bytes by content
    hash and removes them only when the last row referencing them goes.
    """
    name = _resolve_file(file_id=file_id, file_url=file_url, folder_id=folder_id)
    doc = _file_in_folder(name)

    # Authorised the same way the upload is: write access to the containing
    # folder. `delete_doc` then applies File's own permission check on top.
    context = _ensure_folder_permission(doc.folder, perm="write")
    frappe.delete_doc("File", name)
    _log(context, "removed", doc.file_name, course_schedule)

    return {"name": name, "folder_id": doc.folder}


@frappe.whitelist()
def rename_file(
    file_id: str,
    new_name: str,
    course_schedule: str | None = None,
    **kwargs,
):
    """Rename one file (its display `file_name`; the stored bytes are untouched)."""
    new_name = (new_name or "").strip()
    if not new_name:
        frappe.throw(_("A file name is required."))
    if "/" in new_name or "\\" in new_name:
        frappe.throw(_("A file name cannot contain a path separator."))

    name = _resolve_file(file_id=file_id)
    doc = _file_in_folder(name)
    context = _ensure_folder_permission(doc.folder, perm="write")

    old_name = doc.file_name
    if old_name != new_name:
        frappe.db.set_value("File", name, "file_name", new_name)
        _log(context, "renamed", f"{old_name} -> {new_name}", course_schedule)

    return {"name": name, "file_name": new_name, "folder_id": doc.folder}


@frappe.whitelist()
def move_file(
    file_id: str,
    folder_id: str,
    course_schedule: str | None = None,
    **kwargs,
):
    """Move one file into another folder of the **same** Course Folder tree."""
    name = _resolve_file(file_id=file_id)
    doc = _file_in_folder(name)
    target = _resolve_folder(folder_id=folder_id)
    if not frappe.db.get_value("File", target, "is_folder"):
        _not_available()

    context = _ensure_folder_permission(doc.folder, perm="write")
    target_context = _ensure_folder_permission(target, perm="write")
    if (context or {}).get("course_folder") != (target_context or {}).get(
        "course_folder"
    ):
        frappe.throw(_("A file can only be moved within its own course folder."))

    if doc.folder != target:
        source_label = frappe.db.get_value("File", doc.folder, "file_name")
        target_label = frappe.db.get_value("File", target, "file_name")
        frappe.db.set_value("File", name, "folder", target)
        _log(
            context,
            "moved",
            f"{doc.file_name} ({source_label} -> {target_label})",
            course_schedule,
        )

    return {"name": name, "folder_id": target}


def _add_folder_to_zip(
    archive: zipfile.ZipFile,
    folder_id: str,
    base_path: str,
    visited: Set[str],
) -> None:
    """Recursively write the contents of a folder into the zip archive."""
    if folder_id in visited:
        return
    visited.add(folder_id)

    entries = frappe.get_all(
        "File",
        filters={"folder": folder_id},
        fields=["name", "file_name", "is_folder"],
        order_by="is_folder desc, file_name asc",
        ignore_permissions=True,
    )

    if not entries and base_path:
        # Preserve empty folders in the archive.
        archive.writestr(f"{base_path}/", b"")
        return

    for entry in entries:
        entry_path = f"{base_path}/{entry.file_name}" if base_path else entry.file_name
        if entry.is_folder:
            _add_folder_to_zip(archive, entry.name, entry_path, visited)
            continue
        # Streamed rather than read whole: a course folder of lecture video would
        # otherwise sit in worker memory in its entirety. Works the same whether
        # the file is on disk or offloaded to object storage (privatedocs/p004).
        copy_into_zip(archive, entry.name, entry_path)


@frappe.whitelist()
def download_folder(
    course_folder: str | None = None, folder_id: str | None = None, **kwargs
):
    """Stream a zip archive of the folder, including its sub-folders and files."""
    folder = _resolve_folder(course_folder=course_folder, folder_id=folder_id)
    _ensure_folder_permission(folder, perm="read")

    root_name = frappe.db.get_value("File", folder, "file_name") or "folder"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _add_folder_to_zip(archive, folder, root_name, visited=set())

    frappe.local.response.filename = f"{root_name}.zip"
    frappe.local.response.filecontent = buffer.getvalue()
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"


@frappe.whitelist()
def create_subfolder(
    parent_folder_id: str | None = None,
    subfoldername: str | None = None,
    course_folder: str | None = None,
    course_schedule: str | None = None,
    **kwargs,
):
    """Create a sub-folder under a Course Folder root or one of its subfolders."""
    subfoldername = (subfoldername or "").strip()
    if not subfoldername:
        frappe.throw(_("Sub-folder name is required."))
    if "/" in subfoldername or "\\" in subfoldername:
        frappe.throw(_("A folder name cannot contain a path separator."))

    parent_folder = _resolve_folder(
        course_folder=course_folder, folder_id=parent_folder_id
    )
    context = _ensure_folder_permission(parent_folder, perm="write")

    existing = frappe.db.exists(
        "File",
        {
            "file_name": subfoldername,
            "folder": parent_folder,
            "is_folder": 1,
        },
    )
    if existing:
        frappe.throw(
            _("A folder named '{0}' already exists in this location.").format(
                subfoldername
            )
        )

    folder_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": subfoldername,
            "folder": parent_folder,
            "is_folder": 1,
            "is_private": 1,
        }
    )
    # Authorised above by the folder's scope rule; the File-level role check
    # would refuse an Instructor who has no File create permission of their own.
    folder_doc.insert(ignore_permissions=True)
    if context:
        _link_file_to_course_folder(folder_doc.name, context["course_folder"])
    _log(context, "added", f"{subfoldername}/", course_schedule)

    return {
        "name": folder_doc.name,
        "file_name": folder_doc.file_name,
        "folder": folder_doc.folder,
        "is_folder": folder_doc.is_folder,
    }
