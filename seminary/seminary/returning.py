# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Returning and second-degree students (decisions/118).

A Person holds one Student. A returning applicant is matched to that Student, flagged when it was
dismissed or suspended, and admitted onto it rather than onto a new one. An admitting decision lifts
the holds it answers; standing stays derived (033).
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, today, validate_email_address

APPLICANT = "Student Applicant"
# A standing that a readmission has to answer for (§2).
FLAGGED = ("Dismissed", "Suspended")
# The holds an admitting decision lifts (§3): the ones behind Dismissed and Suspended.
ANSWERED_HOLDS = ("Disciplinary", "Academic")


def student_of(person):
	return frappe.db.get_value("Student", {"person": person}, "name") if person else None


# --------------------------------------------------------------------------- #
# §2 The flag on the application
# --------------------------------------------------------------------------- #
def refresh(applicant):
	"""Derive the returning-student fields. Frozen once admitted."""
	if applicant.application_status == "Admitted":
		return
	student = student_of(applicant.person)
	standing = frappe.db.get_value("Student", student, "student_standing") if student else None
	values = {
		"returning_student": student,
		"prior_standing": standing,
		"readmission_review": 1 if standing in FLAGGED else 0,
	}
	if any((applicant.get(k) or None) != (v or None) for k, v in values.items()):
		applicant.db_set(values, update_modified=False)


def is_flagged(applicant):
	return bool(cint(frappe.db.get_value(APPLICANT, applicant, "readmission_review")))


def active_holds(student, types=None):
	filters = {"parent": student, "parentfield": "student_holds", "is_active": 1}
	if types:
		filters["hold_type"] = ("in", types)
	return frappe.get_all(
		"Student Hold",
		filters=filters,
		fields=["name", "hold_type", "reason", "raised_on", "blocks_reenrollment"],
		order_by="raised_on asc",
	)


def summary(applicant):
	"""What staff see about a returning applicant (§2, §6), or None."""
	doc = applicant if hasattr(applicant, "doctype") else frappe.get_doc(APPLICANT, applicant)
	student = doc.get("returning_student") or student_of(doc.person)
	alumni = frappe.db.exists("Alumni Profile", {"person": doc.person}) if doc.person else None
	if not (student or alumni):
		return None
	programs = (
		frappe.get_all(
			"Program Enrollment",
			filters={"student": student, "docstatus": 1},
			fields=["name", "program", "status"],
			order_by="enrollment_date asc",
		)
		if student
		else []
	)
	return {
		"student": student,
		"alumni": bool(alumni),
		"standing": doc.get("prior_standing"),
		"readmission_review": cint(doc.get("readmission_review")),
		"programs": programs,
		"holds": active_holds(student) if student else [],
	}


def summary_text(info):
	"""One line for a ToDo or a headline, escaped."""
	if not info:
		return ""
	label = _("Already a student") if info["student"] else _("Alumnus")
	programs = ", ".join(f"{p.program} ({_(p.status)})" for p in info["programs"])
	text = f"{label}: {info['student'] or ''}"
	if programs:
		text += f" — {programs}"
	if info["readmission_review"]:
		text += ". " + _("Previously {0}: check whether what led to it has changed before admitting.").format(
			_(info["standing"]).lower()
		)
	holds = [f"{_(h.hold_type)} ({h.raised_on}){': ' + h.reason if h.reason else ''}" for h in info["holds"]]
	if holds:
		text += " " + _("Active holds: {0}.").format("; ".join(holds))
	return escape_html(text)


# --------------------------------------------------------------------------- #
# §3 Accepting lifts the holds it answers
# --------------------------------------------------------------------------- #
def lift_holds(decision):
	"""Admission Decision.on_submit, for an admitting decision."""
	student = frappe.db.get_value(APPLICANT, decision.student_applicant, "returning_student")
	if not student:
		return []
	lifted = []
	for hold in active_holds(student, ANSWERED_HOLDS):
		if not hold.blocks_reenrollment:
			continue
		frappe.db.set_value(
			"Student Hold",
			hold.name,
			{
				"is_active": 0,
				"lifted_on": today(),
				"lifted_by": frappe.session.user,
				"lifted_through_doctype": decision.doctype,
				"lifted_through": decision.name,
			},
			update_modified=False,
		)
		lifted.append(hold.name)
	if lifted:
		from seminary.seminary.student_standing import recompute_standing

		recompute_standing(student)
	return lifted


def restore_holds(decision):
	"""Admission Decision.on_cancel: the holds this decision lifted are active again."""
	rows = frappe.get_all(
		"Student Hold",
		filters={"lifted_through_doctype": decision.doctype, "lifted_through": decision.name},
		fields=["name", "parent"],
	)
	for row in rows:
		frappe.db.set_value(
			"Student Hold",
			row.name,
			{
				"is_active": 1,
				"lifted_on": None,
				"lifted_by": None,
				"lifted_through_doctype": None,
				"lifted_through": None,
			},
			update_modified=False,
		)
	if rows:
		from seminary.seminary.student_standing import recompute_standing

		for student in {r.parent for r in rows}:
			recompute_standing(student)


# --------------------------------------------------------------------------- #
# §1 Applying signed in
# --------------------------------------------------------------------------- #
def signed_in_user():
	"""The applicant's own login on the public form, or None (Guest, or staff in Desk)."""
	if frappe.session.user == "Guest" or not frappe.flags.in_web_form:
		return None
	return frappe.session.user


def bind_signed_in(applicant):
	"""Student Applicant.validate: a signed-in applicant's email is their account's."""
	user = signed_in_user()
	if not user or not applicant.is_new():
		return
	email = frappe.db.get_value("User", user, "email")
	if email:
		applicant.student_email_id = email


@frappe.whitelist()
def signed_in_prefill():
	"""The public form's prefill for a signed-in applicant: their Person's details."""
	user = frappe.session.user
	if user == "Guest":
		return {}
	from seminary.seminary.person import find_person

	email = frappe.db.get_value("User", user, "email")
	person = find_person(email=email, user=user)
	out = {"student_email_id": email}
	if person:
		row = frappe.db.get_value(
			"Person",
			person,
			["first_name", "middle_name", "last_name", "date_of_birth", "primary_mobile"],
			as_dict=True,
		)
		if row:
			out.update(
				{
					"first_name": row.first_name,
					"middle_name": row.middle_name,
					"last_name": row.last_name,
					"date_of_birth": row.date_of_birth,
					"student_mobile_number": row.primary_mobile,
				}
			)
	return {k: v for k, v in out.items() if v}


# --------------------------------------------------------------------------- #
# §1 "I can't use my old email"
# --------------------------------------------------------------------------- #
# Public: a returning student who can't sign in. It only creates registrar ToDos.
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep
@rate_limit(limit=5, seconds=60 * 60, ip_based=True)
def request_access(
	full_name: str,
	new_email: str,
	date_of_birth: str | None = None,
	old_email: str | None = None,
	phone: str | None = None,
	program: str | None = None,
):
	"""A returning student who lost their old email asks the registrar to move their record. It
	creates a ToDo per registrar and nothing else; the answer is the same whoever asks, so the page
	can't tell anyone whether a record exists."""
	full_name = (full_name or "").strip()
	new_email = (new_email or "").strip()
	if not full_name or not validate_email_address(new_email):
		frappe.throw(_("Give your name and an email address we can write to."))
	rows = [
		(_("Name"), full_name),
		(_("New email"), new_email),
		(_("Date of birth"), date_of_birth),
		(_("Email used before"), old_email),
		(_("Phone"), phone),
		(_("Program of interest"), program),
	]
	details = "<br>".join(
		f"<b>{escape_html(k)}:</b> {escape_html((v or '').strip()[:200])}" for k, v in rows if v
	)
	description = (
		_("A returning student can't use their old email.")
		+ "<br>"
		+ details
		+ "<br><br>"
		+ _(
			"Confirm who they are, then change the email on their Person and User and send them a "
			"password reset, so they can sign in and apply."
		)
	)
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	from seminary.seminary.cei_lifecycle import _registrar_emails

	for user in _registrar_emails():
		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"owner": user,
				"allocated_to": user,
				"description": description,
				"priority": "Medium",
			}
		).insert(ignore_permissions=True)
		# A ToDo inserted directly rings no bell, and it belongs to no record, so without this the
		# registrar has to go looking for it.
		make_notification_logs(
			{
				"type": "Assignment",
				"document_type": "ToDo",
				"document_name": todo.name,
				"subject": _("Returning student: {0} can't use their old email").format(
					escape_html(full_name[:140])
				),
				"from_user": "Administrator",
			},
			[user],
		)
	return {"ok": True}
