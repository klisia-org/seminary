"""Partner-organization internship portal API (ADR 054).

The employer side of internships: partner staff post and edit internship
positions, run the application pipeline (accept/reject), manage placements
(assign a site supervisor, dates, status), verify logged hours, submit their
party of each requirement, and record the site-supervisor evaluation. Every
function resolves the caller's organization via the shared portal helpers and
scopes strictly to it; mutations use `ignore_permissions` after an explicit
ownership check (this API is the permission boundary).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

from seminary.partner.portal import (
    _own_doc,
    _parse,
    _require_org,
    list_locations,
)

# Statuses a partner may set on an application. Accepting triggers placement
# creation + faculty assignment in the controller; Active/Completed are academic
# (faculty) decisions and are intentionally not partner-settable.
PARTNER_PIPELINE = ("Under Review", "Accepted", "Rejected")

POSITION_EDITABLE_FIELDS = (
    "title",
    "internship_type",
    "description",
    "qualifications",
    "location",
    "acceptance_mode",
    "min_hours_per_week",
    "flexible_dates",
    "preferred_start",
    "preferred_end",
    "flexible_schedule",
    "schedule_notes",
    "open_students",
    "planned_placements",
    "default_site_supervisor",
)

PLACEMENT_EDITABLE_FIELDS = (
    "site_supervisor",
    "location",
    "hours_allocated",
    "actual_start",
    "actual_end",
    "site_learning_focus",
)

EVALUATION_FIELDS = (
    "overall_readiness",
    "theological_integration",
    "relational_skills",
    "initiative",
    "comments",
    "endorses_ministry",
)


# --------------------------------------------------------------------------- #
# Pickers
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_internship_types(org=None) -> list[dict]:
    """Active internship types this org may post. Honours the org's Allowed
    Internship Types gate (empty = any active type)."""
    org = _require_org(org)
    allowed = frappe.get_all(
        "Partner Allowed Internship Type",
        filters={"parenttype": "Partner Organization", "parent": org},
        pluck="internship_type",
    )
    filters = {"is_active": 1}
    if allowed:
        filters["name"] = ["in", allowed]
    return frappe.get_all(
        "Internship Type",
        filters=filters,
        fields=["name", "total_hours_required", "hours_tracking", "allow_multi_site"],
        order_by="name asc",
    )


@frappe.whitelist()
def get_org_supervisors(org=None) -> list[dict]:
    """Contacts of the org eligible to supervise (can_supervise), for the
    supervisor picker."""
    org = _require_org(org)
    doc = frappe.get_doc("Partner Organization", org)
    out = []
    for c in doc.contacts:
        if not c.person or not c.can_supervise:
            continue
        out.append(
            {
                "person": c.person,
                "full_name": frappe.db.get_value("Person", c.person, "full_name"),
                "role_at_org": c.role_at_org,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Positions
# --------------------------------------------------------------------------- #
def _position_state(status, publish) -> str:
    if status == "Closed":
        return "Closed"
    return "Live" if publish else "Pending review"


@frappe.whitelist()
def list_internship_postings(org=None) -> list[dict]:
    org = _require_org(org)
    rows = frappe.get_all(
        "Internship Position",
        filters={"partner_org": org},
        fields=[
            "name",
            "title",
            "internship_type",
            "status",
            "publish",
            "planned_placements",
            "placements_filled",
            "acceptance_mode",
        ],
        order_by="creation desc",
    )
    for r in rows:
        r["state"] = _position_state(r["status"], r["publish"])
        r["application_count"] = frappe.db.count(
            "Internship Application",
            {"internship_position": r["name"], "status": ["!=", "Draft"]},
        )
    return rows


@frappe.whitelist()
def get_internship_posting(name=None, org=None) -> dict:
    org = _require_org(org)
    pickers = {
        "types": list_internship_types(org),
        "locations": list_locations(org),
        "supervisors": get_org_supervisors(org),
    }
    if not name:
        return {
            "is_new": True,
            "status": "Open",
            "acceptance_mode": "Evaluate Applications",
            "planned_placements": 1,
            "open_students": 1,
            "flexible_dates": 1,
            "flexible_schedule": 1,
            "weekly_schedule": [],
            **pickers,
        }
    doc = _own_doc("Internship Position", name, org)
    data = {f: doc.get(f) for f in POSITION_EDITABLE_FIELDS}
    data.update(
        {
            "name": doc.name,
            "status": doc.status,
            "publish": doc.publish,
            "state": _position_state(doc.status, doc.publish),
            "weekly_schedule": [
                {
                    "day_of_week": s.day_of_week,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                }
                for s in doc.weekly_schedule
            ],
            **pickers,
        }
    )
    return data


@frappe.whitelist(methods=["POST"])
def save_internship_posting(values, name=None, org=None) -> dict:
    org = _require_org(org)
    values = _parse(values)
    if name:
        doc = _own_doc("Internship Position", name, org)
    else:
        doc = frappe.new_doc("Internship Position")
        doc.partner_org = org
    for field in POSITION_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    if values.get("status") in ("Open", "Closed"):
        doc.status = values["status"]
    if "weekly_schedule" in values:
        doc.weekly_schedule = []
        for slot in values.get("weekly_schedule") or []:
            if slot.get("day_of_week"):
                doc.append("weekly_schedule", slot)
    # Partner edits always return to pending staff review.
    doc.publish = 0
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": _position_state(doc.status, doc.publish)}


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
def _student_name(student) -> str | None:
    return frappe.db.get_value("Student", student, "student_name") if student else None


@frappe.whitelist()
def list_internship_applications(position, status=None, org=None) -> dict:
    org = _require_org(org)
    pos = frappe.db.get_value(
        "Internship Position", position, ["partner_org", "title"], as_dict=True
    )
    if not pos or pos.partner_org != org:
        frappe.throw(
            _("That position isn't part of your organization."), frappe.PermissionError
        )

    total = frappe.db.count(
        "Internship Application",
        {"internship_position": position, "status": ["!=", "Draft"]},
    )
    filters = {"internship_position": position, "status": ["!=", "Draft"]}
    if status and status in (
        *PARTNER_PIPELINE,
        "Submitted",
        "Active",
        "Completed",
        "Withdrawn",
    ):
        filters["status"] = status

    rows = frappe.get_all(
        "Internship Application",
        filters=filters,
        fields=[
            "name",
            "student",
            "status",
            "submission_date",
            "total_hours_logged",
            "total_hours_needed",
        ],
        order_by="submission_date desc",
    )
    for r in rows:
        r["student_name"] = _student_name(r["student"])
        r["hours_target"] = _hours_target(r["name"], r["total_hours_needed"])
        r["academics"] = _shared_academics(r["name"])
    return {"title": pos.title, "total": total, "applications": rows}


def _shared_academics(application: str) -> dict:
    """Applicant academic details the seminary has opted to share with partners
    (Seminary Settings → Internships). Empty unless at least one toggle is on."""
    settings = frappe.get_cached_doc("Seminary Settings")
    flags = {
        "program": settings.internship_share_program,
        "credits": settings.internship_share_credits,
        "gpa": settings.internship_share_gpa,
        "expected_graduation": settings.internship_share_expected_graduation,
    }
    if not any(flags.values()):
        return {}
    pe_name = frappe.db.get_value(
        "Internship Application", application, "program_enrollment"
    )
    if not pe_name:
        return {}
    pe = (
        frappe.db.get_value(
            "Program Enrollment",
            pe_name,
            ["program", "totalcredits", "current_gpa", "expected_graduation_date"],
            as_dict=True,
        )
        or {}
    )
    out = {}
    if flags["program"] and pe.get("program"):
        out["program"] = (
            frappe.db.get_value("Program", pe.program, "program_name") or pe.program
        )
    if flags["credits"]:
        out["credits_passed"] = pe.get("totalcredits")
    if flags["gpa"]:
        out["gpa"] = pe.get("current_gpa")
    if flags["expected_graduation"]:
        out["expected_graduation"] = pe.get("expected_graduation_date")
    return out


def _hours_target(application, total_hours_needed) -> float:
    """Hours a student is actually planned for: the sum of placement allocations
    when placements exist, else the type's requirement. Drives the X / Y display
    so it reflects what was allocated, not the raw type default."""
    allocated = sum(
        a or 0
        for a in frappe.get_all(
            "Internship Placement",
            filters={"internship_application": application},
            pluck="hours_allocated",
        )
    )
    return allocated or (total_hours_needed or 0)


@frappe.whitelist()
def get_internship_application(name, org=None) -> dict:
    org = _require_org(org)
    doc = _own_doc("Internship Application", name, org)
    if doc.status == "Draft":
        frappe.throw(
            _("This application hasn't been submitted yet."), frappe.PermissionError
        )
    placements = frappe.get_all(
        "Internship Placement",
        filters={"internship_application": name},
        fields=[
            "name",
            "site_supervisor",
            "location",
            "placement_status",
            "hours_allocated",
            "hours_logged",
            "actual_start",
            "actual_end",
        ],
        order_by="creation asc",
    )
    return {
        "name": doc.name,
        "internship_position": doc.internship_position,
        "position_title": frappe.db.get_value(
            "Internship Position", doc.internship_position, "title"
        ),
        "student": doc.student,
        "student_name": _student_name(doc.student),
        "academics": _shared_academics(doc.name),
        "status": doc.status,
        "submission_date": doc.submission_date,
        "internship_type": doc.internship_type,
        "total_hours_needed": doc.total_hours_needed,
        "total_hours_logged": doc.total_hours_logged,
        "hours_target": sum(p.get("hours_allocated") or 0 for p in placements)
        or (doc.total_hours_needed or 0),
        "placements": placements,
        "statuses": list(PARTNER_PIPELINE),
    }


@frappe.whitelist(methods=["POST"])
def set_internship_application_status(name, status, org=None) -> dict:
    org = _require_org(org)
    if status not in PARTNER_PIPELINE:
        frappe.throw(_("Invalid status."))
    doc = _own_doc("Internship Application", name, org)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


# --------------------------------------------------------------------------- #
# Placements
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_placements(org=None) -> list[dict]:
    """All active-ish placements for the org, for the placements dashboard."""
    org = _require_org(org)
    rows = frappe.get_all(
        "Internship Placement",
        filters={"partner_org": org},
        fields=[
            "name",
            "internship_application",
            "site_supervisor",
            "placement_status",
            "hours_allocated",
            "hours_logged",
            "actual_start",
            "actual_end",
        ],
        order_by="creation desc",
    )
    for r in rows:
        app = (
            frappe.db.get_value(
                "Internship Application",
                r["internship_application"],
                ["student", "internship_position", "internship_type"],
                as_dict=True,
            )
            or frappe._dict()
        )
        r["student"] = app.student
        r["student_name"] = _student_name(app.student)
        r["internship_position"] = app.internship_position
        r["internship_type"] = app.internship_type
        r["supervisor_name"] = (
            frappe.db.get_value("Person", r["site_supervisor"], "full_name")
            if r["site_supervisor"]
            else None
        )
    return rows


@frappe.whitelist(methods=["POST"])
def terminate_placement(name, org=None) -> dict:
    """End an internship before its hours are complete; opens the supervisor
    evaluation. (Auto-completion handles the normal, hours-met path.)"""
    org = _require_org(org)
    doc = _own_doc("Internship Placement", name, org)
    doc.placement_status = "Terminated"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "placement_status": doc.placement_status}


def _validate_supervisor(org, person):
    """A site supervisor must be an org contact flagged Can Supervise."""
    if not person:
        return
    ok = frappe.db.exists(
        "Partner Contact",
        {
            "parenttype": "Partner Organization",
            "parent": org,
            "person": person,
            "can_supervise": 1,
        },
    )
    if not ok:
        frappe.throw(
            _("That person isn't an eligible supervisor for your organization.")
        )


@frappe.whitelist(methods=["POST"])
def save_placement(values, name, org=None) -> dict:
    org = _require_org(org)
    values = _parse(values)
    doc = _own_doc("Internship Placement", name, org)
    if "site_supervisor" in values:
        _validate_supervisor(org, values.get("site_supervisor"))
    for field in PLACEMENT_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "placement_status": doc.placement_status}


# --------------------------------------------------------------------------- #
# Hours
# --------------------------------------------------------------------------- #
def _own_placement(placement, org) -> str:
    if frappe.db.get_value("Internship Placement", placement, "partner_org") != org:
        frappe.throw(
            _("That placement isn't part of your organization."), frappe.PermissionError
        )
    return placement


@frappe.whitelist()
def list_hours(placement, org=None) -> list[dict]:
    org = _require_org(org)
    _own_placement(placement, org)
    return frappe.get_all(
        "Internship Hours Log",
        filters={"internship_placement": placement},
        fields=[
            "name",
            "log_date",
            "hours",
            "description",
            "supervisor_verified",
            "verified_on",
        ],
        order_by="log_date desc",
    )


@frappe.whitelist(methods=["POST"])
def verify_hours(name, verified=1, org=None) -> dict:
    org = _require_org(org)
    log = frappe.get_doc("Internship Hours Log", name)
    _own_placement(log.internship_placement, org)
    log.supervisor_verified = 1 if str(verified) in ("1", "true", "True", "yes") else 0
    log.save(ignore_permissions=True)
    return {"name": log.name, "supervisor_verified": log.supervisor_verified}


@frappe.whitelist(methods=["POST"])
def add_hours(placement, log_date, hours, description=None, org=None) -> dict:
    """A supervisor logging hours on the student's behalf (verified at source)."""
    org = _require_org(org)
    _own_placement(placement, org)
    doc = frappe.get_doc(
        {
            "doctype": "Internship Hours Log",
            "internship_placement": placement,
            "log_date": getdate(log_date),
            "hours": flt(hours),
            "description": description,
            "supervisor_verified": 1,
        }
    ).insert(ignore_permissions=True)
    return {"name": doc.name}


# --------------------------------------------------------------------------- #
# Requirements (partner party)
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_requirements(application, org=None) -> list[dict]:
    org = _require_org(org)
    _own_doc("Internship Application", application, org)
    rows = frappe.get_all(
        "Internship Requirement",
        filters={"internship_application": application, "partner_submits": 1},
        fields=[
            "name",
            "title",
            "status",
            "due_date",
            "partner_label",
            "partner_submission_type",
            "partner_submission_value",
            "partner_attachment",
            "partner_acknowledged",
            "partner_signs_complete",
            "partner_signoff",
            "submit_template",
        ],
        order_by="due_date asc",
    )
    return rows


@frappe.whitelist(methods=["POST"])
def save_requirement_partner(name, values, org=None) -> dict:
    """Record the partner's submission and/or sign-off on a requirement. A
    placement-scope requirement carries the placement's org; an application-scope
    one has no placement, so we fall back to the application's org."""
    org = _require_org(org)
    values = _parse(values)
    application = frappe.db.get_value(
        "Internship Requirement", name, "internship_application"
    )
    _own_doc("Internship Application", application, org)
    doc = frappe.get_doc("Internship Requirement", name)
    for field in (
        "partner_submission_value",
        "partner_attachment",
        "partner_acknowledged",
        "partner_signoff",
    ):
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


# --------------------------------------------------------------------------- #
# Supervisor evaluation
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_supervisor_evaluation(placement, org=None) -> dict:
    org = _require_org(org)
    _own_placement(placement, org)
    existing = frappe.get_all(
        "Internship Supervisor Evaluation",
        filters={"internship_placement": placement, "docstatus": ["<", 2]},
        fields=["name", "docstatus", *EVALUATION_FIELDS],
        limit=1,
    )
    return existing[0] if existing else {"is_new": True, "placement": placement}


@frappe.whitelist(methods=["POST"])
def save_supervisor_evaluation(
    placement, values, submit=0, name=None, org=None
) -> dict:
    org = _require_org(org)
    values = _parse(values)
    _own_placement(placement, org)
    if name:
        doc = frappe.get_doc("Internship Supervisor Evaluation", name)
        if doc.internship_placement != placement:
            frappe.throw(_("Evaluation does not match the placement."))
    else:
        doc = frappe.new_doc("Internship Supervisor Evaluation")
        doc.internship_placement = placement
    for field in EVALUATION_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    if str(submit) in ("1", "true", "True", "yes") and doc.docstatus == 0:
        doc.submit()
    return {"name": doc.name, "docstatus": doc.docstatus}
