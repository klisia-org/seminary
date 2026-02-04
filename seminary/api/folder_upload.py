from __future__ import annotations

from typing import Optional, Set

import frappe
from frappe.utils.file_manager import save_file

from seminary.seminary.utils import user_is_enrolled_in_course


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


@frappe.whitelist()
def upload_folder():
    """Handle folder uploads using Frappe's file system."""
    foldername = frappe.form_dict.get("foldername")
    folder_id = frappe.form_dict.get("folder_id")
    uploaded_files = frappe.request.files.getlist("files")

    if not uploaded_files:
        frappe.throw("No files were provided for upload.")

    folder = _resolve_folder(foldername=foldername, folder_id=folder_id)
    _ensure_folder_permission(folder, perm="write")
    context = _get_course_folder_context(folder)

    saved = []
    for file in uploaded_files:
        content = file.stream.read()
        file_doc = save_file(
            file.filename,
            content,
            dt=None,
            dn=None,
            folder=folder,
            is_private=True,
        )
        if context:
            _link_file_to_course_folder(file_doc.name, context["course_folder"])
        saved.append(
            {
                "name": file_doc.name,
                "file_name": file_doc.file_name,
                "file_url": file_doc.file_url,
                "is_private": file_doc.is_private,
            }
        )

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
