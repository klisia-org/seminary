# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Transcripts (decisions/119 §5-6).

One render, two uses. The unofficial transcript is watermarked and can be opened
at any time by the student, or by the registrar for any student. The official one
is issued from a Transcript Request: Financial and Administrative holds block it,
the financial backend may charge for it, and on issue the PDF gets the registrar's
signature image and a verification code. Its SHA-256 is stored, so the public
verification page can confirm a copy without ever showing the grades.
"""

import hashlib
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, flt, getdate, now_datetime, today

TEMPLATE = "templates/transcript.html"
BLOCKING_HOLDS = ("Financial", "Administrative")
DOWNLOAD_DAYS = 30
SCHOOL_ROLES = {"Registrar", "Seminary Manager", "System Manager", "Program Chair"}
ISSUE_ROLES = {"Registrar", "Seminary Manager", "System Manager"}

# Transcript marks for row states that aren't a plain grade.
NOTES = {
	"repeated": "R",
	"transfer": "T",
	"incomplete": "I",
}


# -- data -------------------------------------------------------------------------------


def _person_birth_date(person):
	if not person:
		return None
	meta = frappe.get_meta("Person")
	for field in ("birth_date", "date_of_birth", "dob"):
		if meta.has_field(field):
			return frappe.db.get_value("Person", person, field)
	return None


def _courses():
	return {
		c.name: c
		for c in frappe.get_all("Course", fields=["name", "course_name", "coursecode", "course_credits"])
	}


def _terms():
	return {
		t.name: t for t in frappe.get_all("Academic Term", fields=["name", "term_name", "term_start_date"])
	}


def _scale_types():
	return {
		cs.name: cs.grscale_type
		for cs in frappe.db.sql(
			"""SELECT cs.name, gs.grscale_type FROM `tabCourse Schedule` cs
			   LEFT JOIN `tabGrading Scale` gs ON gs.name = cs.gradesc_cs""",
			as_dict=True,
		)
	}


def data(student, program_enrollment=None):
	"""Everything a transcript shows, grouped by enrollment and term."""
	stu = frappe.db.get_value(
		"Student",
		student,
		["name", "student_name", "person", "student_email_id", "joining_date"],
		as_dict=True,
	)
	if not stu:
		frappe.throw(_("Student {0} not found.").format(student))
	filters = {"student": student, "docstatus": 1}
	if program_enrollment:
		filters["name"] = program_enrollment
	pes = frappe.get_all(
		"Program Enrollment",
		filters=filters,
		fields=[
			"name",
			"program",
			"enrollment_date",
			"date_of_conclusion",
			"status",
			"totalcredits",
			"current_gpa",
			"current_honor",
		],
		order_by="enrollment_date asc",
	)
	courses, terms, scales = _courses(), _terms(), _scale_types()
	partners = {
		p.name: p.partner_seminary_name
		for p in frappe.get_all("Partner Seminary", fields=["name", "partner_seminary_name"])
	}
	out = []
	for pe in pes:
		program = (
			frappe.db.get_value(
				"Program", pe.program, ["program_name", "program_level", "basis_for_gpa"], as_dict=True
			)
			or frappe._dict()
		)
		rows = frappe.get_all(
			"Program Enrollment Course",
			filters={"parent": pe.name, "parenttype": "Program Enrollment"},
			fields=[
				"course",
				"course_name",
				"academic_term",
				"credits",
				"pec_finalgradecode",
				"pec_finalgradenum",
				"status",
				"count_in_gpa",
				"is_transfer",
				"partner_seminary",
				"source_course_code",
				"source_term",
				"repeated",
				"attempt",
			],
			order_by="idx asc",
		)
		by_term = {}
		for r in rows:
			if not r.pec_finalgradecode and r.status not in ("Incomplete", "Withdrawn"):
				continue  # still in progress: not on a transcript
			c = courses.get(r.course_name) or frappe._dict()
			marks = []
			if r.repeated:
				marks.append(NOTES["repeated"])
			if r.is_transfer:
				marks.append(NOTES["transfer"])
			if r.status == "Incomplete":
				marks.append(NOTES["incomplete"])
			# Only a Points scale's number is a percentage; a Descriptive or CBE value is a
			# level, and is never shown as a score (decisions/072).
			numeric = (
				flt(r.pec_finalgradenum)
				if scales.get(r.course) == "Points"
				and r.status in ("Pass", "Fail")
				and r.pec_finalgradenum is not None
				else None
			)
			term = r.academic_term or (r.source_term if r.is_transfer else None) or ""
			key = (r.is_transfer and r.partner_seminary) or term
			label = (
				_("Transfer credit: {0}").format(partners.get(r.partner_seminary) or r.partner_seminary)
				if r.is_transfer and r.partner_seminary
				else (terms.get(term).term_name if terms.get(term) and terms.get(term).term_name else term)
				or _("Other")
			)
			start = str(terms.get(term).term_start_date or "") if terms.get(term) else ""
			group = by_term.setdefault(
				key, {"label": label, "start": start, "transfer": bool(r.is_transfer), "rows": []}
			)
			earned = flt(r.credits) if r.status == "Pass" and not r.repeated else 0
			group["rows"].append(
				frappe._dict(
					code=c.coursecode or r.source_course_code or "",
					title=c.course_name or r.course_name,
					credits=flt(r.credits) if not r.repeated else flt(c.course_credits),
					earned=earned,
					grade=r.pec_finalgradecode or "",
					numeric=numeric,
					status=r.status,
					marks=" ".join(marks),
				)
			)
		groups = sorted(by_term.values(), key=lambda g: (not g["transfer"], g["start"], g["label"]))
		out.append(
			frappe._dict(
				name=pe.name,
				program=program.program_name or pe.program,
				level=program.program_level,
				enrolled=pe.enrollment_date,
				status=pe.status,
				concluded=pe.date_of_conclusion,
				graduated=pe.status == "Graduated",
				honor=pe.current_honor,
				gpa=pe.current_gpa if flt(program.basis_for_gpa) else None,
				gpa_basis=flt(program.basis_for_gpa) or None,
				credits=flt(pe.totalcredits),
				terms=groups,
			)
		)
	return frappe._dict(
		student=stu,
		birth_date=_person_birth_date(stu.person),
		enrollments=out,
		school=_school(),
		generated=now_datetime(),
	)


def _school():
	from seminary.seminary.doctype.seminary_announcement.seminary_announcement import school_name

	s = frappe.get_cached_doc("Seminary Settings")
	return frappe._dict(
		name=school_name(),
		letterhead=s.letterhead,
		signature=s.transcript_signature,
		signatory=s.transcript_signatory_name,
		signatory_title=s.transcript_signatory_title or _("Registrar"),
	)


# -- render -----------------------------------------------------------------------------


def html(student, program_enrollment=None, official=False, request=None):
	ctx = data(student, program_enrollment)
	ctx.official = official
	ctx.request = request
	ctx.verify_url = frappe.utils.get_url("/transcript-verify")
	ctx.marks = {
		NOTES["repeated"]: _("Repeated: this attempt doesn't count toward credits or GPA."),
		NOTES["transfer"]: _("Transfer credit."),
		NOTES["incomplete"]: _("Incomplete: work still to be finished."),
	}
	body = frappe.render_template(TEMPLATE, ctx)  # nosemgrep -- a template file in this app
	from seminary.seminary.doctype.seminary_announcement.seminary_announcement import _wrap_letterhead
	from seminary.seminary.requirements import _letterhead

	return _wrap_letterhead(_letterhead(), body)


def pdf(student, program_enrollment=None, official=False, request=None):
	from seminary.pdf import render
	from seminary.seminary import comms

	name = frappe.db.get_value("Student", student, "student_name") or student
	title = (
		_("Official Transcript: {0}").format(name)
		if official
		else _("Unofficial Transcript: {0}").format(name)
	)
	return render(
		comms.pdf_html(html(student, program_enrollment, official, request)),
		footer=_("Page {0} of {1}").format("[page]", "[topage]"),
		title=title,
	)


def _may_read(student):
	from seminary.seminary.guards import current_student, is_school_role

	if is_school_role() or set(frappe.get_roles()) & SCHOOL_ROLES:
		return True
	return bool(student) and current_student() == student


@frappe.whitelist()
def unofficial(student: str | None = None, program_enrollment: str | None = None):
	"""Download the unofficial transcript: the student's own, or any student's for staff."""
	from seminary.seminary.guards import current_student

	student = student or current_student()
	if not student or not _may_read(student):
		frappe.throw(_("You can only download your own transcript."), frappe.PermissionError)
	if (
		program_enrollment
		and frappe.db.get_value("Program Enrollment", program_enrollment, "student") != student
	):
		frappe.throw(_("That enrollment belongs to another student."), frappe.PermissionError)
	frappe.local.response.filename = f"unofficial-transcript-{student}.pdf"
	frappe.local.response.filecontent = pdf(student, program_enrollment, official=False)
	frappe.local.response.type = "download"


# -- requests ---------------------------------------------------------------------------


def blocking_holds(student):
	return frappe.get_all(
		"Student Hold",
		filters={
			"parent": student,
			"parenttype": "Student",
			"is_active": 1,
			"hold_type": ("in", BLOCKING_HOLDS),
		},
		fields=["hold_type", "reason"],
	)


def validate_request(doc):
	"""Transcript Request validate."""
	from seminary.seminary.guards import current_student

	if not set(frappe.get_roles()) & SCHOOL_ROLES:
		mine = current_student()
		if not mine:
			frappe.throw(
				_("Only a student, or the registrar, can request a transcript."), frappe.PermissionError
			)
		if doc.is_new():
			doc.student = mine
		elif doc.student != mine:
			frappe.throw(_("You can only request your own transcript."), frappe.PermissionError)
	if (
		doc.program_enrollment
		and frappe.db.get_value("Program Enrollment", doc.program_enrollment, "student") != doc.student
	):
		frappe.throw(_("That enrollment belongs to another student."))
	doc.student_name = frappe.db.get_value("Student", doc.student, "student_name")
	doc.copies = max(cint(doc.copies) or 1, 1)
	if doc.delivery == "Email":
		if not doc.recipient_email:
			frappe.throw(_("Give the recipient's email address."))
		frappe.utils.validate_email_address(doc.recipient_email, throw=True)
	if doc.delivery == "Printed copy" and not (doc.mailing_address or "").strip():
		frappe.throw(_("Give the mailing address for the printed copy."))
	if doc.delivery != "Printed copy":
		doc.copies = 1


def after_insert_request(doc):
	"""Submit: check holds, charge the fee, and move on as far as it can go."""
	from seminary.seminary.financial.backend import get_financial_backend

	charges = get_financial_backend().charge_transcript_request(doc.name) or []
	doc.db_set("charges", "\n".join(charges), update_modified=False)
	advance(doc.name)


def _is_paid(doc):
	from seminary.seminary.financial.backend import get_financial_backend

	if doc.fee_waived or not doc.charges:
		return True
	return flt(get_financial_backend().payment_status_for_transcript_request(doc.name).paid_percent) >= 100


def advance(name):
	"""Move a request to the furthest state it can reach now. Ready requests for
	the student or by email are issued straight away; a printed copy waits for the
	registrar, who prints and mails it."""
	doc = frappe.get_doc("Transcript Request", name)
	if doc.status in ("Issued", "Cancelled"):
		return doc.status
	holds = blocking_holds(doc.student)
	if holds:
		note = "\n".join(f"{_(h.hold_type)}: {h.reason or ''}".strip() for h in holds)
		if doc.status != "On Hold" or doc.hold_note != note:
			doc.db_set({"status": "On Hold", "hold_note": note})
			_notify_student(doc, "transcript-request-on-hold", {"holds": note})
		return "On Hold"
	if not _is_paid(doc):
		if doc.status != "Awaiting Payment":
			doc.db_set({"status": "Awaiting Payment", "hold_note": None})
		return "Awaiting Payment"
	doc.db_set({"status": "Ready", "hold_note": None})
	if doc.delivery in ("Student", "Email"):
		frappe.enqueue(
			"seminary.seminary.transcripts.issue_job",
			name=doc.name,
			enqueue_after_commit=True,
			job_id=f"transcript-issue::{doc.name}",
			deduplicate=True,
		)
	else:
		_notify_registrar(doc, "transcript-request-ready")
	return "Ready"


def react_to_transcript_payment(name):
	"""Called by the financial backend when a payment lands on the request."""
	if frappe.db.get_value("Transcript Request", name, "status") == "Awaiting Payment":
		advance(name)


def issue_job(name):
	doc = frappe.get_doc("Transcript Request", name)
	if doc.status != "Ready":
		return
	_issue(doc, frappe.db.get_value("Transcript Request", name, "owner"))


def _require_issuer():
	if not set(frappe.get_roles()) & ISSUE_ROLES:
		frappe.throw(_("Only the registrar issues official transcripts."), frappe.PermissionError)


@frappe.whitelist()
def issue(name: str):
	"""The registrar issues a Ready request (a printed copy, or a retry)."""
	_require_issuer()
	doc = frappe.get_doc("Transcript Request", name)
	if advance(name) != "Ready":
		frappe.throw(
			_("This request can't be issued: it is {0}.").format(
				_(frappe.db.get_value("Transcript Request", name, "status"))
			)
		)
	doc.reload()
	return _issue(doc, frappe.session.user)


def _code():
	alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # pragma: allowlist secret
	raw = "".join(secrets.choice(alphabet) for _i in range(12))
	return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _issue(doc, user):
	from frappe.utils.file_manager import save_file

	code = doc.verification_code or _code()
	doc.verification_code = code
	content = pdf(doc.student, doc.program_enrollment, official=True, request=doc)
	digest = hashlib.sha256(content).hexdigest()
	f = save_file(f"transcript-{doc.name}.pdf", content, doc.doctype, doc.name, is_private=1)
	values = {
		"verification_code": code,
		"pdf_sha256": digest,
		"transcript_file": f.file_url,
		"issued_on": now_datetime(),
		"issued_by": user,
		"status": "Issued",
	}
	if doc.delivery == "Email":
		values["download_key"] = secrets.token_urlsafe(24)
		values["download_expires"] = add_days(today(), DOWNLOAD_DAYS)
	doc.db_set(values)
	doc.reload()
	if doc.delivery == "Email":
		_send_to_recipient(doc)
	elif doc.delivery == "Student":
		_notify_student(doc, "transcript-issued", {"code": code})
	return doc.status


@frappe.whitelist()
def waive_fee(name: str, reason: str):
	from seminary.seminary.financial.backend import get_financial_backend

	_require_issuer()
	if not (reason or "").strip():
		frappe.throw(_("Give the reason for waiving the fee."))
	doc = frappe.get_doc("Transcript Request", name)
	if doc.status in ("Issued", "Cancelled"):
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	get_financial_backend().waive_request_charges(doc.doctype, doc.name, reason.strip())
	doc.db_set({"fee_waived": 1, "fee_waiver_reason": reason.strip()})
	return advance(name)


@frappe.whitelist()
def recheck(name: str):
	"""Re-read holds and payment, after a hold is lifted or a payment recorded."""
	doc = frappe.get_doc("Transcript Request", name)
	if not (set(frappe.get_roles()) & SCHOOL_ROLES or _may_read(doc.student)):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return advance(name)


@frappe.whitelist()
def cancel_request(name: str, reason: str | None = None):
	from seminary.seminary.financial.backend import get_financial_backend
	from seminary.seminary.guards import current_student

	doc = frappe.get_doc("Transcript Request", name)
	staff = bool(set(frappe.get_roles()) & ISSUE_ROLES)
	if not staff and current_student() != doc.student:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if doc.status in ("Issued", "Cancelled"):
		frappe.throw(_("This request is already {0}.").format(_(doc.status)))
	if doc.charges and not doc.fee_waived:
		get_financial_backend().waive_request_charges(doc.doctype, doc.name, reason or _("Request cancelled"))
	doc.db_set({"status": "Cancelled", "cancel_reason": reason})
	return "Cancelled"


def daily():
	"""Requests waiting on a hold or a payment are re-read once a day."""
	for name in frappe.get_all(
		"Transcript Request",
		filters={"status": ("in", ("On Hold", "Awaiting Payment", "Draft"))},
		pluck="name",
	):
		try:
			advance(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Transcript request check failed: {name}")


# -- notices ----------------------------------------------------------------------------


def _ctx(doc, extra=None):
	return {
		"student": doc.student_name,
		"request": doc.name,
		"recipient": doc.recipient_name or doc.recipient_email or "",
		"verify_url": frappe.utils.get_url(f"/transcript-verify?code={doc.verification_code or ''}"),
		**(extra or {}),
	}


def _notify_student(doc, template, extra=None):
	from seminary.seminary import comms

	person = frappe.db.get_value("Student", doc.student, "person")
	if not person:
		return
	try:
		comms.send(
			person,
			template,
			context=_ctx(doc, extra),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			triggered_by=template,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"{template} notice failed: {doc.name}")


def _notify_registrar(doc, template, extra=None):
	from seminary.seminary import comms

	try:
		comms.send_to_role(
			"Registrar",
			template,
			context=_ctx(doc, extra),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			triggered_by=template,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"{template} notice failed: {doc.name}")


def _send_to_recipient(doc):
	from seminary.seminary import comms

	link = frappe.utils.get_url(
		f"/api/method/seminary.seminary.transcripts.download?code={doc.verification_code}&key={doc.download_key}"
	)
	try:
		comms.send(
			None,
			"transcript-delivery",
			to_address=doc.recipient_email,
			context=_ctx(doc, {"download_url": link, "expires": frappe.format(doc.download_expires, "Date")}),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			triggered_by="transcript-delivery",
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Transcript delivery failed: {doc.name}")
	_notify_student(doc, "transcript-issued", {"code": doc.verification_code})


# -- public: download and verification ---------------------------------------------------


def _by_code(code):
	code = (code or "").strip().upper()
	if not code:
		return None
	return frappe.db.get_value(
		"Transcript Request",
		{"verification_code": code, "status": "Issued"},
		[
			"name",
			"student_name",
			"issued_on",
			"pdf_sha256",
			"transcript_file",
			"download_key",
			"download_expires",
		],
		as_dict=True,
	)


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep
@rate_limit(limit=30, seconds=3600)
def download(code: str | None = None, key: str | None = None):
	"""The emailed link. Guest-reachable on purpose: the recipient has no account.
	The key is the authorization, it expires, and the endpoint is rate-limited."""
	row = _by_code(code)
	if not row or not row.download_key or not key or not secrets.compare_digest(row.download_key, key):
		frappe.throw(_("This link isn't valid."), frappe.PermissionError)
	if row.download_expires and getdate(row.download_expires) < getdate(today()):
		frappe.throw(
			_("This link has expired. Ask the student to request a new transcript."), frappe.PermissionError
		)
	file_doc = frappe.get_doc("File", {"file_url": row.transcript_file})
	frappe.local.response.filename = f"transcript-{row.name}.pdf"
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "download"


def verify(code):
	"""What the public page may show: never the grades."""
	row = _by_code(code)
	if not row:
		return None
	return frappe._dict(
		student_name=row.student_name,
		issued_on=row.issued_on,
		sha256=row.pdf_sha256,
		request=row.name,
	)


# -- portal -----------------------------------------------------------------------------


@frappe.whitelist()
def my_requests():
	from seminary.seminary.guards import current_student

	student = current_student()
	if not student:
		return {"requests": [], "enrollments": []}
	return {
		"requests": frappe.get_all(
			"Transcript Request",
			filters={"student": student},
			fields=[
				"name",
				"status",
				"delivery",
				"recipient_name",
				"recipient_email",
				"copies",
				"program_enrollment",
				"hold_note",
				"charges",
				"issued_on",
				"transcript_file",
				"verification_code",
				"creation",
			],
			order_by="creation desc",
		),
		"enrollments": frappe.get_all(
			"Program Enrollment",
			filters={"student": student, "docstatus": 1},
			fields=["name", "program"],
		),
	}


@frappe.whitelist(methods=["POST"])
def new_request(
	delivery: str,
	program_enrollment: str | None = None,
	recipient_name: str | None = None,
	recipient_email: str | None = None,
	mailing_address: str | None = None,
	copies: int | str = 1,
):
	from seminary.seminary.guards import current_student

	student = current_student()
	if not student:
		frappe.throw(_("Only a student can request their transcript here."), frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": "Transcript Request",
			"student": student,
			"delivery": delivery,
			"program_enrollment": program_enrollment or None,
			"recipient_name": recipient_name,
			"recipient_email": recipient_email,
			"mailing_address": mailing_address,
			"copies": copies,
		}
	)
	doc.insert()
	return {"name": doc.name, "status": frappe.db.get_value("Transcript Request", doc.name, "status")}
