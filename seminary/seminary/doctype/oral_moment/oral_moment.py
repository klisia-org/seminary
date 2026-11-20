# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""A passage of a recording worth grading (decisions/100 §2, §6).

A step's moment arrives as *Suggested*; only the instructor keeps or dismisses
it. A moment the instructor marks by hand is *Kept* from the start.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OralMoment(Document):
    def validate(self):
        if flt(self.start) < 0:
            frappe.throw(_("A moment cannot start before the recording."))
        if self.end is not None and self.end != "" and flt(self.end) < flt(self.start):
            frappe.throw(_("A moment cannot end before it starts."))
        if self.source == "Instructor" and self.state == "Suggested":
            self.state = "Kept"
        if self.is_new() and self.source == "Suggested" and not self.flags.from_step:
            frappe.throw(_("Only a processing step can suggest a moment."))
