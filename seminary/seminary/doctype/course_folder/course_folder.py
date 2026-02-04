# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from seminary.seminary.utils import user_is_enrolled_in_course


def _ensure_file_folder(folder_name: str, parent_file: str | None = None) -> str:
    """Ensure a File doc exists for the given folder name under the specified parent."""
    parent = parent_file or "Home"
    existing = frappe.db.get_value(
        "File",
        {
            "file_name": folder_name,
            "folder": parent,
            "is_folder": 1,
        },
        "name",
    )
    if existing:
        return existing

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": folder_name,
            "folder": parent,
            "is_folder": 1,
            "is_private": 1,
        }
    )
    file_doc.insert(ignore_permissions=True)
    return file_doc.name


def _ensure_course_root(course: str | None) -> str:
    root = _ensure_file_folder("Course Folders", "Home")
    if course:
        return _ensure_file_folder(course, root)
    return root


class CourseFolder(Document):
    def before_insert(self):
        parent_file = _ensure_course_root(self.course)
        folder_file = _ensure_file_folder(self.foldername, parent_file)
        self.parent_folder = parent_file
        self.file_reference = folder_file

    def after_insert(self):
        self._sync_file_reference_link()

    def on_update(self):
        self._sync_file_reference_link()

    def has_permission(self, permtype: str, user: str | None = None, **kwargs) -> bool:
        if super().has_permission(permtype, user=user, **kwargs):
            return True
        if permtype == "read" and user_is_enrolled_in_course(self.course, user=user):
            return True
        return False

    def _sync_file_reference_link(self) -> None:
        if not self.file_reference:
            return
        current = frappe.db.get_value(
            "File",
            self.file_reference,
            ["attached_to_doctype", "attached_to_name"],
            as_dict=True,
        )
        if (
            current
            and current.attached_to_doctype == self.doctype
            and current.attached_to_name == self.name
        ):
            return
        frappe.db.set_value(
            "File",
            self.file_reference,
            "attached_to_doctype",
            self.doctype,
            update_modified=False,
        )
        frappe.db.set_value(
            "File",
            self.file_reference,
            "attached_to_name",
            self.name,
            update_modified=False,
        )
