# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
import seminary.seminary.api


class ScheduledCourseRoster(Document):
    @frappe.whitelist()
    def validate(self):
        self.validate_score()

    @frappe.whitelist()
    def validate_score(self):
        course = frappe.get_doc("Course Schedule", self.course_sc)
        gscale = course.gradesc_cs
        grading_scale = frappe.get_doc("Grading Scale", gscale)
        detail = self.stdroster_grade

        if grading_scale.grscale_type == "Points":
            for row in detail:
                score = row.rawscore_card
                extrapoints = row.actualextrapt_card
                extra = row.extracredit_card

                if score is not None and extra == 0:
                    if score > grading_scale.maxnumgrade:
                        frappe.throw(
                            "Score cannot be greater than the maximum score of the grading scale"
                        )
                elif extrapoints is not None and extra == 1:
                    if extrapoints > row.maxextrapoints_card:
                        frappe.throw(
                            "Extra credit points cannot be greater than the maximum extra credit points of the grading scale"
                        )

        elif grading_scale.grscale_type == "Descriptive":
            # The cell holds one of the scale's interval thresholds, not a free
            # number. Without this check a typo resolves silently into a lower
            # band instead of erroring (ADR 072).
            levels = {flt(i.threshold) for i in grading_scale.intervals}
            for row in detail:
                if not row.graded_card or row.extracredit_card:
                    continue
                if flt(row.rawscore_card) not in levels:
                    frappe.throw(
                        _(
                            "Row {0}: {1} is not a level on grading scale {2}. "
                            "Valid levels are {3}."
                        ).format(
                            row.idx,
                            flt(row.rawscore_card),
                            grading_scale.name,
                            ", ".join(str(lv) for lv in sorted(levels)),
                        )
                    )
        return "ok"
