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

    def on_payment_authorized(self, *args, **kwargs):
        self.db_set("paid", 1)
