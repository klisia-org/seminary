import frappe
from frappe import _
from frappe.model.document import Document


class AlumniProfile(Document):
    def validate(self):
        self._sync_email_from_user()
        self._sync_full_name_from_student()
        self._resolve_person()

    def _resolve_person(self):
        """Person spine seam (ADR 042). The same human's Student record (if
        any) already created the Person and linked the same User, so
        ensure_person resolves to it; non-student alumni (honorary, transfer,
        board) get one created from their User."""
        from seminary.seminary import person as person_spine

        if self.person:
            return
        self.person = person_spine.ensure_person(email=self.email, user=self.user)

    def _sync_email_from_user(self):
        if not self.user:
            return
        user_email = frappe.db.get_value("User", self.user, "email") or self.user
        if not self.email:
            self.email = user_email
        elif self.email != user_email:
            frappe.throw(_("Email must match the linked User's email."))

    def _sync_full_name_from_student(self):
        if self.full_name or not self.student:
            return
        self.full_name = frappe.db.get_value("Student", self.student, "student_name")
