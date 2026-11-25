# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Applicant review and admission decisions (decisions/112).

An application is *complete* when its documents, agreements and any
application fee are in (its required answers are checked when it is saved).
A complete application on an Automatic program is admitted at once; on a
Reviewed program it goes *In Review*, and each reviewer gets an Application
Review and a ToDo. A reviewer recommends, comments and scores the program's
rubric, or recuses. The outcome is an Admission Decision; the applicant's
status follows the latest submitted one and is never set by hand.

Another app may decide for a program. Each path in the
``seminary_admission_deciders`` hook is called with the program name and may
return ``{"reviewers": [user, ...], "due_date": date, "label": str}`` to claim
it. A claimed program is reviewed by those users and decided only through
``record_decision``, which the claiming app calls with the record that
produced the outcome as ``decided_through``.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, escape_html, flt, getdate, now_datetime, today

from seminary.seminary.guards import _roles

APPLICANT = "Student Applicant"
REVIEW = "Application Review"
DECISION = "Admission Decision"
DECIDERS_HOOK = "seminary_admission_deciders"
STAFF = {"Registrar", "Seminary Manager", "System Manager"}
RECOMMENDATIONS = ("Admit", "Admit with conditions", "Waitlist", "Decline")
ADMIT = {"Admit", "Admit with conditions"}
# Decision -> application status.
OUTCOME_STATUS = {
	"Admit": "Approved",
	"Admit with conditions": "Approved",
	"Waitlist": "Waitlisted",
	"Decline": "Rejected",
}
# Statuses a decision may be recorded from.
DECIDABLE = ("In Review", "Waitlisted")
TEMPLATES = {
	"Admit": "admission-admitted",
	"Admit with conditions": "admission-admitted-conditions",
	"Waitlist": "admission-waitlisted",
	"Decline": "admission-declined",
}


def is_staff(user=None):
	return bool(_roles(user) & STAFF)


# --------------------------------------------------------------------------- #
# Who reviews and who decides
# --------------------------------------------------------------------------- #
def claim(program):
	"""The first app that claims this program's admissions, or None."""
	if not program:
		return None
	for path in frappe.get_hooks(DECIDERS_HOOK) or []:
		try:
			result = frappe.get_attr(path)(program)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"{DECIDERS_HOOK}: {path}")
			continue
		if result:
			return frappe._dict(result)
	return None


def is_claimed(program):
	return bool(claim(program))


def _registrars():
	from seminary.seminary.cei_lifecycle import _registrar_emails

	return _registrar_emails()


def admissions_unit(program):
	"""The program's Program Admissions unit, if it is still one (decisions/112 §1a)."""
	unit = frappe.db.get_value("Program", program, "admissions_unit") if program else None
	if unit and frappe.db.get_value("Academic Unit", unit, ["unit_type", "is_active"]) == (
		"Program Admissions",
		1,
	):
		return unit
	return None


def _enabled(users):
	return [u for u in users if u and frappe.db.get_value("User", u, "enabled")]


def unit_members(unit):
	"""Users of the unit's active members, in a stable order."""
	persons = frappe.get_all(
		"Academic Unit Membership", filters={"unit": unit, "is_active": 1}, pluck="person"
	)
	users = frappe.get_all("Person", filters={"name": ("in", persons or ["-"])}, pluck="user")
	return sorted(set(_enabled(users)))


def unit_chair(program):
	unit = admissions_unit(program)
	person = frappe.db.get_value("Academic Unit", unit, "chair") if unit else None
	return frappe.db.get_value("Person", person, "user") if person else None


def reviewers_for(program, claimed=None):
	"""(users, due_date): the claiming app's, else the admissions unit's members, else the program
	director, else the Registrars."""
	claimed = claimed if claimed is not None else claim(program)
	if claimed:
		return _enabled(claimed.get("reviewers") or []), claimed.get("due_date")
	unit = admissions_unit(program)
	members = unit_members(unit) if unit else []
	if members:
		# The chair decides, so the chair reviews too, as the director does without a unit.
		return sorted(set(members + _enabled([unit_chair(program)]))), None
	director = frappe.db.get_value("Program", program, "program_director")
	if director and frappe.db.get_value("User", director, "enabled"):
		return [director], None
	return _registrars(), None


def is_director(program, user=None):
	user = user or frappe.session.user
	return bool(program) and frappe.db.get_value("Program", program, "program_director") == user


def may_decide(program, user=None):
	user = user or frappe.session.user
	return is_staff(user) or is_director(program, user) or bool(program and unit_chair(program) == user)


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
def set_status(applicant, status):
	"""The only writer of `application_status` besides enrolment (Admitted).

	`modified` is left alone: a status change often happens inside the save of
	the application itself, and bumping it would make the form the user is
	holding stale. The decision record carries its own time."""
	frappe.db.set_value(APPLICANT, applicant, "application_status", status, update_modified=False)


def missing(doc):
	"""What a saved application still lacks before it can be reviewed."""
	from seminary.seminary.financial.backend import get_financial_backend

	out = []
	for row in doc.get("documents") or []:
		if not row.file:
			out.append(_("Document: {0}").format(_(row.document_type)))
	for row in doc.get("agreements") or []:
		if not row.signed_agreement:
			title = frappe.db.get_value("Agreement Template", row.agreement_template, "title")
			out.append(_("Agreement: {0}").format(title or row.agreement_template))
	if not cint(doc.paid):
		try:
			owed = get_financial_backend().application_fee_outstanding(doc.name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "application fee check failed")
			owed = False
		if owed:
			out.append(_("Application fee"))
	return out


def check(applicant):
	"""Start review once an Applied application is complete. Safe to call
	often; returns the status the application has afterwards."""
	doc = applicant if hasattr(applicant, "doctype") else frappe.get_doc(APPLICANT, applicant)
	if doc.application_status != "Applied" or not doc.program or frappe.flags.in_import:
		return doc.application_status
	if missing(doc):
		return "Applied"
	status = start_review(doc)
	# The caller's copy follows the database, so the form it returns is current.
	doc.application_status = status
	return status


def start_review(doc):
	mode = frappe.db.get_value("Program", doc.program, "admission_mode") or "Reviewed"
	if mode == "Automatic":
		set_status(doc.name, "In Review")
		record_decision(
			doc.name,
			"Admit",
			rationale=_("Admitted automatically: this program admits every complete application."),
		)
		return "Approved"
	set_status(doc.name, "In Review")
	claimed = claim(doc.program)
	users, due = reviewers_for(doc.program, claimed)
	rubric = frappe.db.get_value("Program", doc.program, "admission_rubric")
	for user in users:
		assign_review(doc, user, due, rubric)
	return "In Review"


def assign_review(applicant, user, due_date=None, rubric=None):
	"""One review per reviewer per applicant; returns its name."""
	name = frappe.db.get_value(REVIEW, {"student_applicant": applicant.name, "reviewer": user})
	if name:
		return name
	review = frappe.get_doc(
		{
			"doctype": REVIEW,
			"student_applicant": applicant.name,
			"reviewer": user,
			"due_date": getdate(due_date) if due_date else None,
			"rubric": rubric,
			"status": "Open",
		}
	)
	review.flags.from_admissions = True
	review.insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"owner": user,
			"allocated_to": user,
			"reference_type": REVIEW,
			"reference_name": review.name,
			"date": review.due_date,
			"description": _("Review the application of {0} for {1}.").format(
				escape_html(applicant.title or applicant.name), escape_html(applicant.program)
			),
		}
	).insert(ignore_permissions=True)
	return review.name


def _close_todos(review):
	for name in frappe.get_all(
		"ToDo",
		filters={"reference_type": REVIEW, "reference_name": review, "status": "Open"},
		pluck="name",
	):
		frappe.db.set_value("ToDo", name, "status", "Closed")


@frappe.whitelist()
def check_now(applicant: str):
	"""Applicant form button: start review if complete, else say what is missing."""
	frappe.has_permission(APPLICANT, "write", applicant, throw=True)
	doc = frappe.get_doc(APPLICANT, applicant)
	status = check(doc)
	return {"status": status, "missing": missing(doc) if status == "Applied" else []}


@frappe.whitelist()
def form_state(applicant: str):
	"""What the applicant's Desk form offers."""
	frappe.has_permission(APPLICANT, "read", applicant, throw=True)
	doc = frappe.get_doc(APPLICANT, applicant)
	claimed = claim(doc.program)
	return {
		"is_staff": is_staff(),
		"may_decide": may_decide(doc.program),
		"claimed": (claimed.get("label") or _("a committee")) if claimed else None,
		"missing": missing(doc) if doc.application_status == "Applied" else [],
	}


@frappe.whitelist()
def withdraw(applicant: str):
	if not is_staff():
		frappe.throw(_("Only the registrars can withdraw an application."), frappe.PermissionError)
	status = frappe.db.get_value(APPLICANT, applicant, "application_status")
	if status == "Admitted":
		frappe.throw(_("An admitted applicant is already a student."))
	set_status(applicant, "Withdrawn")
	for review in frappe.get_all(
		REVIEW, filters={"student_applicant": applicant, "status": "Open"}, pluck="name"
	):
		_close_todos(review)
	return "Withdrawn"


# --------------------------------------------------------------------------- #
# Reviewing
# --------------------------------------------------------------------------- #
def _own_open_review(review):
	doc = frappe.get_doc(REVIEW, review)
	if doc.reviewer != frappe.session.user:
		frappe.throw(_("Only the reviewer can change this review."), frappe.PermissionError)
	if doc.status != "Open":
		frappe.throw(_("This review is already {0}.").format(_(doc.status)))
	return doc


def _scores(review):
	return frappe.get_all(
		"Rubric Score",
		filters={"submission_doctype": REVIEW, "submission": review},
		fields=["name", "rubric", "criterion_code", "level", "percent", "comment"],
	)


def overall_percent(review_doc):
	"""Σ share × level percent over the rubric's criteria, or None while a
	criterion is unscored."""
	from seminary.seminary import rubrics

	if not review_doc.rubric:
		return None
	rubric = frappe.get_doc("Rubric", review_doc.rubric)
	shares = rubrics.shares([c.as_dict() for c in rubric.criteria])
	scores = {s.criterion_code: flt(s.percent) for s in _scores(review_doc.name) if s.rubric == rubric.name}
	if any(c.criterion_code not in scores for c in rubric.criteria):
		return None
	return round(sum(shares.get(code, 0) * pct for code, pct in scores.items()), 2)


@frappe.whitelist()
def review_panel(review: str):
	"""The review form's rubric grid and, once this reviewer is done, the
	other reviews."""
	from seminary.seminary import rubrics

	frappe.has_permission(REVIEW, "read", review, throw=True)
	doc = frappe.get_doc(REVIEW, review)
	mine = doc.reviewer == frappe.session.user
	return {
		"rubric": rubrics.rubric_payload(doc.rubric) if doc.rubric else None,
		"scores": _scores(doc.name),
		"can_edit": mine and doc.status == "Open",
		"overall_percent": overall_percent(doc),
		"others": others(doc),
	}


def others(doc):
	user = frappe.session.user
	if not is_staff(user):
		own = frappe.db.get_value(
			REVIEW, {"student_applicant": doc.student_applicant, "reviewer": user}, "status"
		)
		if own in (None, "Open"):
			return None
	return frappe.get_all(
		REVIEW,
		filters={
			"student_applicant": doc.student_applicant,
			"name": ["!=", doc.name],
			"status": ["!=", "Open"],
		},
		fields=[
			"name",
			"reviewer_name",
			"status",
			"recommendation",
			"overall_percent",
			"comments",
			"conflict_note",
		],
		order_by="submitted_on asc",
	)


@frappe.whitelist()
def save_review_scores(review: str, scores: str | list):
	"""Upsert the reviewer's level and comment per criterion."""
	doc = _own_open_review(review)
	if not doc.rubric:
		frappe.throw(_("This program has no review rubric."))
	existing = {s.criterion_code: s.name for s in _scores(doc.name)}
	for row in frappe.parse_json(scores) or []:
		code, level = row.get("criterion_code"), row.get("level")
		name = existing.get(code)
		if not level:
			if name:
				frappe.delete_doc("Rubric Score", name, ignore_permissions=True)
			continue
		score = frappe.get_doc("Rubric Score", name) if name else frappe.new_doc("Rubric Score")
		score.update(
			{
				"submission_doctype": REVIEW,
				"submission": doc.name,
				"rubric": doc.rubric,
				"criterion_code": code,
				"level": level,
				"comment": row.get("comment"),
			}
		)
		score.save(ignore_permissions=True)
	percent = overall_percent(doc)
	# The column holds 0 while a criterion is unscored; the form shows None.
	doc.db_set("overall_percent", percent or 0)
	return {"overall_percent": percent}


@frappe.whitelist()
def submit_review(review: str, recommendation: str, comments: str | None = None):
	doc = _own_open_review(review)
	if recommendation not in RECOMMENDATIONS:
		frappe.throw(_("Choose a recommendation."))
	if doc.rubric:
		percent = overall_percent(doc)
		if percent is None:
			frappe.throw(_("Score every criterion of the rubric before submitting."))
		doc.overall_percent = percent
	doc.recommendation = recommendation
	doc.comments = comments if comments is not None else doc.comments
	doc.status = "Submitted"
	doc.submitted_on = now_datetime()
	doc.flags.from_admissions = True
	doc.save(ignore_permissions=True)
	_close_todos(doc.name)
	return doc.status


@frappe.whitelist()
def recuse(review: str, note: str):
	doc = _own_open_review(review)
	note = cstr(note).strip()
	if len(note) < 3:
		frappe.throw(_("Say briefly what the conflict of interest is."))
	doc.status = "Recused"
	doc.conflict_note = note
	doc.submitted_on = now_datetime()
	doc.flags.from_admissions = True
	doc.save(ignore_permissions=True)
	_close_todos(doc.name)
	return doc.status


def tally(applicant):
	"""({recommendation: count}, majority or None) over submitted reviews. The
	majority is the recommendation more than half the reviews made."""
	counts = {}
	for rec in frappe.get_all(
		REVIEW, filters={"student_applicant": applicant, "status": "Submitted"}, pluck="recommendation"
	):
		if rec:
			counts[rec] = counts.get(rec, 0) + 1
	total = sum(counts.values())
	majority = next((r for r, n in counts.items() if n * 2 > total), None)
	return counts, majority


def tally_text(counts):
	return ", ".join(f"{_(r)}: {counts[r]}" for r in RECOMMENDATIONS if counts.get(r))


def same_side(a, b):
	return a == b or (a in ADMIT and b in ADMIT)


# --------------------------------------------------------------------------- #
# Deciding
# --------------------------------------------------------------------------- #
def record_decision(
	applicant,
	decision,
	conditions=None,
	rationale=None,
	decided_through=None,
	requires_leveling=0,
):
	"""Record and submit the outcome. Called by Automatic admission and by an
	app that claims the program, with the record that produced the outcome
	(a document, or a (doctype, name) pair) as `decided_through`."""
	through_doctype = through_name = None
	if decided_through is not None:
		if hasattr(decided_through, "doctype"):
			through_doctype, through_name = decided_through.doctype, decided_through.name
		else:
			through_doctype, through_name = decided_through
	doc = frappe.get_doc(
		{
			"doctype": DECISION,
			"student_applicant": applicant,
			"decision": decision,
			"conditions": conditions,
			"requires_leveling": cint(requires_leveling),
			"rationale": rationale,
			"decided_on": today(),
			"decided_through_doctype": through_doctype,
			"decided_through": through_name,
		}
	)
	doc.flags.from_record_decision = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def apply_decision(doc):
	"""Admission Decision.on_submit."""
	set_status(doc.student_applicant, OUTCOME_STATUS[doc.decision])
	for review in frappe.get_all(
		REVIEW, filters={"student_applicant": doc.student_applicant, "status": "Open"}, pluck="name"
	):
		_close_todos(review)
	if doc.requires_leveling:
		_leveling_todo(doc)
	notify(doc)


def revert_decision(doc):
	"""Admission Decision.on_cancel: the status the previous decision gave, or In Review."""
	previous = frappe.get_all(
		DECISION,
		filters={"student_applicant": doc.student_applicant, "docstatus": 1, "name": ["!=", doc.name]},
		fields=["decision"],
		order_by="creation desc",
		limit=1,
	)
	set_status(doc.student_applicant, OUTCOME_STATUS[previous[0].decision] if previous else "In Review")


def latest_decision(applicant):
	return frappe.db.get_value(
		DECISION,
		{"student_applicant": applicant, "docstatus": 1},
		["name", "decision", "conditions", "requires_leveling"],
		as_dict=True,
		order_by="creation desc",
	)


def _leveling_todo(doc):
	for user in _registrars():
		if frappe.db.exists(
			"ToDo",
			{
				"allocated_to": user,
				"reference_type": APPLICANT,
				"reference_name": doc.student_applicant,
				"status": "Open",
			},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"owner": user,
				"allocated_to": user,
				"reference_type": APPLICANT,
				"reference_name": doc.student_applicant,
				"description": _(
					"Applicant {0} was admitted on condition of leveling. Plan leveling on their enrollment."
				).format(doc.student_applicant),
			}
		).insert(ignore_permissions=True)


def status_url(applicant):
	key = frappe.db.get_value(APPLICANT, applicant, "access_key") or ""
	return frappe.utils.get_url(f"/applicant-payment?applicant={applicant}&key={key}")


def notify(doc):
	"""Tell the applicant (decisions/112 §9). A missing template or address
	never stops the decision."""
	from seminary.seminary import comms

	template = TEMPLATES.get(doc.decision)
	app = frappe.db.get_value(
		APPLICANT, doc.student_applicant, ["person", "student_email_id", "title", "program"], as_dict=True
	)
	if not (
		template and app and app.student_email_id and frappe.db.exists("Communication Template", template)
	):
		return
	try:
		comms.send(
			app.person,
			template,
			to_address=app.student_email_id,
			channel="Email",
			reference_doctype=DECISION,
			reference_name=doc.name,
			dedupe_key=f"admission-{doc.name}",
			context={
				"applicant": app.title,
				"program": app.program,
				"conditions": doc.conditions or "",
				"status_url": status_url(doc.student_applicant),
			},
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "admission notice failed")


def public_status(applicant, key):
	"""What the applicant's own page shows: status and conditions, never reviews."""
	import hmac

	expected = frappe.db.get_value(APPLICANT, applicant, "access_key")
	if not (expected and key and hmac.compare_digest(str(key), str(expected))):
		return None
	status = frappe.db.get_value(APPLICANT, applicant, "application_status")
	latest = latest_decision(applicant)
	return frappe._dict(
		status=status,
		conditions=(latest.conditions if latest and latest.decision == "Admit with conditions" else None),
	)


# --------------------------------------------------------------------------- #
# Rubric
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def edit_review_rubric(program: str):
	"""Program button: the rubric to edit. Creates one on the default scale,
	or a new version when reviewers have scored on the current one."""
	from seminary.seminary import rubrics

	frappe.has_permission("Program", "write", program, throw=True)
	frappe.has_permission("Rubric", "create", throw=True)
	current = frappe.db.get_value("Program", program, "admission_rubric")
	if current and not rubrics.is_locked(current):
		return current
	scale = frappe.db.get_value("Rubric Scale", {"enabled": 1, "is_default": 1}) or frappe.db.get_value(
		"Rubric Scale", {"enabled": 1}
	)
	if not scale:
		frappe.throw(_("Create a Rubric Scale first."))
	doc = frappe.new_doc("Rubric")
	doc.update(
		{
			"activity_doctype": "Program",
			"activity": program,
			"scale": scale,
			"version": (cint(frappe.db.get_value("Rubric", current, "version")) + 1) if current else 1,
			"previous_version": current,
		}
	)
	if current:
		old = frappe.get_doc("Rubric", current)
		doc.scale = old.scale
		for c in old.criteria:
			doc.append(
				"criteria",
				{
					"criterion_code": c.criterion_code,
					"title": c.title,
					"description": c.description,
					"weight": c.weight,
				},
			)
		for c in old.cells:
			doc.append(
				"cells", {"criterion_code": c.criterion_code, "level": c.level, "descriptor": c.descriptor}
			)
	else:
		doc.append("criteria", {"title": _("Overall fit for the program")})
	doc.insert()
	frappe.db.set_value("Program", program, "admission_rubric", doc.name)
	return doc.name


# --------------------------------------------------------------------------- #
# Scheduler and events
# --------------------------------------------------------------------------- #
def daily():
	"""Applications completed outside a save (a fee paid elsewhere) start review."""
	for name in frappe.get_all(APPLICANT, filters={"application_status": "Applied"}, pluck="name"):
		try:
			check(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"admission check failed for {name}")


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
def _school(user):
	from seminary.seminary.guards import SCHOOL_ROLES

	return bool(_roles(user) & SCHOOL_ROLES)


def applicant_query(user=None):
	user = user or frappe.session.user
	if _school(user):
		return ""
	u = frappe.db.escape(user)
	return (
		f"(`tabStudent Applicant`.owner = {u} or `tabStudent Applicant`.name in "
		f"(select student_applicant from `tabApplication Review` where reviewer = {u}))"  # nosec B608 -- user is escaped
	)


def applicant_has(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if _school(user) or doc.owner == user:
		return True
	if ptype not in (None, "read", "print"):
		return False
	return bool(frappe.db.exists(REVIEW, {"student_applicant": doc.name, "reviewer": user}))


def review_query(user=None):
	user = user or frappe.session.user
	if is_staff(user):
		return ""
	u = frappe.db.escape(user)
	return (
		f"(`tabApplication Review`.reviewer = {u} or `tabApplication Review`.student_applicant in "
		f"(select student_applicant from `tabApplication Review` where reviewer = {u} and status != 'Open'))"  # nosec B608 -- user is escaped
	)


def review_has(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_staff(user):
		return True
	if doc.reviewer == user:
		return ptype in (None, "read", "print", "write") and (ptype != "write" or doc.status == "Open")
	if ptype not in (None, "read", "print"):
		return False
	own = frappe.db.get_value(
		REVIEW, {"student_applicant": doc.student_applicant, "reviewer": user}, "status"
	)
	return own not in (None, "Open")


def decision_query(user=None):
	user = user or frappe.session.user
	if is_staff(user):
		return ""
	u = frappe.db.escape(user)
	return (
		f"(`tabAdmission Decision`.program in (select name from `tabProgram` where program_director = {u} "
		f"or admissions_unit in (select au.name from `tabAcademic Unit` au join `tabPerson` p on p.name = au.chair "
		f"where p.user = {u} and au.unit_type = 'Program Admissions' and au.is_active = 1)) "
		f"or `tabAdmission Decision`.student_applicant in "
		f"(select student_applicant from `tabApplication Review` where reviewer = {u}))"  # nosec B608 -- user is escaped
	)


def decision_has(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if is_staff(user):
		return True
	program = doc.get("program") or frappe.db.get_value(APPLICANT, doc.get("student_applicant"), "program")
	if is_director(program, user) or (program and unit_chair(program) == user):
		return True
	if ptype not in (None, "read", "print"):
		return False
	return bool(
		frappe.db.exists(REVIEW, {"student_applicant": doc.get("student_applicant"), "reviewer": user})
	)
