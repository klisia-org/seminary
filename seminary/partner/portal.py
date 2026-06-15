"""Partner-organization portal API (ADR 053).

The employer side of the job board: partner staff manage their own organization's
profile, people, locations, job postings, and applicants. Every function resolves
the caller's organization via `my_partner_org` and scopes strictly to it; data for
any other org is never returned or writable. Mutations use `ignore_permissions`
(this API is the permission boundary) after an explicit ownership check.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from seminary.partner.permissions import my_partner_org
from seminary.seminary.person import ensure_person

PIPELINE_STATUSES = (
    "Open",
    "Replied",
    "Shortlisted",
    "Hold",
    "Rejected",
    "Accepted",
    "Withdrawn",
)

ORG_EDITABLE_FIELDS = (
    "about_us",
    "doctrinal_statement",
    "website",
    "image",
    "primary_email",
    "primary_phone",
    "address_line_1",
    "address_line_2",
    "pincode",
    "city",
    "state",
    "country",
)

LOCATION_EDITABLE_FIELDS = (
    "location_name",
    "address_line_1",
    "address_line_2",
    "pincode",
    "city",
    "state",
    "country",
    "ministry_setting",
    "congregation_size",
)

OPENING_EDITABLE_FIELDS = (
    "job_title",
    "description",
    "qualifications",
    "employment_type",
    "position_type",
    "location",
    "planned_vacancies",
    "closes_on",
    "open_students",
    "open_alumni",
    "require_doctrinal_alignment",
)

APP_SORT_FIELDS = {
    "submission_date": "submission_date",
    "average_rating": "average_rating",
    "applicant": "full_name",
}


# --------------------------------------------------------------------------- #
# Resolution helpers
# --------------------------------------------------------------------------- #
def _require_org() -> str:
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    org = my_partner_org()
    if not org:
        frappe.throw(
            _("Your account isn't linked to a partner organization."),
            frappe.PermissionError,
        )
    return org


def _current_person() -> str | None:
    person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
    if person:
        return person
    return frappe.db.get_value(
        "Partner Contact",
        {"portal_user": frappe.session.user, "portal_access": 1},
        "person",
    )


def _require_person() -> str:
    person = _current_person()
    if not person:
        frappe.throw(
            _("Your account isn't linked to a person record."), frappe.PermissionError
        )
    return person


def _own_doc(doctype: str, name: str, org: str) -> "frappe.model.document.Document":
    """Load a doc and confirm it belongs to the caller's org (by partner_org)."""
    if frappe.db.get_value(doctype, name, "partner_org") != org:
        frappe.throw(
            _("That record isn't part of your organization."), frappe.PermissionError
        )
    return frappe.get_doc(doctype, name)


def _parse(values):
    return frappe.parse_json(values) if isinstance(values, str) else (values or {})


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_my_org() -> dict:
    org = _require_org()
    doc = frappe.get_doc("Partner Organization", org)
    data = {f: doc.get(f) for f in ORG_EDITABLE_FIELDS}
    data.update(
        {
            "name": doc.name,
            "organization_name": doc.organization_name,
            "partner_type": doc.partner_type,
            "status": doc.status,
            "locations": list_locations(),
        }
    )
    return data


@frappe.whitelist()
def update_org(values) -> dict:
    org = _require_org()
    values = _parse(values)
    doc = frappe.get_doc("Partner Organization", org)
    for field in ORG_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return get_my_org()


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_people() -> list[dict]:
    org = _require_org()
    doc = frappe.get_doc("Partner Organization", org)
    people = []
    for c in doc.contacts:
        person = (
            frappe.db.get_value(
                "Person",
                c.person,
                ["full_name", "primary_email", "primary_mobile"],
                as_dict=True,
            )
            or {}
        )
        people.append(
            {
                "row": c.name,
                "person": c.person,
                "full_name": person.get("full_name"),
                "email": person.get("primary_email"),
                "mobile": person.get("primary_mobile"),
                "role_at_org": c.role_at_org,
                "is_primary": c.is_primary,
                "portal_access": c.portal_access,
            }
        )
    return people


@frappe.whitelist(methods=["POST"])
def create_contact(
    first_name,
    last_name=None,
    email=None,
    mobile=None,
    role_at_org=None,
    grant_portal_access=0,
) -> dict:
    org = _require_org()
    if not email:
        frappe.throw(_("An email is required to create a contact."))
    grant = str(grant_portal_access).strip().lower() in ("1", "true", "yes")

    portal_user = _ensure_user(email, first_name, last_name) if grant else None
    person = ensure_person(
        email=email,
        user=portal_user,
        first_name=first_name,
        last_name=last_name,
        mobile=mobile,
    )

    doc = frappe.get_doc("Partner Organization", org)
    doc.append(
        "contacts",
        {
            "person": person,
            "role_at_org": role_at_org,
            "portal_user": portal_user,
            "portal_access": 1 if grant else 0,
        },
    )
    doc.save(ignore_permissions=True)  # on_update grants the Partner role
    return {"person": person, "portal_user": portal_user}


def _ensure_user(email, first_name, last_name) -> str:
    if frappe.db.exists("User", email):
        return email
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name or email.split("@")[0],
            "last_name": last_name,
            "user_type": "Website User",
            "send_welcome_email": 1,
        }
    )
    user.insert(ignore_permissions=True)
    return user.name


# --------------------------------------------------------------------------- #
# Locations
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_locations() -> list[dict]:
    org = _require_org()
    return frappe.get_all(
        "Partner Organization Location",
        filters={"partner_org": org},
        fields=[
            "name",
            "location_name",
            "address_line_1",
            "address_line_2",
            "pincode",
            "city",
            "state",
            "country",
            "ministry_setting",
            "congregation_size",
        ],
        order_by="location_name asc",
    )


@frappe.whitelist(methods=["POST"])
def save_location(values, name=None) -> dict:
    org = _require_org()
    values = _parse(values)
    if name:
        doc = _own_doc("Partner Organization Location", name, org)
    else:
        doc = frappe.new_doc("Partner Organization Location")
        doc.partner_org = org
    for field in LOCATION_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return {"name": doc.name}


# --------------------------------------------------------------------------- #
# Job postings
# --------------------------------------------------------------------------- #
def _posting_state(status, publish) -> str:
    if status == "Closed":
        return "Closed"
    return "Live" if publish else "Pending review"


@frappe.whitelist()
def get_skill_tags() -> list[str]:
    """Active Skill Tag names for the posting form's skills picker."""
    _require_org()
    return frappe.get_all(
        "Skill Tag", filters={"is_active": 1}, pluck="name", order_by="name asc"
    )


@frappe.whitelist()
def list_job_postings() -> list[dict]:
    org = _require_org()
    rows = frappe.get_all(
        "Partner Job Opening",
        filters={"partner_org": org},
        fields=[
            "name",
            "job_title",
            "status",
            "publish",
            "position_type",
            "employment_type",
            "planned_vacancies",
            "vacancies",
            "posted_on",
        ],
        order_by="creation desc",
    )
    for r in rows:
        r["state"] = _posting_state(r["status"], r["publish"])
        r["application_count"] = frappe.db.count(
            "Partner Job Application",
            {"job_opening": r["name"], "status": ["!=", "Draft"]},
        )
    return rows


@frappe.whitelist()
def get_job_posting(name=None) -> dict:
    org = _require_org()
    if not name:
        return {
            "is_new": True,
            "status": "Open",
            "planned_vacancies": 1,
            "open_students": 0,
            "open_alumni": 0,
            "require_doctrinal_alignment": 0,
            "skills": [],
            "locations": list_locations(),
        }
    doc = _own_doc("Partner Job Opening", name, org)
    data = {f: doc.get(f) for f in OPENING_EDITABLE_FIELDS}
    data.update(
        {
            "name": doc.name,
            "status": doc.status,
            "publish": doc.publish,
            "state": _posting_state(doc.status, doc.publish),
            "skills": [s.skill_tag for s in doc.skills],
            "locations": list_locations(),
        }
    )
    return data


@frappe.whitelist(methods=["POST"])
def save_job_posting(values, name=None) -> dict:
    org = _require_org()
    values = _parse(values)
    if name:
        doc = _own_doc("Partner Job Opening", name, org)
    else:
        doc = frappe.new_doc("Partner Job Opening")
        doc.partner_org = org
    for field in OPENING_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    if values.get("status") in ("Open", "Closed"):
        doc.status = values["status"]
    if "skills" in values:
        doc.skills = []
        for tag in values.get("skills") or []:
            if tag:
                doc.append("skills", {"skill_tag": tag})
    # Partner edits always return to pending staff review.
    doc.publish = 0
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": _posting_state(doc.status, doc.publish)}


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def list_applications(
    opening, status=None, sort_by="submission_date", sort_dir="desc", query=""
) -> list[dict]:
    org = _require_org()
    if frappe.db.get_value("Partner Job Opening", opening, "partner_org") != org:
        frappe.throw(
            _("That posting isn't part of your organization."), frappe.PermissionError
        )

    filters = {"job_opening": opening, "status": ["!=", "Draft"]}
    if status and status in PIPELINE_STATUSES:
        filters["status"] = status
    or_filters = [["full_name", "like", f"%{query}%"]] if query else None
    sort_col = APP_SORT_FIELDS.get(sort_by, "submission_date")
    direction = "asc" if str(sort_dir).lower() == "asc" else "desc"

    return frappe.get_all(
        "Partner Job Application",
        fields=[
            "name",
            "applicant",
            "full_name",
            "status",
            "average_rating",
            "submission_date",
        ],
        filters=filters,
        or_filters=or_filters,
        order_by=f"{sort_col} {direction}",
    )


@frappe.whitelist()
def get_application(name) -> dict:
    org = _require_org()
    doc = _own_doc("Partner Job Application", name, org)
    if doc.status == "Draft":
        frappe.throw(
            _("This application hasn't been submitted yet."), frappe.PermissionError
        )

    person = _current_person()
    reviews = [
        {
            "row": r.name,
            "reviewer": r.reviewer,
            "reviewer_name": (
                frappe.db.get_value("Person", r.reviewer, "full_name")
                if r.reviewer
                else None
            ),
            "rating": r.rating,
            "reviewed_on": r.reviewed_on,
            "notes": r.notes,
            "is_mine": bool(person) and r.reviewer == person,
        }
        for r in doc.reviews
    ]
    contacts = [
        {
            "row": c.name,
            "contact_type": c.contact_type,
            "contacted_on": c.contacted_on,
            "participants": c.participants,
            "notes": c.notes,
        }
        for c in doc.contacts
    ]
    return {
        "name": doc.name,
        "job_opening": doc.job_opening,
        "job_title": frappe.db.get_value(
            "Partner Job Opening", doc.job_opening, "job_title"
        ),
        "applicant": doc.applicant,
        "full_name": doc.full_name,
        "email": doc.primary_email,
        "mobile": doc.primary_mobile,
        "status": doc.status,
        "submission_date": doc.submission_date,
        "cover_letter": doc.cover_letter,
        "resume": doc.resume,
        "doctrinal_alignment": doc.doctrinal_alignment,
        "alignment_explanation": doc.alignment_explanation,
        "average_rating": doc.average_rating,
        "reviews": reviews,
        "my_review": next((rv for rv in reviews if rv["is_mine"]), None),
        "contacts": contacts,
        "statuses": list(PIPELINE_STATUSES),
    }


@frappe.whitelist(methods=["POST"])
def set_application_status(name, status) -> dict:
    org = _require_org()
    if status not in PIPELINE_STATUSES:
        frappe.throw(_("Invalid status."))
    doc = _own_doc("Partner Job Application", name, org)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def save_review(application, rating=None, notes=None) -> dict:
    org = _require_org()
    person = _require_person()
    doc = _own_doc("Partner Job Application", application, org)
    row = next((r for r in doc.reviews if r.reviewer == person), None)
    if row:
        row.rating = flt(rating)
        row.notes = notes
        row.reviewed_on = now_datetime()
    else:
        doc.append(
            "reviews",
            {
                "reviewer": person,
                "rating": flt(rating),
                "notes": notes,
                "reviewed_on": now_datetime(),
            },
        )
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "average_rating": doc.average_rating}


@frappe.whitelist(methods=["POST"])
def save_contact_log(
    application,
    contact_type=None,
    contacted_on=None,
    participants=None,
    notes=None,
    row=None,
) -> dict:
    org = _require_org()
    doc = _own_doc("Partner Job Application", application, org)
    if row:
        target = next((c for c in doc.contacts if c.name == row), None)
        if not target:
            frappe.throw(_("Contact entry not found."))
        target.contact_type = contact_type
        target.contacted_on = contacted_on or target.contacted_on
        target.participants = participants
        target.notes = notes
    else:
        doc.append(
            "contacts",
            {
                "contact_type": contact_type,
                "contacted_on": contacted_on or now_datetime(),
                "participants": participants,
                "notes": notes,
            },
        )
    doc.save(ignore_permissions=True)
    return {"name": doc.name}
