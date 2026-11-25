# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today


class PersonEducation(Document):
	"""A qualification a person holds (decisions/111 §5). Applications add
	rows; staff edit them; the person can read their own."""

	def validate(self):
		year = cint(self.year_completed)
		if year and not 1900 <= year <= getdate(today()).year + 10:
			frappe.throw(_("Year Completed must be a four-digit year."))
		if self.person_document:
			owner = frappe.db.get_value("Person Document", self.person_document, "person")
			if owner != self.person:
				frappe.throw(_("The diploma must be a document of the same person."))


def get_permission_query_conditions(user=None):
	from seminary.seminary import requirements

	return requirements._person_condition("Person Education", user)


def has_permission(doc, ptype=None, user=None):
	from seminary.seminary import requirements

	if ptype not in (None, "read", "print") and not requirements._is_staff(user):
		return False
	return requirements._person_has(doc, user)
