# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from seminary.seminary.utils import has_course_instructor_role, has_course_moderator_role


class AssignmentActivity(Document):
	

	@frappe.whitelist()
	def save_assignment(assignment, title, type, question):
		if not has_course_moderator_role() or not has_course_instructor_role():
			return

		if assignment:
			doc = frappe.get_doc("Assignment Activity", assignment)
		else:
			doc = frappe.get_doc({"doctype": "Assignment Activity"})

		doc.update({"title": title, "type": type, "question": question})
		doc.save(ignore_permissions=True)
		return doc.name