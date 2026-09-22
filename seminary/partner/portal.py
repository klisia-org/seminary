"""Partner-organization portal API (ADR 053).

The employer side of the job board: partner staff manage their own organization's
profile, people, locations, job postings, and applicants. Every function resolves
the caller's organization via `my_partner_org` and scopes strictly to it; data for
any other org is never returned or writable. Mutations use `ignore_permissions`
(this API is the permission boundary) after an explicit ownership check.
"""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from seminary.partner.permissions import STAFF_BYPASS, my_partner_org
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
    "tax_id",
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
def _my_orgs() -> list[dict]:
    """Every Partner Organization the current user may act on — one per portal
    `Partner Contact` row (a user can be a contact on several orgs)."""
    rows = frappe.get_all(
        "Partner Contact",
        filters={
            "portal_user": frappe.session.user,
            "portal_access": 1,
            "parenttype": "Partner Organization",
        },
        fields=["parent"],
    )
    names = [r.parent for r in rows]
    if not names:
        return []
    return frappe.get_all(
        "Partner Organization",
        filters={"name": ["in", names]},
        fields=["name", "organization_name"],
        order_by="organization_name asc",
    )


def _require_org(org: str | None = None) -> str:
    """Resolve the org for this request. When `org` is given it must be one the
    user belongs to; otherwise fall back to their default (first) org."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    if org:
        valid = {o["name"] for o in _my_orgs()}
        if org not in valid:
            frappe.throw(_("That organization isn't yours."), frappe.PermissionError)
        return org
    org = my_partner_org()
    if not org:
        frappe.throw(
            _("Your account isn't linked to a partner organization."),
            frappe.PermissionError,
        )
    return org


@frappe.whitelist()
def list_my_orgs() -> list[dict]:
    """Organizations the partner user can act on, for the portal org picker."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)
    return _my_orgs()


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


# Field types whose partner-supplied value is stored (and later rendered) as
# text or HTML; sanitised with nh3's allow-list before doc.set (p006 F13).
_SANITIZED_FIELDTYPES = {"Text Editor", "Small Text", "Long Text", "Text"}


def _clean(doctype: str, field: str, value):
    df = frappe.get_meta(doctype).get_field(field)
    if isinstance(value, str) and df and df.fieldtype in _SANITIZED_FIELDTYPES:
        return frappe.utils.sanitize_html(value, always_sanitize=True)
    return value


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_my_org(org=None) -> dict:
    org = _require_org(org)
    doc = frappe.get_doc("Partner Organization", org)
    data = {f: doc.get(f) for f in ORG_EDITABLE_FIELDS}
    data.update(
        {
            "name": doc.name,
            "organization_name": doc.organization_name,
            "partner_type": doc.partner_type,
            "status": doc.status,
            "locations": list_locations(org),
        }
    )
    return data


@frappe.whitelist()
def update_org(values, org=None) -> dict:
    org = _require_org(org)
    values = _parse(values)
    doc = frappe.get_doc("Partner Organization", org)
    for field in ORG_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, _clean("Partner Organization", field, values[field]))
    doc.save(ignore_permissions=True)
    return get_my_org(org)


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
@frappe.whitelist()
def get_people(org=None) -> list[dict]:
    org = _require_org(org)
    doc = frappe.get_doc("Partner Organization", org)
    me = _current_person()
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
                # ADR 077: who currently acts for the org, and whether the
                # caller is the one who may change that.
                "relationship_status": c.relationship_status or "Active",
            }
        )
    is_staff = bool(set(frappe.get_roles(frappe.session.user)) & STAFF_BYPASS)
    may_manage = is_staff or _is_primary_contact(org, me)
    for p in people:
        p["may_manage"] = bool(may_manage and p["person"] != me)
    return people


@frappe.whitelist(methods=["POST"])
def create_contact(
    first_name,
    last_name=None,
    email=None,
    mobile=None,
    role_at_org=None,
    grant_portal_access=0,
    org=None,
) -> dict:
    org = _require_org(org)
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
def list_locations(org=None) -> list[dict]:
    org = _require_org(org)
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
def save_location(values, name=None, org=None) -> dict:
    org = _require_org(org)
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
def get_skill_tags(org=None) -> list[str]:
    """Active Skill Tag names for the posting form's skills picker."""
    _require_org(org)
    return frappe.get_all(
        "Skill Tag", filters={"is_active": 1}, pluck="name", order_by="name asc"
    )


@frappe.whitelist()
def list_job_postings(org=None) -> list[dict]:
    org = _require_org(org)
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
def get_job_posting(name=None, org=None) -> dict:
    org = _require_org(org)
    if not name:
        return {
            "is_new": True,
            "status": "Open",
            "planned_vacancies": 1,
            "open_students": 0,
            "open_alumni": 0,
            "require_doctrinal_alignment": 0,
            "skills": [],
            "locations": list_locations(org),
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
            "locations": list_locations(org),
        }
    )
    return data


@frappe.whitelist(methods=["POST"])
def save_job_posting(values, name=None, org=None) -> dict:
    org = _require_org(org)
    values = _parse(values)
    if name:
        doc = _own_doc("Partner Job Opening", name, org)
    else:
        doc = frappe.new_doc("Partner Job Opening")
        doc.partner_org = org
    for field in OPENING_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, _clean("Partner Job Opening", field, values[field]))
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
    opening,
    status=None,
    evaluated="",
    sort_by="submission_date",
    sort_dir="desc",
    query="",
    org=None,
) -> dict:
    org = _require_org(org)
    opening_doc = frappe.db.get_value(
        "Partner Job Opening", opening, ["partner_org", "job_title"], as_dict=True
    )
    if not opening_doc or opening_doc.partner_org != org:
        frappe.throw(
            _("That posting isn't part of your organization."), frappe.PermissionError
        )

    # Total received — every submitted application for this opening, unaffected by
    # the active filters/search (so the header count is a stable "X applications").
    total = frappe.db.count(
        "Partner Job Application", {"job_opening": opening, "status": ["!=", "Draft"]}
    )

    filters = {"job_opening": opening, "status": ["!=", "Draft"]}
    if status and status in PIPELINE_STATUSES:
        filters["status"] = status
    or_filters = [["full_name", "like", f"%{query}%"]] if query else None
    sort_col = APP_SORT_FIELDS.get(sort_by, "submission_date")
    direction = "asc" if str(sort_dir).lower() == "asc" else "desc"

    rows = frappe.get_all(
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

    if rows:
        names = [r["name"] for r in rows]
        # "Evaluated by me" — applications where the caller's Person has a review row.
        person = _current_person()
        reviewed_by_me = set()
        if person:
            reviewed_by_me = set(
                frappe.get_all(
                    "Partner Job Application Review",
                    filters={
                        "parenttype": "Partner Job Application",
                        "parent": ["in", names],
                        "reviewer": person,
                    },
                    pluck="parent",
                )
            )
        # Logged-contact counts, grouped by application (counted in Python — raw SQL
        # aggregates aren't allowed in get_all's field list).
        contact_counts = Counter(
            frappe.get_all(
                "Partner Job Application Contact",
                filters={
                    "parenttype": "Partner Job Application",
                    "parent": ["in", names],
                },
                pluck="parent",
            )
        )
        for r in rows:
            r["evaluated_by_me"] = r["name"] in reviewed_by_me
            r["contact_count"] = contact_counts.get(r["name"], 0)

        if evaluated == "yes":
            rows = [r for r in rows if r["evaluated_by_me"]]
        elif evaluated == "no":
            rows = [r for r in rows if not r["evaluated_by_me"]]

    return {
        "job_title": opening_doc.job_title,
        "total": total,
        "applications": rows,
    }


@frappe.whitelist()
def get_application(name, org=None) -> dict:
    org = _require_org(org)
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
def set_application_status(name, status, org=None) -> dict:
    org = _require_org(org)
    if status not in PIPELINE_STATUSES:
        frappe.throw(_("Invalid status."))
    doc = _own_doc("Partner Job Application", name, org)
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def save_review(application, rating=None, notes=None, org=None) -> dict:
    org = _require_org(org)
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
    org=None,
) -> dict:
    org = _require_org(org)
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


# --------------------------------------------------------------------------- #
# Membership lifecycle (ADR 077)
# --------------------------------------------------------------------------- #
def _contact_row(org: str, person: str):
    """The Partner Contact child row for `person` on `org`, or None."""
    doc = frappe.get_doc("Partner Organization", org)
    for row in doc.contacts:
        if row.person == person:
            return doc, row
    return doc, None


def _is_primary_contact(org: str, person: str) -> bool:
    _doc, row = _contact_row(org, person)
    return bool(row and row.is_primary and row.relationship_status == "Active")


def _revoke_partner_role_if_orphaned(user: str) -> None:
    """Drop the `Partner` role once a user holds no portal-enabled contact row.

    `Partner Organization.on_update` grants the role and nothing has ever taken
    it back, so without this the role outlives every relationship that justified
    it -- and it is what puts /partner in the sidebar (ADR 074).
    """
    if not user:
        return
    still = frappe.get_all(
        "Partner Contact",
        filters={
            "portal_user": user,
            "portal_access": 1,
            "parenttype": "Partner Organization",
        },
        limit=1,
    )
    if still:
        return
    if "Partner" not in set(frappe.get_roles(user)):
        return
    user_doc = frappe.get_doc("User", user)
    # Mirrors _grant_portal_roles: a portal user cannot write User, and reading
    # the roles child table back as one yields an empty list -- so check via
    # frappe.get_roles and save with permissions ignored. Doing it the obvious
    # way fails *silently*, leaving the role behind.
    user_doc.flags.ignore_permissions = True
    user_doc.remove_roles("Partner")


@frappe.whitelist(methods=["POST"])
def update_my_contact(role_at_org=None, org=None) -> dict:
    """Let a contact correct their own role at an organization (ADR 077).

    `role_at_org` is the *representation* role -- what this person does for the
    organization as a partner -- and is distinct from the alumni profile's
    free-text employment, which records where they work and needs no partner
    relationship at all.
    """
    org = _require_org(org)
    person = _require_person()
    doc, row = _contact_row(org, person)
    if not row:
        frappe.throw(
            _("You are not a contact of this organization."), frappe.PermissionError
        )
    row.role_at_org = (role_at_org or "").strip() or None
    doc.save(ignore_permissions=True)
    return {"org": org, "role_at_org": row.role_at_org}


@frappe.whitelist(methods=["POST"])
def leave_organization(org=None) -> dict:
    """End your own relationship with an organization (ADR 077).

    A status transition, not a deletion: the row stays so the organization keeps
    a true record of who set it up and acted for it. Portal access is cleared and
    the `Partner` role revoked once no portal-enabled row remains.

    Leaving is never blocked for being the last contact. An organization with no
    contacts is staff's to resolve -- see the "no active contact" report -- and
    refusing the leave would trap someone in a relationship they have ended in
    real life.
    """
    org = _require_org(org)
    person = _require_person()
    doc, row = _contact_row(org, person)
    if not row:
        frappe.throw(
            _("You are not a contact of this organization."), frappe.PermissionError
        )
    user = row.portal_user
    row.relationship_status = "Former"
    row.portal_access = 0
    row.portal_user = None
    row.is_primary = 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    _revoke_partner_role_if_orphaned(user)
    return {"org": org, "left": True}


@frappe.whitelist(methods=["POST"])
def set_contact_status(person, status, org=None) -> dict:
    """The primary contact ends or restores another contact's relationship.

    Who speaks for an organization is the primary contact's call (ADR 077), not
    staff's and not every contact's. Reactivation is also how a `Former` contact
    rejoins -- a second row would split one relationship in two.
    """
    if status not in ("Active", "Former"):
        frappe.throw(_("Invalid status."))
    org = _require_org(org)
    me = _require_person()
    is_staff = bool(set(frappe.get_roles(frappe.session.user)) & STAFF_BYPASS)
    if not (_is_primary_contact(org, me) or is_staff):
        frappe.throw(
            _("Only the primary contact can change who acts for this organization."),
            frappe.PermissionError,
        )
    if person == me:
        frappe.throw(_("Use Leave to end your own relationship."))
    doc, row = _contact_row(org, person)
    if not row:
        frappe.throw(_("That person is not a contact of this organization."))
    user = row.portal_user
    row.relationship_status = status
    if status == "Former":
        row.portal_access = 0
        row.portal_user = None
        row.is_primary = 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    if status == "Former":
        _revoke_partner_role_if_orphaned(user)
    return {"org": org, "person": person, "status": status}
