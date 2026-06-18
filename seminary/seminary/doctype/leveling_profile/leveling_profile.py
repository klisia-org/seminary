# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LevelingProfile(Document):
    def validate(self):
        for row in self.items or []:
            if row.kind == "Leveling Course" and not row.course:
                frappe.throw(_("Leveling Course rows require a Course."))
            if row.kind == "Course Exemption" and not row.course:
                frappe.throw(_("Course Exemption rows require a Course."))
            if row.kind == "Placement Assessment" and not row.gating_assessment:
                frappe.throw(
                    _(
                        "Placement Assessment rows require a linked Placement Assessment."
                    )
                )
            if row.kind == "Requirement Waiver" and not row.graduation_requirement_item:
                frappe.throw(
                    _("Requirement Waiver rows require a Graduation Requirement.")
                )
