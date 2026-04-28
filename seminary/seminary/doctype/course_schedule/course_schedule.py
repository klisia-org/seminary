# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, getdate, now
import calendar
from datetime import timedelta
from dateutil import relativedelta

from seminary.seminary.utils import OverlapError
import json
import secrets


CANCELLABLE_STATES = ("Open for Enrollment", "Enrollment Closed")
CANCEL_ROLES = ("Registrar", "Seminary Manager")


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
