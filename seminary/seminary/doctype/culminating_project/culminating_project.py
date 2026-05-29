# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from seminary.seminary import date_rules

# Active-ish lifecycle states in which milestones are live (snapshot + tracked).
_ACTIVE_STATES = ("Active", "Under Review", "Completed")

# Required-sign-off check field -> sign-off role label.
_SIGNOFF_ROLES = (
    ("signoff_advisor", "Advisor"),
    ("signoff_second_reader", "Second Reader"),
    ("signoff_third_reader", "Third Reader"),
    ("signoff_committee", "Committee"),
)

# Sign-off role -> the Culminating Project reader field it must be filled from.
_ROLE_READER_FIELD = {
    "Second Reader": "second_reader",
    "Third Reader": "third_reader",
}


class CulminatingProject(Document):
    def validate(self):
        self._update_round_counter()
        self._maybe_snapshot_milestones()
        self._stamp_submission_metadata()
        self._validate_readers_for_milestones()
        self._derive_milestone_dates()
        self._compute_milestones_complete()

    def on_submit(self):
        self._link_to_sgr()

    def before_update_after_submit(self):
        # validate() does not run on update_after_submit saves, so recompute the
        # milestone-derived fields here too (e.g. after a sign-off flips a
        # milestone to Approved). These fields are allow_on_submit.
        self._derive_milestone_dates()
        self._compute_milestones_complete()

    def on_update_after_submit(self):
        self._reflect_state_to_sgr()

    def _update_round_counter(self):
        rounds = [int(s.round or 0) for s in self.submissions or []]
        self.current_round = max(rounds) if rounds else 0

    def _maybe_snapshot_milestones(self):
        """Materialize the project type's milestone template onto this project
        the first time it becomes active. Idempotent (skips once populated)."""
        if self.milestones or not self.project_type:
            return
        if self.workflow_state not in _ACTIVE_STATES:
            return
        snapshot_milestones(self)

    def _stamp_submission_metadata(self):
        """Auto-stamp submitted_by/submitted_on when a row is added without them."""
        for row in self.submissions or []:
            if not row.submitted_by:
                row.submitted_by = frappe.session.user
            if not row.submitted_on:
                row.submitted_on = now_datetime()
            if (
                row.reviewer_decision
                and row.reviewer_decision != "Pending"
                and not row.reviewed_on
            ):
                row.reviewed_on = now_datetime()

    def _validate_readers_for_milestones(self):
        """A milestone requiring a Second/Third Reader sign-off needs that
        reader slot populated on the project before work begins."""
        needed = set()
        for row in self.milestones or []:
            for check, role in _SIGNOFF_ROLES:
                if row.get(check) and role in _ROLE_READER_FIELD:
                    needed.add(role)
        for role in needed:
            field = _ROLE_READER_FIELD[role]
            if not self.get(field):
                frappe.throw(
                    _(
                        "A milestone requires a {0} sign-off — set the {0} on this project first."
                    ).format(role)
                )

    def _derive_milestone_dates(self):
        """Stamp proposal_approved_on / defended_on from the matching milestone's
        completion. Falls back to the legacy submissions signal for the proposal."""
        for row in self.milestones or []:
            if not row.completed_on:
                continue
            if row.milestone_kind == "Proposal" and not self.proposal_approved_on:
                self.proposal_approved_on = row.completed_on
            if row.milestone_kind == "Defense" and not self.defended_on:
                self.defended_on = row.completed_on

        if not self.proposal_approved_on:
            for row in self.submissions or []:
                if (
                    row.submission_type == "Proposal"
                    and row.reviewer_decision == "Accepted"
                ):
                    self.proposal_approved_on = today()
                    break

    def _compute_milestones_complete(self):
        """milestones_complete = every mandatory milestone is Approved/Waived
        (vacuously true when there are no mandatory milestones)."""
        mandatory = [m for m in (self.milestones or []) if m.mandatory]
        self.milestones_complete = (
            0 if any(m.status not in ("Approved", "Waived") for m in mandatory) else 1
        )

    def _link_to_sgr(self):
        if not self.student_grad_requirement or not self.program_enrollment:
            return
        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        dirty = False
        for row in pe.graduation_requirements or []:
            if row.name == self.student_grad_requirement:
                if row.linked_doc != self.name:
                    row.linked_doc = self.name
                    row.link_doctype = "Culminating Project"
                    row.status = "In Progress"
                    dirty = True
                break
        if dirty:
            pe.save(ignore_permissions=True)

    def _reflect_state_to_sgr(self):
        if not self.student_grad_requirement or not self.program_enrollment:
            return

        mapping = {
            "Active": "In Progress",
            "Under Review": "Submitted",
            "Completed": "Fulfilled",
            "Rejected": "Failed",
            "Withdrawn": "Failed",
        }
        new_status = mapping.get(self.workflow_state)
        if not new_status:
            return

        pe = frappe.get_doc("Program Enrollment", self.program_enrollment)
        dirty = False
        for row in pe.graduation_requirements or []:
            if row.name != self.student_grad_requirement:
                continue
            if row.status != new_status:
                row.status = new_status
                if new_status == "Fulfilled":
                    row.fulfilled_on = today()
                dirty = True
            break
        if dirty:
            pe.save(ignore_permissions=True)


@frappe.whitelist()
def add_submission(name, submission_type, attachment, student_note=None):
    """Whitelisted endpoint for the student to add a new submission round."""
    doc = frappe.get_doc("Culminating Project", name)
    if not _user_owns_project(doc):
        frappe.throw(
            _("You can only submit to your own project."), frappe.PermissionError
        )
    row = doc.append(
        "submissions",
        {
            "round": (doc.current_round or 0) + 1,
            "submission_type": submission_type,
            "attachment": attachment,
            "student_note": student_note,
            "submitted_by": frappe.session.user,
            "submitted_on": now_datetime(),
            "reviewer": doc.advisor,
            "reviewer_decision": "Pending",
        },
    )
    doc.save(ignore_permissions=True)
    return {"round": row.round}


def _user_owns_project(doc):
    user_email = frappe.session.user
    student_email = frappe.db.get_value("Student", doc.student, "student_email_id")
    return user_email == student_email


# ---------------------------------------------------------------------------
# Milestones (ADR 025): template on Culminating Project Type -> dated snapshot
# on the project. Mirrors graduation.snapshot_graduation_requirements.
# ---------------------------------------------------------------------------


def snapshot_milestones(project):
    """Populate `project.milestones` from its type's template, computing each
    due date via the unified date_rules resolver. Idempotent."""
    if project.get("milestones"):
        return
    type_doc = frappe.get_cached_doc("Culminating Project Type", project.project_type)
    template = sorted(
        type_doc.get("milestones") or [], key=lambda r: (r.sequence or 0, r.idx)
    )
    if not template:
        return

    context = _milestone_context(project)
    prev_due = None
    for tmpl in template:
        count = max(int(tmpl.default_count or 1), 1) if tmpl.repeatable else 1
        for instance in range(1, count + 1):
            name = tmpl.milestone_name
            if tmpl.repeatable and count > 1:
                name = f"{name} {instance}"
            due = _compute_milestone_due(tmpl, context, prev_due)
            row = project.append(
                "milestones",
                {
                    "milestone_name": name,
                    "sequence": tmpl.sequence,
                    "instance": instance,
                    "milestone_kind": tmpl.milestone_kind,
                    "mandatory": tmpl.mandatory,
                    "requires_submission": tmpl.requires_submission,
                    "creates_event": tmpl.creates_event,
                    "signoff_advisor": tmpl.signoff_advisor,
                    "signoff_second_reader": tmpl.signoff_second_reader,
                    "signoff_third_reader": tmpl.signoff_third_reader,
                    "signoff_committee": tmpl.signoff_committee,
                    "template_row": tmpl.name,
                    "status": "Not Started",
                },
            )
            if due:
                row.due_date = due
                prev_due = due


def _milestone_context(project):
    """Build the anchor dates available to the resolver for this project."""
    pe = (
        frappe.db.get_value(
            "Program Enrollment",
            project.program_enrollment,
            ["enrollment_date", "expected_graduation_date", "academic_term"],
            as_dict=True,
        )
        or {}
    )
    term = pe.get("academic_term")
    term_start = (
        frappe.db.get_value("Academic Term", term, "term_start_date") if term else None
    )
    anchors = {
        "Project Start": (
            getdate(project.creation) if project.get("creation") else today()
        ),
        "Enrollment Date": pe.get("enrollment_date"),
        "Expected Graduation": pe.get("expected_graduation_date"),
        "Term Start": term_start,
    }
    return {"anchors": anchors, "term": term}


def _compute_milestone_due(tmpl, base_context, prev_due):
    context = dict(base_context)
    anchors = dict(base_context.get("anchors") or {})
    if prev_due:
        anchors["Previous Milestone"] = prev_due
    context["anchors"] = anchors
    return date_rules.resolve(tmpl.anchor, tmpl.offset_value, tmpl.offset_unit, context)


@frappe.whitelist()
def resnapshot_milestones(name):
    """Registrar action: rebuild the milestone snapshot from the current type
    template (e.g. after editing the template). Clears existing rows."""
    project = frappe.get_doc("Culminating Project", name)
    if not frappe.has_permission("Culminating Project", "write", project):
        frappe.throw(_("Not permitted."), frappe.PermissionError)
    project.milestones = []
    snapshot_milestones(project)
    project.save(ignore_permissions=True)
    return {"milestones": len(project.milestones)}


@frappe.whitelist()
def record_signoff(
    culminating_project,
    milestone_row,
    role,
    decision="Approved",
    comment=None,
    attachment=None,
):
    """Record a reviewer sign-off on a milestone and recompute its status. A
    milestone is Approved once every required role has an Approved sign-off."""
    project = frappe.get_doc("Culminating Project", culminating_project)
    if not frappe.has_permission("Culminating Project", "write", project):
        frappe.throw(
            _("Not permitted to sign off on this project."), frappe.PermissionError
        )

    row = next((m for m in project.milestones if m.name == milestone_row), None)
    if not row:
        frappe.throw(
            _("Milestone {0} not found on this project.").format(milestone_row)
        )

    reader_field = _ROLE_READER_FIELD.get(role)
    if reader_field and not project.get(reader_field):
        frappe.throw(_("This project has no {0} to sign off.").format(role))

    signoff = frappe.get_doc(
        {
            "doctype": "Culminating Project Milestone Signoff",
            "culminating_project": project.name,
            "milestone_row": milestone_row,
            "milestone_name": row.milestone_name,
            "role": role,
            "decision": decision,
            "signed_by": frappe.session.user,
            "signed_on": now_datetime(),
            "comment": comment,
            "attachment": attachment,
        }
    )
    signoff.insert(ignore_permissions=True)

    _recompute_milestone_status(project, row)
    project.save(ignore_permissions=True)
    return {"status": row.status, "signoff": signoff.name}


def _recompute_milestone_status(project, row):
    """Set the milestone row's status from its sign-offs. Approved when every
    required role (the signoff_* checks) has an Approved sign-off."""
    if row.status == "Waived":
        return

    required = [role for check, role in _SIGNOFF_ROLES if row.get(check)]
    signoffs = frappe.get_all(
        "Culminating Project Milestone Signoff",
        filters={"culminating_project": project.name, "milestone_row": row.name},
        fields=["role", "decision"],
    )
    approved_roles = {s.role for s in signoffs if s.decision == "Approved"}

    complete = (
        all(r in approved_roles for r in required)
        if required
        else any(s.decision == "Approved" for s in signoffs)
    )
    if complete:
        row.status = "Approved"
        if not row.completed_on:
            row.completed_on = today()
    elif signoffs:
        row.status = "In Progress"


@frappe.whitelist()
def enroll_in_project_course(name, course_schedule):
    """Provision and link a Course Enrollment Individual for this project's
    backing course (the course mapped on its Culminating Project Type).

    Reusing the regular course-enrollment machinery is what gives a thesis its
    fee (CEI on_submit), credits (Program Course), and the grade that flows to
    GPA and the transcript via the Program Enrollment Course row (ADR 024). The
    CEI is created in Draft; the registrar/student advances it through the
    normal Course Enrollment Lifecycle (which charges the fee on submit).

    Staff action: requires create permission on Course Enrollment Individual.
    """
    if not frappe.has_permission("Course Enrollment Individual", "create"):
        frappe.throw(
            _("You are not permitted to create course enrollments."),
            frappe.PermissionError,
        )

    project = frappe.get_doc("Culminating Project", name)
    if project.course_enrollment:
        frappe.throw(
            _("This project is already linked to course enrollment {0}.").format(
                project.course_enrollment
            )
        )
    if not project.program_enrollment:
        frappe.throw(_("This project has no Program Enrollment."))

    cs_course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    if not cs_course:
        frappe.throw(_("Course Schedule {0} not found.").format(course_schedule))

    # If the project type declares a backing course, the chosen schedule must
    # teach it — guards against enrolling a thesis into an unrelated course.
    if project.project_type:
        backing_course = frappe.db.get_value(
            "Culminating Project Type", project.project_type, "course"
        )
        if backing_course and backing_course != cs_course:
            frappe.throw(
                _(
                    "Course Schedule {0} teaches {1}, but project type {2} expects {3}."
                ).format(
                    course_schedule, cs_course, project.project_type, backing_course
                )
            )

    program = frappe.db.get_value(
        "Program Enrollment", project.program_enrollment, "program"
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
            "program_ce": project.program_enrollment,
            "coursesc_ce": course_schedule,
            "student_ce": project.student,
            "credits": credits,
        }
    )
    cei.insert(ignore_permissions=True)

    project.db_set("course_enrollment", cei.name)
    return {"course_enrollment": cei.name}
