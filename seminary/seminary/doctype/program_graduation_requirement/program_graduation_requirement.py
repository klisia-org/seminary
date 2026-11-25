# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class ProgramGraduationRequirement(Document):
	"""A program's catalog year (decisions/115). See seminary.seminary.catalog_year."""

	def validate(self):
		self._sync_lifecycle_fields()
		self._set_window()
		self._validate_catalog_rows()
		self._validate_linked_doc_status_values()
		self._normalize_blocks_graduation_request()

	def before_submit(self):
		self._validate_order()

	def on_submit(self):
		from seminary.seminary import catalog_year

		catalog_year.on_submit(self)

	def _sync_lifecycle_fields(self):
		"""`active` is derived from the workflow state: the catalog in force for new students."""
		self.active = 1 if self.workflow_state == "Active" else 0

	def _set_window(self):
		"""The window starts with the first term; the catalog year is that term's academic year."""
		if not self.academic_term_from:
			return
		term = frappe.db.get_value(
			"Academic Term",
			self.academic_term_from,
			["term_start_date", "academic_year"],
			as_dict=True,
		)
		if not term or not term.term_start_date:
			frappe.throw(_("The first term needs a start date."))
		self.starts_on = term.term_start_date
		self.catalog_year = term.academic_year or self.academic_term_from

	def _validate_catalog_rows(self):
		"""Courses come from the Program's courses and tracks from its tracks, once each."""
		if not self.program_name:
			return
		program_courses = set(
			frappe.get_all(
				"Program Course",
				filters={"parent": self.program_name, "parenttype": "Program"},
				pluck="course",
			)
		)
		program_tracks = set(
			frappe.get_all(
				"Program Track",
				filters={"parent": self.program_name, "parenttype": "Program"},
				pluck="name",
			)
		)
		seen = set()
		for row in self.catalog_courses or []:
			if row.course not in program_courses:
				frappe.throw(
					_("Row {0}: {1} isn't one of the program's courses. Add it to the program first.").format(
						row.idx, frappe.bold(row.course_name or row.course)
					)
				)
			if row.course in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, frappe.bold(row.course)))
			seen.add(row.course)
		for table in ("catalog_tracks", "catalog_track_courses"):
			for row in self.get(table) or []:
				if row.program_track not in program_tracks:
					frappe.throw(_("Row {0}: that track isn't one of the program's tracks.").format(row.idx))
		pairs = set()
		for row in self.catalog_track_courses or []:
			key = (row.program_track, row.course)
			if key in pairs:
				frappe.throw(_("Row {0}: that track course is listed twice.").format(row.idx))
			pairs.add(key)

	def _validate_order(self):
		"""Catalog years follow each other: a new one starts after every submitted one."""
		later = frappe.get_all(
			"Program Graduation Requirement",
			filters={
				"program_name": self.program_name,
				"docstatus": 1,
				"name": ("!=", self.name),
				"starts_on": (">=", self.starts_on),
			},
			fields=["name", "catalog_year"],
			limit=1,
		)
		if later:
			frappe.throw(
				_("Catalog year {0} already starts in or after this first term. Choose a later term.").format(
					get_link_to_form(self.doctype, later[0].name, later[0].catalog_year)
				)
			)

	def _normalize_blocks_graduation_request(self):
		"""`blocks_graduation_request` is only meaningful for mandatory rows
		(mirrors the GRI's depends_on). If a non-mandatory row still carries the
		flag — e.g. the grid editor didn't hide it — silently clear it so the
		snapshot can't inherit a contradictory state."""
		for row in self.pgr_items or []:
			if row.blocks_graduation_request and not row.mandatory:
				row.blocks_graduation_request = 0

	def _validate_linked_doc_status_values(self):
		"""Catch typos in linked_doc_status at policy authoring time."""
		for row in self.pgr_items or []:
			if row.activation_mode != "On Document Status":
				continue
			if not row.on_document or not row.linked_doc_status:
				continue
			if not _status_value_exists(row.on_document, row.linked_doc_status):
				frappe.throw(
					_("Row {0}: '{1}' is not a valid workflow_state or status value on {2}.").format(
						row.idx, row.linked_doc_status, row.on_document
					)
				)


def _status_value_exists(doctype, value):
	"""Check value exists as a Workflow State or as a Select option on workflow_state/status."""
	workflow_name = frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "name")
	if workflow_name:
		states = frappe.get_all(
			"Workflow Document State",
			filters={"parent": workflow_name},
			pluck="state",
		)
		if value in states:
			return True

	meta = frappe.get_meta(doctype)
	for fieldname in ("workflow_state", "status"):
		field = meta.get_field(fieldname)
		if field and field.fieldtype == "Select" and field.options:
			if value in [opt.strip() for opt in field.options.split("\n") if opt.strip()]:
				return True

	return False
