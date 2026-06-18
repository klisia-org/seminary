# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AcademicUnit(Document):
    def validate(self):
        self._validate_member_units()

    def _validate_member_units(self):
        """Member units belong only to an Academic Interdepartment, and must be
        real, distinct departments — not the unit itself and not another
        interdepartment (transitive resolution unions one level; nesting would
        recurse)."""
        if self.unit_type != "Academic Interdepartment":
            if self.member_units:
                frappe.throw(
                    _("Member Units apply only to an Academic Interdepartment.")
                )
            return

        seen = set()
        for row in self.member_units:
            if row.member_unit == self.name:
                frappe.throw(_("An interdepartment cannot list itself as a member."))
            if row.member_unit in seen:
                frappe.throw(
                    _("{0} is listed twice in Member Units.").format(row.member_unit)
                )
            seen.add(row.member_unit)
            member_type = frappe.db.get_value(
                "Academic Unit", row.member_unit, "unit_type"
            )
            if member_type == "Academic Interdepartment":
                frappe.throw(
                    _(
                        "Member Unit {0} is itself an interdepartment; list its "
                        "constituent departments instead."
                    ).format(row.member_unit)
                )
