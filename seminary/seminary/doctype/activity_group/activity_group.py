# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Activity Group (decisions/120 §2): students doing one activity together."""

import frappe
from frappe import _
from frappe.model.document import Document


class ActivityGroup(Document):
	def validate(self):
		from seminary.seminary import group_work

		group_work._check_doctype(self.activity_doctype)
		if not group_work.scac_row(self.course_schedule, self.activity_doctype, self.activity):
			frappe.throw(_("This activity is not part of this section's assessments."))
		seen = set()
		for m in self.members:
			if m.left_on:
				continue
			if m.student in seen:
				frappe.throw(_("{0} is in this group twice.").format(m.student_name or m.student))
			seen.add(m.student)
		if seen:
			clash = frappe.db.sql(
				"""select m.student, g.group_name from `tabActivity Group` g
				join `tabActivity Group Member` m on m.parent = g.name and m.parenttype = 'Activity Group'
				where g.course_schedule = %s and g.activity_doctype = %s and g.activity = %s
				  and g.name != %s and m.left_on is null and m.student in %s
				limit 1""",
				(self.course_schedule, self.activity_doctype, self.activity, self.name or "", tuple(seen)),
				as_dict=True,
			)
			if clash:
				frappe.throw(
					_("{0} is already in {1} on this activity.").format(clash[0].student, clash[0].group_name)
				)
		if self.topic and frappe.db.get_value("Activity Topic", self.topic, "activity") != self.activity:
			frappe.throw(_("This topic belongs to another activity."))
