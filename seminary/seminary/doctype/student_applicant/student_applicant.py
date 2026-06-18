# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class StudentApplicant(Document):
    def before_insert(self):
        if self.ds2 and self.ds_body:
            return
        ds = frappe.db.get_value(
            "Doctrinal Statement",
            {"active": 1, "use_in_student_admission": 1, "docstatus": 1},
            ["name", "doctrinal_statement"],
            as_dict=True,
            order_by="creation desc",
        )
        if not ds:
            return
        if not self.ds2:
            self.ds2 = ds.name
        if not self.ds_body:
            self.ds_body = ds.doctrinal_statement

    def autoname(self):
        from frappe.model.naming import set_name_by_naming_series

        if self.program:
            program_naming_series = frappe.db.get_value(
                "Program", self.program, "applicant_naming_series"
            )
            if program_naming_series:
                self.naming_series = program_naming_series

        set_name_by_naming_series(self)

    def validate(self):
        self.set_title()
        self.validate_dates()
        self.validate_term()

    def set_title(self):
        self.title = " ".join(
            filter(None, [self.first_name, self.middle_name, self.last_name])
        )

    def validate_dates(self):
        if self.date_of_birth and getdate(self.date_of_birth) >= getdate():
            frappe.throw(_("Date of Birth cannot be greater than today."))

    def validate_term(self):
        if self.academic_year and self.academic_term:
            actual_academic_year = frappe.db.get_value(
                "Academic Term", self.academic_term, "academic_year"
            )
            if actual_academic_year != self.academic_year:
                frappe.throw(
                    _("Academic Term {0} does not belong to Academic Year {1}").format(
                        self.academic_term, self.academic_year
                    )
                )

    def after_insert(self):
        # Person spine seam (ADR 042): public intake captures contact fields
        # here (a guest can't write Person directly) and promotes them on
        # insert — no User exists yet.
        self._promote_to_person()

        # Generate Application-fee Sales Invoice(s) on creation, not on submit:
        # web-form-created applicants stay at docstatus=0 indefinitely (no submit
        # action), so on_submit never fires. Billing must run on insert so the
        # post-application payment page has an SI to charge against.
        from seminary.seminary.api import generate_application_invoices

        try:
            generate_application_invoices(self.name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Application invoice generation failed for {self.name}",
            )

    def on_update(self):
        self._repromote_to_person()
        self._flag_requirement_review()

    def _flag_requirement_review(self):
        """ADR 058: when an applicant self-reports a circumstance needing
        leveling / advanced-standing review, raise an open ToDo per Registrar so
        they build the leveling plan on the new enrollment. Idempotent."""
        choice = self.get("requests_requirement_review")
        if not choice or choice == "None":
            return
        from seminary.seminary.cei_lifecycle import _registrar_emails

        for user in _registrar_emails():
            if frappe.db.exists(
                "ToDo",
                {
                    "allocated_to": user,
                    "reference_type": "Student Applicant",
                    "reference_name": self.name,
                    "status": "Open",
                },
            ):
                continue
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "owner": user,
                    "allocated_to": user,
                    "reference_type": "Student Applicant",
                    "reference_name": self.name,
                    "description": _(
                        "Applicant {0} requested requirement review ({1}). "
                        "Plan leveling / advanced standing on their enrollment."
                    ).format(self.name, choice),
                }
            ).insert(ignore_permissions=True)

    def _promote_to_person(self):
        from seminary.seminary import person as person_spine

        person = person_spine.ensure_person(
            email=self.student_email_id,
            first_name=self.first_name,
            middle_name=self.middle_name,
            last_name=self.last_name,
            mobile=self.student_mobile_number,
            country=self.country,
            image=self.image,
        )
        self.db_set("person", person, update_modified=False)

    def _repromote_to_person(self):
        """While the applicant is the sole role attached (no User yet, not
        Admitted), the intake form stays the authoritative editor: staff fix
        typos where they see them and the edit re-promotes last-write-wins
        (ADR 042). From admission on, edits happen on the Person."""
        from seminary.seminary import person as person_spine

        if not self.person or self.application_status == "Admitted":
            return
        if frappe.db.get_value("Person", self.person, "user"):
            return
        person_spine.update_person(
            self.person,
            email=self.student_email_id,
            first_name=self.first_name,
            middle_name=self.middle_name,
            last_name=self.last_name,
            mobile=self.student_mobile_number,
            country=self.country,
            image=self.image,
            overwrite=True,
        )

    def on_payment_authorized(self, *args, **kwargs):
        self.db_set("paid", 1)
