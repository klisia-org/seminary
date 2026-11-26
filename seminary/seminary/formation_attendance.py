# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Formation attendance requirements (decisions/116).

Chapel (029) and cohort meetings (101 §7) count toward graduation through the
student's Student Graduation Requirement (SGR) rows. A row is measured by
Count (attend N) or Percentage (attend a share of those held, over the whole
program or each term). The rate is always derived from the attendance records,
never stored as an input: Excused occasions and occasions on a leave-of-absence
day (081 §3) are left out of the base.

``evaluate`` is the pure decision; the readers turn records into occasions.
"""

import frappe
from frappe.utils import cint, getdate, now_datetime, today

from seminary.seminary.attendance import leave_periods, on_leave

CHAPEL = "Chapel Attendance"
COHORT = "Cohort Meeting Attendance"
TYPES = (CHAPEL, COHORT)
COUNT, PERCENTAGE = "Count", "Percentage"
WHOLE, EACH_TERM = "Whole program", "Each term"
PRESENT, ABSENT, EXCUSED = "Present", "Absent", "Excused"


# ---------------------------------------------------------------- snapshot


def snapshot_fields(library):
	"""SGR fields frozen from the Graduation Requirement Item (ADR 012)."""
	measure = library.get("attendance_measure") or COUNT
	row = {
		"attendance_measure": measure,
		"attended_count": 0,
		"counted_cohort_types": "\n".join(
			r.cohort_type for r in (library.get("cohort_types") or []) if r.cohort_type
		)
		if library.requirement_type == COHORT
		else None,
	}
	if measure == PERCENTAGE:
		row.update(
			{
				"percentage_period": library.get("percentage_period") or WHOLE,
				"required_percentage": cint(library.default_quantity) or 100,
				"minimum_held": cint(library.get("minimum_held")),
			}
		)
	else:
		row["required_count"] = cint(library.default_quantity) or 1
	return row


# ---------------------------------------------------------------- decision


def _rate(present, base):
	return round(100.0 * present / base, 1) if base else 0.0


def evaluate(row, occasions, terms=()):
	"""Status and figures for one SGR row.

	``occasions`` is a list of ``(date, status)`` or ``(date, status, on_leave)``
	where status is Present, Absent or Excused. Excused and on-leave occasions
	are left out of a percentage's base. ``terms`` is a
	list of ``(label, start, end)`` completed terms, oldest first.

	Returns a dict with status, attended_count, attendance_rate, term_rates.
	"""
	present = sum(1 for o in occasions if o[1] == PRESENT)
	measure = row.get("attendance_measure") or COUNT
	out = {"attended_count": present, "attendance_rate": 0.0, "term_rates": None}

	if measure != PERCENTAGE:
		required = cint(row.get("required_count")) or 1
		out["status"] = "Fulfilled" if present >= required else ("In Progress" if present else "Not Started")
		return out

	target = cint(row.get("required_percentage")) or 100
	minimum = max(cint(row.get("minimum_held")), 1)

	def counted(items):
		base = [o for o in items if o[1] != EXCUSED and not (len(o) > 2 and o[2])]
		return sum(1 for o in base if o[1] == PRESENT), len(base)

	if (row.get("percentage_period") or WHOLE) == WHOLE:
		p, base = counted(occasions)
		out["attendance_rate"] = _rate(p, base)
		if base >= minimum and out["attendance_rate"] >= target:
			out["status"] = "Fulfilled"
		else:
			out["status"] = "In Progress" if (base or present) else "Not Started"
		return out

	judged, lines = [], []
	for label, start, end in terms:
		start, end = getdate(start), getdate(end)
		p, base = counted([o for o in occasions if start <= getdate(o[0]) <= end])
		if base < minimum:
			continue
		rate = _rate(p, base)
		judged.append(rate)
		lines.append(f"{label}: {rate:g}%")
	out["term_rates"] = "\n".join(lines) or None
	if judged:
		out["attendance_rate"] = judged[-1]
	if judged and all(r >= target for r in judged):
		out["status"] = "Fulfilled"
	else:
		out["status"] = "In Progress" if (occasions or present) else "Not Started"
	return out


# ---------------------------------------------------------------- readers


def _since(pe):
	return getdate(pe.enrollment_date) if pe.enrollment_date else None


def chapel_occasions(student, since=None):
	"""Every confirmed chapel already started (since ``since``), with the
	student's status: Present, Excused, or Absent when there is no record.
	"""
	filters = {"confirmed": 1, "starts_on": ["<=", now_datetime()]}
	if since:
		filters["starts_on"] = ["between", [since, now_datetime()]]
	held = frappe.get_all("Chapel", filters=filters, fields=["name", "starts_on"])
	marks = {
		r.chapel: r.status
		for r in frappe.get_all(
			"Chapel Attendance", filters={"student": student}, fields=["chapel", "status"]
		)
	}
	return [(getdate(c.starts_on), marks.get(c.name, ABSENT)) for c in held]


def chapel_present_count(student, since=None):
	"""Count mode keeps 029's rule: every Present record since enrollment,
	whether or not the chapel is still marked confirmed."""
	filters = {"student": student, "status": PRESENT}
	if since:
		filters["check_in_time"] = [">=", since]
	return frappe.db.count("Chapel Attendance", filters)


def cohort_occasions(person, cohort_types, since=None):
	"""Scheduled meetings already started of cohorts of these types, where the
	leader marked this person. Unmarked rows are not counted at all."""
	if not (person and cohort_types):
		return []
	rows = frappe.db.sql(
		"""
		SELECT m.starts_on, a.status
		FROM `tabCohort Meeting` m
		JOIN `tabCohort Meeting Attendance` a
		  ON a.parent = m.name AND a.parenttype = 'Cohort Meeting'
		JOIN `tabCohort` c ON c.name = m.cohort
		WHERE a.person = %(person)s
		  AND a.status IN ('Present', 'Absent', 'Excused')
		  AND m.status = 'Scheduled'
		  AND m.starts_on <= %(now)s
		  AND (%(since)s IS NULL OR m.starts_on >= %(since)s)
		  AND c.cohort_type IN %(types)s
		""",
		{"person": person, "now": now_datetime(), "since": since, "types": tuple(cohort_types)},
		as_dict=True,
	)
	return [(getdate(r.starts_on), r.status) for r in rows]


def completed_terms(since=None):
	"""Academic terms already over, overlapping the enrollment, oldest first."""
	filters = [["term_end_date", "<", today()]]
	if since:
		filters.append(["term_end_date", ">=", since])
	return [
		(t.title or t.name, t.term_start_date, t.term_end_date)
		for t in frappe.get_all(
			"Academic Term",
			filters=filters,
			fields=["name", "title", "term_start_date", "term_end_date"],
			order_by="term_start_date asc",
		)
		if t.term_start_date and t.term_end_date
	]


# ---------------------------------------------------------------- recompute


def _with_leave(occasions, periods):
	return [(d, s, on_leave(d, periods)) for d, s in occasions] if periods else occasions


def _apply(row, result):
	"""Write ``result`` onto ``row``; True when anything changed. A row that
	stays Fulfilled keeps its first fulfilled_on."""
	changed = False
	for field in ("attended_count", "attendance_rate", "term_rates"):
		if (row.get(field) or None) != (result.get(field) or None):
			row.set(field, result.get(field))
			changed = True
	status = result["status"]
	if row.status != status:
		row.status = status
		row.fulfilled_on = today() if status == "Fulfilled" else None
		changed = True
	elif status != "Fulfilled" and row.fulfilled_on:
		row.fulfilled_on = None
		changed = True
	return changed


def recompute_enrollment(pe):
	pe = pe if hasattr(pe, "doctype") else frappe.get_doc("Program Enrollment", pe)
	rows = [
		r
		for r in (pe.graduation_requirements or [])
		if r.requirement_type in TYPES and not (r.waived or r.status == "Waived")
	]
	if not rows:
		return False
	since = _since(pe)
	periods = leave_periods(pe.student, pe.program)
	person = frappe.db.get_value("Student", pe.student, "person")
	terms, cache, changed = None, {}, False

	def occasions_for(row):
		if row.requirement_type == CHAPEL:
			key = (CHAPEL,)
			if key not in cache:
				cache[key] = _with_leave(chapel_occasions(pe.student, since), periods)
		else:
			types = tuple(sorted(t for t in (row.counted_cohort_types or "").split("\n") if t))
			key = (COHORT, types)
			if key not in cache:
				cache[key] = _with_leave(cohort_occasions(person, types, since), periods)
		return cache[key]

	for row in rows:
		percentage = row.attendance_measure == PERCENTAGE
		if row.requirement_type == CHAPEL and not percentage:
			# 029's rule: every Present record since enrollment.
			result = evaluate(row, [(None, PRESENT)] * chapel_present_count(pe.student, since))
		else:
			if percentage and row.percentage_period == EACH_TERM and terms is None:
				terms = completed_terms(since)
			result = evaluate(row, occasions_for(row), terms or ())
		changed |= _apply(row, result)
	if changed:
		pe.save(ignore_permissions=True)
	return changed


def recompute_for_student(student):
	if not student:
		return
	for pe in frappe.get_all(
		"Program Enrollment", filters={"student": student, "docstatus": 1}, pluck="name"
	):
		recompute_enrollment(pe)


def recompute_for_people(people):
	people = [p for p in set(people or []) if p]
	if not people:
		return
	for student in frappe.get_all("Student", filters={"person": ["in", people]}, pluck="name"):
		recompute_for_student(student)


# ---------------------------------------------------------------- hooks


def on_chapel_attendance(doc, method=None):
	"""Chapel Attendance on_update / after_delete."""
	recompute_for_student(doc.get("student"))


def on_chapel_change(doc, method=None):
	"""Chapel on_update / after_delete: a chapel confirmed, moved or removed
	changes the base of every percentage row."""
	before = doc.get_doc_before_save() if method == "on_update" else None
	if before and (before.confirmed, str(before.starts_on)) == (doc.confirmed, str(doc.starts_on)):
		return
	frappe.enqueue(
		"seminary.seminary.formation_attendance.recompute_percentage_rows",
		requirement_type=CHAPEL,
		enqueue_after_commit=True,
	)


def on_cohort_meeting(doc, method=None):
	"""Cohort Meeting on_update: recompute the members whose marked row or
	whose meeting (cancelled, moved) changed."""
	before = doc.get_doc_before_save()
	now = {a.person: a.status for a in doc.attendance or []}
	if not before:
		touched = [p for p, s in now.items() if s]
	else:
		old = {a.person: a.status for a in before.attendance or []}
		if (before.status, str(before.starts_on)) != (doc.status, str(doc.starts_on)):
			touched = [p for p in set(old) | set(now) if old.get(p) or now.get(p)]
		else:
			touched = [p for p in set(old) | set(now) if old.get(p) != now.get(p)]
	recompute_for_people(touched)


def recompute_percentage_rows(requirement_type=None):
	"""Every student with a percentage row (of one type, or both). Run daily so
	an occasion held but not attended lowers the rate, and a term that has just
	ended is judged."""
	filters = {
		"parenttype": "Program Enrollment",
		"requirement_type": ["in", [requirement_type] if requirement_type else list(TYPES)],
		"attendance_measure": PERCENTAGE,
		"waived": 0,
	}
	parents = list(set(frappe.get_all("Student Graduation Requirement", filters=filters, pluck="parent")))
	if not parents:
		return
	for pe in frappe.get_all(
		"Program Enrollment", filters={"name": ["in", parents], "docstatus": 1}, pluck="name"
	):
		try:
			recompute_enrollment(pe)
		except Exception:
			frappe.log_error(title=f"Formation attendance recompute failed for {pe}")


def daily():
	recompute_percentage_rows()
