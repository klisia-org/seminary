# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# The levels the system provides, with their tier (p016). Accreditation reads these names, so they
# cannot be renamed, deleted or moved to another tier. Their policies stay the school's to set.
SEEDED = {
    "Certificate": "Certificate",
    "Bachelors": "Bachelor's",
    "Master of Arts": "Master's",
    "Master of Divinity": "Master's",
    "Master of Theology": "Master's",
    "Doctor of Ministry": "Doctoral",
    "Other Professional Doctorate": "Doctoral",
    "PhD/Research Doctorate": "Doctoral",
    "Non Formal Program": "Non-formal",
}


class ProgramLevel(Document):
    def validate(self):
        self._keep_seeded_tier()

    def before_update_after_submit(self):
        self._keep_seeded_tier()

    def _keep_seeded_tier(self):
        tier = SEEDED.get(self.name)
        if tier and self.degree_tier != tier:
            frappe.throw(
                _("{0} is provided by the system and its tier stays {1}.").format(
                    frappe.bold(self.name), frappe.bold(_(tier))
                )
            )

    def before_cancel(self):
        _refuse_if_seeded(self.name, _("cancelled"))

    def on_trash(self):
        _refuse_if_seeded(self.name, _("deleted"))

    def before_rename(self, old, new, merge=False):
        _refuse_if_seeded(old, _("renamed"))


def _refuse_if_seeded(name, action):
    if name in SEEDED and not frappe.flags.in_patch:
        frappe.throw(
            _(
                "{0} is provided by the system and cannot be {1}. Add a level of your own instead."
            ).format(frappe.bold(name), action)
        )


def levels_in_tier(tier):
    """The levels of a tier: what a cohort type bound to that tier spans."""
    if not tier:
        return []
    return frappe.get_all("Program Level", filters={"degree_tier": tier}, pluck="name")


def programs_in_tier(tier):
    levels = levels_in_tier(tier)
    if not levels:
        return []
    return frappe.get_all(
        "Program", filters={"program_level": ("in", levels)}, pluck="name"
    )


def tier_of_program(program):
    level = (
        frappe.db.get_value("Program", program, "program_level") if program else None
    )
    return frappe.db.get_value("Program Level", level, "degree_tier") if level else None


def seed_program_levels():
    """Create the system's levels when missing, submitted, and give a seeded level that lacks one
    its tier. Create-only: a school's policy edits survive migrate."""
    for name, tier in SEEDED.items():
        if frappe.db.exists("Program Level", name):
            if frappe.db.get_value("Program Level", name, "degree_tier") != tier:
                frappe.db.set_value(
                    "Program Level", name, "degree_tier", tier, update_modified=False
                )
            continue
        doc = frappe.get_doc(
            {"doctype": "Program Level", "pgm_level": name, "degree_tier": tier}
        ).insert(ignore_permissions=True)
        doc.submit()
