# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Diploma controller.

A Diploma is the artefact issued automatically when a Graduation Request
reaches the 'Approved' state (see ``GraduationRequest._issue_diploma``).
Two identifiers coexist:

- ``name`` (autoname=hash) — opaque, unguessable; anchors the future
  public verification page.
- ``diploma_serial`` (DIP-YYYY-####) — human-readable, used in printed
  text and registrar correspondence.

Diplomas are never deleted on cancellation: ``revoked`` is flipped so the
verification hash stays addressable and can report a clean revoked status.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Diploma(Document):
    def before_insert(self):
        if not self.diploma_serial:
            self.diploma_serial = self._next_serial()

    def after_insert(self):
        if not self.verification_hash:
            self.db_set("verification_hash", self.name, update_modified=False)

    def _next_serial(self):
        year = getdate(self.issued_on or today()).year
        prefix = f"DIP-{year}-"
        last = frappe.db.sql(
            """
            SELECT diploma_serial FROM `tabDiploma`
            WHERE diploma_serial LIKE %s
            ORDER BY creation DESC LIMIT 1
            """,
            (f"{prefix}%",),
        )
        if last and last[0][0]:
            try:
                next_n = int(last[0][0].split("-")[-1]) + 1
            except (ValueError, IndexError):
                next_n = 1
        else:
            next_n = 1
        return f"{prefix}{next_n:04d}"


def get_permission_query_conditions(user):
    """Limit Student-role users to their own diplomas."""
    if not user:
        user = frappe.session.user
    roles = set(frappe.get_roles(user))
    if roles & {"System Manager", "Seminary Manager", "Academics User"}:
        return ""
    student = frappe.db.get_value("Student", {"student_email_id": user}, "name")
    if not student:
        return "1=0"
    return f"`tabDiploma`.student = {frappe.db.escape(student)}"


def has_permission(doc, user=None, permission_type=None):
    if not user:
        user = frappe.session.user
    roles = set(frappe.get_roles(user))
    if roles & {"System Manager", "Seminary Manager", "Academics User"}:
        return True
    student = frappe.db.get_value("Student", {"student_email_id": user}, "name")
    return bool(student) and doc.student == student
