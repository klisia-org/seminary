# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


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
