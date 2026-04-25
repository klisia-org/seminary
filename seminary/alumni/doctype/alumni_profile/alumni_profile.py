import frappe
from frappe import _
from frappe.model.document import Document


class AlumniProfile(Document):
    def validate(self):
        self._sync_email_from_user()
        self._sync_full_name_from_student()

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
