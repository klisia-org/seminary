# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""One student's own opening on one chapter (decisions/107 §6).

A blank `open_from` follows the chapter's release. Waiving prerequisites also
lifts the CBE self-assessment lock, so the reason is required and kept.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class StudentChapterReleaseOverride(Document):
	def validate(self):
		chapter = frappe.db.get_value(
			"Course Schedule Chapter", self.chapter, ["coursesc", "chapter_title"], as_dict=True
		)
		if not chapter:
			frappe.throw(_("Choose a chapter of this section."))
		if self.course_schedule and self.course_schedule != chapter.coursesc:
			frappe.throw(
				_("{0} belongs to another section, not {1}.").format(
					chapter.chapter_title, self.course_schedule
				)
			)
		self.course_schedule = chapter.coursesc
		self.chapter_title = chapter.chapter_title

		from seminary.seminary.guards import GRADE, require_section_capability

		require_section_capability(self.course_schedule, GRADE, include_registrar=True)

		if not frappe.db.exists(
			"Scheduled Course Roster",
			{"course_sc": self.course_schedule, "student": self.student},
		):
			frappe.throw(
				_("{0} is not on the roster of {1}.").format(
					self.student_name or self.student, self.course_schedule
				)
			)
		if frappe.db.exists(
			"Student Chapter Release Override",
			{"chapter": self.chapter, "student": self.student, "name": ["!=", self.name]},
		):
			frappe.throw(
				_("{0} already has an exception for {1}. Edit that one instead.").format(
					self.student_name or self.student, chapter.chapter_title
				)
			)
		if not (self.open_from or self.waive_prerequisites):
			frappe.throw(_("Set an opening date or waive the prerequisites."))
		if not (self.reason or "").strip():
			frappe.throw(_("Say why this student's chapter opens differently."))

	def on_trash(self):
		from seminary.seminary.guards import GRADE, require_section_capability

		require_section_capability(self.course_schedule, GRADE, include_registrar=True)
