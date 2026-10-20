# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, today


class PersonRequirement(Document):
    """One thing one person must sign or upload (ADR 091 §3). Its status is
    derived from the record that satisfies it; see `requirements.compute_status`."""

    def validate(self):
        from seminary.seminary import requirements

        if self.reference_doctype not in requirements.SUBJECTS:
            frappe.throw(
                _("A requirement is for a Program Enrollment or an Instructor.")
            )
        person = requirements.person_of(self.reference_doctype, self.reference_name)
        if not person:
            frappe.throw(
                _("{0} {1} has no Person.").format(
                    _(self.reference_doctype), self.reference_name
                )
            )
        self.person = person
        if self.kind == "Agreement":
            self.document_type = None
        else:
            self.agreement_template = None
        if not self.start_date:
            self.start_date = today()
        if not self.due_date:
            self.due_date = add_days(
                max(getdate(self.start_date), getdate(today())), cint(self.due_days)
            )
        if not self.renewal:
            self.renewal = requirements.NOT_RENEWED

    def after_insert(self):
        from seminary.seminary import requirements

        # A diploma sent with the application already satisfies the new row.
        requirements.recompute(self.name)
