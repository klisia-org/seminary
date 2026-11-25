"""decisions/111: the application's questions move to a shared pool.

- Seed the pool with the questions the form used to hard-code, and link them
  to every program that has none, so each form asks what it asked before.
- Emergency contacts on Student move to the Person; `Student.contacts` and
  the Student Contacts / Student Education doctypes go.
- One application form: other Student Applicant web forms are unpublished,
  since programs no longer point at them.

No school is live, so the old answers are not carried into the new table.
"""

import frappe


def execute():
	from seminary.seminary import application_form

	application_form.setup()
	_move_emergency_contacts()
	_unpublish_other_forms()
	for doctype in ("Student Contacts", "Student Education"):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, ignore_missing=True, force=True)


def _move_emergency_contacts():
	if not frappe.db.table_exists("Student Contacts"):
		return
	columns = set(frappe.db.get_table_columns("Student Contacts"))
	if "emergency" not in columns:
		return
	rows = frappe.db.sql(
		"""select c.contact_name, c.relation, s.person
		from `tabStudent Contacts` c join `tabStudent` s on s.name = c.parent
		where c.parenttype = 'Student' and c.emergency = 1 and ifnull(s.person, '') != ''""",
		as_dict=True,
	)
	relations = {"Spouse": "Spouse", "Relative": "Relative"}
	by_person = {}
	for r in rows:
		by_person.setdefault(r.person, []).append(r)
	for person, contacts in by_person.items():
		if not frappe.db.exists("Person", person):
			continue
		doc = frappe.get_doc("Person", person)
		have = {(c.contact_name or "").strip().lower() for c in doc.get("emergency_contacts") or []}
		for c in contacts:
			name = (c.contact_name or "").strip()
			if not name or name.lower() in have:
				continue
			doc.append(
				"emergency_contacts",
				{"contact_name": name, "relation": relations.get(c.relation, "Other")},
			)
			have.add(name.lower())
		doc.flags.ignore_permissions = True
		doc.flags.ignore_validate = True
		doc.save()


def _unpublish_other_forms():
	for name in frappe.get_all(
		"Web Form",
		filters={"doc_type": "Student Applicant", "name": ["!=", "student-applicant"], "published": 1},
		pluck="name",
	):
		frappe.db.set_value("Web Form", name, "published", 0)
