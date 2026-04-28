# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, formatdate, getdate, now
import calendar
from datetime import timedelta
from dateutil import relativedelta

from seminary.seminary.utils import OverlapError
import json
import secrets


CANCELLABLE_STATES = ("Open for Enrollment", "Enrollment Closed")
CANCEL_ROLES = ("Registrar", "Seminary Manager")

# Import only into pre-enrollment-close states. Once enrollment has closed,
# the prof has effectively committed to the structure for the term. If the
# workflow's Draft / Open for Enrollment state names ever change in
# cs_lifecycle.py / workflow.json, update this list.
TEMPLATE_IMPORT_STATES = ("Draft", "Open for Enrollment")
TEMPLATE_IMPORT_ROLES = ("Academics User", "Seminary Manager", "Registrar")


class CourseSchedule(Document):
    @frappe.whitelist()
    def validate(self):
        self.generate_token()
        self.set_title()
        if frappe.flags.in_demo_install:
            return
        self.validate_date()
        self.validate_time()
        self.validate_assessment_criteria()
        self.validate_instructor_categories()
        self.clean_name()
        self._resolve_dates_if_needed()

    def before_insert(self):
        if not self.workflow_state:
            from seminary.seminary.cs_lifecycle import get_default_initial_state

            self.workflow_state = get_default_initial_state(self)

        self._seed_assessment_criteria_from_course()

    def _seed_assessment_criteria_from_course(self):
        """Auto-populate courseassescrit_sc from Course.assessment_criteria.

        Runs only on a fresh CS (SCAC empty, course set). Maps Course
        Assessment Criteria → Scheduled Course Assess Criteria field by
        field. Includes ``title`` (mandatory on SCAC). ``type`` is
        intentionally omitted — SCAC.type is fetch_from
        assesscriteria_scac.type and resolves on save.
        """
        if self.courseassescrit_sc or not self.course:
            return

        for cc in frappe.get_all(
            "Course Assessment Criteria",
            filters={"parent": self.course, "parenttype": "Course"},
            fields=["title", "assessment_criteria", "weightage"],
            order_by="idx asc",
        ):
            self.append(
                "courseassescrit_sc",
                {
                    "title": cc.title,
                    "assesscriteria_scac": cc.assessment_criteria,
                    "weight_scac": cc.weightage,
                    # Explicit 0 — validate_assessment_criteria's if/elif on
                    # extracredit_scac silently skips rows where the value
                    # is None, causing the weight sum to drop and fail the
                    # 100% check. Course Assessment Criteria has no extra-
                    # credit field; everything copied here is non-extra-credit.
                    "extracredit_scac": 0,
                },
            )

    def on_trash(self):
        if self.workflow_state and self.workflow_state != "Draft":
            frappe.throw(
                _(
                    "Only Course Schedules in the Draft state can be deleted. "
                    "Use Cancel Course to retire a course that has opened for enrollment."
                )
            )

    def _resolve_dates_if_needed(self):
        from seminary.seminary.cs_lifecycle import resolve_window_dates

        dates = resolve_window_dates(self)
        self.enrollment_open_date = dates.get("enrollment_open")
        self.enrollment_close_date = dates.get("enrollment_close")
        self.grade_close_date = dates.get("grade_close")

    def validate_instructor_categories(self):
        """When HRMS payroll is enabled, every instructor row needs a category."""
        if not frappe.db.get_single_value("Seminary Settings", "hrms_enable"):
            return
        for row in self.get("instructor1", []):
            if not row.instructor_category:
                frappe.throw(
                    _(
                        "Instructor {0} (row {1}) is missing an Instructor Category. "
                        "Category is required while HRMS Payroll is enabled."
                    ).format(row.instructor or "?", row.idx)
                )

    def set_title(self):
        section = self.section if hasattr(self, "section") and self.section else ""
        parts = [self.course or "", self.academic_term or ""]
        if section:
            parts.append(section)
        self.title = " - ".join(p for p in parts if p)

    def clean_name(self):
        if self.name and ("/" in self.name or "\\" in self.name):
            # Just remove forward slashes and let Frappe handle the rest
            self.name = self.name.replace("/", "-").replace("\\", "-")

    def validate_assessment_criteria(self):
        """Validates if the total weightage of all assessment criteria is 100%"""
        if self.courseassescrit_sc:
            total_weight_scac = 0
            for criteria in self.courseassescrit_sc:
                if criteria.extracredit_scac == 0:
                    total_weight_scac += criteria.weight_scac or 0
                elif criteria.extracredit_scac == 1:
                    continue
            if total_weight_scac != 100:
                frappe.throw(
                    _("Total Weight of all Assessment Criteria must total 100%")
                )

    def convert_to_date(self, date):
        if isinstance(date, str):
            return datetime.strptime(date, "%Y-%m-%d").date()
        if isinstance(date, datetime):
            return date.date()
        return date

    def validate_date(self):
        academic_term = self.academic_term
        start_date, end_date = frappe.db.get_value(
            "Academic Term", academic_term, ["term_start_date", "term_end_date"]
        )
        start_date = self.convert_to_date(start_date)
        end_date = self.convert_to_date(end_date)
        course_datestart = self.c_datestart
        course_dateend = self.c_dateend
        course_datestart = self.convert_to_date(course_datestart)
        course_dateend = self.convert_to_date(course_dateend)
        if (
            start_date
            and end_date
            and ((course_datestart < start_date) or (course_dateend > end_date))
        ):
            frappe.throw(
                _(
                    "Schedule date selected does not lie within the Academic Term: {}"
                ).format(self.academic_term)
            )

    def validate_time(self):
        """Validates if from_time is greater than to_time"""
        if (
            self.is_new()
            or self.has_value_changed("from_time")
            or self.has_value_changed("to_time")
        ):
            if self.from_time and self.to_time:
                if self.from_time > self.to_time:
                    frappe.throw(_("From Time cannot be greater than To Time."))

    def generate_token(self):
        if not self.calendar_token:
            self.calendar_token = secrets.token_hex(32)

    @frappe.whitelist()
    def regenerate_token(self):
        self.calendar_token = secrets.token_hex(32)
        self.save()
        return self.calendar_token

    @frappe.whitelist()
    def schedule_dates(self, days):
        """Returns a list of meeting dates and also creates child documents for each meeting date"""
        meeting_dates = []
        meeting_dates_errors = []

        # Remove existing meeting dates through the ORM (not raw SQL)
        self.set("cs_meetinfo", [])

        current_date = self.c_datestart

        while current_date <= self.c_dateend:
            if calendar.day_name[getdate(current_date).weekday()] in days:
                try:
                    meeting_date = self.append(
                        "cs_meetinfo",
                        {
                            "cs_meetdate": current_date,
                            "cs_fromtime": self.from_time,
                            "cs_totime": self.to_time,
                        },
                    )
                    meeting_dates.append(meeting_date)
                except OverlapError:
                    meeting_dates_errors.append(current_date)

            current_date = add_days(current_date, 1)

        # Save the parent once — this persists all children and updates the timestamp
        self.hasmtgdate = 1 if meeting_dates else 0
        self.flags.ignore_permissions = True
        self.save()

        return dict(
            meeting_dates=meeting_dates,
            meeting_dates_errors=meeting_dates_errors,
        )

    @frappe.whitelist()
    def cancel_course(self, reason):
        """Transition a Course Schedule to Cancelled and run the cascade.

        Permitted only from Open for Enrollment or Enrollment Closed (the
        state machine forbids cancellation once grading has started). Marks
        each non-withdrawn Course Enrollment Individual as course_cancelled,
        deletes the auto-populated Program Enrollment Course rows (preserving
        partner-seminary rows per ADR 005), and submits a Seminary
        Announcement to enrolled students.
        """
        roles = set(frappe.get_roles(frappe.session.user))
        if not roles.intersection(CANCEL_ROLES):
            frappe.throw(
                _("Only Registrar or Seminary Manager can cancel a course."),
                frappe.PermissionError,
            )

        if self.workflow_state not in CANCELLABLE_STATES:
            frappe.throw(
                _(
                    "Cannot cancel a course in state {0}. Cancellation is "
                    "only allowed before grading starts."
                ).format(self.workflow_state or _("(none)"))
            )

        if not frappe.db.exists("Course Cancellation Reason", reason):
            frappe.throw(_("Cancellation reason {0} does not exist.").format(reason))

        # Cancellation isn't a regular workflow transition (intentionally
        # absent from the workflow fixture so the Desk Action menu cannot
        # bypass this method). Use db.set_value to skip Frappe's
        # transition validator — the role/state gates above are the
        # authoritative checks.
        cancelled_at = now()
        user = frappe.session.user
        frappe.db.set_value(
            "Course Schedule",
            self.name,
            {
                "cancellation_reason": reason,
                "cancelled_on": cancelled_at,
                "cancelled_by": user,
                "workflow_state": "Cancelled",
            },
        )
        self.cancellation_reason = reason
        self.cancelled_on = cancelled_at
        self.cancelled_by = user
        self.workflow_state = "Cancelled"

        _cascade_cancel_pec_and_cei(self.name, reason)
        _create_cancellation_announcement(self, reason)

    @frappe.whitelist()
    def import_template(self, source_cs):
        """Copy LMS structure (chapters, lessons, assessment criteria) from
        another Course Schedule of the same course into this one.

        All validations (target + source) run as cheap reads up-front. Only
        when every check passes does the write phase begin — there are no
        expected rollbacks. Frappe's request-level transaction still rolls
        back on genuine exceptions.

        Replaces the target's SCAC rows (so the placeholder satisfying
        ``courseassescrit_sc.reqd:1`` is overwritten). Refuses if the target
        already has chapters or any graded data. Roster, grades, and SCAC
        due_dates are NOT copied.
        """
        self._validate_target_for_import(source_cs)
        _validate_source_for_import(source_cs)

        # All persistence is via direct child-doc inserts. self.save() is
        # avoided on purpose: Course Lesson.updates_lessons (and any other
        # denorm hook chain) bumps target fields via db.set_value during
        # the inserts below, and a parent save would race that — both on
        # the modified timestamp (TimestampMismatchError) and on stale
        # denorm field values (lessons count getting overwritten with the
        # in-memory 0). Source weights are validated up-front, so we don't
        # lose any meaningful save-time check.
        scac_name_map = _replace_scac_rows(source_cs, self.name)
        n_chapters, n_lessons, lesson_name_map = _copy_chapters_and_lessons(
            source_cs, self.name
        )
        _remap_lesson_scac_links(lesson_name_map, scac_name_map)

        n_scac = len(scac_name_map)
        self.add_comment(
            "Info",
            _(
                "Imported template from {0} on {1} by {2}. "
                "Copied: {3} chapters, {4} lessons, {5} assessment criteria."
            ).format(
                source_cs,
                formatdate(now()),
                frappe.session.user,
                n_chapters,
                n_lessons,
                n_scac,
            ),
        )

        return {
            "chapters": n_chapters,
            "lessons": n_lessons,
            "scac": n_scac,
        }

    def _validate_target_for_import(self, source_cs):
        """Read-only checks on the target side. Throws on any violation."""
        roles = set(frappe.get_roles(frappe.session.user))
        if not roles.intersection(TEMPLATE_IMPORT_ROLES):
            frappe.throw(
                _(
                    "Only Academics User, Seminary Manager, or Registrar can "
                    "import a course template."
                ),
                frappe.PermissionError,
            )

        if self.workflow_state not in TEMPLATE_IMPORT_STATES:
            frappe.throw(
                _(
                    "Cannot import a template while the course is in state {0}. "
                    "Allowed states: Draft, Open for Enrollment."
                ).format(self.workflow_state or _("(none)"))
            )

        if source_cs == self.name:
            frappe.throw(_("A schedule cannot be imported into itself."))

        if not frappe.db.exists("Course Schedule", source_cs):
            frappe.throw(
                _("Source Course Schedule {0} does not exist.").format(source_cs)
            )

        source_course = frappe.db.get_value("Course Schedule", source_cs, "course")
        if source_course != self.course:
            frappe.throw(
                _(
                    "Source schedule belongs to course {0}; this schedule "
                    "belongs to {1}. Templates can only be imported between "
                    "schedules of the same course."
                ).format(source_course, self.course)
            )

        n_chapters = len(self.chapters or [])
        if n_chapters > 0:
            frappe.throw(
                _(
                    "Target schedule already has {0} chapter(s). Clear them "
                    "first or import into a fresh schedule."
                ).format(n_chapters)
            )

        graded_count = frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM `tabCourse Assess Results Detail` card
            JOIN `tabScheduled Course Roster` scr ON card.parent = scr.name
            WHERE scr.course_sc = %s AND COALESCE(card.graded_card, 0) = 1
            """,
            (self.name,),
        )[0][0]
        if graded_count:
            frappe.throw(
                _(
                    "Target schedule already has graded assessments and cannot "
                    "be overwritten by a template import."
                )
            )


def _cascade_cancel_pec_and_cei(cs_name, reason):
    """Mark CEIs as course-cancelled and hard-delete the auto-populated PECs.

    Mirrors the direct ``db.set_value`` pattern used in withdrawal.py to avoid
    re-running CEI validate() on every flip. Partner-seminary PEC rows (per
    ADR 005) are preserved by the COALESCE filter — those rows reuse the same
    course link with a different meaning and are not part of this cascade.
    """
    cei_names = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "coursesc_ce": cs_name,
            "withdrawn": 0,
            "docstatus": 1,
        },
        pluck="name",
    )
    cancelled_at = now()
    for cei in cei_names:
        frappe.db.set_value(
            "Course Enrollment Individual",
            cei,
            {
                "course_cancelled": 1,
                "course_cancellation_reason": reason,
                "course_cancelled_on": cancelled_at,
            },
        )

    frappe.db.sql(
        """
        DELETE FROM `tabProgram Enrollment Course`
        WHERE course = %s
          AND COALESCE(partner_seminary, '') = ''
        """,
        (cs_name,),
    )


def _create_cancellation_announcement(cs, reason):
    """Submit a Seminary Announcement notifying enrolled students.

    Skipped when there are no enrolled students — Seminary Announcement
    rejects empty audiences and the throw would roll back the cancellation
    transaction. A cancellation with nobody to notify is still a valid
    cancellation.
    """
    if not frappe.db.count(
        "Course Enrollment Individual",
        {"coursesc_ce": cs.name, "withdrawn": 0, "docstatus": 1},
    ):
        return

    doc = frappe.get_doc(
        {
            "doctype": "Seminary Announcement",
            "subject": _("Course cancelled: {0}").format(cs.title or cs.name),
            "academic_term": cs.academic_term,
            "message": _(
                "<p>The course <b>{course}</b> ({term}) has been cancelled.</p>"
                "<p><b>Reason:</b> {reason}</p>"
                "<p>Please contact the registrar about rescheduling or "
                "alternative enrollment options.</p>"
            ).format(
                course=cs.title or cs.name,
                term=cs.academic_term,
                reason=reason,
            ),
            "audience_students_enrolled": 1,
            "courses": [{"course_schedule": cs.name}],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()


@frappe.whitelist()
def bulk_close_enrollment(names):
    """Drive selected Course Schedules from Open for Enrollment to Enrollment Closed.

    Used by the registrar to mass-close enrollment at the end of the
    registration window when a manual sweep is preferred over the daily
    scheduler. Skips schedules that are not in Open for Enrollment or that
    the caller cannot edit.
    """
    if isinstance(names, str):
        names = json.loads(names)

    closed, skipped = [], []
    for name in names:
        if not frappe.has_permission("Course Schedule", "write", doc=name):
            skipped.append(name)
            continue
        state = frappe.db.get_value("Course Schedule", name, "workflow_state")
        if state != "Open for Enrollment":
            skipped.append(name)
            continue
        try:
            apply_workflow(frappe.get_doc("Course Schedule", name), "Close Enrollment")
            closed.append(name)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"bulk_close_enrollment failed: {name}",
            )
            skipped.append(name)
    return {"closed": closed, "skipped": skipped}


# ── Course Template Import helpers ──────────────────────────────────────────


def _validate_source_for_import(source_cs):
    """Read-only checks on the source side. Throws on any violation."""
    scac_count = frappe.db.count(
        "Scheduled Course Assess Criteria", {"parent": source_cs}
    )
    if not scac_count:
        frappe.throw(
            _(
                "Source schedule {0} has no assessment criteria; "
                "nothing structural to import."
            ).format(source_cs)
        )

    weight_total = (
        frappe.db.sql(
            """
            SELECT COALESCE(SUM(weight_scac), 0)
            FROM `tabScheduled Course Assess Criteria`
            WHERE parent = %s AND COALESCE(extracredit_scac, 0) = 0
            """,
            (source_cs,),
        )[0][0]
        or 0
    )
    if int(weight_total) != 100:
        frappe.throw(
            _(
                "Source schedule {0}'s non-extra-credit weights total {1}% "
                "(must be 100% before it can be used as a template). "
                "Fix source first."
            ).format(source_cs, weight_total)
        )


# Fields excluded when copying a SCAC row:
#   - due_date: per-CS state; stays null on target until set
#   - lesson:   free-text label of the source lesson; not valid on target
_SCAC_COPYABLE_FIELDS = (
    "assesscriteria_scac",
    "title",
    "weight_scac",
    "quiz",
    "assignment",
    "exam",
    "discussion",
    "extracredit_scac",
    "fudgepoints_scac",
)


def _replace_scac_rows(source_cs_name, target_cs_name):
    """Delete target's SCAC rows and insert fresh copies from source via
    direct child-doc inserts (bypasses parent save).

    Returns ``{source_scac_name: new_scac_name}`` for the lesson Link remap.
    """
    frappe.db.delete(
        "Scheduled Course Assess Criteria",
        {"parent": target_cs_name, "parenttype": "Course Schedule"},
    )

    source_rows = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": source_cs_name, "parenttype": "Course Schedule"},
        fields=["name", "idx"] + list(_SCAC_COPYABLE_FIELDS),
        order_by="idx asc",
    )

    name_map = {}
    for row in source_rows:
        new_row = frappe.get_doc(
            {
                "doctype": "Scheduled Course Assess Criteria",
                "parent": target_cs_name,
                "parenttype": "Course Schedule",
                "parentfield": "courseassescrit_sc",
                "idx": row.idx,
                **{field: row.get(field) for field in _SCAC_COPYABLE_FIELDS},
            }
        )
        new_row.flags.ignore_permissions = True
        new_row.insert()
        name_map[row.name] = new_row.name
    return name_map


# Course Schedule Chapter fields copied verbatim (besides chapter_title and
# the back-reference coursesc which are set explicitly). SCORM file references
# are shared between CSes — the underlying File doc is independent of any CS.
_CHAPTER_COPYABLE_FIELDS = (
    "is_scorm_package",
    "scorm_package",
    "scorm_package_path",
    "manifest_file",
    "launch_file",
)

# Course Lesson content fields copied verbatim. assessment_criteria_* fields
# are NOT copied here — they're handled by _remap_lesson_scac_links after the
# target SCAC rows have names. course_sc, course_code, is_scorm_package
# auto-fetch from the new chapter.
_LESSON_COPYABLE_FIELDS = (
    "lesson_title",
    "body",
    "content",
    "preview",
    "youtube",
    "instructor_notes",
    "instructor_content",
    "allow_discuss",
)


def _copy_chapters_and_lessons(source_cs_name, target_cs_name):
    """Clone Course Schedule Chapter + Course Lesson docs from source to target.

    All child-table refs (chapter refs on the CS, lesson refs on each new
    chapter) are inserted as direct child docs — no parent save. This is
    deliberate: ``Course Lesson.updates_lessons`` (and any other denorm
    hook) writes back to the target via ``db.set_value`` during the lesson
    inserts, and a subsequent parent save would race those writes. See
    ``import_template`` for the full rationale.

    Returns ``(n_chapters, n_lessons, lesson_name_map)``. The map is
    ``{source_lesson_name: new_lesson_name}`` — used by the SCAC link remap.
    """
    n_chapters = 0
    n_lessons = 0
    lesson_name_map = {}

    chapter_refs = frappe.get_all(
        "Course Schedule Chapter Reference",
        filters={"parent": source_cs_name, "parenttype": "Course Schedule"},
        fields=["chapter", "idx"],
        order_by="idx asc",
    )
    for ref in chapter_refs:
        if not ref.chapter:
            continue
        src_chapter = frappe.get_doc("Course Schedule Chapter", ref.chapter)

        new_chapter = frappe.new_doc("Course Schedule Chapter")
        new_chapter.coursesc = target_cs_name
        new_chapter.chapter_title = src_chapter.chapter_title
        for field in _CHAPTER_COPYABLE_FIELDS:
            new_chapter.set(field, src_chapter.get(field))
        new_chapter.flags.ignore_permissions = True
        new_chapter.insert()
        n_chapters += 1

        lesson_refs = frappe.get_all(
            "Course Schedule Lesson Reference",
            filters={
                "parent": src_chapter.name,
                "parenttype": "Course Schedule Chapter",
            },
            fields=["lesson", "idx"],
            order_by="idx asc",
        )
        for lesson_idx, lref in enumerate(lesson_refs, start=1):
            if not lref.lesson:
                continue
            src_lesson = frappe.get_doc("Course Lesson", lref.lesson)
            new_lesson = frappe.new_doc("Course Lesson")
            new_lesson.chapter = new_chapter.name
            for field in _LESSON_COPYABLE_FIELDS:
                new_lesson.set(field, src_lesson.get(field))
            new_lesson.flags.ignore_permissions = True
            new_lesson.insert()
            n_lessons += 1
            lesson_name_map[src_lesson.name] = new_lesson.name

            # Direct child insert into Course Schedule Chapter.lessons —
            # skips a chapter parent save.
            lesson_ref = frappe.get_doc(
                {
                    "doctype": "Course Schedule Lesson Reference",
                    "parent": new_chapter.name,
                    "parenttype": "Course Schedule Chapter",
                    "parentfield": "lessons",
                    "idx": lesson_idx,
                    "lesson": new_lesson.name,
                }
            )
            lesson_ref.flags.ignore_permissions = True
            lesson_ref.insert()

        # Direct child insert into Course Schedule.chapters — skips the CS
        # parent save (which would race the denorm hooks above).
        chapter_ref = frappe.get_doc(
            {
                "doctype": "Course Schedule Chapter Reference",
                "parent": target_cs_name,
                "parenttype": "Course Schedule",
                "parentfield": "chapters",
                "idx": ref.idx,
                "chapter": new_chapter.name,
            }
        )
        chapter_ref.flags.ignore_permissions = True
        chapter_ref.insert()

    return n_chapters, n_lessons, lesson_name_map


_LESSON_SCAC_LINK_FIELDS = (
    "assessment_criteria_quiz",
    "assessment_criteria_assignment",
    "assessment_criteria_exam",
    "assessment_criteria_discussion",
)


def _remap_lesson_scac_links(lesson_name_map, scac_name_map):
    """Rewrite each new lesson's assessment_criteria_* Links to point at the
    target CS's SCAC rows (not the source CS's).

    Reads source's Links, looks up the new SCAC name in scac_name_map, writes
    via ``frappe.db.set_value`` (which bypasses ``Course Lesson.on_update``
    so we don't race ``update_lesson_assessments``). Skips nulls.
    """
    for src_lesson_name, new_lesson_name in lesson_name_map.items():
        src_links = frappe.db.get_value(
            "Course Lesson",
            src_lesson_name,
            list(_LESSON_SCAC_LINK_FIELDS),
            as_dict=True,
        )
        if not src_links:
            continue
        update = {}
        for field in _LESSON_SCAC_LINK_FIELDS:
            old_scac = src_links.get(field)
            if not old_scac:
                continue
            new_scac = scac_name_map.get(old_scac)
            if new_scac:
                update[field] = new_scac
        if update:
            frappe.db.set_value("Course Lesson", new_lesson_name, update)
