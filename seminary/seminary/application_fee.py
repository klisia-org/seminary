# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Application fee discounts and waivers (decisions/113).

Seminary decides the discount; the installed financial backend applies it.
An application carries one discount, a percent, from one source:

- *Window*: the program's Application Fee Window that holds the application's
  creation date;
- *Code*: an Application Fee Code the applicant typed on the form;
- *Request*: a waiver the applicant asked for and staff approved.

The largest wins; discounts never add up. Window and code are fixed when the
application is created, so the backend can price the fee on insert. A request
is decided later and the backend credits the open charge.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, cstr, escape_html, flt, getdate, now_datetime, nowdate

APPLICANT = "Student Applicant"
CODE = "Application Fee Code"
REQUESTED, APPROVED, DECLINED = "Requested", "Approved", "Declined"
TEMPLATES = {APPROVED: "fee-waiver-approved", DECLINED: "fee-waiver-declined"}


def pct(value):
	"""50 rather than 50.0 in what people read."""
	return f"{flt(value):g}"


def _backend():
	from seminary.seminary.financial.backend import get_financial_backend

	return get_financial_backend()


def fee_configured(program):
	"""Whether the program charges an application fee at all."""
	if not program or frappe.db.get_value("Program", program, "is_free"):
		return False
	try:
		return bool(_backend().application_fee_configured(program))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "application fee lookup failed")
		return False


# --------------------------------------------------------------------------- #
# Windows and codes
# --------------------------------------------------------------------------- #
def window_for(program, on_date=None):
	"""The program's fee window holding `on_date`, or None."""
	if not program:
		return None
	on_date = getdate(on_date or nowdate())
	for row in frappe.get_all(
		"Application Fee Window",
		filters={"parent": program, "parenttype": "Program", "parentfield": "application_fee_windows"},
		fields=["label", "from_date", "to_date", "discount_percent"],
		order_by="from_date asc",
	):
		if getdate(row.from_date) <= on_date <= getdate(row.to_date):
			return row
	return None


def normalize_code(code):
	return cstr(code).strip().upper()


def code_uses(code, exclude=None):
	filters = {"fee_waiver_code": normalize_code(code)}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.db.count(APPLICANT, filters)


def check_code(code, program, on_date=None, applicant=None):
	"""The code's discount for this program and date, or a plain error."""
	code = normalize_code(code)
	shown = escape_html(code)
	row = frappe.db.get_value(
		CODE,
		code,
		["name", "discount_percent", "active", "valid_from", "valid_to", "max_uses"],
		as_dict=True,
	)
	if not row or not cint(row.active):
		frappe.throw(_("The fee code {0} is not valid.").format(shown), title=_("Fee code"))
	on_date = getdate(on_date or nowdate())
	if (row.valid_from and on_date < getdate(row.valid_from)) or (
		row.valid_to and on_date > getdate(row.valid_to)
	):
		frappe.throw(_("The fee code {0} is not valid on this date.").format(shown), title=_("Fee code"))
	programs = frappe.get_all(
		"Application Fee Code Program", filters={"parent": code, "parenttype": CODE}, pluck="program"
	)
	if programs and program not in programs:
		frappe.throw(_("The fee code {0} is not valid for this program.").format(shown), title=_("Fee code"))
	if cint(row.max_uses) and code_uses(code, exclude=applicant) >= cint(row.max_uses):
		frappe.throw(_("The fee code {0} has been used up.").format(shown), title=_("Fee code"))
	return flt(row.discount_percent)


# --------------------------------------------------------------------------- #
# The application's discount
# --------------------------------------------------------------------------- #
def validate(doc):
	"""Student Applicant.validate: fix the window and code discount on a new
	application, and open a waiver request when the program accepts them."""
	before = None if doc.is_new() else doc.get_doc_before_save()
	doc.fee_waiver_code = normalize_code(doc.fee_waiver_code) or None
	if before and cstr(before.fee_waiver_code) != cstr(doc.fee_waiver_code):
		frappe.throw(
			_("The fee code is fixed when the application is made. Use a fee waiver instead."),
			title=_("Fee code"),
		)
	if doc.is_new() and not frappe.flags.in_import:
		on_date = doc.application_date or nowdate()
		best, source = 0.0, None
		window = window_for(doc.program, on_date)
		if window and flt(window.discount_percent) > best:
			best, source = flt(window.discount_percent), "Window"
		if doc.fee_waiver_code:
			pct = check_code(doc.fee_waiver_code, doc.program, on_date)
			if pct > best:
				best, source = pct, "Code"
		doc.fee_discount_percent = min(best, 100)
		doc.fee_discount_source = source
	_open_request(doc, before)


def _open_request(doc, before):
	if before and before.fee_waiver_status:
		# Decided or open: the decision fields are written only by `decide_waiver`.
		for field in ("fee_waiver_requested", "fee_waiver_reason", "fee_waiver_status"):
			doc.set(field, before.get(field))
		return
	doc.fee_waiver_status = None
	if not cint(doc.fee_waiver_requested):
		return
	allowed = doc.program and cint(frappe.db.get_value("Program", doc.program, "allow_fee_waiver_requests"))
	if not allowed or flt(doc.fee_discount_percent) >= 100 or not fee_configured(doc.program):
		# Nothing to waive, or the program doesn't take requests.
		doc.fee_waiver_requested = 0
		doc.fee_waiver_reason = None
		return
	if not cstr(doc.fee_waiver_reason).strip():
		frappe.throw(_("Say why you are asking for a fee waiver."), title=_("Fee waiver"))
	doc.fee_waiver_status = REQUESTED


def discount(applicant):
	"""(percent, source) the backend applies to the fee (decisions/113 §4)."""
	doc = applicant if hasattr(applicant, "doctype") else frappe.get_doc(APPLICANT, applicant)
	return flt(doc.get("fee_discount_percent")), doc.get("fee_discount_source")


def request_open(doc):
	return doc.get("fee_waiver_status") == REQUESTED


# --------------------------------------------------------------------------- #
# Deciding a request
# --------------------------------------------------------------------------- #
def may_decide_waiver(program, user=None):
	"""The admissions unit's chair, a Registrar or a Seminary Manager (decisions/113 §5)."""
	from seminary.seminary import admissions

	user = user or frappe.session.user
	return admissions.is_staff(user) or bool(program and admissions.unit_chair(program) == user)


@frappe.whitelist()
def decide_waiver(applicant: str, approve: int | str, note: str, percent: float | None = None):
	doc = frappe.get_doc(APPLICANT, applicant)
	if not may_decide_waiver(doc.program):
		frappe.throw(_("You cannot decide fee waivers for this program."), frappe.PermissionError)
	if not request_open(doc):
		frappe.throw(_("There is no open fee waiver request on this application."))
	note = cstr(note).strip()
	if not note:
		frappe.throw(_("Say why, so the decision is on record."))
	approve = cint(approve)
	status = APPROVED if approve else DECLINED
	values = {
		"fee_waiver_status": status,
		"fee_waiver_decided_by": frappe.session.user,
		"fee_waiver_decided_on": now_datetime(),
		"fee_waiver_note": note,
	}
	if approve:
		percent = flt(percent if percent not in (None, "") else 100)
		if not 0 < percent <= 100:
			frappe.throw(_("The waiver must be more than 0 and at most 100 percent."))
		if percent <= flt(doc.fee_discount_percent):
			frappe.throw(
				_("This application already has {0}% off the fee.").format(pct(doc.fee_discount_percent))
			)
		backend = _backend()
		if flt(backend.application_fee_paid(doc.name)) > 0:
			frappe.throw(_("Part of the fee is already paid. Waiving it now would be a refund."))
		backend.waive_application_fee(doc.name, percent, note)
		values.update(
			{"fee_waiver_percent": percent, "fee_discount_percent": percent, "fee_discount_source": "Request"}
		)
	frappe.db.set_value(APPLICANT, doc.name, values, update_modified=False)
	doc.update(values)
	notify(doc)
	from seminary.seminary import admissions

	admissions.check(doc)
	return status


def notify(doc):
	"""Tell the applicant. A missing template or address never stops the decision."""
	from seminary.seminary import admissions, comms

	template = TEMPLATES.get(doc.fee_waiver_status)
	if not (template and doc.student_email_id and frappe.db.exists("Communication Template", template)):
		return
	try:
		comms.send(
			doc.person,
			template,
			to_address=doc.student_email_id,
			channel="Email",
			reference_doctype=APPLICANT,
			reference_name=doc.name,
			dedupe_key=f"fee-waiver-{doc.name}",
			context={
				"applicant": doc.title,
				"program": doc.program,
				"percent": pct(doc.fee_waiver_percent),
				"note": doc.fee_waiver_note or "",
				"status_url": admissions.status_url(doc.name),
			},
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "fee waiver notice failed")


# --------------------------------------------------------------------------- #
# Public form and program page
# --------------------------------------------------------------------------- #
def window_note(program):
	""" "No application fee until 15 January", for the program page (§2)."""
	if not fee_configured(program):
		return None
	window = window_for(program)
	if not window:
		return None
	until = frappe.utils.formatdate(window.to_date, "d MMMM")
	if flt(window.discount_percent) >= 100:
		text = _("No application fee until {0}").format(until)
	else:
		text = _("{0}% off the application fee until {1}").format(pct(window.discount_percent), until)
	return f"{window.label}: {text}" if window.label else text


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep.rules.security.guest-whitelisted-method
@rate_limit(limit=300, seconds=3600, ip_based=True)
def form_options(program: str | None = None):
	"""What the public form offers for one program: the code field and the
	waiver request only when the program charges a fee."""
	if not program or not frappe.db.exists("Program", program) or not fee_configured(program):
		return {"has_fee": False, "allow_requests": False, "window": None}
	return {
		"has_fee": True,
		"allow_requests": bool(cint(frappe.db.get_value("Program", program, "allow_fee_waiver_requests"))),
		"window": window_note(program),
	}
