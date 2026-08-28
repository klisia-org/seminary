# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from seminary.seminary.utils import assert_url_safe_code


class GradingScale(Document):
    def validate(self):
        thresholds = []
        for d in self.intervals:
            threshold = flt(d.threshold)
            if threshold in thresholds:
                frappe.throw(
                    _("Threshold {0} appears more than once").format(threshold)
                )
            thresholds.append(threshold)
        if self.grscale_type == "Points" and 0 not in thresholds:
            frappe.throw(_("Please define a grade for Threshold 0"))
        self.validate_cbe_scale()

    def validate_cbe_scale(self):
        """Validate the extra structure a competency-based scale must carry.

        A CBE scale supplies two vocabularies to everything downstream: the
        proficiency levels (the intervals, whose threshold is the level value)
        and the dimensions. Both must be complete and stable before any
        competency record can reference them. Child-row rules live here on the
        parent per ADR 023.
        """
        if self.grscale_type != "Competency-based education":
            return

        if not self.gradingscaledimensions:
            frappe.throw(
                _("A Competency-based education scale needs at least one dimension.")
            )

        seen_codes = {}
        for d in self.gradingscaledimensions:
            if not d.dimension_code:
                frappe.throw(_("Row {0}: Dimension Code is required.").format(d.idx))
            assert_url_safe_code(
                d.dimension_code, _("Row {0}: Dimension Code").format(d.idx)
            )
            if d.dimension_code in seen_codes:
                frappe.throw(
                    _("Dimension Code {0} appears in rows {1} and {2}.").format(
                        d.dimension_code, seen_codes[d.dimension_code], d.idx
                    )
                )
            seen_codes[d.dimension_code] = d.idx

        if not self.intervals:
            frappe.throw(
                _(
                    "A Competency-based education scale needs at least one interval "
                    "to define its proficiency levels."
                )
            )

        for d in self.intervals:
            if d.threshold is None or d.threshold == "":
                frappe.throw(
                    _(
                        "Row {0}: Threshold is required on every interval of a "
                        "Competency-based education scale. It holds the level value "
                        "(for example 1, 2, 3, 4)."
                    ).format(d.idx)
                )
