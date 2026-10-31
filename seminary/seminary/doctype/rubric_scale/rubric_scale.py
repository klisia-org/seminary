# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Rubric Scale (decisions/095 §1): the school's levels, shared by every rubric."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RubricScale(Document):
    def validate(self):
        self.validate_levels()
        self.validate_locked()

    def validate_levels(self):
        if len(self.levels) < 2:
            frappe.throw(_("A scale needs at least two levels."))
        labels = [(lv.label or "").strip() for lv in self.levels]
        if len(set(l.lower() for l in labels)) != len(labels):
            frappe.throw(_("Each level needs its own label."))
        percents = [flt(lv.percent) for lv in self.levels]
        if any(p < 0 or p > 100 for p in percents):
            frappe.throw(_("A level's percent must be between 0 and 100."))
        if any(a <= b for a, b in zip(percents, percents[1:])):
            frappe.throw(
                _(
                    "List the levels from highest to lowest, each worth less than the one above."
                )
            )
        if sum(1 for lv in self.levels if lv.meets_expectations) != 1:
            frappe.throw(_("Mark exactly one level as meeting expectations."))

    def validate_locked(self):
        """Grades already given read their level's percent from here, so the
        levels of a scale in use never change; a new scale replaces it."""
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before or _levels(before) == _levels(self):
            return
        used = frappe.db.sql(
            """select 1 from `tabRubric Score` s
            join `tabRubric` r on r.name = s.rubric
            where r.scale = %s limit 1""",
            self.name,
        )
        if used:
            frappe.throw(
                _(
                    "Students have been graded on this scale, so its levels cannot change. Create a new scale and make it the default."
                )
            )

    def on_update(self):
        if self.is_default:
            frappe.db.sql(
                "update `tabRubric Scale` set is_default = 0 where name != %s and is_default = 1",
                self.name,
            )


def _levels(doc):
    return [
        (
            (lv.label or "").strip(),
            flt(lv.percent),
            lv.meets_expectations,
            lv.description or "",
        )
        for lv in doc.levels
    ]
