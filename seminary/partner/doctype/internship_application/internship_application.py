# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from seminary.partner import internship
from seminary.partner.doctype.internship_type.internship_type import (
    claim_advisor_slot,
    release_advisor_slot,
)

# Statuses in which the placement(s) and requirements exist and the position
# counts the application as filled.
ACTIVE_STATES = ("Accepted", "Active", "Completed")
CLOSED_OUT_STATES = ("Rejected", "Withdrawn")

# Application status -> the status it reflects onto the graduation requirement row.
SGR_STATUS_MAP = {
    "Submitted": "In Progress",
    "Under Review": "Submitted",
    "Accepted": "In Progress",
    "Active": "In Progress",
    "Completed": "Fulfilled",
}


class InternshipApplication(Document):
    def before_validate(self):
        self._resolve_student_from_session()
        self._default_hours_needed()

    def validate(self):
        self._prevent_duplicate()
        self._handle_submission()
        self._auto_accept()

    def on_update(self):
        self._apply_status_effects()
        internship.recompute_application_hours(self.name)

    def on_trash(self):
        if self.faculty_advisor:
            release_advisor_slot(self.internship_type, self.faculty_advisor)

    # ------------------------------------------------------------------ #
    # before_validate
    # ------------------------------------------------------------------ #
    def _resolve_student_from_session(self):
        """Portal safety net: resolve the student from the logged-in user's
        Person spine when a caller omits it."""
        if self.student:
            return
        person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
        if person:
            self.student = frappe.db.get_value("Student", {"person": person}, "name")

    def _default_hours_needed(self):
        if not self.total_hours_needed and self.internship_type:
            self.total_hours_needed = frappe.db.get_value(
                "Internship Type", self.internship_type, "total_hours_required"
            )

    # ------------------------------------------------------------------ #
    # validate
    # ------------------------------------------------------------------ #
    def _prevent_duplicate(self):
        """One live application per student per position (a withdrawn one may be
        replaced)."""
        dupe = frappe.db.exists(
            "Internship Application",
            {
                "internship_position": self.internship_position,
                "student": self.student,
                "status": ("!=", "Withdrawn"),
                "name": ("!=", self.name),
            },
        )
        if dupe:
            frappe.throw(
                _("{0} already has an application to this position ({1}).").format(
                    frappe.bold(self.student), dupe
                )
            )

    def _handle_submission(self):
        """When the application first leaves Draft: confirm the position is open,
        gate on an open graduation requirement, and stamp the submission time."""
        before = self.get_doc_before_save()
        was_draft = before.status == "Draft" if before else True
        entering = self.status != "Draft" and (self.is_new() or was_draft)
        if not entering:
            return

        status = frappe.db.get_value(
            "Internship Position", self.internship_position, "status"
        )
        if status == "Closed":
            frappe.throw(
                _(
                    "This internship position is closed and no longer accepting applications."
                )
            )

        self._resolve_eligibility()
        self._resolve_required_hours()
        if not self.submission_date:
            self.submission_date = now_datetime()

    def _resolve_required_hours(self):
        """Required hours come from the student's frozen graduation requirement
        row (snapshotted from the program's policy, so one type serves many
        programs), falling back to the Internship Type default."""
        hours = None
        if self.student_grad_requirement:
            hours = frappe.db.get_value(
                "Student Graduation Requirement",
                self.student_grad_requirement,
                "internship_hours_required",
            )
        if not hours:
            hours = frappe.db.get_value(
                "Internship Type", self.internship_type, "total_hours_required"
            )
        if hours:
            self.total_hours_needed = hours

    def _resolve_eligibility(self):
        """Set program_enrollment + student_grad_requirement from the student's
        open requirement of this internship type (ADR 054 §6). Ungated when the
        type maps to no requirement item."""
        if self.student_grad_requirement and self.program_enrollment:
            return
        match = internship.resolve_open_requirement(self.student, self.internship_type)
        if match:
            self.program_enrollment = match["program_enrollment"]
            self.student_grad_requirement = match["student_grad_requirement"]
            return
        item = frappe.db.get_value(
            "Internship Type", self.internship_type, "graduation_requirement_item"
        )
        if item:
            frappe.throw(
                _(
                    "{0} has no open graduation requirement for this internship type, so "
                    "they aren't eligible to apply."
                ).format(frappe.bold(self.student))
            )

    def _auto_accept(self):
        if self.status != "Submitted":
            return
        mode = frappe.db.get_value(
            "Internship Position", self.internship_position, "acceptance_mode"
        )
        if mode == "Auto-Accept on Submission":
            self.status = "Accepted"

    # ------------------------------------------------------------------ #
    # on_update — status side effects
    # ------------------------------------------------------------------ #
    def _apply_status_effects(self):
        before = self.get_doc_before_save()
        prev = before.status if before else None

        self._reflect_sgr()

        if self.status in ACTIVE_STATES and prev not in ACTIVE_STATES:
            self._on_accepted()
        if self.status in CLOSED_OUT_STATES and prev not in CLOSED_OUT_STATES:
            self._on_closed_out()

    def _reflect_sgr(self):
        """Mirror the application status onto its graduation requirement row, and
        release the row (back to Not Started) if the application is rejected or
        withdrawn so the student can apply elsewhere."""
        if not self.student_grad_requirement or not self.program_enrollment:
            return
        reset = self.status in CLOSED_OUT_STATES
        target = SGR_STATUS_MAP.get(self.status)

        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        dirty = False
        for row in pe.graduation_requirements or []:
            if row.name != self.student_grad_requirement:
                continue
            if reset:
                if row.linked_doc == self.name:
                    row.linked_doc = None
                    row.link_doctype = None
                    if row.status not in ("Fulfilled", "Waived"):
                        row.status = "Not Started"
                    dirty = True
            else:
                if (
                    row.link_doctype != "Internship Application"
                    or row.linked_doc != self.name
                ):
                    row.link_doctype = "Internship Application"
                    row.linked_doc = self.name
                    dirty = True
                if target and row.status != target:
                    row.status = target
                    if target == "Fulfilled":
                        row.fulfilled_on = today()
                    dirty = True
            break
        if dirty:
            pe.save(ignore_permissions=True)

    def _on_accepted(self):
        self._assign_faculty()
        internship.snapshot_application_requirements(self)
        self._ensure_default_placement()
        self._sync_position()

    def _assign_faculty(self):
        if self.faculty_advisor:
            return
        instructor = claim_advisor_slot(self.internship_type)
        if instructor:
            self.db_set("faculty_advisor", instructor)

    def _ensure_default_placement(self):
        if frappe.db.exists(
            "Internship Placement", {"internship_application": self.name}
        ):
            return
        pos = frappe.db.get_value(
            "Internship Position",
            self.internship_position,
            ["partner_org", "location", "default_site_supervisor"],
            as_dict=True,
        )
        frappe.get_doc(
            {
                "doctype": "Internship Placement",
                "internship_application": self.name,
                "partner_org": pos.partner_org,
                "location": pos.location,
                "site_supervisor": pos.default_site_supervisor,
                "hours_allocated": self.total_hours_needed,
                "placement_status": "Proposed",
            }
        ).insert(ignore_permissions=True)

    def _on_closed_out(self):
        if self.faculty_advisor:
            release_advisor_slot(self.internship_type, self.faculty_advisor)
        self._sync_position()

    def _sync_position(self):
        frappe.get_doc(
            "Internship Position", self.internship_position
        ).sync_placements_filled()


@frappe.whitelist()
def enroll_in_internship_course(application, course_schedule):
    """Provision and link a Course Enrollment Individual for a course-backed
    internship — the same machinery a Culminating Project uses (ADR 024/054 §5),
    giving the internship its fee, credits, and the grade that flows to the
    transcript via the Program Enrollment Course row. Staff action.
    """
    if not frappe.has_permission("Course Enrollment Individual", "create"):
        frappe.throw(
            _("You are not permitted to create course enrollments."),
            frappe.PermissionError,
        )

    app = frappe.get_doc("Internship Application", application)
    if app.course_enrollment:
        frappe.throw(
            _("This internship is already linked to course enrollment {0}.").format(
                app.course_enrollment
            )
        )
    if not app.program_enrollment:
        frappe.throw(_("This application has no Program Enrollment yet."))
    if not app.backing_course:
        frappe.throw(_("This internship type has no backing course."))

    cs_course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    if not cs_course:
        frappe.throw(_("Course Schedule {0} not found.").format(course_schedule))
    if cs_course != app.backing_course:
        frappe.throw(
            _(
                "Course Schedule {0} teaches {1}, but this internship expects {2}."
            ).format(course_schedule, cs_course, app.backing_course)
        )

    program = frappe.db.get_value(
        "Program Enrollment", app.program_enrollment, "program"
    )
    credits = (
        frappe.db.get_value(
            "Program Course",
            {"parent": program, "course": cs_course},
            "pgmcourse_credits",
        )
        or 0
    )

    cei = frappe.get_doc(
        {
            "doctype": "Course Enrollment Individual",
            "program_ce": app.program_enrollment,
            "coursesc_ce": course_schedule,
            "student_ce": app.student,
            "credits": credits,
        }
    )
    cei.insert(ignore_permissions=True)
    app.db_set("course_enrollment", cei.name)
    return {"course_enrollment": cei.name}
