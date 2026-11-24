"""When a score an LTI tool posts reaches the gradebook (decisions/110 §7).

The score is kept on an **LTI Score** whatever happens. It is written to a
gradebook cell under the four rules SCORM passback follows (p009 §2.12,
`seminary.scorm.grades`):

1. **The lesson is mapped.** `Course Lesson.lti_assessment_criteria`, set by
   staff or by a Deep Linking line item. Unmapped keeps the score on the lesson.
2. **Competency and narrative sections stand down.** Their cell holds a level,
   and a percentage written there would be read back as one.
3. **A grader's number wins, permanently.** A cell is ours while ungraded, or
   while it still holds the number we last wrote there.
4. **Only `FullyGraded` reports.** A tool still grading has nothing final.

A tool's score is more trustworthy than a SCORM one -- it comes server to server
under a signed token, not from the student's browser -- but it is still a claim
by someone else's software, which is why the mapping stays an instructor's act.
"""

from __future__ import annotations

import frappe
from frappe import _

REPORTING = {"FullyGraded"}


def percentage(score_given, score_maximum) -> float | None:
	if score_given is None:
		return None
	try:
		given = float(score_given)
		top = float(score_maximum) if score_maximum not in (None, "") else 100.0
	except (TypeError, ValueError):
		return None
	if top <= 0:
		return None
	return max(0.0, min(100.0, given / top * 100.0))


def _last_pushed(lesson: str, member: str, exclude: str | None = None) -> float | None:
	filters = {"lesson": lesson, "member": member, "reported": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"LTI Score", filters=filters, fields=["pushed_score"], order_by="creation desc", limit=1
	)
	return rows[0].pushed_score if rows else None


def push(score) -> dict:
	"""Write `score` (an LTI Score) to its lesson's mapped cell if the rules hold."""
	criteria = frappe.db.get_value("Course Lesson", score.lesson, "lti_assessment_criteria")
	if not criteria:
		return {"reported": False, "reason": "not mapped"}
	if score.grading_progress not in REPORTING:
		return {"reported": False, "reason": "not fully graded"}
	if not score.has_score or score.percentage is None:
		return {"reported": False, "reason": "no score"}

	from seminary.seminary import cbe
	from seminary.seminary.api import narrative_section

	if cbe.framework_for(score.course):
		return {"reported": False, "reason": "competency section"}
	if narrative_section(score.course):
		return {"reported": False, "reason": "narrative section"}

	student = (
		frappe.db.get_value("Scheduled Course Roster", score.roster, "student") if score.roster else None
	)
	if not student:
		return {"reported": False, "reason": "no roster row"}
	card_name = frappe.db.get_value(
		"Course Assess Results Detail",
		{"assessment_criteria": criteria, "student_card": student},
		"name",
	)
	if not card_name:
		frappe.log_error(
			f"No Course Assess Results Detail for criterion {criteria} and student {student} "
			f"(LTI Score {score.name}). Score not propagated.",
			"lti grades: missing CARD row",
		)
		return {"reported": False, "reason": "no gradebook cell"}

	card = frappe.get_doc("Course Assess Results Detail", card_name)
	if card.graded_card:
		last = _last_pushed(score.lesson, score.member, exclude=score.name)
		if (
			not card.lti_reported_card
			or last is None
			or abs(float(card.rawscore_card or 0) - float(last)) >= 0.001
		):
			return {"reported": False, "reason": "a grader owns this cell"}

	card.rawscore_card = score.percentage
	card.graded_card = 1
	card.lti_reported_card = 1
	card.save(ignore_permissions=True)
	return {"reported": True, "percentage": score.percentage, "criteria": criteria}


def new_criterion(course: str, title: str) -> str | None:
	"""A gradebook row for a Deep Linking line item: weight 0, so the section
	can't be saved until someone weighs it (108's rule for imported grades).
	None on a competency or narrative section, where the row would never fill."""
	from seminary.seminary import cbe
	from seminary.seminary.api import narrative_section

	if cbe.framework_for(course) or narrative_section(course):
		return None
	ac = None
	for kind in ("Offline", "Assignment"):
		ac = frappe.db.get_value("Assessment Criteria", {"type": kind}, ["name", "type"], as_dict=True)
		if ac:
			break
	if not ac:
		return None
	row = frappe.get_doc(
		{
			"doctype": "Scheduled Course Assess Criteria",
			"parent": course,
			"parenttype": "Course Schedule",
			"parentfield": "courseassescrit_sc",
			"title": title,
			"assesscriteria_scac": ac.name,
			"type": ac.type,
			"weight_scac": 0,
		}
	)
	row.flags.ignore_permissions = True
	row.insert()
	return row.name


# ---------------------------------------------------------------- the mapping, in the SPA


def _staff_lesson(lesson: str):
	"""The lesson, for its section's staff only; a lesson you may not see is
	refused the same way as one that does not exist."""
	from seminary.lti.launch import lesson_context
	from seminary.seminary.guards import require_course_staff

	row = lesson_context(lesson)
	require_course_staff(row.course, include_registrar=True)
	if not row.lti_tool:
		frappe.throw(_("This lesson does not open an external tool."), frappe.DoesNotExistError)
	return row


@frappe.whitelist()
def criteria_for_lesson(lesson: str) -> dict:
	from seminary.seminary import cbe
	from seminary.seminary.api import narrative_section

	row = _staff_lesson(lesson)
	return {
		"lesson": lesson,
		"course": row.course,
		"current": row.lti_assessment_criteria,
		"competency_section": bool(cbe.framework_for(row.course) or narrative_section(row.course)),
		"criteria": frappe.get_all(
			"Scheduled Course Assess Criteria",
			filters={"parent": row.course, "parenttype": "Course Schedule"},
			fields=["name", "title", "assesscriteria_scac", "weight_scac", "type"],
			order_by="idx asc",
		),
	}


@frappe.whitelist(methods=["POST"])
def set_criteria(lesson: str, criteria: str | None = None) -> dict:
	from seminary.seminary.guards import CONTENT, require_section_capability

	row = _staff_lesson(lesson)
	require_section_capability(row.course, CONTENT, include_registrar=True)
	criteria = (criteria or "").strip() or None
	if criteria:
		owner = frappe.db.get_value(
			"Scheduled Course Assess Criteria", criteria, ["parent", "parenttype"], as_dict=True
		)
		if not owner or owner.parenttype != "Course Schedule":
			frappe.throw(_("No such assessment criterion."), frappe.DoesNotExistError)
		if owner.parent != row.course:
			from seminary.seminary import security_log

			security_log.record_denial("lti_criteria_scope", lesson=lesson, course=row.course)
			frappe.throw(_("That criterion belongs to a different section."), frappe.PermissionError)
	frappe.db.set_value("Course Lesson", lesson, "lti_assessment_criteria", criteria)
	return {"ok": True, "lesson": lesson, "current": criteria}
