# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Chapel attendance: student self check-in + count-based graduation fulfilment.

Chapel is a public, recurring Event (all students/instructors invited). A
graduation requirement of type "Chapel Attendance" is *count-based* ("attend N
chapels"), unlike ADR 028's single-occurrence "Event Attendance". Students self
check-in from the portal; each check-in is a Chapel Attendance record, and the
running count is reflected onto the student's Chapel Attendance Student
Graduation Requirement (SGR) rows. Kept separate from events.py on purpose.
"""

import hmac

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, get_datetime, now_datetime

from seminary.seminary import security_log
from seminary.seminary.utils import get_current_student

SGR_DOCTYPE = "Student Graduation Requirement"
CHAPEL_REQUIREMENT_TYPE = "Chapel Attendance"


# ---------------------------------------------------------------------------
# Check-in window / code
# ---------------------------------------------------------------------------


def _checkin_bounds(chapel_doc, settings):
	"""(open_dt, close_dt) for self check-in, or None when the window is
	disabled (both settings 0 → check-in allowed any time)."""
	before = int(settings.chapel_checkin_opens_before_mins or 0)
	after = int(settings.chapel_checkin_closes_after_mins or 0)
	if before == 0 and after == 0:
		return None
	start = get_datetime(chapel_doc.starts_on)
	end = get_datetime(chapel_doc.ends_on) if chapel_doc.get("ends_on") else start
	return add_to_date(start, minutes=-before), add_to_date(end, minutes=after)


def _is_open_now(chapel_doc, settings, now=None):
	bounds = _checkin_bounds(chapel_doc, settings)
	if bounds is None:
		return True
	now = now or now_datetime()
	return bounds[0] <= now <= bounds[1]


def _validate_window(chapel_doc, settings):
	if not _is_open_now(chapel_doc, settings):
		frappe.throw(_("Check-in for this chapel is not open right now."))


def _validate_code(chapel_doc, settings, code):
	if not settings.require_chapel_checkin_code:
		return
	expected = (chapel_doc.checkin_code or "").strip().upper()
	given = (code or "").strip().upper()
	# See `course_checkin._validate_code` for why the code stays short.
	# Bytes, not str: `compare_digest` raises TypeError on a non-ASCII str, so
	# a student typing an accented character would get a 500 instead of
	# "incorrect code".
	if not expected or not hmac.compare_digest(
		given.encode("utf-8", "ignore"), expected.encode("utf-8", "ignore")
	):
		security_log.record_denial("checkin_code", kind_of="chapel")
		frappe.throw(_("Incorrect or missing check-in code."))


# ---------------------------------------------------------------------------
# Student self check-in (portal)
# ---------------------------------------------------------------------------


def _active_enrollment(student):
	"""A submitted Program Enrollment for this student, preferring one that
	carries a Chapel Attendance requirement. Informational on the record;
	fulfilment recomputes across all enrollments regardless."""
	with_req = frappe.db.sql(
		"""
        SELECT pe.name
        FROM `tabProgram Enrollment` pe
        JOIN `tabStudent Graduation Requirement` sgr ON sgr.parent = pe.name
        WHERE pe.student = %(student)s AND pe.docstatus = 1
          AND sgr.parenttype = 'Program Enrollment'
          AND sgr.requirement_type = %(t)s
        ORDER BY pe.creation DESC
        LIMIT 1
        """,
		{"student": student, "t": CHAPEL_REQUIREMENT_TYPE},
	)
	if with_req:
		return with_req[0][0]
	return frappe.db.get_value("Program Enrollment", {"student": student, "docstatus": 1}, "name")


@frappe.whitelist()
@rate_limit(key="chapel", limit=20, seconds=3600, ip_based=False)
def check_in(chapel: str, code: str | None = None):
	"""Student self check-in to a chapel. Validates the chapel is confirmed,
	the check-in window (unless disabled), and the code (if required); rejects
	duplicates. Returns the student's updated Chapel Attendance progress."""
	student = get_current_student()
	if not student:
		frappe.throw(_("Only enrolled students can check in to chapel."), frappe.PermissionError)

	chapel_doc = frappe.get_doc("Chapel", chapel)
	if not chapel_doc.confirmed:
		frappe.throw(_("This chapel is not open for check-in yet."))

	settings = frappe.get_cached_doc("Seminary Settings")
	_validate_window(chapel_doc, settings)
	_validate_code(chapel_doc, settings, code)

	existing = frappe.db.get_value(
		"Chapel Attendance", {"chapel": chapel, "student": student.name}, ["name", "status"], as_dict=True
	)
	if existing and existing.status != "Excused":
		frappe.throw(_("You have already checked in to this chapel."))
	if existing:
		# Excused ahead, but came after all (decisions/116 §5).
		doc = frappe.get_doc("Chapel Attendance", existing.name)
		doc.status, doc.method, doc.check_in_time = "Present", "Self check-in", now_datetime()
		doc.save(ignore_permissions=True)
		return _student_progress(student.name)

	frappe.get_doc(
		{
			"doctype": "Chapel Attendance",
			"chapel": chapel,
			"student": student.name,
			"program_enrollment": _active_enrollment(student.name),
			"check_in_time": now_datetime(),
			"status": "Present",
			"method": "Self check-in",
		}
	).insert(ignore_permissions=True)

	return _student_progress(student.name)


@frappe.whitelist()
def get_chapel_status():
	"""Portal feed: recent confirmed chapels (with open-for-check-in / already-
	checked-in flags) plus the student's Chapel Attendance requirement progress."""
	student = get_current_student()
	if not student:
		return {"chapels": [], "requires_code": False, "progress": []}

	settings = frappe.get_cached_doc("Seminary Settings")
	now = now_datetime()
	checked_in = set(
		frappe.get_all(
			"Chapel Attendance", filters={"student": student.name, "status": "Present"}, pluck="chapel"
		)
	)
	requires_code = bool(settings.require_chapel_checkin_code)

	chapels = []
	for c in frappe.get_all(
		"Chapel",
		filters={"confirmed": 1},
		fields=["name", "chapel_topic", "starts_on", "ends_on", "room"],
		order_by="starts_on desc",
		limit=20,
	):
		chapels.append(
			{
				**c,
				"open_for_checkin": _is_open_now(frappe._dict(c), settings, now),
				"already_checked_in": c.name in checked_in,
			}
		)

	return {
		"chapels": chapels,
		"requires_code": requires_code,
		"progress": _student_progress(student.name),
	}


def _student_progress(student):
	return frappe.db.sql(
		"""
        SELECT sgr.name AS sgr_name, sgr.requirement_name, sgr.status,
               sgr.required_count, sgr.attended_count, sgr.attendance_measure,
               sgr.percentage_period, sgr.required_percentage, sgr.attendance_rate,
               pe.name AS program_enrollment, pe.program
        FROM `tabStudent Graduation Requirement` sgr
        JOIN `tabProgram Enrollment` pe ON pe.name = sgr.parent
        WHERE sgr.parenttype = 'Program Enrollment'
          AND sgr.requirement_type = %(t)s
          AND pe.student = %(student)s AND pe.docstatus = 1
        ORDER BY pe.name
        """,
		{"student": student, "t": CHAPEL_REQUIREMENT_TYPE},
		as_dict=True,
	)


# ---------------------------------------------------------------------------
# Roll (decisions/116 §5). Fulfilment lives in formation_attendance.
# ---------------------------------------------------------------------------

ROLL_ROLES = ("Chaplain", "Seminary Manager", "Program Chair", "System Manager")


def _require_roll_taker():
	if not set(ROLL_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("Only a chaplain or school staff can take the chapel roll."), frappe.PermissionError)


def _roll_students():
	"""Students on a submitted enrollment that carries a Chapel Attendance
	requirement: those the roll is taken for."""
	return frappe.db.sql(
		"""
        SELECT DISTINCT pe.student AS student, pe.student_name AS student_name
        FROM `tabProgram Enrollment` pe
        JOIN `tabStudent Graduation Requirement` sgr ON sgr.parent = pe.name
        WHERE pe.docstatus = 1 AND pe.pgmenrol_active = 1
          AND sgr.parenttype = 'Program Enrollment'
          AND sgr.requirement_type = %(t)s
        ORDER BY pe.student_name
        """,
		{"t": CHAPEL_REQUIREMENT_TYPE},
		as_dict=True,
	)


@frappe.whitelist()
def search_contacts(
	doctype: str,
	txt: str | None,
	searchfield: str | None,
	start: int | str,
	page_len: int | str,
	filters: dict | str | None,
):
	"""Contact picker for the Chapel Team: a chaplain has no read on Contact."""
	_require_roll_taker()
	like = f"%{txt or ''}%"
	return frappe.db.sql(
		"""
        SELECT name, full_name, email_id FROM `tabContact`
        WHERE name LIKE %(t)s OR full_name LIKE %(t)s OR email_id LIKE %(t)s
        ORDER BY full_name LIMIT %(start)s, %(len)s
        """,
		{"t": like, "start": int(start or 0), "len": int(page_len or 20)},
	)


@frappe.whitelist()
def get_roll(chapel: str):
	"""The chapel's roll: every student it is taken for, plus anyone already
	recorded, with their status (blank when not recorded)."""
	_require_roll_taker()
	frappe.get_doc("Chapel", chapel).check_permission("read")
	marks = {
		r.student: r
		for r in frappe.get_all(
			"Chapel Attendance",
			filters={"chapel": chapel},
			fields=["student", "student_name", "status", "method"],
		)
	}
	rows = {
		s.student: {"student": s.student, "student_name": s.student_name, "status": "", "method": ""}
		for s in _roll_students()
	}
	for student, m in marks.items():
		rows[student] = {
			"student": student,
			"student_name": m.student_name or rows.get(student, {}).get("student_name"),
			"status": m.status,
			"method": m.method,
		}
	return sorted(rows.values(), key=lambda r: (r["student_name"] or r["student"]).lower())


@frappe.whitelist(methods=["POST"])
def save_roll(chapel: str, rows: str | list):
	"""Set each student's status on this chapel: Present, Excused, or blank to
	remove the record. Excused may be set ahead; Present only once the chapel
	has started."""
	_require_roll_taker()
	chapel_doc = frappe.get_doc("Chapel", chapel)
	chapel_doc.check_permission("write")
	if not chapel_doc.confirmed:
		frappe.throw(_("Confirm the chapel before taking its roll."))
	started = get_datetime(chapel_doc.starts_on) <= now_datetime()
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	existing = {
		r.student: r
		for r in frappe.get_all(
			"Chapel Attendance", filters={"chapel": chapel}, fields=["name", "student", "status"]
		)
	}
	for r in rows or []:
		student, status = r.get("student"), (r.get("status") or "").strip()
		if not student:
			continue
		if status not in ("", "Present", "Excused"):
			frappe.throw(_("Mark Present or Excused, or leave blank."))
		if status == "Present" and not started:
			frappe.throw(_("Present is marked once the chapel has started."))
		have = existing.get(student)
		if not status:
			if have:
				frappe.delete_doc("Chapel Attendance", have.name, ignore_permissions=True)
			continue
		if have:
			if have.status != status:
				doc = frappe.get_doc("Chapel Attendance", have.name)
				doc.status, doc.method = status, "Roster"
				doc.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{
				"doctype": "Chapel Attendance",
				"chapel": chapel,
				"student": student,
				"status": status,
				"method": "Roster",
				"program_enrollment": _active_enrollment(student),
				"check_in_time": chapel_doc.starts_on,
			}
		).insert(ignore_permissions=True)
	return get_roll(chapel)
