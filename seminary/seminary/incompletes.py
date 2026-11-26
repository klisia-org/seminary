# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Incompletes (decisions/119 §1).

Before Send Grades the instructor marks a student Incomplete with a reason and a
completion date. That student doesn't count as ungraded, so the class's grades go
out and the course closes. The student's transcript row carries the scale's
Incomplete code and their roster stays active. The gradebook stays open for that
one student until the instructor sends their grade, or the date passes and the
daily job applies the school's lapse rule.

A date past the instructor's limit (Seminary Settings) needs an Incomplete
Extension Request, which the registrar decides.
"""

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, today

INCOMPLETE = "Incomplete"
COMPLETED = "Completed"
LAPSED = "Lapsed"
# Marks the individual due dates an Incomplete set, so clearing it removes only those.
OVERRIDE_TAG = "Incomplete"
OPEN_STATES = ("Enrollment Closed", "Grading")
ROSTER_FIELDS = [
	"name",
	"course_sc",
	"student",
	"stuname_roster",
	"program_std_scr",
	"audit_bool",
	"active",
	"incomplete",
	"incomplete_until",
	"incomplete_reason",
	"incomplete_reminder_sent",
	"incomplete_resolution",
]


# -- settings and dates -------------------------------------------------------------------


def _settings():
	return frappe.get_cached_doc("Seminary Settings")


def course_end(course_schedule):
	"""The day classes end: the section's end date, else its term's."""
	end, term = frappe.db.get_value("Course Schedule", course_schedule, ["c_dateend", "academic_term"])
	if not end and term:
		end = frappe.db.get_value("Academic Term", term, "term_end_date")
	return getdate(end) if end else getdate(today())


def default_until(course_schedule):
	return add_days(course_end(course_schedule), cint(_settings().incomplete_default_days) or 30)


def instructor_limit(course_schedule):
	"""The latest completion date an instructor may set without the registrar."""
	return getdate(
		add_days(course_end(course_schedule), cint(_settings().incomplete_instructor_max_days) or 0)
	)


def inc_code(course_schedule):
	scale = frappe.db.get_value("Course Schedule", course_schedule, "gradesc_cs")
	return (frappe.db.get_value("Grading Scale", scale, "inc_code") if scale else None) or None


def _roster(name):
	row = frappe.db.get_value("Scheduled Course Roster", name, ROSTER_FIELDS, as_dict=True)
	if not row:
		frappe.throw(_("Roster {0} not found.").format(name))
	return row


def _is_school():
	from seminary.seminary.api import SCHOOL_ROLES

	return bool(set(frappe.get_roles()) & SCHOOL_ROLES)


def _require_grader(course_schedule):
	from seminary.seminary.api import _assert_may_send_grades, _require_send_scope

	_assert_may_send_grades()
	_require_send_scope(course_schedule)


def is_open(roster):
	"""An Incomplete still being worked on: marked, and its grade not sent."""
	return bool(roster.incomplete and roster.active and not roster.incomplete_resolution)


# -- marking -----------------------------------------------------------------------------


@frappe.whitelist()
def mark_incomplete(roster: str, reason: str, until: str | date | None = None):
	"""Mark a student Incomplete before Send Grades."""
	row = _roster(roster)
	_require_grader(row.course_sc)
	state, open_ended = frappe.db.get_value(
		"Course Schedule", row.course_sc, ["workflow_state", "open_ended"]
	)
	if open_ended:
		frappe.throw(
			_("An open-ended section sends each student's grade when they finish; it has no Incompletes.")
		)
	if state not in OPEN_STATES:
		frappe.throw(_("A student can be marked Incomplete only before the course's grades are sent."))
	if not row.active or row.audit_bool:
		frappe.throw(_("This student's grade has already been sent, or they are auditing."))
	if not (reason or "").strip():
		frappe.throw(_("Give the reason for the Incomplete."))
	if not _unfinished_assessments(row.name):
		frappe.throw(_("This student has no unfinished work, so there is nothing to finish later."))
	if not inc_code(row.course_sc):
		frappe.throw(
			_("Set a 'Code for Incomplete' on the course's Grading Scale first."),
			title=_("No Incomplete code"),
		)
	until = getdate(until) if until else default_until(row.course_sc)
	if until <= getdate(today()):
		frappe.throw(_("The completion date must be after today."))
	limit = instructor_limit(row.course_sc)
	if until > limit and not _is_school():
		frappe.throw(
			_(
				"The latest date you can set is {0}. For more time, the student can file an "
				"Incomplete Extension Request, which the registrar decides."
			).format(frappe.format(limit, "Date"))
		)
	frappe.db.set_value(
		"Scheduled Course Roster",
		row.name,
		{
			"incomplete": 1,
			"incomplete_reason": reason.strip(),
			"incomplete_until": until,
			"incomplete_granted_by": frappe.session.user,
			"incomplete_reminder_sent": 0,
			"incomplete_resolution": None,
		},
	)
	extend_due_dates(row.name, until)
	return {"incomplete_until": str(until)}


@frappe.whitelist()
def clear_incomplete(roster: str):
	"""Take the mark back off, before Send Grades."""
	row = _roster(roster)
	_require_grader(row.course_sc)
	if not is_open(row):
		return
	state = frappe.db.get_value("Course Schedule", row.course_sc, "workflow_state")
	if state not in OPEN_STATES:
		frappe.throw(_("The course's grades are sent. Send this student's grade instead."))
	frappe.db.set_value(
		"Scheduled Course Roster",
		row.name,
		{
			"incomplete": 0,
			"incomplete_reason": None,
			"incomplete_until": None,
			"incomplete_granted_by": None,
			"incomplete_reminder_sent": 0,
		},
	)
	for name in frappe.get_all(
		"Student Due Date Override",
		filters={
			"course_schedule": row.course_sc,
			"student": row.student,
			"reason": ("like", f"{OVERRIDE_TAG}%"),
		},
		pluck="name",
	):
		frappe.delete_doc("Student Due Date Override", name, ignore_permissions=True)


def _unfinished_assessments(roster_name):
	"""The roster's cells still ungraded and not excused, as (card, assessment)."""
	return frappe.get_all(
		"Course Assess Results Detail",
		filters={
			"parent": roster_name,
			"parenttype": "Scheduled Course Roster",
			"graded_card": 0,
			"excused": 0,
		},
		fields=["name", "assessment_criteria"],
	)


def extend_due_dates(roster_name, until, source="Instructor"):
	"""Give the student until the end of `until` on every unfinished assessment.
	An existing individual date is moved later, never earlier."""
	row = _roster(roster_name)
	end = get_datetime(f"{getdate(until)} 23:59:59")
	reason = _("{0} until {1}").format(OVERRIDE_TAG, getdate(until))
	for cell in _unfinished_assessments(roster_name):
		if not cell.assessment_criteria:
			continue
		name = frappe.db.get_value(
			"Student Due Date Override",
			{"course_assess": cell.assessment_criteria, "student": row.student},
		)
		if name:
			doc = frappe.get_doc("Student Due Date Override", name)
			if doc.due_date and get_datetime(doc.due_date) >= end:
				continue
			doc.due_date = end
			if doc.cutoff_date:
				doc.cutoff_date = max(get_datetime(doc.cutoff_date), end)
			doc.reason = reason
			doc.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{
				"doctype": "Student Due Date Override",
				"course_schedule": row.course_sc,
				"course_assess": cell.assessment_criteria,
				"student": row.student,
				"due_date": end,
				"cutoff_date": end,
				"reason": reason,
				"source": source,
			}
		).insert(ignore_permissions=True)


# -- Send Grades -------------------------------------------------------------------------


def open_rosters(course_schedule):
	return frappe.get_all(
		"Scheduled Course Roster",
		filters={
			"course_sc": course_schedule,
			"active": 1,
			"audit_bool": 0,
			"incomplete": 1,
			"incomplete_resolution": ("in", ("", None)),
		},
		pluck="name",
	)


def record_incomplete(roster_name):
	"""Write the Incomplete onto the student's transcript row at Send Grades. No
	credits (status isn't Pass) and out of the GPA until the grade is sent: the
	numeric column can't be empty, so `count_in_gpa` carries it."""
	from seminary.seminary.api import _pe_and_pec

	row = _roster(roster_name)
	pe, pec = _pe_and_pec(row)
	if not pec:
		return None
	frappe.db.set_value(
		"Program Enrollment Course",
		pec,
		{
			"pec_finalgradecode": inc_code(row.course_sc),
			"pec_finalgradenum": 0,
			"status": INCOMPLETE,
			"count_in_gpa": 0,
		},
	)
	return pe


@frappe.whitelist()
def send_incomplete_grade(roster: str):
	"""The instructor sends one Incomplete student's grade after the course closed."""
	from seminary.seminary import absence_decisions
	from seminary.seminary.api import (
		_assert_evaluators_finished,
		_assert_pdp_complete,
		_ungraded_roster_count,
	)

	row = _roster(roster)
	_require_grader(row.course_sc)
	if not is_open(row):
		frappe.throw(_("This student has no open Incomplete."))
	if frappe.db.get_value("Course Schedule", row.course_sc, "workflow_state") != "Closed":
		frappe.throw(_("Clear the Incomplete and send the grade with the class instead."))
	if _ungraded_roster_count(row.course_sc, [row.name], include_incomplete=True):
		frappe.throw(_("Fill in every assessment (or 0 explicitly) before sending this grade."))
	_assert_evaluators_finished(row.course_sc, [row.name])
	_assert_pdp_complete(row.course_sc, [row.name])
	absence_decisions.assert_decided(row.course_sc, [row.name])
	return finish(row.name, COMPLETED)


def finish(roster_name, resolution):
	"""Finalize an Incomplete student as Send Grades would have."""
	from seminary.seminary import api
	from seminary.seminary.progression import after_grades_sent

	row = _roster(roster_name)
	_pe, pec = api._pe_and_pec(row)
	if pec:
		# Back into the GPA; finalize_roster sets it again for a competency section.
		frappe.db.set_value("Program Enrollment Course", pec, "count_in_gpa", 1)
	pe = api.finalize_roster(row.name)
	frappe.db.set_value("Scheduled Course Roster", row.name, "incomplete_resolution", resolution)
	api._conclude_enrollments(row.course_sc, [row.student])
	if pe:
		api._post_finalization([pe])
		after_grades_sent(row.course_sc, [pe])
	_notify(row, "incomplete-resolved", {"resolution": _(resolution)})
	return {"program_enrollment": pe, "resolution": resolution}


# -- daily job ---------------------------------------------------------------------------


def daily(today_=None):
	"""Remind before the completion date, and lapse after it."""
	day = getdate(today_) if today_ else getdate(today())
	days = cint(_settings().incomplete_reminder_days)
	rows = frappe.get_all(
		"Scheduled Course Roster",
		filters={"active": 1, "audit_bool": 0, "incomplete": 1, "incomplete_resolution": ("in", ("", None))},
		fields=ROSTER_FIELDS,
	)
	for row in rows:
		try:
			until = getdate(row.incomplete_until) if row.incomplete_until else None
			if not until:
				continue
			if until < day:
				lapse(row.name)
			elif days and not row.incomplete_reminder_sent and add_days(until, -days) <= day:
				_remind(row)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Incomplete job failed: {row.name}")


def unsubmitted(row):
	"""Titles of the unfinished assessments the student hasn't handed anything in for."""
	from seminary.seminary.deadlines import latest_submission

	out = []
	for cell in _unfinished_assessments(row.name):
		if cell.assessment_criteria and not latest_submission(cell.assessment_criteria, row.student):
			out.append(
				frappe.db.get_value("Scheduled Course Assess Criteria", cell.assessment_criteria, "title")
				or cell.assessment_criteria
			)
	return out


def _remind(row):
	missing = unsubmitted(row)
	if missing:
		_notify(
			row,
			"incomplete-reminder",
			{"due": frappe.format(row.incomplete_until, "Date"), "missing": ", ".join(missing)},
			registrar=False,
		)
	frappe.db.set_value("Scheduled Course Roster", row.name, "incomplete_reminder_sent", 1)


def lapse(roster_name):
	"""The completion date passed: send the grade. The scale's lapse code, when set,
	is the final grade; without one, unfinished work counts as 0."""
	row = _roster(roster_name)
	if not is_open(row):
		return None
	scale = frappe.db.get_value("Course Schedule", row.course_sc, "gradesc_cs")
	code = frappe.db.get_value("Grading Scale", scale, "lapse_code") if scale else None
	interval = None
	if code:
		interval = frappe.db.get_value(
			"Grading Scale Interval",
			{"parent": scale, "grade_code": code},
			["grade_code", "threshold", "grade_pass"],
			as_dict=True,
		)
		if not interval:
			frappe.log_error(
				f"Grading Scale {scale} has no lapse code among its grades; {roster_name} lapses as 0.",
				"Incomplete lapse: no lapse code",
			)
	_zero_unfinished(row.name)
	result = finish(row.name, LAPSED)
	if interval:
		_apply_lapse_code(row, interval)
	return result


def _zero_unfinished(roster_name):
	doc = frappe.get_doc("Scheduled Course Roster", roster_name)
	changed = False
	for card in doc.stdroster_grade or []:
		if not card.graded_card and not card.excused:
			card.rawscore_card = 0
			card.graded_card = 1
			changed = True
	if changed:
		doc.save(ignore_permissions=True)


def _apply_lapse_code(row, interval):
	"""Overwrite the computed grade with the scale's lapse code, then recount."""
	from seminary.seminary import api, repeats

	frappe.db.set_value(
		"Scheduled Course Roster",
		row.name,
		{
			"fgrade": interval.grade_code,
			"fgradepass": interval.grade_pass or "Fail",
			"fscore": interval.threshold,
		},
	)
	pe, pec = api._pe_and_pec(row)
	if not pec:
		return
	frappe.db.set_value(
		"Program Enrollment Course",
		pec,
		{
			"pec_finalgradecode": interval.grade_code,
			"pec_finalgradenum": interval.threshold,
			"status": interval.grade_pass or "Fail",
		},
	)
	repeats.recount(pe)
	api._post_finalization([pe])


# -- extension requests ------------------------------------------------------------------


def _notify(row, template, context=None, registrar=True):
	from seminary.seminary import comms
	from seminary.seminary.cs_lifecycle import _instructor_persons_for_cs

	cs = frappe.db.get_value("Course Schedule", row.course_sc, ["title", "academic_term"], as_dict=True) or {}
	ctx = {
		"course": cs.get("title") or row.course_sc,
		"term": cs.get("academic_term"),
		"student": row.stuname_roster or row.student,
		"until": frappe.format(row.incomplete_until, "Date") if row.incomplete_until else "",
		**(context or {}),
	}
	people = list(_instructor_persons_for_cs(row.course_sc))
	student_person = frappe.db.get_value("Student", row.student, "person")
	if student_person:
		people.append(student_person)
	for person in people:
		try:
			comms.send(
				person,
				template,
				context=ctx,
				reference_doctype="Scheduled Course Roster",
				reference_name=row.name,
				triggered_by=template,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"{template} notice failed: {row.name}")
	if registrar:
		try:
			comms.send_to_role(
				"Registrar",
				template,
				context=ctx,
				reference_doctype="Scheduled Course Roster",
				reference_name=row.name,
				triggered_by=template,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"{template} notice failed: {row.name}")


@frappe.whitelist()
def request_extension(roster: str, requested_until: str | date, reason: str):
	"""Student portal: ask for more time than the instructor may grant."""
	from seminary.seminary.guards import current_student

	row = _roster(roster)
	student = current_student()
	if not student or student != row.student:
		frappe.throw(_("You can only ask for an extension on your own course."), frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": "Incomplete Extension Request",
			"roster": row.name,
			"student": row.student,
			"requested_until": requested_until,
			"reason": reason,
		}
	)
	doc.insert()
	return doc.name


@frappe.whitelist()
def my_incompletes():
	"""Student portal: the student's open Incompletes and their requests."""
	from seminary.seminary.guards import current_student

	student = current_student()
	if not student:
		return []
	out = []
	for row in frappe.get_all(
		"Scheduled Course Roster",
		filters={
			"student": student,
			"active": 1,
			"incomplete": 1,
			"incomplete_resolution": ("in", ("", None)),
		},
		fields=ROSTER_FIELDS,
	):
		out.append(
			{
				"roster": row.name,
				"course_schedule": row.course_sc,
				"course": frappe.db.get_value("Course Schedule", row.course_sc, "title"),
				"until": row.incomplete_until,
				"reason": row.incomplete_reason,
				"unsubmitted": unsubmitted(row),
				"requests": frappe.get_all(
					"Incomplete Extension Request",
					filters={"roster": row.name},
					fields=["name", "status", "requested_until", "decision_note", "creation"],
					order_by="creation desc",
				),
			}
		)
	return out


# -- Incomplete Extension Request --------------------------------------------------------

REGISTRAR_ROLES = {"Registrar", "Seminary Manager", "System Manager"}


def fill_extension_request(doc):
	"""Incomplete Extension Request validate."""
	row = _roster(doc.roster)
	if doc.is_new():
		if not is_open(row):
			frappe.throw(_("This course has no open Incomplete to extend."))
		if frappe.db.exists("Incomplete Extension Request", {"roster": row.name, "status": "Open"}):
			frappe.throw(_("There is already an open extension request for this course."))
		doc.current_until = row.incomplete_until
		if getdate(doc.requested_until) <= getdate(row.incomplete_until):
			frappe.throw(
				_("Ask for a date after the current completion date, {0}.").format(
					frappe.format(row.incomplete_until, "Date")
				)
			)
	doc.course_schedule = row.course_sc
	doc.course_title = frappe.db.get_value("Course Schedule", row.course_sc, "title")
	doc.student = row.student
	doc.student_name = row.stuname_roster


def _require_registrar():
	if not set(frappe.get_roles()) & REGISTRAR_ROLES:
		frappe.throw(_("Only the registrar decides extension requests."), frappe.PermissionError)


@frappe.whitelist()
def approve_extension(name: str, note: str | None = None):
	from seminary.seminary.financial.backend import get_financial_backend

	_require_registrar()
	doc = frappe.get_doc("Incomplete Extension Request", name)
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	row = _roster(doc.roster)
	if not is_open(row):
		frappe.throw(_("The Incomplete is no longer open."))
	frappe.db.set_value(
		"Scheduled Course Roster",
		row.name,
		{"incomplete_until": doc.requested_until, "incomplete_reminder_sent": 0},
	)
	extend_due_dates(row.name, doc.requested_until, source="Registrar")
	doc.status = "Approved"
	doc.decided_by, doc.decided_on, doc.decision_note = frappe.session.user, frappe.utils.now_datetime(), note
	doc.charges = "\n".join(get_financial_backend().charge_incomplete_extension(doc.name) or [])
	doc.save(ignore_permissions=True)
	_notify(
		_roster(row.name),
		"incomplete-extension-decided",
		{"decision": _("approved"), "note": note or ""},
		registrar=False,
	)
	return doc.status


@frappe.whitelist()
def decline_extension(name: str, note: str):
	_require_registrar()
	doc = frappe.get_doc("Incomplete Extension Request", name)
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	if not (note or "").strip():
		frappe.throw(_("Say why the request is declined."))
	doc.status = "Declined"
	doc.decided_by, doc.decided_on, doc.decision_note = (
		frappe.session.user,
		frappe.utils.now_datetime(),
		note.strip(),
	)
	doc.save(ignore_permissions=True)
	_notify(
		_roster(doc.roster),
		"incomplete-extension-decided",
		{"decision": _("declined"), "note": note.strip()},
		registrar=False,
	)
	return doc.status


@frappe.whitelist()
def withdraw_extension(name: str):
	doc = frappe.get_doc("Incomplete Extension Request", name)
	if doc.owner != frappe.session.user:
		_require_registrar()
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	doc.status = "Withdrawn"
	doc.save(ignore_permissions=True)
	return doc.status
