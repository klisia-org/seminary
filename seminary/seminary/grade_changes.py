# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Sent grades are frozen; a Grade Change Request is the one way to change them
(decisions/119 §2-3).

A finalized roster (`active = 0`) refuses any change to its assessment results or
its final grade, whatever the path: the gradebook, Desk, the REST API or a late
submission grade. An approved Grade Change Request writes the new scores under a
flag, recomputes the final grade and updates the transcript row, credits, GPA and
standing. The request is the audit record.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, now_datetime

CARD_FIELDS = (
	"rawscore_card",
	"actualextrapt_card",
	"score",
	"grade",
	"graded_card",
	"excused",
	"dropped_card",
)
ROSTER_FIELDS = ("fscore", "fgrade", "fgradepass")
FLAG = "seminary_grade_change"


def _changing():
	return bool(frappe.flags.get(FLAG))


def _frozen_message():
	return _(
		"This grade has been sent, so it can't be edited. To correct it, raise a Grade Change Request, "
		"which the registrar approves."
	)


def _differs(a, b):
	if isinstance(a, int | float) or isinstance(b, int | float):
		return abs(flt(a) - flt(b)) > 1e-9
	return (a or "") != (b or "")


def assert_roster_not_frozen(doc):
	"""Scheduled Course Roster validate: a finalized roster's grades stay put."""
	if doc.is_new() or _changing() or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	before = doc.get_doc_before_save()
	if not before or cint(before.active):
		return
	for field in ROSTER_FIELDS:
		if _differs(doc.get(field), before.get(field)):
			frappe.throw(_frozen_message(), title=_("Grade already sent"))
	old = {c.name: c for c in before.stdroster_grade or []}
	for card in doc.stdroster_grade or []:
		prev = old.get(card.name)
		if prev is None:
			continue
		for field in CARD_FIELDS:
			if _differs(card.get(field), prev.get(field)):
				frappe.throw(_frozen_message(), title=_("Grade already sent"))


def assert_card_not_frozen(doc, method=None):
	"""Course Assess Results Detail validate, for a row saved on its own."""
	if doc.is_new() or _changing() or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	if doc.parenttype != "Scheduled Course Roster" or not doc.parent:
		return
	if cint(frappe.db.get_value("Scheduled Course Roster", doc.parent, "active")):
		return
	before = frappe.db.get_value("Course Assess Results Detail", doc.name, list(CARD_FIELDS), as_dict=True)
	if before and any(_differs(doc.get(f), before.get(f)) for f in CARD_FIELDS):
		frappe.throw(_frozen_message(), title=_("Grade already sent"))


def roster_is_frozen(roster_name):
	return not cint(frappe.db.get_value("Scheduled Course Roster", roster_name, "active"))


# -- the request ----------------------------------------------------------------------------


def _settings():
	return frappe.get_cached_doc("Seminary Settings")


def needs_second_approval(grades_sent_on, on=None):
	"""(needed, role) under Seminary Settings."""
	s = _settings()
	role, days = s.grade_change_second_approver_role, cint(s.grade_change_second_approval_days)
	if not role or not days or not grades_sent_on:
		return False, None
	return date_diff(on or now_datetime(), grades_sent_on) > days, role


def fill(doc):
	"""Grade Change Request validate: derive everything from the roster."""
	from seminary.seminary.api import narrative_section
	from seminary.seminary.cbe import framework_for

	row = frappe.db.get_value(
		"Scheduled Course Roster",
		doc.roster,
		[
			"name",
			"course_sc",
			"student",
			"stuname_roster",
			"active",
			"audit_bool",
			"fgrade",
			"grades_sent_on",
		],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Choose a student's roster row."))
	if row.active or row.audit_bool:
		frappe.throw(_("This grade hasn't been sent. Change it in the gradebook."))
	if framework_for(row.course_sc):
		frappe.throw(
			_(
				"A competency-based course's grade comes from the competency levels. Ask the registrar to reopen it."
			)
		)
	doc.course_schedule = row.course_sc
	doc.course_title = frappe.db.get_value("Course Schedule", row.course_sc, "title")
	doc.student = row.student
	doc.student_name = row.stuname_roster
	doc.grades_sent_on = row.grades_sent_on
	if doc.status == "Open":
		doc.old_grade = row.fgrade
	cards = {
		c.assessment_criteria: c
		for c in frappe.get_all(
			"Course Assess Results Detail",
			filters={"parent": row.name, "parenttype": "Scheduled Course Roster"},
			fields=[
				"name",
				"assessment_criteria",
				"assessment_title",
				"extracredit_card",
				"rawscore_card",
				"actualextrapt_card",
			],
		)
	}
	seen = set()
	levels = None
	if narrative_section(row.course_sc):
		scale = frappe.db.get_value("Course Schedule", row.course_sc, "gradesc_cs")
		levels = {
			flt(i.threshold)
			for i in frappe.get_all("Grading Scale Interval", filters={"parent": scale}, fields=["threshold"])
		}
	for item in doc.changes or []:
		card = cards.get(item.assessment)
		if not card:
			frappe.throw(_("Row {0}: that assessment isn't in this course.").format(item.idx))
		if item.assessment in seen:
			frappe.throw(_("Row {0}: {1} is listed twice.").format(item.idx, card.assessment_title))
		seen.add(item.assessment)
		item.card = card.name
		item.assessment_title = card.assessment_title
		item.is_extra_credit = cint(card.extracredit_card)
		if doc.status == "Open":
			item.old_value = flt(card.actualextrapt_card if card.extracredit_card else card.rawscore_card)
		if levels is not None and not item.is_extra_credit and flt(item.new_value) not in levels:
			frappe.throw(
				_("Row {0}: {1} isn't a level on this course's grading scale.").format(
					item.idx, item.new_value
				)
			)
		if flt(item.new_value) < 0:
			frappe.throw(_("Row {0}: a score can't be negative.").format(item.idx))
	if doc.status == "Open":
		needed, role = needs_second_approval(row.grades_sent_on)
		doc.needs_second_approval = 1 if needed else 0
		doc.second_approver_role = role if needed else None


def assert_may_raise(doc):
	"""An instructor raises a request only for a section they grade."""
	from seminary.seminary import guards
	from seminary.seminary.api import SCHOOL_ROLES

	if set(frappe.get_roles()) & SCHOOL_ROLES:
		return
	guards.require_section_capability(doc.course_schedule, guards.GRADE)


def _require_registrar():
	if not set(frappe.get_roles()) & {"Registrar", "Seminary Manager", "System Manager"}:
		frappe.throw(_("Only the registrar approves grade changes."), frappe.PermissionError)


@frappe.whitelist()
def approve(name: str, note: str | None = None):
	"""The registrar's approval, or the second approver's. Applies the change once
	every approval it needs is in."""
	doc = frappe.get_doc("Grade Change Request", name)
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	roles = set(frappe.get_roles())
	user = frappe.session.user
	acted = False
	if not doc.registrar_approved_by and roles & {"Registrar", "Seminary Manager", "System Manager"}:
		doc.registrar_approved_by, doc.registrar_approved_on = user, now_datetime()
		acted = True
	elif (
		doc.needs_second_approval
		and not doc.second_approved_by
		and doc.second_approver_role in roles
		and user != doc.registrar_approved_by
	):
		doc.second_approved_by, doc.second_approved_on = user, now_datetime()
		acted = True
	if not acted:
		if doc.needs_second_approval and doc.registrar_approved_by == user:
			frappe.throw(
				_("A second person in the role {0} must approve this change.").format(
					doc.second_approver_role
				)
			)
		frappe.throw(_("You can't approve this request."), frappe.PermissionError)
	if note:
		doc.decision_note = note
	if doc.registrar_approved_by and (not doc.needs_second_approval or doc.second_approved_by):
		_apply(doc)
		doc.status = "Approved"
	doc.save(ignore_permissions=True)
	return doc.status


@frappe.whitelist()
def reject(name: str, note: str):
	doc = frappe.get_doc("Grade Change Request", name)
	roles = set(frappe.get_roles())
	if not (
		roles & {"Registrar", "Seminary Manager", "System Manager"}
		or (doc.second_approver_role and doc.second_approver_role in roles)
	):
		frappe.throw(_("Only an approver can reject a grade change."), frappe.PermissionError)
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	if not (note or "").strip():
		frappe.throw(_("Say why the change is rejected."))
	doc.status, doc.decision_note = "Rejected", note.strip()
	doc.save(ignore_permissions=True)
	return doc.status


@frappe.whitelist()
def withdraw(name: str):
	doc = frappe.get_doc("Grade Change Request", name)
	if doc.owner != frappe.session.user:
		_require_registrar()
	if doc.status != "Open":
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	doc.status = "Withdrawn"
	doc.save(ignore_permissions=True)
	return doc.status


def _apply(doc):
	"""Write the new scores, recompute the final grade and the transcript row."""
	from seminary.seminary import api, repeats

	roster = frappe.get_doc("Scheduled Course Roster", doc.roster)
	if roster.active:
		frappe.throw(_("This grade is no longer sent; change it in the gradebook."))
	by_name = {c.name: c for c in roster.stdroster_grade or []}
	frappe.flags[FLAG] = True
	try:
		for item in doc.changes:
			card = by_name.get(item.card)
			if not card:
				continue
			if item.is_extra_credit:
				card.actualextrapt_card = flt(item.new_value)
			else:
				card.rawscore_card = flt(item.new_value)
			card.graded_card = 1
		roster.save(ignore_permissions=True)
		api._grade_thisstudent(roster.name)
		api._fgrade_this_std(roster.name)
	finally:
		frappe.flags[FLAG] = False
	fscore, fgrade, fgradepass = frappe.db.get_value(
		"Scheduled Course Roster", roster.name, ["fscore", "fgrade", "fgradepass"]
	)
	api._assert_grade_computed(roster.name, fgrade, fgradepass)
	pe, pec = api._pe_and_pec(roster)
	if pec:
		frappe.db.set_value(
			"Program Enrollment Course",
			pec,
			{"pec_finalgradenum": fscore, "pec_finalgradecode": fgrade, "status": fgradepass},
		)
	doc.new_grade = fgrade
	if pe:
		repeats.recount(pe)
		api._post_finalization([pe])
		from seminary.seminary.student_standing import recompute_standing

		recompute_standing(frappe.db.get_value("Program Enrollment", pe, "student"))
	roster.add_comment(
		"Info",
		_("Grade changed from {0} to {1} by {2}.").format(doc.old_grade or "-", fgrade or "-", doc.name),
	)
