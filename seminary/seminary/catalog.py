"""Course catalog rules (decisions/114): course codes that follow the academic unit,
replaced courses, and "any one of" prerequisite groups."""

import frappe
from frappe import _
from frappe.utils import strip_html_tags

from seminary.seminary.utils import is_url_safe_code

# Course Schedule and Course Competency store a fetched copy of the course code
# (fetch_from course.coursecode), which only refreshes when that record is saved,
# so a code change updates them here (114 §4). Assignment Activity's copy is a
# virtual field, read live.
CODE_COPIES = (
	("Course Schedule", "coursecode_cs"),
	("Course Competency", "coursecode"),
)


# --------------------------------------------------------------------------- #
# Course codes (§4)
# --------------------------------------------------------------------------- #
def unit_prefix(unit):
	if not unit:
		return ""
	return (frappe.db.get_value("Academic Unit", unit, "unit_code") or "").strip()


def course_code(course_id, prefix):
	course_id = (course_id or "").strip()
	return f"{prefix}-{course_id}" if prefix and course_id else course_id


def split_code(code, prefix):
	"""The Course ID inside ``code`` when it starts with ``prefix`` ("ST-501",
	"ST_501" or "ST501" give "501"), the whole code when there is no prefix,
	and None when the code doesn't start with the prefix."""
	code = (code or "").strip()
	if not code:
		return None
	if not prefix:
		return code
	if not code.upper().startswith(prefix.upper()):
		return None
	rest = code[len(prefix) :]
	if rest[:1] in ("-", "_"):
		rest = rest.lstrip("-_")
	elif not rest[:1].isdigit():
		return None  # "ST501" splits under "ST"; "ST501" under "S" does not
	return rest or None


def refresh_code_copies(course, code):
	for doctype, field in CODE_COPIES:
		frappe.db.set_value(doctype, {"course": course}, field, code, update_modified=False)


def rederive_unit_codes(unit, prefix):
	"""Re-derive the code of every course homed in ``unit`` after its prefix
	changed. Courses with no Course ID keep their code until someone gives them
	one (the 114 patch leaves those)."""
	for row in frappe.get_all(
		"Course",
		filters={"academic_unit": unit, "course_id": ["is", "set"]},
		fields=["name", "course_id", "coursecode"],
	):
		code = course_code(row.course_id, prefix)
		if code != row.coursecode:
			frappe.db.set_value("Course", row.name, "coursecode", code)
			refresh_code_copies(row.name, code)


def unit_code_clashes(unit, prefix):
	"""Codes that would collide with another course if ``unit`` took ``prefix``."""
	rows = frappe.get_all(
		"Course",
		filters={"academic_unit": unit, "course_id": ["is", "set"]},
		fields=["name", "course_id"],
	)
	clashes = []
	for row in rows:
		code = course_code(row.course_id, prefix)
		if frappe.db.exists("Course", {"coursecode": code, "name": ["!=", row.name]}):
			clashes.append(code)
	return clashes


def assert_url_safe_prefix(prefix):
	if prefix and not is_url_safe_code(prefix):
		frappe.throw(
			_(
				"The Code of a unit that owns courses may contain only letters, numbers, "
				"hyphens and underscores, because it starts every course code: {0}"
			).format(prefix)
		)


# --------------------------------------------------------------------------- #
# Replaced courses (§3)
# --------------------------------------------------------------------------- #
def replacements():
	"""{old course: {courses that replace it}}."""
	out = {}
	for row in frappe.get_all(
		"Replaced Course",
		filters={"parenttype": "Course", "parentfield": "replaced_courses"},
		fields=["parent", "course"],
	):
		out.setdefault(row.course, set()).add(row.parent)
	return out


def with_replacements(courses, replaced_by=None):
	"""``courses`` plus every course that replaces one of them, following chains
	(A replaced by B, B replaced by C)."""
	replaced_by = replacements() if replaced_by is None else replaced_by
	out = set(courses)
	todo = list(out)
	while todo:
		for newer in replaced_by.get(todo.pop(), ()):
			if newer not in out:
				out.add(newer)
				todo.append(newer)
	return out


def replaces_passed(course, passed):
	"""True when ``course`` counts as passed only because it replaces a course in
	``passed``: registering for it would count the same course twice."""
	return course not in passed and course in with_replacements(passed)


# --------------------------------------------------------------------------- #
# Prerequisites (§1, §2)
# --------------------------------------------------------------------------- #
def mandatory_prerequisites(course):
	"""[[course, ...], ...]: each inner list must have one course satisfied. A
	course required on its own is a list of one; a group lists its options."""
	singles, groups = [], {}
	for row in frappe.get_all(
		"Course_prerequisite",
		filters={"parent": course, "parenttype": "Course", "prereq_mandatory": "Mandatory"},
		fields=["course", "prereq_group"],
		order_by="idx asc",
	):
		if row.prereq_group:
			groups.setdefault(row.prereq_group, []).append(row.course)
		else:
			singles.append([row.course])
	return singles + list(groups.values())


def any_of_label(options):
	if len(options) == 1:
		return options[0]
	return _("{0} or {1}").format(", ".join(options[:-1]), options[-1])


def prerequisite_counted(pe_name):
	"""Courses graded and not failed on the enrollment: the long-standing
	prerequisite rule, before exceptions and replacements are added."""
	return set(
		frappe.get_all(
			"Program Enrollment Course",
			filters={
				"parent": pe_name,
				"pec_finalgradecode": ["is", "set"],
				"status": ["!=", "Fail"],
			},
			pluck="course_name",
		)
	)


def prerequisite_satisfied(pe_name):
	"""What satisfies a prerequisite for this enrollment: graded non-Fail courses,
	058 exemptions, approved 098 waivers and substitutions, and replacements."""
	from seminary.seminary.exceptions import satisfied_courses

	return satisfied_courses(pe_name, counted=prerequisite_counted(pe_name))


def unmet_prerequisites(pe_name, course, satisfied=None):
	"""Labels of the mandatory prerequisites (or "A or B" groups) that ``pe_name``
	has not satisfied for ``course``. Empty when all are met."""
	needs = mandatory_prerequisites(course)
	if not needs:
		return []
	if satisfied is None:
		satisfied = prerequisite_satisfied(pe_name)
	return [any_of_label(options) for options in needs if not set(options) & satisfied]


def validate_prerequisite_rows(doc):
	"""Course.validate: a group needs two courses, a Recommended row takes no
	group, and a course is not its own prerequisite."""
	groups = {}
	for row in doc.get("course_prerequisite") or []:
		if row.course == doc.name:
			frappe.throw(_("Row {0}: a course can't be its own prerequisite.").format(row.idx))
		if not row.prereq_group:
			continue
		if row.prereq_mandatory != "Mandatory":
			frappe.throw(
				_("Row {0}: only a Mandatory prerequisite can be in an Any-One-Of Group.").format(row.idx)
			)
		groups.setdefault(row.prereq_group, []).append(row.course)
	for number, courses in groups.items():
		if len(set(courses)) < 2:
			frappe.throw(
				_(
					"Any-One-Of Group {0} has only one course ({1}). A group needs at least two; "
					"check the group number or leave it blank."
				).format(number, courses[0])
			)


def validate_replaced_rows(doc):
	"""Course.validate: no self, no duplicates, and no cycle. A cycle would make
	two courses count as each other, the cross-listing 059 §6 rejected."""
	seen = set()
	for row in doc.get("replaced_courses") or []:
		if row.course == doc.name:
			frappe.throw(_("Row {0}: a course can't replace itself.").format(row.idx))
		if row.course in seen:
			frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, row.course))
		seen.add(row.course)
	if not seen or doc.is_new():
		return
	replaced_by = replacements()
	for newers in replaced_by.values():
		newers.discard(doc.name)  # this course's own rows, as they were before the edit
	if any(older in with_replacements({doc.name}, replaced_by) for older in seen):
		frappe.throw(
			_(
				"{0} already counts as one of these courses, so they would count as each other. "
				"A course shared by two departments belongs in one record homed in an Academic "
				"Interdepartment."
			).format(doc.name)
		)


# --------------------------------------------------------------------------- #
# Display (§6)
# --------------------------------------------------------------------------- #
def jointly_offered_by(unit):
	"""Names of the member units when ``unit`` is an Academic Interdepartment."""
	if not unit or frappe.db.get_value("Academic Unit", unit, "unit_type") != "Academic Interdepartment":
		return []
	members = frappe.get_all(
		"Academic Unit Constituent",
		filters={"parent": unit, "parenttype": "Academic Unit"},
		pluck="member_unit",
		order_by="idx asc",
	)
	if not members:
		return []
	names = {
		r.name: r.unit_name
		for r in frappe.get_all(
			"Academic Unit", filters={"name": ["in", members]}, fields=["name", "unit_name"]
		)
	}
	return [names.get(m) or m for m in members]


def joint_label(unit):
	names = jointly_offered_by(unit)
	if not names:
		return ""
	if len(names) == 1:
		return names[0]
	return _("{0} and {1}").format(", ".join(names[:-1]), names[-1])


def program_courses(program):
	"""The public program page's course list: active program courses that are not
	retired, with code, credits, a short description, prerequisites and the
	joint-offering line."""
	rows = [pc for pc in (program.courses or []) if not pc.disabled and pc.course]
	if not rows:
		return []
	courses = {
		c.name: c
		for c in frappe.get_all(
			"Course",
			filters={"name": ["in", [pc.course for pc in rows]], "disabled": 0},
			fields=["name", "course_name", "coursecode", "course_credits", "description", "academic_unit"],
		)
	}
	out = []
	for pc in rows:
		c = courses.get(pc.course)
		if not c:
			continue
		description = strip_html_tags(c.description or "").strip()
		if len(description) > 220:
			description = description[:220].rsplit(" ", 1)[0] + "…"
		needs = mandatory_prerequisites(c.name)
		out.append(
			frappe._dict(
				code=c.coursecode,
				name=c.course_name or c.name,
				credits=pc.pgmcourse_credits or c.course_credits,
				description=description,
				prerequisites=[any_of_label(o) for o in needs],
				prerequisite_options=needs,
				joint=joint_label(c.academic_unit),
			)
		)
	return out
