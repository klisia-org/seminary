# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Application questions from a shared pool, chosen per program (decisions/111).

The pool is `Application Question`; a program links the ones its form asks in
`Program.application_questions`, with Required on each row. Answers land in
`Student Applicant.answers` with the question's label and group as the
applicant saw them. Three pool entries are *Table sections*: they show or
require a child table that stays on the applicant (education, emergency
contacts, references).

Education history and emergency contacts are facts about the person, so the
rows typed on the application are copied to the Person when it is saved.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, cstr, getdate, validate_email_address


def N_(text):
	"""Marks a seeded label for translation; `_()` translates it when shown."""
	return text


QUESTION = "Application Question"
TABLE_SECTION = "Table section"
# Table section -> Student Applicant table field.
TABLE_FIELDS = {
	"Education history": "education",
	"Emergency contacts": "contacts",
	"References": "references",
}

_READING = "\n".join(
	(
		N_("I read books, magazines, and articles frequently"),
		N_("I read books and magazines occasionally"),
		N_("I don't have the habit of reading, but I used to"),
		N_("I never developed the habit of reading"),
	)
)
_COMPUTER = "\n".join(
	(
		N_("I am familiar with and have access to a computer with internet, word processor, and email"),
		N_("I have a computer but I struggle with new programs"),
		N_("I am proficient in email, internet, and word processors, but I don't have a computer"),
		N_("I don't have a computer and my computer skills need development"),
	)
)

# The questions the form used to hard-code, in the order it asked them
# (decisions/111 §6 and §8). Seeded once, by `seed_key`; schools edit them.
SEED = (
	("education-history", N_("Your education"), TABLE_SECTION, None, N_("Education"), "Education history"),
	(
		"reading",
		N_("Regarding your reading habits, which option best describes you?"),
		"Select",
		_READING,
		N_("Education"),
		None,
	),
	(
		"computer-literacy",
		N_("Regarding your computer literacy, which option best describes you?"),
		"Select",
		_COMPUTER,
		N_("Education"),
		None,
	),
	("email-daily", N_("Do you check your email daily (Mon-Sat)?"), "Check", None, N_("Education"), None),
	(
		"emergency-contacts",
		N_("Emergency contacts"),
		TABLE_SECTION,
		None,
		N_("Contacts"),
		"Emergency contacts",
	),
	("references", N_("References"), TABLE_SECTION, None, N_("Contacts"), "References"),
	("employer", N_("Place of Employment"), "Short text", None, N_("Employment"), None),
	("position", N_("Position"), "Short text", None, N_("Employment"), None),
	("employer-address", N_("Employer Business Address"), "Short text", None, N_("Employment"), None),
	("employer-city", N_("Employer City"), "Short text", None, N_("Employment"), None),
	("employer-postal-code", N_("Employer ZIP code"), "Short text", None, N_("Employment"), None),
	("employment-start", N_("Start Date"), "Date", None, N_("Employment"), None),
	("supervisor", N_("Direct Supervisor"), "Short text", None, N_("Employment"), None),
	("supervisor-phone", N_("Supervisor Phone"), "Phone", None, N_("Employment"), None),
	("church-name", N_("Name of the Church"), "Short text", None, N_("Church"), None),
	("church-address", N_("Church Address"), "Short text", None, N_("Church"), None),
	("church-city", N_("Church City"), "Short text", None, N_("Church"), None),
	("church-state", N_("Church State"), "Short text", None, N_("Church"), None),
	("church-postal-code", N_("Church ZIP code"), "Short text", None, N_("Church"), None),
	(
		"church-contact",
		N_("Who should we contact to confirm your church participation?"),
		"Short text",
		None,
		N_("Church"),
		None,
	),
	("church-contact-title", N_("Title of this person"), "Short text", None, N_("Church"), None),
	("church-contact-phone", N_("Phone number of this person"), "Phone", None, N_("Church"), None),
	("church-contact-email", N_("Email of this person"), "Email", None, N_("Church"), None),
	(
		"gospel",
		N_("Please explain your understanding of the gospel and the Christian life."),
		"Long text",
		None,
		N_("Faith and Practice"),
		None,
	),
	(
		"testimony",
		N_("How did you become a believer? What changed in your life?"),
		"Long text",
		None,
		N_("Faith and Practice"),
		None,
	),
	(
		"program-expectations",
		N_("How will enrolling in this program help you serve the church?"),
		"Long text",
		None,
		N_("Faith and Practice"),
		None,
	),
)


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #
def seed_questions():
	"""Create the seeded pool questions that are missing. Returns their names in
	seed order, existing ones included."""
	names = []
	for key, question, answer_type, options, group, table in SEED:
		name = frappe.db.get_value(QUESTION, {"seed_key": key})
		if not name:
			doc = frappe.get_doc(
				{
					"doctype": QUESTION,
					"seed_key": key,
					"question": question,
					"answer_type": answer_type,
					"options": options,
					"group_label": group,
					"table_section": table,
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
			name = doc.name
		names.append(name)
	return names


def link_to_programs(names, programs=None):
	"""Give every program without application questions the seeded ones, so
	its form asks what it asked before (decisions/111 §8)."""
	for program in programs or frappe.get_all("Program", pluck="name"):
		if frappe.db.exists(
			"Program Application Question",
			{"parent": program, "parenttype": "Program", "parentfield": "application_questions"},
		):
			continue
		doc = frappe.get_doc("Program", program)
		for name in names:
			doc.append("application_questions", {"question": name, "required": 0})
		doc.flags.ignore_validate = True
		doc.flags.ignore_mandatory = True
		doc.save(ignore_permissions=True)


def setup():
	if frappe.db.exists("DocType", QUESTION):
		link_to_programs(seed_questions())


# --------------------------------------------------------------------------- #
# What a program asks
# --------------------------------------------------------------------------- #
def program_questions(program):
	"""The program's rows joined to the pool, in order. Inactive questions are
	left out."""
	if not program:
		return []
	rows = frappe.get_all(
		"Program Application Question",
		filters={"parent": program, "parenttype": "Program", "parentfield": "application_questions"},
		fields=["question", "required"],
		order_by="idx asc",
	)
	if not rows:
		return []
	pool = {
		q.name: q
		for q in frappe.get_all(
			QUESTION,
			filters={"name": ["in", [r.question for r in rows]], "is_active": 1},
			fields=[
				"name",
				"question",
				"answer_type",
				"options",
				"table_section",
				"group_label",
				"help_text",
			],
		)
	}
	out = []
	for r in rows:
		q = pool.get(r.question)
		if q:
			out.append(frappe._dict(q, required=cint(r.required)))
	return out


def choices(q):
	return [c.strip() for c in cstr(q.options).split("\n") if c.strip()]


# The public form reads school configuration, rate-limited; nothing about any person.
@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep.rules.security.guest-whitelisted-method
@rate_limit(limit=300, seconds=3600, ip_based=True)
def application_questions(program: str | None = None):
	"""What the public form shows for one program: its questions and which of
	the three tables it asks for."""
	if not program or not frappe.db.exists("Program", program):
		return {"questions": [], "tables": {}}
	questions, tables = [], {}
	for q in program_questions(program):
		if q.answer_type == TABLE_SECTION:
			field = TABLE_FIELDS.get(q.table_section)
			if field:
				tables[field] = {
					"label": _(q.question),
					"help": _(q.help_text) if q.help_text else "",
					"required": q.required,
				}
			continue
		questions.append(
			{
				"question": q.name,
				"label": _(q.question),
				"answer_type": q.answer_type,
				"choices": [{"value": c, "label": _(c)} for c in choices(q)],
				"group": _(q.group_label) if q.group_label else "",
				"help": _(q.help_text) if q.help_text else "",
				"required": q.required,
			}
		)
	return {"questions": questions, "tables": tables}


# --------------------------------------------------------------------------- #
# Checking answers
# --------------------------------------------------------------------------- #
def _check_value(q, value):
	label = _(q.question)
	if q.answer_type == "Select" and value not in choices(q):
		frappe.throw(_("{0}: choose one of the options.").format(label))
	if q.answer_type == "Check" and value not in ("0", "1"):
		frappe.throw(_("{0}: answer yes or no.").format(label))
	if q.answer_type == "Number":
		try:
			float(value)
		except ValueError:
			frappe.throw(_("{0}: enter a number.").format(label))
	if q.answer_type == "Date":
		try:
			getdate(value)
		except Exception:
			frappe.throw(_("{0}: enter a date.").format(label))
	if q.answer_type == "Email" and not validate_email_address(value):
		frappe.throw(_("{0}: enter a valid email address.").format(label))


def _empty(q, value):
	if q.answer_type == "Check":
		return value != "1"
	return not value


def check_answers(applicant):
	"""Keep only answers to the program's questions, record each question as it
	reads now, and refuse a missing required answer or table."""
	questions = program_questions(applicant.program)
	by_name = {q.name: q for q in questions}
	given = {}
	for row in applicant.get("answers") or []:
		if row.question in by_name and row.question not in given:
			given[row.question] = cstr(row.answer).strip()

	answers = []
	for q in questions:
		if q.answer_type == TABLE_SECTION:
			field = TABLE_FIELDS.get(q.table_section)
			if field and q.required and not applicant.get(field):
				frappe.throw(
					_("Add at least one row to {0}.").format(_(q.question)), title=_("Missing information")
				)
			continue
		value = given.get(q.name, "")
		if q.answer_type == "Check":
			value = "1" if value in ("1", "true", "True", "on") else ("0" if value else "")
		if q.required and _empty(q, value):
			frappe.throw(_("{0} is required.").format(_(q.question)), title=_("Missing information"))
		if value:
			_check_value(q, value)
		answers.append(
			{
				"question": q.name,
				"question_label": q.question,
				"group_label": q.group_label,
				"answer": value,
			}
		)
	# A table the program does not ask for is not kept.
	asked = {TABLE_FIELDS.get(q.table_section) for q in questions if q.answer_type == TABLE_SECTION}
	for field in TABLE_FIELDS.values():
		if field not in asked and applicant.get(field) and applicant.is_new():
			applicant.set(field, [])
	applicant.set("answers", answers)


def _answers_key(doc):
	return [(r.question, cstr(r.answer)) for r in doc.get("answers") or []]


def validate(applicant):
	"""Student Applicant.validate: answers are checked while the application
	is open and frozen once it is in review (decisions/111 §4, 112 §2)."""
	before = None if applicant.is_new() else applicant.get_doc_before_save()
	locked = before is not None and before.application_status not in ("Applied", None, "")
	if locked:
		if _answers_key(applicant) != _answers_key(before) or applicant.program != before.program:
			frappe.throw(
				_("The answers and the program cannot change once the application is in review."),
				title=_("Application is in review"),
			)
		return
	if frappe.flags.in_import:
		return
	check_answers(applicant)


# --------------------------------------------------------------------------- #
# What crosses to the Person
# --------------------------------------------------------------------------- #
def adopt_education(applicant):
	"""Each education row becomes a Person Education (decisions/111 §5)."""
	if not applicant.person:
		return
	for row in applicant.get("education") or []:
		if row.person_education or not (row.institution or "").strip():
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Person Education",
				"person": applicant.person,
				"institution": row.institution,
				"country": row.country,
				"degree": row.degree,
				"level": row.level,
				"field_of_study": row.field_of_study,
				"year_completed": row.year_completed,
				"student_applicant": applicant.name,
			}
		).insert(ignore_permissions=True)
		row.db_set("person_education", doc.name, update_modified=False)


def _contact_key(row):
	return (
		cstr(row.get("contact_name")).strip().lower(),
		cstr(row.get("phone")).strip(),
		cstr(row.get("email")).strip().lower(),
	)


def adopt_emergency_contacts(applicant):
	"""Emergency contacts typed on the application join the Person's
	(decisions/111 §6). A contact already there is not added twice."""
	rows = [r for r in applicant.get("contacts") or [] if (r.contact_name or "").strip()]
	if not applicant.person or not rows:
		return
	person = frappe.get_doc("Person", applicant.person)
	have = {_contact_key(r) for r in person.get("emergency_contacts") or []}
	added = False
	for r in rows:
		if _contact_key(r) in have:
			continue
		person.append(
			"emergency_contacts",
			{"contact_name": r.contact_name, "relation": r.relation, "phone": r.phone, "email": r.email},
		)
		have.add(_contact_key(r))
		added = True
	if added:
		person.flags.ignore_permissions = True
		person.save()


def adopt(applicant):
	"""after_insert / on_update: what the application carries to the Person."""
	from seminary.seminary import requirements

	adopt_education(applicant)
	adopt_emergency_contacts(applicant)
	requirements.sign_application_agreements(applicant)


# --------------------------------------------------------------------------- #
# Pool upkeep
# --------------------------------------------------------------------------- #
def has_answers(question):
	return bool(frappe.db.exists("Student Applicant Answer", {"question": question}))
