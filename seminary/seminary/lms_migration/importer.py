"""Import a course from another LMS into an empty Course Schedule (decisions/108).

The upload is recognised, read into a Course Pack manifest by its reader, and
handed to the Course Pack importer (decisions/041), which here fills this
section instead of creating one. The report lists what was created and what
was skipped, with the reason (§4)."""

import frappe
from frappe import _
from frappe.utils import flt, formatdate, now

from seminary.seminary.course_pack.constants import IMPORT_ROLES
from seminary.seminary.course_pack.import_ import _Importer

from .archive import Archive
from .builder import FakeZip

IMPORT_STATES = ("Draft", "Open for Enrollment")


class MigrationImporter(_Importer):
	def __init__(self, builder, cs):
		super().__init__(builder.manifest(), FakeZip(builder.blobs), "existing", cs.course, None, None, None)
		self.builder = builder
		self.target = cs
		self.rubric_count = 0

	def resolve_course(self):
		return self.target.course

	def create_cs(self):
		from seminary.seminary import cbe_reflection

		cs = self.target
		if cs.chapters:
			cbe_reflection.clear_scaffold(cs.name)
		# The section's own assessment rows are replaced only when the course
		# brings graded work, as Import Course Template replaces them (014).
		if self.m.get("scac"):
			frappe.db.delete(
				"Scheduled Course Assess Criteria",
				{"parent": cs.name, "parenttype": "Course Schedule"},
			)
		return frappe.get_doc("Course Schedule", cs.name)

	def after_content(self, cs):
		for rec in self.builder.rubrics:
			activity = self.a_map.get(rec["src"])
			if activity:
				self._rubric(rec, activity)

	def _rubric(self, rec, activity):
		from seminary.seminary import rubrics

		scale = frappe.db.get_value(
			"Rubric Scale", {"is_default": 1, "enabled": 1}, "name"
		) or frappe.db.get_value("Rubric Scale", {"enabled": 1}, "name")
		if not scale:
			self.builder.skip(rec["title"], _("rubric: this site has no rubric scale"))
			return
		levels = sorted(rubrics.scale_levels(scale), key=lambda lv: flt(lv.percent))
		total = sum(flt(c.get("points")) for c in rec["criteria"]) or 0
		criteria = []
		for c in rec["criteria"]:
			cells = {}
			top = flt(c.get("points")) or max([flt(p) for p, _t in c.get("ratings") or []] or [0])
			for points, descriptor in c.get("ratings") or []:
				if not (descriptor or "").strip() or not levels:
					continue
				pct = (flt(points) / top * 100) if top else 0
				level = min(levels, key=lambda lv: abs(flt(lv.percent) - pct)).label
				cells[level] = f"{cells[level]}; {descriptor}" if level in cells else descriptor
			criteria.append(
				{
					"title": c.get("title") or _("Criterion"),
					"description": c.get("description") or "",
					"weight": round(flt(c.get("points")) / total * 100, 2) if total else 0,
					"cells": cells,
				}
			)
		rubrics.save_rubric(rec["doctype"], activity, scale, criteria)
		self.rubric_count += 1

	def summary_comment(self, n_ch, n_les):
		return _(
			"Imported a course from {0} on {1} by {2}: {3} chapters, {4} lessons, {5} activities, "
			"{6} questions, {7} skipped."
		).format(
			self.builder.source_format,
			formatdate(now()),
			frappe.session.user,
			n_ch,
			n_les,
			len(self.a_map),
			len(self.q_map),
			len(self.builder.skipped),
		)


def _check_target(cs):
	from seminary.seminary import cbe_reflection

	if not set(frappe.get_roles()).intersection(IMPORT_ROLES):
		frappe.throw(
			_("Only Program Chair, Seminary Manager, or Registrar can import a course."),
			frappe.PermissionError,
		)
	cs.check_permission("write")
	if cs.workflow_state not in IMPORT_STATES:
		frappe.throw(_("A course can only be imported while the section is in Draft or Open for Enrollment."))
	if cs.chapters and not cbe_reflection.untouched_scaffold(cs.name):
		frappe.throw(_("This section already has chapters. Import into a section with none."))
	graded = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabCourse Assess Results Detail` card
		JOIN `tabScheduled Course Roster` scr ON card.parent = scr.name
		WHERE scr.course_sc = %s AND COALESCE(card.graded_card, 0) = 1
		""",
		(cs.name,),
	)[0][0]
	if graded:
		frappe.throw(_("This section already has grades, so a course cannot be imported into it."))


def read_course(content):
	"""The builder for an upload: a Common Cartridge or a Moodle backup."""
	from . import common_cartridge, moodle

	archive = Archive(content)
	if archive.has("imsmanifest.xml"):
		return common_cartridge.read(archive)
	if archive.has("moodle_backup.xml"):
		return moodle.read(archive)
	frappe.throw(
		_("This file is neither a Common Cartridge (.imscc) nor a Moodle backup (.mbz)."),
		title=_("Not a course export"),
	)


def import_into(cs_name, content):
	"""Core import from the upload's bytes; reusable in tests."""
	cs = frappe.get_doc("Course Schedule", cs_name)
	_check_target(cs)
	builder = read_course(content)
	importer = MigrationImporter(builder, cs)
	result = importer.run()
	return {
		"source": builder.source_format,
		"chapters": result["chapters"],
		"lessons": result["lessons"],
		"activities": result["activities"],
		"questions": result["questions"],
		"rubrics": importer.rubric_count,
		"files": result["media"],
		"skipped": builder.skipped,
		"notes": builder.notes + [{"title": "", "note": w} for w in result["warnings"]],
	}


@frappe.whitelist(methods=["POST"])
def import_course(course_schedule: str, file_url: str) -> dict:
	"""Import an uploaded .imscc or .mbz into this section. The upload is the
	caller's own private File and is deleted afterwards."""
	cs = frappe.get_doc("Course Schedule", course_schedule)
	_check_target(cs)  # before the upload is read
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("The uploaded file was not found."))
	f = frappe.get_doc("File", name)
	if f.owner != frappe.session.user:
		frappe.throw(_("Upload the file yourself to import it."), frappe.PermissionError)
	from .archive import MAX_BYTES, limit

	if (f.file_size or 0) > limit("lms_migration_max_bytes", MAX_BYTES):
		frappe.throw(_("The file is too large to import."))
	content = f.get_content(encodings=[])
	if isinstance(content, str):
		content = content.encode("utf-8")
	report = import_into(course_schedule, content)
	f.delete(ignore_permissions=True)
	return report
