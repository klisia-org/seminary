# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Repeated courses (decisions/119 §4).

A second final grade for the same course, or for a course that replaces it
(decisions/114 §3), in the same Program Enrollment is a repeat. Nobody enters it:
`apply` derives it from the transcript rows after every finalize. The Program's
`repeat_policy` picks the attempt that counts (*Most recent* or *Highest*). The
others stay on the transcript, marked Repeated, with no credits and out of the
GPA. Transfer rows are left alone: they are evaluated, not attempted here.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

MOST_RECENT = "Most recent"
HIGHEST = "Highest"
COMPETING = ("Pass", "Fail")


def _families(replaced_by):
	"""{course: family key}: a course and every course that replaces it, chained,
	share one key."""
	parent = {}

	def find(x):
		parent.setdefault(x, x)
		while parent[x] != x:
			parent[x] = parent[parent[x]]
			x = parent[x]
		return x

	for old, newer in replaced_by.items():
		for n in newer:
			a, b = find(old), find(n)
			if a != b:
				parent[a] = b
	return find


def _rows(pe_name):
	return frappe.db.sql(
		"""SELECT pec.name, pec.course, pec.course_name, pec.status, pec.pec_finalgradenum,
		          pec.pec_finalgradecode, pec.credits, pec.count_in_gpa, pec.repeated, pec.attempt,
		          pec.creation, COALESCE(at.term_start_date, cs.c_datestart) AS started
		   FROM `tabProgram Enrollment Course` pec
		   LEFT JOIN `tabCourse Schedule` cs ON cs.name = pec.course
		   LEFT JOIN `tabAcademic Term` at ON at.name = COALESCE(pec.academic_term, cs.academic_term)
		   WHERE pec.parent = %s AND pec.parenttype = 'Program Enrollment'
		     AND COALESCE(pec.is_transfer, 0) = 0
		     AND COALESCE(pec.course_name, '') != ''""",
		(pe_name,),
		as_dict=True,
	)


def _order(row):
	return (str(row.started or ""), str(row.creation or ""))


def groups(pe_name):
	"""{family: [rows in attempt order]} for this enrollment."""
	from seminary.seminary.catalog import replacements

	key = _families(replacements())
	out = {}
	for row in _rows(pe_name):
		out.setdefault(key(row.course_name), []).append(row)
	for rows in out.values():
		rows.sort(key=_order)
	return out


def counting(rows, policy):
	"""The attempt that counts among graded attempts, or None."""
	graded = [r for r in rows if r.status in COMPETING and r.pec_finalgradecode]
	if not graded:
		return None
	if policy == HIGHEST:
		best = max(flt(r.pec_finalgradenum) for r in graded)
		return [r for r in graded if flt(r.pec_finalgradenum) == best][-1]
	return graded[-1]


def apply(pe_name):
	"""Mark repeats and restore the counting attempt. Returns True when a row
	changed (credits were then recounted)."""
	from seminary.seminary.api import _cbe_count_in_gpa
	from seminary.seminary.catalog_year import course_credits

	program = frappe.db.get_value("Program Enrollment", pe_name, "program")
	if not program:
		return False
	policy = frappe.db.get_value("Program", program, "repeat_policy") or MOST_RECENT
	changed = False
	for rows in groups(pe_name).values():
		keep = counting(rows, policy) if len(rows) > 1 else None
		graded = {r.name for r in rows if r.status in COMPETING and r.pec_finalgradecode}
		for n, row in enumerate(rows, start=1):
			values = {}
			if cint(row.attempt) != (n if len(rows) > 1 else 0):
				values["attempt"] = n if len(rows) > 1 else 0
			repeated = bool(keep and row.name in graded and row.name != keep.name)
			if repeated and not row.repeated:
				values.update(repeated=1, count_in_gpa=0, credits=0)
			elif not repeated and row.repeated:
				flag = _cbe_count_in_gpa(row.course) if row.course else None
				values.update(
					repeated=0,
					count_in_gpa=1 if flag is None else flag,
					credits=course_credits(pe_name, row.course_name),
				)
			if values:
				frappe.db.set_value("Program Enrollment Course", row.name, values, update_modified=False)
				changed = changed or set(values) != {"attempt"}
	if changed:
		recount(pe_name)
	return changed


def recount(pe_name):
	"""Re-sum credits from passing rows (repeated rows carry 0)."""
	from seminary.seminary.doctype.partner_transcript_import_batch.partner_transcript_import_batch import (
		_refresh_totalcredits,
	)

	_refresh_totalcredits(pe_name)


def attempts_of(pe_name, course):
	"""Earlier attempts at `course` (or a course it replaces, or that replaces it),
	not counting withdrawn or cancelled enrollments that never reached a grade."""
	from seminary.seminary.catalog import replacements

	key = _families(replacements())
	mine = key(course)
	return [
		r
		for r in _rows(pe_name)
		if key(r.course_name) == mine and (r.pec_finalgradecode or r.status in COMPETING)
	]


def assert_attempts_left(pe_name, course):
	"""Refuse an enrollment past the Program's `max_attempts`, unless the
	registrar enrolls the student."""
	from seminary.seminary.api import SCHOOL_ROLES

	if not pe_name or not course:
		return
	program = frappe.db.get_value("Program Enrollment", pe_name, "program")
	limit = cint(frappe.db.get_value("Program", program, "max_attempts")) if program else 0
	if not limit or set(frappe.get_roles()) & SCHOOL_ROLES:
		return
	if len(attempts_of(pe_name, course)) >= limit:
		frappe.throw(
			_(
				"You have taken {0} the most times the program allows ({1}). Ask the registrar to enroll you."
			).format(frappe.db.get_value("Course", course, "course_name") or course, limit),
			title=_("Attempt limit reached"),
		)
