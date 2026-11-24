"""privatedocs p027: suggested attendance needs half the meeting unless the school
says otherwise. On an existing site the new field would otherwise read as 0."""

import frappe


def execute():
	field = "meeting_attendance_min_share"
	if not frappe.db.exists("Singles", {"doctype": "Seminary Settings", "field": field}):
		frappe.db.set_single_value("Seminary Settings", field, 50)
