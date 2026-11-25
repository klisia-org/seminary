"""Fill Course.course_id from today's course codes (decisions/114 §4).

The code becomes <unit code>-<course_id>. A course whose code starts with its
unit's code gets the rest as its Course ID and the derived code. A course with no
unit gets its whole code. A course whose code doesn't start with its unit's code
keeps the code it has and no Course ID: the form asks for one at the next save,
so nobody's code changes without someone choosing it. Stored with db_set, so no
validation runs and nothing else is touched.
"""

import frappe

from seminary.seminary.catalog import course_code, refresh_code_copies, split_code


def execute():
	frappe.reload_doc("seminary", "doctype", "replaced_course")
	frappe.reload_doc("seminary", "doctype", "course_prerequisite")
	frappe.reload_doc("seminary", "doctype", "course")

	prefixes = {
		u.name: (u.unit_code or "").strip()
		for u in frappe.get_all("Academic Unit", fields=["name", "unit_code"])
	}
	taken = set(frappe.get_all("Course", pluck="coursecode"))
	left = []
	for c in frappe.get_all(
		"Course",
		filters={"course_id": ["is", "not set"]},
		fields=["name", "coursecode", "academic_unit"],
	):
		prefix = prefixes.get(c.academic_unit, "")
		course_id = split_code(c.coursecode, prefix)
		if not course_id:
			left.append(c.name)
			continue
		code = course_code(course_id, prefix)
		if code != c.coursecode and code in taken:
			left.append(c.name)
			continue
		frappe.db.set_value("Course", c.name, "course_id", course_id, update_modified=False)
		if code != c.coursecode:
			taken.discard(c.coursecode)
			taken.add(code)
			frappe.db.set_value("Course", c.name, "coursecode", code, update_modified=False)
			refresh_code_copies(c.name, code)
	if left:
		print(
			f"ADR 114: {len(left)} course(s) need a Course ID (code doesn't start with the unit's code): "
			+ ", ".join(left[:20])
		)
