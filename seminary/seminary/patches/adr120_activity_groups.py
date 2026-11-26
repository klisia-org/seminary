"""Group meetings made before decisions/120 kept their groups on the meeting
(100d-a §3). Each becomes an Activity Group, and the meeting points to it."""

import frappe


def execute():
	from seminary.seminary import group_work

	if not frappe.db.has_column("Oral Activity Meeting", "activity_group"):
		return
	meetings = frappe.get_all(
		"Oral Activity Meeting",
		filters={"kind": "Group", "activity_group": ["is", "not set"], "status": ["!=", "Cancelled"]},
		fields=["name", "course_schedule", "oral_activity", "group_label"],
		order_by="creation asc",
	)
	for m in meetings:
		if not (m.course_schedule and m.oral_activity):
			continue
		if not group_work.scac_row(m.course_schedule, group_work.ORAL, m.oral_activity):
			continue
		students = frappe.get_all(
			"Oral Activity Meeting Member",
			filters={"parent": m.name, "parenttype": "Oral Activity Meeting"},
			pluck="student",
			order_by="idx asc",
		)
		if not students:
			continue
		group = group_work.make_group(
			m.course_schedule,
			group_work.ORAL,
			m.oral_activity,
			m.group_label or frappe._("Group"),
			[s for s in dict.fromkeys(students) if s],
			source="Meetings",
		)
		frappe.db.set_value(
			"Oral Activity Meeting", m.name, "activity_group", group.name, update_modified=False
		)
