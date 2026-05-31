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
        # round counter and milestone-derived fields here too (e.g. after a
        # submission is added or a sign-off flips a milestone). allow_on_submit.
        self._update_round_counter()
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
def add_submission(
    name, attachment, student_note=None, milestone_row=None, submission_type=None
):
    """Student endpoint to add a submission round against a milestone. The type
    is derived server-side (students don't choose it): Proposal for a Proposal
    milestone, Draft for the first round of any other milestone, Revision for
    later rounds. Round number is derived from existing rounds, since the
    validate counter doesn't run on a submitted project."""
    doc = frappe.get_doc("Culminating Project", name)
    if not _user_owns_project(doc):
        frappe.throw(
            _("You can only submit to your own project."), frappe.PermissionError
        )
    milestone = (
        next((m for m in doc.milestones or [] if m.name == milestone_row), None)
        if milestone_row
        else None
    )
    round_no = max([int(s.round or 0) for s in doc.submissions or []], default=0) + 1
    sub_type = _derive_submission_type(doc, milestone)
    row = doc.append(
        "submissions",
        {
            "round": round_no,
            "submission_type": sub_type,
            "milestone_row": milestone_row,
            "attachment": attachment,
            "student_note": student_note,
            "submitted_by": frappe.session.user,
            "submitted_on": now_datetime(),
            "reviewer": doc.advisor,
            "reviewer_decision": "Pending",
        },
    )
    if milestone:
        milestone.submission_round = round_no
        if milestone.status in ("Not Started", "In Progress", "Submitted"):
            milestone.status = "Submitted"
    doc.save(ignore_permissions=True)
    _attach_to_project(attachment, name)
    return {"round": row.round, "submission_type": sub_type}


def _derive_submission_type(doc, milestone):
    """Type is implied by the milestone, never chosen by the student: Proposal
    for a Proposal milestone; otherwise Draft for the first round against that
    milestone and Revision for every round after. (Final is set by the advisor
    when the final milestone is approved — see record_signoff.)"""
    if milestone and (milestone.milestone_kind or "").strip() == "Proposal":
        return "Proposal"
    if milestone:
        prior = [
            s
            for s in doc.submissions or []
            if (s.milestone_row or None) == milestone.name
        ]
        return "Revision" if prior else "Draft"
    return "Draft"


def _user_owns_project(doc):
    user_email = frappe.session.user
    student_email = frappe.db.get_value("Student", doc.student, "student_email_id")
    return user_email == student_email


@frappe.whitelist()
def save_abstract(name, abstract):
    """Student edits their own abstract until the project is defended. The HTML
    is sanitized server-side (student-supplied, rendered to readers as HTML)."""
    doc = frappe.get_doc("Culminating Project", name)
    if not _user_owns_project(doc):
        frappe.throw(
            _("You can only edit your own project's abstract."),
            frappe.PermissionError,
        )
    if doc.defended_on:
        frappe.throw(_("The abstract can no longer be edited after the defense."))
    clean = frappe.utils.sanitize_html(abstract or "", always_sanitize=True)
    # abstract isn't allow_on_submit and the project is submitted once active, so
    # write it directly (already sanitized) rather than through doc.save().
    frappe.db.set_value("Culminating Project", name, "abstract", clean)
    return {"abstract": clean}


def _attach_to_project(file_url, project_name):
    """Attach an uploaded (unattached) private File to the project so anyone with
    read access to the Culminating Project can open it. Students upload files
    unattached (they lack write on the project), so we bind them here."""
    if not file_url:
        return
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if file_name:
        frappe.db.set_value(
            "File",
            file_name,
            {
                "attached_to_doctype": "Culminating Project",
                "attached_to_name": project_name,
            },
            update_modified=False,
        )


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
                    "event_custom_category": tmpl.event_custom_category,
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

    # The committee doesn't sign individually — the advisor records its sign-off
    # on the committee's behalf, and the committee must exist first.
    if role == "Committee":
        _require_advisor(project)
        if not (project.committee or []):
            frappe.throw(_("Add the committee members before signing on their behalf."))

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
    _attach_to_project(attachment, project.name)

    _recompute_milestone_status(project, row)
    # "Final" is the advisor's call, made when the final-submission milestone is
    # approved — not a type the student picks at upload time.
    if (
        row.status == "Approved"
        and (row.milestone_kind or "").strip() == "Final Submission"
        and row.submission_round
    ):
        for s in project.submissions or []:
            if int(s.round or 0) == int(row.submission_round):
                s.submission_type = "Final"
                break
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


# ---------------------------------------------------------------------------
# Workbench API (ADR 025 follow-up): student + advisor/reader views.
# ---------------------------------------------------------------------------

# Culminating Project reader Link field -> role label.
_READER_FIELDS = (
    ("advisor", "Advisor"),
    ("second_reader", "Second Reader"),
    ("third_reader", "Third Reader"),
)
_STAFF_ROLES = ("Academics User", "Seminary Manager", "Registrar")
# Sign-off role -> the milestone's required-sign-off check field.
_ROLE_SIGNOFF_FIELD = {
    "Advisor": "signoff_advisor",
    "Second Reader": "signoff_second_reader",
    "Third Reader": "signoff_third_reader",
    "Committee": "signoff_committee",
}


def _responsible_signoff_roles(role):
    """Sign-off roles a user in `role` must action. The advisor also signs on
    the committee's behalf, so they carry the Committee role too."""
    roles = [role] if role in _ROLE_SIGNOFF_FIELD else []
    if role == "Advisor":
        roles.append("Committee")
    return roles


@frappe.whitelist()
def get_my_culminating_projects():
    """Projects the current user owns (as student) or advises (as a reader)."""
    student = frappe.db.get_value(
        "Student", {"user": frappe.session.user, "enabled": 1}, "name"
    )
    instructor = frappe.db.get_value(
        "Instructor", {"user": frappe.session.user}, "name"
    )

    student_projects = []
    if student:
        for cp in frappe.get_all(
            "Culminating Project",
            filters={"student": student},
            fields=[
                "name",
                "project_title",
                "project_type",
                "program_enrollment",
                "workflow_state",
                "student",
            ],
            order_by="modified desc",
        ):
            student_projects.append(_project_row(cp, "Student", None))

    advisor_projects = []
    if instructor:
        for cp in frappe.get_all(
            "Culminating Project",
            or_filters={
                "advisor": instructor,
                "second_reader": instructor,
                "third_reader": instructor,
            },
            fields=[
                "name",
                "project_title",
                "project_type",
                "program_enrollment",
                "workflow_state",
                "student",
                "advisor",
                "second_reader",
                "third_reader",
            ],
            order_by="modified desc",
        ):
            my_role = next(
                (label for f, label in _READER_FIELDS if cp.get(f) == instructor),
                None,
            )
            advisor_projects.append(_project_row(cp, my_role, instructor))

    return {"student_projects": student_projects, "advisor_projects": advisor_projects}


def _project_row(cp, role, instructor):
    """Compact list row: program, student, active milestone, due, (needs_action)."""
    milestones = frappe.get_all(
        "Culminating Project Milestone",
        filters={"parent": cp.name, "parenttype": "Culminating Project"},
        fields=[
            "name",
            "milestone_name",
            "status",
            "due_date",
            "requires_submission",
            "submission_round",
            "signoff_advisor",
            "signoff_second_reader",
            "signoff_third_reader",
        ],
        order_by="sequence asc, instance asc",
    )
    active = next(
        (m for m in milestones if m.status not in ("Approved", "Waived")), None
    )
    row = {
        "name": cp.name,
        "project_title": cp.project_title,
        "project_type": cp.project_type,
        "program": frappe.db.get_value(
            "Program Enrollment", cp.program_enrollment, "program"
        ),
        "student_name": (
            frappe.db.get_value("Student", cp.get("student"), "student_name")
            if cp.get("student")
            else None
        ),
        "status": cp.workflow_state,
        "my_role": role,
        "active_milestone": active.milestone_name if active else None,
        "due": active.due_date if active else None,
    }
    if instructor:
        row["needs_action"] = _needs_action(cp.name, instructor, role, active)
    return row


def _latest_submission_for(cp_name, milestone):
    """Latest submission round against a milestone (by stored link, else the
    legacy submission_round pointer)."""
    if not milestone:
        return None
    subs = frappe.get_all(
        "Culminating Project Submission",
        filters={
            "parent": cp_name,
            "parenttype": "Culminating Project",
            "milestone_row": milestone.name,
        },
        fields=["round", "reviewer", "reviewer_decision"],
        order_by="round desc",
        limit=1,
    )
    if subs:
        return subs[0]
    if milestone.get("submission_round"):
        legacy = frappe.get_all(
            "Culminating Project Submission",
            filters={
                "parent": cp_name,
                "parenttype": "Culminating Project",
                "round": milestone.submission_round,
            },
            fields=["round", "reviewer", "reviewer_decision"],
            limit=1,
        )
        if legacy:
            return legacy[0]
    return None


def _needs_action(cp_name, instructor, role, active):
    """True when *I* have something to do right now:
    - a submission round assigned to me is still Pending review, or
    - the active milestone requires a sign-off I'm responsible for (my own role,
      plus Committee for the advisor), I haven't signed it, and it's ready to
      sign — its latest submission was Accepted, or a co-reader has already
      signed off (the sign-off round is under way, so it's my turn too).
    A milestone awaiting the student's first submission, or with revisions
    outstanding (and no sign-offs yet), is the student's ball — it does NOT
    count. (The lingering 'Needs you' bug came from treating any unsigned
    milestone as mine.)"""
    if frappe.get_all(
        "Culminating Project Submission",
        filters={
            "parent": cp_name,
            "parenttype": "Culminating Project",
            "reviewer": instructor,
            "reviewer_decision": "Pending",
        },
        limit=1,
    ):
        return True

    if not active:
        return False
    for rrole in _responsible_signoff_roles(role):
        signoff_field = _ROLE_SIGNOFF_FIELD[rrole]
        if not active.get(signoff_field):
            continue
        if frappe.db.exists(
            "Culminating Project Milestone Signoff",
            {
                "culminating_project": cp_name,
                "milestone_row": active.name,
                "role": rrole,
                "decision": "Approved",
            },
        ):
            continue
        if _signoff_ready(cp_name, active):
            return True
    return False


def _signoff_ready(cp_name, active):
    """A milestone is ready for reader sign-off once its latest submission was
    Accepted, or any required reader has already signed off (round under way)."""
    latest = _latest_submission_for(cp_name, active)
    if latest and latest.reviewer_decision == "Accepted":
        return True
    return bool(
        frappe.db.exists(
            "Culminating Project Milestone Signoff",
            {
                "culminating_project": cp_name,
                "milestone_row": active.name,
                "decision": "Approved",
            },
        )
    )


@frappe.whitelist()
def get_culminating_project(name):
    """Full detail for the workbench. Authorized to the student owner, a reader
    (advisor/second/third), or staff."""
    project = frappe.get_doc("Culminating Project", name)
    student = frappe.db.get_value(
        "Student", {"user": frappe.session.user, "enabled": 1}, "name"
    )
    instructor = frappe.db.get_value(
        "Instructor", {"user": frappe.session.user}, "name"
    )
    roles = frappe.get_roles(frappe.session.user)
    is_staff = any(r in roles for r in _STAFF_ROLES)
    is_owner = bool(student and project.student == student)
    my_role = (
        next(
            (label for f, label in _READER_FIELDS if project.get(f) == instructor), None
        )
        if instructor
        else None
    )
    is_reader = my_role is not None
    if not (is_owner or is_reader or is_staff):
        frappe.throw(
            _("You are not permitted to view this project."), frappe.PermissionError
        )
    if is_owner:
        my_role = "Student"
    elif my_role is None:
        my_role = "Staff"

    from seminary.seminary.utils import get_instructor_messaging_apps

    advisors = []
    for field, label in _READER_FIELDS:
        inst = project.get(field)
        if not inst:
            continue
        info = (
            frappe.db.get_value(
                "Instructor",
                inst,
                ["instructor_name", "prof_email", "profileimage", "phone_message"],
                as_dict=True,
            )
            or {}
        )
        info["name"] = inst
        info["role"] = label
        info["messaging_apps"] = (
            get_instructor_messaging_apps(inst) if info.get("phone_message") else []
        )
        advisors.append(info)

    signoffs_by_row = {}
    for s in frappe.get_all(
        "Culminating Project Milestone Signoff",
        filters={"culminating_project": name},
        fields=[
            "milestone_row",
            "role",
            "decision",
            "signed_by",
            "signed_on",
            "comment",
            "attachment",
        ],
        order_by="signed_on asc",
    ):
        signoffs_by_row.setdefault(s.milestone_row, []).append(s)

    # Group every submission round under its milestone (full history → reader
    # record per (e)); fall back to the legacy submission_round pointer for rows
    # uploaded before submissions were linked.
    subs_by_milestone = {}
    subs_by_round = {}
    for s in project.submissions or []:
        d = _submission_dict(s)
        subs_by_round[s.round] = d
        if s.milestone_row:
            subs_by_milestone.setdefault(s.milestone_row, []).append(d)

    # Pull the instructions and defense-event config live from each milestone's
    # type template, so edits show without re-snapshotting and existing projects
    # (snapshotted before event_custom_category/creates_event existed) still work.
    template_rows = [m.template_row for m in project.milestones or [] if m.template_row]
    templates = {
        r.name: r
        for r in (
            frappe.get_all(
                "Culminating Project Type Milestone",
                filters={"name": ["in", template_rows]},
                fields=[
                    "name",
                    "description",
                    "creates_event",
                    "event_custom_category",
                ],
            )
            if template_rows
            else []
        )
    }

    milestones = []
    for m in sorted(
        project.milestones or [], key=lambda r: (r.sequence or 0, r.instance or 0)
    ):
        msubs = list(subs_by_milestone.get(m.name, []))
        if not msubs and m.submission_round and m.submission_round in subs_by_round:
            msubs = [subs_by_round[m.submission_round]]
        msubs.sort(key=lambda x: x["round"] or 0)
        tmpl = templates.get(m.template_row) or {}
        milestones.append(
            {
                "row": m.name,
                "milestone_name": m.milestone_name,
                "sequence": m.sequence,
                "instance": m.instance,
                "kind": m.milestone_kind,
                "status": m.status,
                "due_date": m.due_date,
                "completed_on": m.completed_on,
                "mandatory": m.mandatory,
                "requires_submission": m.requires_submission,
                "description": tmpl.get("description"),
                "required_roles": [label for c, label in _SIGNOFF_ROLES if m.get(c)],
                "signoffs": signoffs_by_row.get(m.name, []),
                "submissions": msubs,
                "submission": msubs[-1] if msubs else None,
                # Instance value with template fallback (snapshot may predate these).
                "creates_event": m.creates_event or tmpl.get("creates_event") or 0,
                "event": m.event,
                "event_starts_on": (
                    frappe.db.get_value("Event", m.event, "starts_on")
                    if m.event
                    else None
                ),
            }
        )

    active = next(
        (m for m in milestones if m["status"] not in ("Approved", "Waived")), None
    )
    return {
        "name": project.name,
        "project_title": project.project_title,
        "abstract": project.abstract,
        "project_type": project.project_type,
        "workflow_state": project.workflow_state,
        "milestones_complete": project.milestones_complete,
        "final_grade": project.final_grade,
        "program": frappe.db.get_value(
            "Program Enrollment", project.program_enrollment, "program"
        ),
        "student_name": (
            frappe.db.get_value("Student", project.student, "student_name")
            if project.student
            else None
        ),
        "student_email": (
            frappe.db.get_value("Student", project.student, "student_email_id")
            if project.student
            else None
        ),
        "proposal_approved_on": project.proposal_approved_on,
        "defended_on": project.defended_on,
        "viewer": {
            "my_role": my_role,
            "can_review": is_reader or is_staff,
            "can_submit": is_owner,
            "can_sign_committee": my_role == "Advisor",
        },
        "advisors": advisors,
        "committee": _committee(project),
        "milestones": milestones,
        "submissions": [_submission_dict(s) for s in (project.submissions or [])],
        "active_milestone": active["row"] if active else None,
        "student_action": _student_action(project, active),
    }


def _committee(project):
    """Committee members for display (internal instructors or external readers)."""
    members = []
    for c in project.get("committee") or []:
        if c.instructor:
            info = (
                frappe.db.get_value(
                    "Instructor",
                    c.instructor,
                    ["instructor_name", "prof_email"],
                    as_dict=True,
                )
                or {}
            )
            member_name, email = info.get("instructor_name"), info.get("prof_email")
        else:
            member_name, email = c.external_name, c.email_external
        members.append(
            {
                "name": c.name,
                "instructor": c.instructor,
                "member_name": member_name,
                "is_external": c.is_external,
                "email": email,
            }
        )
    return members


def _require_advisor(project):
    """The advisor owns the committee — they create and sign for it."""
    instructor = frappe.db.get_value(
        "Instructor", {"user": frappe.session.user}, "name"
    )
    if instructor != project.advisor:
        frappe.throw(
            _("Only the advisor may manage the committee."), frappe.PermissionError
        )


@frappe.whitelist()
def add_committee_member(
    culminating_project, instructor=None, external_name=None, email_external=None
):
    """Advisor adds a committee member — an internal Instructor or an external
    reader (name + optional email)."""
    project = frappe.get_doc("Culminating Project", culminating_project)
    _require_advisor(project)
    if instructor:
        if any(c.instructor == instructor for c in project.committee or []):
            frappe.throw(
                _("{0} is already on the committee.").format(
                    frappe.db.get_value("Instructor", instructor, "instructor_name")
                    or instructor
                )
            )
        project.append("committee", {"instructor": instructor})
    elif external_name:
        project.append(
            "committee",
            {
                "is_external": 1,
                "external_name": external_name,
                "email_external": email_external,
            },
        )
    else:
        frappe.throw(_("Choose an instructor or enter an external member's name."))
    project.save(ignore_permissions=True)
    return {"committee": _committee(project)}


@frappe.whitelist()
def remove_committee_member(culminating_project, row):
    """Advisor removes a committee member (child row name)."""
    project = frappe.get_doc("Culminating Project", culminating_project)
    _require_advisor(project)
    project.committee = [c for c in project.committee or [] if c.name != row]
    project.save(ignore_permissions=True)
    return {"committee": _committee(project)}


@frappe.whitelist()
def create_milestone_event(
    culminating_project, milestone_row, starts_on, ends_on=None, location=None
):
    """Advisor schedules the calendar Event for a milestone (e.g. the Defense).
    Participants are the student + readers + committee (internal by Instructor,
    external by the committee child row). Calendar-only: it carries no SGR
    participants, so it never auto-fulfils a graduation requirement."""
    from seminary.seminary.events import create_event_from_category

    project = frappe.get_doc("Culminating Project", culminating_project)
    _require_advisor(project)
    row = next((m for m in project.milestones if m.name == milestone_row), None)
    if not row:
        frappe.throw(
            _("Milestone {0} not found on this project.").format(milestone_row)
        )
    # Read the category live from the type template when the snapshot predates
    # the field (existing projects were snapshotted before event_custom_category
    # existed, so the instance row is empty even though the template is set).
    category = row.event_custom_category or (
        frappe.db.get_value(
            "Culminating Project Type Milestone",
            row.template_row,
            "event_custom_category",
        )
        if row.template_row
        else None
    )
    if not category:
        frappe.throw(_("This milestone has no Event Category set on its project type."))
    if row.event:
        frappe.throw(_("An event is already scheduled for this milestone."))

    student_name = (
        frappe.db.get_value("Student", project.student, "student_name")
        if project.student
        else None
    )
    event = create_event_from_category(
        category,
        starts_on,
        ends_on=ends_on,
        location=location,
        participants=_defense_participants(project),
        subject="{0} — {1}".format(row.milestone_name, student_name or project.student),
        extra_description=_("{0} for {1}.").format(
            row.milestone_name, project.project_title or project.name
        ),
    )
    frappe.db.set_value("Culminating Project Milestone", milestone_row, "event", event)
    return {"event": event}


def _defense_participants(project):
    """Student + readers + committee, as Event participants. External committee
    members are referenced by their committee child row (no User/Instructor)."""
    participants = []
    if project.student:
        participants.append(
            {
                "reference_doctype": "Student",
                "reference_docname": project.student,
                "email": frappe.db.get_value(
                    "Student", project.student, "student_email_id"
                ),
            }
        )
    for field in ("advisor", "second_reader", "third_reader"):
        inst = project.get(field)
        if inst:
            participants.append(
                {
                    "reference_doctype": "Instructor",
                    "reference_docname": inst,
                    "email": frappe.db.get_value("Instructor", inst, "prof_email"),
                }
            )
    for c in project.committee or []:
        if c.instructor:
            participants.append(
                {
                    "reference_doctype": "Instructor",
                    "reference_docname": c.instructor,
                    "email": frappe.db.get_value(
                        "Instructor", c.instructor, "prof_email"
                    ),
                }
            )
        else:
            participants.append(
                {
                    "reference_doctype": "Culminating Project Committee",
                    "reference_docname": c.name,
                    "email": c.email_external,
                }
            )
    # De-dupe (e.g. advisor also listed on the committee).
    seen, unique = set(), []
    for p in participants:
        key = (p["reference_doctype"], p["reference_docname"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def _submission_dict(s):
    return {
        "round": s.round,
        "submission_type": s.submission_type,
        "attachment": s.attachment,
        "student_note": s.student_note,
        "submitted_on": s.submitted_on,
        "reviewer": s.reviewer,
        "reviewer_name": (
            frappe.db.get_value("Instructor", s.reviewer, "instructor_name")
            if s.reviewer
            else None
        ),
        "reviewer_decision": s.reviewer_decision,
        "reviewer_comment": s.reviewer_comment,
        "reviewer_attachment": s.reviewer_attachment,
        "reviewed_on": s.reviewed_on,
    }


def _student_action(project, active):
    """A one-line 'what's next' hint for the student info card. A milestone is
    'submittable' when it expects student work — it requires a submission or it
    has reader sign-offs (you can't sign off on nothing). The student submits
    first; once the latest round is Accepted the ball is with the readers."""
    if project.milestones_complete or not active:
        return {"state": "done", "message": _("All milestones are complete.")}
    name = active["milestone_name"]
    subs = active.get("submissions") or []
    latest = subs[-1] if subs else None
    submittable = active.get("requires_submission") or bool(
        active.get("required_roles")
    )
    if submittable and not latest:
        return {
            "state": "work",
            "message": _("Submit your work for “{0}”.").format(name),
        }
    if latest:
        decision = latest.get("reviewer_decision")
        if decision in ("Revisions Required", "Rejected"):
            return {
                "state": "work",
                "message": _(
                    "Revisions were requested on “{0}” — submit a revision."
                ).format(name),
            }
        if not decision or decision == "Pending":
            return {
                "state": "waiting",
                "message": _(
                    "Your reviewer is reviewing your submission for “{0}”."
                ).format(name),
            }
    return {
        "state": "waiting",
        "message": _(
            "Your work on “{0}” was accepted — awaiting reader sign-off."
        ).format(name),
    }


@frappe.whitelist()
def review_submission(
    culminating_project, round, decision, comment=None, attachment=None
):
    """Reader/staff action: record a review decision on a submission round."""
    project = frappe.get_doc("Culminating Project", culminating_project)
    instructor = frappe.db.get_value(
        "Instructor", {"user": frappe.session.user}, "name"
    )
    roles = frappe.get_roles(frappe.session.user)
    is_reader = bool(
        instructor and any(project.get(f) == instructor for f, _l in _READER_FIELDS)
    )
    if not (is_reader or any(r in roles for r in _STAFF_ROLES)):
        frappe.throw(_("Not permitted to review this project."), frappe.PermissionError)

    row = next((s for s in project.submissions if int(s.round) == int(round)), None)
    if not row:
        frappe.throw(_("Submission round {0} not found.").format(round))

    row.reviewer = instructor or row.reviewer
    row.reviewer_decision = decision
    row.reviewer_comment = comment
    row.reviewer_attachment = attachment
    row.reviewed_on = now_datetime()

    # Move the ball: a returned submission puts the milestone back in the
    # student's court (In Progress); an accepted one leaves it awaiting the
    # reader sign-offs (Submitted). Without this the milestone stays "Submitted"
    # and the reader keeps showing "Needs you" after replying with revisions.
    milestone = _milestone_of_submission(project, row)
    if milestone and milestone.status not in ("Approved", "Waived"):
        if decision in ("Revisions Required", "Rejected"):
            milestone.status = "In Progress"
        elif decision == "Accepted":
            milestone.status = "Submitted"

    project.save(ignore_permissions=True)
    _attach_to_project(attachment, culminating_project)
    return {"round": row.round, "reviewer_decision": row.reviewer_decision}


def _milestone_of_submission(project, sub):
    """Resolve the milestone a submission belongs to — by the stored link, or
    (for legacy rows) by the milestone whose submission_round matches."""
    if sub.milestone_row:
        m = next((m for m in project.milestones if m.name == sub.milestone_row), None)
        if m:
            return m
    return next(
        (m for m in project.milestones if m.submission_round == sub.round), None
    )
