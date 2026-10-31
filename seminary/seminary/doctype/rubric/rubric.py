# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Rubric (decisions/095 §2-4): one activity's criteria on a school scale.

Locked once anyone has been graded on it; the portal editor then saves a new
version instead (see `rubrics.save_rubric`)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from seminary.seminary import rubrics


class Rubric(Document):
    def validate(self):
        self.set_context()
        self.validate_scale()
        self.validate_criteria()
        self.validate_cells()
        self.validate_locked()

    def set_context(self):
        title_field = rubrics.ACTIVITIES.get(self.activity_doctype)
        if not title_field:
            frappe.throw(_("Rubrics are only for assignments and discussions."))
        values = frappe.db.get_value(
            self.activity_doctype, self.activity, [title_field, "course"], as_dict=True
        )
        if not values:
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    _(self.activity_doctype), self.activity
                )
            )
        version = f" (v{self.version})" if (self.version or 1) > 1 else ""
        self.activity_title = f"{values.get(title_field) or self.activity}{version}"
        self.course = values.course

    def validate_scale(self):
        if self.is_new() or self.has_value_changed("scale"):
            if not frappe.db.get_value("Rubric Scale", self.scale, "enabled"):
                frappe.throw(_("Rubric Scale {0} is disabled.").format(self.scale))

    def validate_criteria(self):
        if not self.criteria:
            frappe.throw(_("Add at least one criterion."))
        seen = set()
        for c in self.criteria:
            if not (c.title or "").strip():
                frappe.throw(_("Criterion {0} needs a title.").format(c.idx))
            code = rubrics.slug(c.criterion_code or c.title)
            base, n = code, 2
            while code in seen:
                code, n = f"{base}-{n}", n + 1
            c.criterion_code = code
            seen.add(code)
            if flt(c.weight) < 0:
                frappe.throw(
                    _("Criterion {0}: a weight cannot be negative.").format(c.title)
                )

    def validate_cells(self):
        codes = {c.criterion_code for c in self.criteria}
        levels = {lv.label for lv in rubrics.scale_levels(self.scale)}
        keep, seen = [], set()
        for cell in self.cells:
            key = (cell.criterion_code, cell.level)
            if (
                cell.criterion_code in codes
                and cell.level in levels
                and key not in seen
            ):
                keep.append(cell)
                seen.add(key)
        self.set("cells", keep)

    def validate_locked(self):
        if not self.is_new() and rubrics.is_locked(self.name):
            frappe.throw(
                _(
                    "Students have been graded on this rubric, so it cannot change. Edit it from the activity to create a new version."
                )
            )

    def on_trash(self):
        if rubrics.is_locked(self.name):
            frappe.throw(
                _("Students have been graded on this rubric, so it cannot be deleted.")
            )
