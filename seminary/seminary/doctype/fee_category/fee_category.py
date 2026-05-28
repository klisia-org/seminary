# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FeeCategory(Document):
    def validate(self):
        self.validate_tuition()
        self.validate_audit()

    def validate_tuition(self):
        if self.fc_event != "Course Enrollment":
            if self.is_credit == 1:
                frappe.throw(
                    _("Credits are only allowed for events of type Course Enrollment")
                )

    def validate_audit(self):
        allow_audit = frappe.get_single_value("Seminary Settings", "allow_audit")
        audit_per_credit = frappe.get_single_value("Seminary Settings", "auditcredit")
        if self.is_audit == 1:
            if allow_audit == 0:
                frappe.throw(_("Please, first enable audits in Seminary Settings"))
            if self.fc_event != "Course Enrollment":
                frappe.throw(
                    _("Audit is only allowed for events of type Course Enrollment")
                )
            if self.is_credit == 1 and audit_per_credit == 0:
                frappe.throw(
                    _(
                        "Seminary Settings are currently set to charge audit as a flat fee, not per credit. Either uncheck Is Credit here, or change Seminary Settings to allow audit per credit."
                    )
                )
