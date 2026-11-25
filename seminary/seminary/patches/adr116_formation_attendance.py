"""Chapel check-ins made before decisions/116 are self check-ins of students who
came, and chapel requirements made before it are counts (029)."""

import frappe


def execute():
	frappe.db.sql(
		"""UPDATE `tabChapel Attendance` SET status = 'Present'
		WHERE status IS NULL OR status = ''"""
	)
	frappe.db.sql(
		"""UPDATE `tabChapel Attendance` SET method = 'Self check-in'
		WHERE method IS NULL OR method = ''"""
	)
	for doctype in ("Graduation Requirement Item", "Student Graduation Requirement"):
		for name in frappe.get_all(
			doctype,
			filters={"requirement_type": "Chapel Attendance", "attendance_measure": ["in", ["", None]]},
			pluck="name",
		):
			frappe.db.set_value(doctype, name, "attendance_measure", "Count", update_modified=False)
