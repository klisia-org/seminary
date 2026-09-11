from __future__ import annotations

import io
import zipfile
from typing import Optional, Set

import frappe

from seminary.seminary.utils import user_is_enrolled_in_course
from seminary.storage.backend import normalize_file_url
from seminary.storage.files import copy_into_zip


def _resolve_folder(foldername: str | None = None, folder_id: str | None = None) -> str:
    """Resolve and return the File document name for the given identifiers."""
    if folder_id:
        if frappe.db.exists("File", folder_id):
            return folder_id
        frappe.throw(f"Folder with id '{folder_id}' not found.")

    if foldername:
        folder = frappe.db.get_value(
            "File", {"file_name": foldername, "is_folder": 1}, "name"
        )
        if folder:
            return folder
        frappe.throw(f"Folder '{foldername}' not found.")

    frappe.throw("Folder identifier is required.")


def _get_course_folder_context(folder_id: str) -> Optional[dict[str, str]]:
    """Return the Course Folder (and Course) linked to the provided File document."""
    visited: Set[str] = set()
    current = folder_id
    while current and current not in visited:
        course_folder = frappe.db.get_value(
            "Course Folder",
            {"file_reference": current},
            ["name", "course"],
            as_dict=True,
        )
        if course_folder:
            return {
                "course_folder": course_folder.name,
                "course": course_folder.course,
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


def _ensure_folder_permission(folder_id: str, perm: str = "read") -> None:
    """Ensure the current user has the specified permission for the folder."""
    folder_doc = frappe.get_doc("File", folder_id)
    if folder_doc.has_permission(perm):
        return
    if perm == "read":
        context = _get_course_folder_context(folder_doc.name)
        if context and user_is_enrolled_in_course(context.get("course")):
            return
    frappe.throw(frappe._(f"Not permitted to access folder '{folder_doc.file_name}'."))


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
def upload_to_folder():
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
    """
    folder = _resolve_folder(
        foldername=frappe.form_dict.get("foldername"),
        folder_id=frappe.form_dict.get("folder_id"),
    )
    _ensure_folder_permission(folder, perm="write")

    content = frappe.local.uploaded_file
    file_name = frappe.local.uploaded_filename
    if content is None or not file_name:
        frappe.throw("No file was provided for upload.")

    stored = _store_file(folder, file_name, content, _get_course_folder_context(folder))

    return {
        "folder_id": folder,
        "folder_name": frappe.db.get_value("File", folder, "file_name"),
        "files": [stored],
    }


@frappe.whitelist()
def upload_folder():
    """Handle folder uploads using Frappe's file system.

    Superseded by `upload_to_folder` for the folder tool, which routes through
    Frappe's own upload endpoint to get a Desk-configurable request ceiling. This
    entry point is kept for any caller that posts here directly, but note that its
    request body is capped at `conf.max_file_size` (default 25 MB) for the *whole*
    request regardless of how many files it carries.
    """
    foldername = frappe.form_dict.get("foldername")
    folder_id = frappe.form_dict.get("folder_id")
    uploaded_files = frappe.request.files.getlist("files")

    if not uploaded_files:
        frappe.throw("No files were provided for upload.")

    folder = _resolve_folder(foldername=foldername, folder_id=folder_id)
    _ensure_folder_permission(folder, perm="write")
    context = _get_course_folder_context(folder)

    saved = [
        _store_file(folder, file.filename, file.stream.read(), context)
        for file in uploaded_files
    ]

    return {
        "folder_id": folder,
        "folder_name": foldername or frappe.db.get_value("File", folder, "file_name"),
        "files": saved,
    }


@frappe.whitelist()
def get_files_in_folder(foldername: str | None = None, folder_id: str | None = None):
    """Retrieve files and sub-folders for the specified folder."""
    folder = _resolve_folder(foldername=foldername, folder_id=folder_id)
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
        frappe.throw(f"File '{file_id}' not found.")

    if not file_url:
        frappe.throw("File identifier is required.")

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
        frappe.throw("File not found.")
    if len(matches) > 1:
        # Guessing here would delete somebody else's row. The caller has the
        # document name in the folder listing; ask for it rather than pick one.
        frappe.throw(
            "More than one file shares this URL. Retry the delete from a "
            "refreshed folder listing."
        )
    return matches[0]


@frappe.whitelist()
def delete_file(
    file_id: str | None = None,
    file_url: str | None = None,
    folder_id: str | None = None,
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

    doc = frappe.get_doc("File", name)
    if doc.is_folder:
        frappe.throw("This is a folder, not a file.")
    if not doc.folder:
        frappe.throw("This file does not belong to a folder.")

    # Authorised the same way the upload is: write access to the containing
    # folder. `delete_doc` then applies File's own permission check on top.
    _ensure_folder_permission(doc.folder, perm="write")
    frappe.delete_doc("File", name)

    return {"name": name, "folder_id": doc.folder}


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
def download_folder(foldername: str | None = None, folder_id: str | None = None):
    """Stream a zip archive of the folder, including its sub-folders and files."""
    folder = _resolve_folder(foldername=foldername, folder_id=folder_id)
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
    parent_foldername: str | None = None,
    parent_folder_id: str | None = None,
    subfoldername: str | None = None,
):
    """Create a sub-folder under the specified parent folder."""
    if not subfoldername:
        frappe.throw("Sub-folder name is required.")

    parent_folder = _resolve_folder(
        foldername=parent_foldername,
        folder_id=parent_folder_id,
    )
    _ensure_folder_permission(parent_folder, perm="write")

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
            f"A folder named '{subfoldername}' already exists in this location."
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
    folder_doc.insert(ignore_permissions=False)
    context = _get_course_folder_context(folder_doc.name)
    if context:
        _link_file_to_course_folder(folder_doc.name, context["course_folder"])

    return {
        "name": folder_doc.name,
        "file_name": folder_doc.file_name,
        "folder": folder_doc.folder,
        "is_folder": folder_doc.is_folder,
    }
