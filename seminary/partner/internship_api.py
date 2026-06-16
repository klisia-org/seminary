"""Student-facing internship portal API (ADR 054).

The student side of internships: browse the internship positions a student is
*eligible* for (their active program enrollment holds an open graduation
requirement of the position's type), apply (a prayerful, in-portal action), and
manage their own internships — placements, requirement deliverables, hours, and
the end-of-placement feedback. Eligibility and the application lifecycle are
enforced by the Internship Application controller; these whitelisted endpoints
are the permission boundary (portal students hold no direct doctype rights).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from seminary.partner import internship

# Applicant-facing status buckets for "My Internships". The org/academic pipeline
# states collapse into a small set the student understands.
STUDENT_BUCKETS = {
    "Draft": ("Draft",),
    "Open": ("Submitted", "Under Review"),
    "Active": ("Accepted", "Active"),
    "Completed": ("Completed",),
    "Rejected": ("Rejected",),
    "Withdrawn": ("Withdrawn",),
}
WITHDRAWABLE = ("Submitted", "Under Review", "Accepted", "Active")

POSITION_LIST_FIELDS = (
    "name",
    "title",
    "partner_org",
    "internship_type",
    "location",
    "ministry_setting",
    "min_hours_per_week",
)


# --------------------------------------------------------------------------- #
# Identity helpers
# --------------------------------------------------------------------------- #
def _require_login() -> None:
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to view internships."), frappe.PermissionError)


def _current_person() -> str | None:
    if frappe.session.user == "Guest":
        return None
    return frappe.db.get_value("Person", {"user": frappe.session.user}, "name")


def _current_student() -> str | None:
    person = _current_person()
    if not person:
        return None
    return frappe.db.get_value("Student", {"person": person}, "name")


def _require_student() -> str:
    student = _current_student()
    if not student:
        frappe.throw(
            _("Your account isn't linked to a student record."), frappe.PermissionError
        )
    return student


def _eligible_for_type(student: str, internship_type: str) -> bool:
    """A gated type (mapped to a graduation requirement) is visible only to
    students holding an open requirement of it. An ungated type (no requirement
    mapped) is Desk-only and hidden from the portal unless the seminary opts in
    to showing ungated internships to all students — so an accidentally-empty
    requirement isn't silently exposed."""
    item = frappe.db.get_value(
        "Internship Type", internship_type, "graduation_requirement_item"
    )
    if item:
        return bool(internship.resolve_open_requirement(student, internship_type))
    return bool(
        frappe.db.get_single_value(
            "Seminary Settings", "show_ungated_internships_to_all"
        )
    )


# --------------------------------------------------------------------------- #
# Browse
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_internships(
    query: str = "", ministry_setting: str = "", internship_type: str = ""
) -> list[dict]:
    """Published, open internship positions the student is eligible for, decorated
    with org / type / location for the card view. Already-applied positions move
    to My Internships; an in-progress draft stays browsable."""
    _require_login()
    student = _current_student()
    if not student:
        return []

    filters: list = [
        ["publish", "=", 1],
        ["status", "=", "Open"],
        ["open_students", "=", 1],
    ]
    if ministry_setting:
        filters.append(["ministry_setting", "=", ministry_setting])
    if internship_type:
        filters.append(["internship_type", "=", internship_type])

    positions = frappe.get_all(
        "Internship Position",
        fields=list(POSITION_LIST_FIELDS),
        filters=filters,
        order_by="creation desc",
        limit_page_length=0,
    )
    if not positions:
        return []

    _decorate(positions)
    applied = _applied_positions(student)
    needle = (query or "").strip().lower()

    results = []
    for p in positions:
        if p["name"] in applied:
            continue
        if not _eligible_for_type(student, p["internship_type"]):
            continue
        if (
            needle
            and needle
            not in " ".join(
                str(p.get(f) or "")
                for f in (
                    "title",
                    "organization_name",
                    "city",
                    "internship_type",
                    "ministry_setting",
                )
            ).lower()
        ):
            continue
        results.append(p)
    return results


def _decorate(positions: list[dict]) -> None:
    org_names = {p["partner_org"] for p in positions if p.get("partner_org")}
    loc_names = {p["location"] for p in positions if p.get("location")}
    orgs = (
        {
            r.name: r
            for r in frappe.get_all(
                "Partner Organization",
                fields=["name", "organization_name", "partner_type", "city"],
                filters={"name": ["in", list(org_names)]},
            )
        }
        if org_names
        else {}
    )
    locs = (
        {
            r.name: r
            for r in frappe.get_all(
                "Partner Organization Location",
                fields=["name", "location_name", "city"],
                filters={"name": ["in", list(loc_names)]},
            )
        }
        if loc_names
        else {}
    )
    for p in positions:
        org = orgs.get(p.get("partner_org"))
        loc = locs.get(p.get("location"))
        p["organization_name"] = org.organization_name if org else p.get("partner_org")
        p["location_name"] = loc.location_name if loc else None
        p["city"] = loc.city if loc and loc.city else (org.city if org else None)


def _applied_positions(student: str) -> set[str]:
    return set(
        frappe.get_all(
            "Internship Application",
            filters={"student": student, "status": ["not in", ["Draft", "Withdrawn"]]},
            pluck="internship_position",
        )
    )


@frappe.whitelist()
def get_internship(name: str) -> dict:
    """Full detail for one published position, plus eligibility flags."""
    _require_login()
    student = _current_student()
    if not frappe.db.exists("Internship Position", name):
        frappe.throw(_("Internship not found."))
    doc = frappe.get_doc("Internship Position", name)
    if not doc.publish:
        frappe.throw(_("This internship is not published."), frappe.PermissionError)

    org = (
        frappe.db.get_value(
            "Partner Organization",
            doc.partner_org,
            ["organization_name", "website", "image", "about_us", "city", "state"],
            as_dict=True,
        )
        or {}
    )
    location = {}
    if doc.location:
        location = (
            frappe.db.get_value(
                "Partner Organization Location",
                doc.location,
                [
                    "location_name",
                    "city",
                    "state",
                    "ministry_setting",
                    "congregation_size",
                ],
                as_dict=True,
            )
            or {}
        )
    type_info = (
        frappe.db.get_value(
            "Internship Type",
            doc.internship_type,
            ["total_hours_required", "hours_tracking", "allow_multi_site"],
            as_dict=True,
        )
        or {}
    )

    existing_status = (
        frappe.db.get_value(
            "Internship Application",
            {"internship_position": name, "student": student},
            "status",
        )
        if student
        else None
    )
    submitted = bool(existing_status and existing_status not in ("Draft", "Withdrawn"))
    has_draft = existing_status == "Draft"
    eligible = bool(student) and _eligible_for_type(student, doc.internship_type)

    return {
        "name": doc.name,
        "title": doc.title,
        "status": doc.status,
        "internship_type": doc.internship_type,
        "description": doc.description,
        "qualifications": doc.qualifications,
        "min_hours_per_week": doc.min_hours_per_week,
        "flexible_dates": doc.flexible_dates,
        "preferred_start": doc.preferred_start,
        "preferred_end": doc.preferred_end,
        "flexible_schedule": doc.flexible_schedule,
        "schedule_notes": doc.schedule_notes,
        "weekly_schedule": [
            {
                "day_of_week": s.day_of_week,
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in doc.weekly_schedule
        ],
        "ministry_setting": doc.ministry_setting,
        "partner_org": doc.partner_org,
        "organization": org,
        "location": location,
        "type_info": type_info,
        "eligible": eligible,
        "already_applied": submitted,
        "has_draft": has_draft,
        "can_apply": bool(doc.status == "Open" and eligible and not submitted),
    }


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #
@frappe.whitelist(methods=["POST"])
def apply_to_internship(internship_position: str, submit: str = "") -> dict:
    """Save (Draft) or submit an Internship Application for the logged-in student.
    Eligibility, duplicate-prevention, and auto-accept are enforced by the
    controller."""
    _require_login()
    student = _require_student()
    do_submit = str(submit).strip().lower() in ("1", "true", "yes")

    existing = frappe.db.get_value(
        "Internship Application",
        {
            "internship_position": internship_position,
            "student": student,
            "status": ["!=", "Withdrawn"],
        },
        ["name", "status"],
        as_dict=True,
    )
    if existing and existing.status not in ("Draft",):
        frappe.throw(_("You have already applied to this internship."))

    if existing:
        doc = frappe.get_doc("Internship Application", existing.name)
    else:
        doc = frappe.new_doc("Internship Application")
        doc.internship_position = internship_position
        doc.student = student
    doc.status = "Submitted" if do_submit else "Draft"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status, "submitted": do_submit}


# --------------------------------------------------------------------------- #
# My internships
# --------------------------------------------------------------------------- #
def _own_application(name: str) -> "frappe._dict":
    student = _current_student()
    app = frappe.db.get_value(
        "Internship Application", name, ["student", "status"], as_dict=True
    )
    if not app or not student or app.student != student:
        frappe.throw(_("That internship isn't yours."), frappe.PermissionError)
    return app


def _own_placement(placement: str) -> str:
    student = _current_student()
    application = frappe.db.get_value(
        "Internship Placement", placement, "internship_application"
    )
    owner = (
        frappe.db.get_value("Internship Application", application, "student")
        if application
        else None
    )
    if not student or owner != student:
        frappe.throw(_("That placement isn't yours."), frappe.PermissionError)
    return application


@frappe.whitelist()
def get_my_internships(status: str = "") -> list[dict]:
    """The student's internship applications for the My Internships list."""
    _require_login()
    student = _current_student()
    if not student:
        return []
    filters = {"student": student}
    bucket = STUDENT_BUCKETS.get(status)
    if bucket:
        filters["status"] = ["in", list(bucket)]
    apps = frappe.get_all(
        "Internship Application",
        fields=[
            "name",
            "internship_position",
            "internship_type",
            "partner_org",
            "status",
            "total_hours_logged",
            "submission_date",
        ],
        filters=filters,
        order_by="modified desc",
        limit_page_length=0,
    )
    for a in apps:
        a["title"] = frappe.db.get_value(
            "Internship Position", a["internship_position"], "title"
        )
        a["organization_name"] = frappe.db.get_value(
            "Partner Organization", a["partner_org"], "organization_name"
        )
        a["hours_target"] = _hours_target(a["name"], a["internship_type"])
    return apps


def _hours_target(application: str, internship_type: str) -> float:
    allocated = sum(
        a or 0
        for a in frappe.get_all(
            "Internship Placement",
            filters={"internship_application": application},
            pluck="hours_allocated",
        )
    )
    if allocated:
        return allocated
    return (
        frappe.db.get_value("Internship Type", internship_type, "total_hours_required")
        or 0
    )


@frappe.whitelist()
def get_my_internship(name: str) -> dict:
    """Full detail of one of the student's internships: placements, requirements
    (the student's party), hours tracking mode, and feedback state."""
    _require_login()
    _own_application(name)
    doc = frappe.get_doc("Internship Application", name)
    tracking = frappe.db.get_value(
        "Internship Type", doc.internship_type, "hours_tracking"
    )

    placements = frappe.get_all(
        "Internship Placement",
        filters={"internship_application": name},
        fields=[
            "name",
            "location",
            "site_supervisor",
            "placement_status",
            "hours_allocated",
            "hours_logged",
            "actual_start",
            "actual_end",
        ],
        order_by="creation asc",
    )
    for p in placements:
        p["supervisor_name"] = (
            frappe.db.get_value("Person", p["site_supervisor"], "full_name")
            if p["site_supervisor"]
            else None
        )
        p["location_name"] = (
            frappe.db.get_value(
                "Partner Organization Location", p["location"], "location_name"
            )
            if p["location"]
            else None
        )
        p["has_feedback"] = bool(
            frappe.db.exists(
                "Student Internship Feedback", {"internship_placement": p["name"]}
            )
        )

    requirements = frappe.get_all(
        "Internship Requirement",
        filters={"internship_application": name, "student_submits": 1},
        fields=[
            "name",
            "title",
            "status",
            "due_date",
            "internship_placement",
            "student_label",
            "student_submission_type",
            "student_instructions",
            "student_submission_value",
            "student_attachment",
            "student_acknowledged",
            "submit_template",
        ],
        order_by="due_date asc",
    )

    return {
        "name": doc.name,
        "title": frappe.db.get_value(
            "Internship Position", doc.internship_position, "title"
        ),
        "organization_name": frappe.db.get_value(
            "Partner Organization", doc.partner_org, "organization_name"
        ),
        "status": doc.status,
        "internship_type": doc.internship_type,
        "hours_tracking": tracking,
        "total_hours_logged": doc.total_hours_logged,
        "hours_target": _hours_target(doc.name, doc.internship_type),
        "placements": placements,
        "requirements": requirements,
    }


@frappe.whitelist(methods=["POST"])
def withdraw_application(name: str) -> dict:
    _require_login()
    app = _own_application(name)
    if app.status not in WITHDRAWABLE:
        frappe.throw(_("This internship can no longer be withdrawn."))
    doc = frappe.get_doc("Internship Application", name)
    doc.status = "Withdrawn"
    doc.save(ignore_permissions=True)
    return {"name": name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def discard_draft(name: str) -> dict:
    _require_login()
    app = _own_application(name)
    if app.status != "Draft":
        frappe.throw(_("Only a draft application can be discarded."))
    frappe.delete_doc("Internship Application", name, ignore_permissions=True)
    return {"name": name}


# --------------------------------------------------------------------------- #
# Hours
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_hours(placement: str) -> list[dict]:
    _require_login()
    _own_placement(placement)
    return frappe.get_all(
        "Internship Hours Log",
        filters={"internship_placement": placement},
        fields=["name", "log_date", "hours", "description", "supervisor_verified"],
        order_by="log_date desc",
    )


@frappe.whitelist(methods=["POST"])
def log_hours(placement: str, log_date: str, hours, description: str = "") -> dict:
    """The student logs a day of hours against their placement (pending supervisor
    verification where the type requires it)."""
    _require_login()
    _own_placement(placement)
    doc = frappe.get_doc(
        {
            "doctype": "Internship Hours Log",
            "internship_placement": placement,
            "log_date": getdate(log_date),
            "hours": flt(hours),
            "description": description,
            "supervisor_verified": 0,
        }
    ).insert(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete_hours(name: str) -> dict:
    """The student removes their own unverified hours entry."""
    _require_login()
    log = frappe.db.get_value(
        "Internship Hours Log",
        name,
        ["internship_placement", "supervisor_verified"],
        as_dict=True,
    )
    if not log:
        frappe.throw(_("Entry not found."))
    _own_placement(log.internship_placement)
    if log.supervisor_verified:
        frappe.throw(_("A verified entry can't be removed; ask your supervisor."))
    frappe.delete_doc("Internship Hours Log", name, ignore_permissions=True)
    return {"name": name}


# --------------------------------------------------------------------------- #
# Requirements (student party)
# --------------------------------------------------------------------------- #
@frappe.whitelist(methods=["POST"])
def save_requirement_student(name: str, values) -> dict:
    """Record the student's submission on one of their requirements."""
    _require_login()
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    application = frappe.db.get_value(
        "Internship Requirement", name, "internship_application"
    )
    _own_application(application)
    doc = frappe.get_doc("Internship Requirement", name)
    for field in (
        "student_submission_value",
        "student_attachment",
        "student_acknowledged",
    ):
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #
FEEDBACK_FIELDS = (
    "overall_rating",
    "supervision_quality",
    "spiritual_formation_value",
    "workload_appropriateness",
    "would_recommend",
    "highlights",
    "concerns",
    "suggestions_for_seminary",
)


@frappe.whitelist()
def get_feedback(placement: str) -> dict:
    _require_login()
    _own_placement(placement)
    existing = frappe.get_all(
        "Student Internship Feedback",
        filters={"internship_placement": placement},
        fields=["name", *FEEDBACK_FIELDS],
        limit=1,
    )
    return existing[0] if existing else {"is_new": True, "placement": placement}


@frappe.whitelist(methods=["POST"])
def submit_feedback(placement: str, values, name: str | None = None) -> dict:
    _require_login()
    _own_placement(placement)
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
    if name:
        doc = frappe.get_doc("Student Internship Feedback", name)
        if doc.internship_placement != placement:
            frappe.throw(_("Feedback does not match the placement."))
    else:
        existing = frappe.db.get_value(
            "Student Internship Feedback", {"internship_placement": placement}, "name"
        )
        doc = (
            frappe.get_doc("Student Internship Feedback", existing)
            if existing
            else frappe.new_doc("Student Internship Feedback")
        )
        doc.internship_placement = placement
    for field in FEEDBACK_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return {"name": doc.name}
