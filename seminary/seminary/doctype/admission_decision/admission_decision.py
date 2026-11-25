# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary import admissions


class AdmissionDecision(Document):
	"""The outcome of an application (decisions/112 §5). The applicant's status
	follows the latest submitted decision."""

	def validate(self):
		status = frappe.db.get_value("Student Applicant", self.student_applicant, "application_status")
		if self.docstatus == 0 and not self.amended_from and status not in admissions.DECIDABLE:
			frappe.throw(
				_("An application can be decided once it is in review or waitlisted. It is {0}.").format(
					_(status)
				)
			)
		if self.amended_from and status == "Admitted":
			frappe.throw(_("The applicant is already a student."))
		if not self.flags.from_record_decision and admissions.is_claimed(self.program):
			frappe.throw(_("This program's applications are decided by its committee."))
		if self.decision != "Admit with conditions":
			self.conditions = None
			self.requires_leveling = 0
		counts, majority = admissions.tally(self.student_applicant)
		self.tally = admissions.tally_text(counts)
		self.majority = majority
		if (
			majority
			and not admissions.same_side(self.decision, majority)
			and not (self.rationale or "").strip()
		):
			frappe.throw(
				_("The decision differs from the majority of reviews ({0}). Give the rationale.").format(
					_(majority)
				),
				title=_("Rationale needed"),
			)

	def before_submit(self):
		if not self.flags.from_record_decision and not admissions.may_decide(self.program):
			frappe.throw(_("Only the program director or a registrar can decide."), frappe.PermissionError)
		self.decided_by = frappe.session.user

	def on_submit(self):
		admissions.apply_decision(self)

	def before_cancel(self):
		if (
			frappe.db.get_value("Student Applicant", self.student_applicant, "application_status")
			== "Admitted"
		):
			frappe.throw(_("The applicant is already a student, so the decision stands."))

	def on_cancel(self):
		admissions.revert_decision(self)
