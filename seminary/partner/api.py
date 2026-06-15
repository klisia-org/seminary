"""Portal-facing API for the partner job board (ADR 053, phase 1).

Serves published `Partner Job Opening` records to the student and alumni portals.
Only the openings a logged-in user is eligible to see are returned — eligibility
follows the opening's audience flags (`open_students` / `open_alumni`); an opening
with neither flag is public to any logged-in portal user. Applications are created
and submitted through `apply_to_job` below (in-portal, not a public Web Form), with
a Draft → Open (submitted) lifecycle on the application's status.
"""

import frappe
from frappe import _

FULL_AGREEMENT = "I agree completely, without reservations"

# Applicant-facing status buckets for the "My Applications" panel. The partner's
# internal pipeline states (Replied/Shortlisted/Hold) are collapsed into "Open" —
# the applicant only needs to know their application is live and under consideration,
# not where it sits in the reviewer's workflow. Each bucket key is also a filter value.
APPLICANT_BUCKETS = {
    "Draft": ("Draft",),
    "Open": ("Open", "Replied", "Shortlisted", "Hold"),
    "Rejected": ("Rejected",),
    "Accepted": ("Accepted",),
    "Withdrawn": ("Withdrawn",),
}

# Live states an applicant may withdraw from (everything in the "Open" bucket).
WITHDRAWABLE_STATUSES = APPLICANT_BUCKETS["Open"]

# Lightweight fields for the list/card view.
LIST_FIELDS = (
    "name",
    "job_title",
    "partner_org",
    "employment_type",
    "position_type",
    "location",
    "ministry_setting",
    "require_doctrinal_alignment",
    "posted_on",
    "vacancies",
    "open_students",
    "open_alumni",
)


def _current_person() -> str | None:
    """The Person spine record (ADR 042) for the logged-in user, if any."""
    if frappe.session.user == "Guest":
        return None
    return frappe.db.get_value("Person", {"user": frappe.session.user}, "name")


def _audience() -> tuple[bool, bool]:
    """(is_student, is_alumni) for the current user, judged by the Person spine's
    linked Student / Alumni Profile records — the SAME signal the
    Partner Job Application controller uses to gate eligibility, so the Apply
    button never promises an application the controller will reject."""
    person = _current_person()
    if not person:
        return False, False
    is_student = bool(frappe.db.exists("Student", {"person": person}))
    is_alumni = bool(frappe.db.exists("Alumni Profile", {"person": person}))
    return is_student, is_alumni


def _is_visible(opening: dict, is_student: bool, is_alumni: bool) -> bool:
    """An opening with no audience flag is public; otherwise the user must match
    a flagged audience."""
    if not (opening.get("open_students") or opening.get("open_alumni")):
        return True
    if opening.get("open_students") and is_student:
        return True
    if opening.get("open_alumni") and is_alumni:
        return True
    return False


def _require_login() -> None:
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to view the job board."), frappe.PermissionError)


@frappe.whitelist()
def get_job_openings(
    query: str = "",
    employment_type: str = "",
    ministry_setting: str = "",
    position_type: str = "",
    partner_type: str = "",
    requires_doctrinal: str = "",
) -> list[dict]:
    """Published, open job postings the current user is eligible to see, with the
    organization name / type / city decorated on for the card view."""
    _require_login()

    filters: list = [["publish", "=", 1], ["status", "=", "Open"]]
    if employment_type:
        filters.append(["employment_type", "=", employment_type])
    if ministry_setting:
        filters.append(["ministry_setting", "=", ministry_setting])
    if position_type:
        filters.append(["position_type", "=", position_type])
    if str(requires_doctrinal).strip().lower() in ("1", "true", "yes"):
        filters.append(["require_doctrinal_alignment", "=", 1])

    openings = frappe.get_all(
        "Partner Job Opening",
        fields=list(LIST_FIELDS),
        filters=filters,
        order_by="posted_on desc, creation desc",
        limit_page_length=0,
    )
    if not openings:
        return []

    _decorate(openings)

    is_student, is_alumni = _audience()
    # Openings the user has already applied to live in the "My Applications" panel,
    # not the master list — so a browsing applicant never asks "did I apply here yet?"
    # Drafts are NOT excluded: an in-progress draft stays browsable so it can be
    # resumed from the opening's detail page.
    applied = _applied_opening_names()
    needle = (query or "").strip().lower()
    results = []
    for o in openings:
        if o["name"] in applied:
            continue
        if not _is_visible(o, is_student, is_alumni):
            continue
        if partner_type and o.get("partner_type") != partner_type:
            continue
        if (
            needle
            and needle
            not in " ".join(
                str(o.get(f) or "")
                for f in (
                    "job_title",
                    "organization_name",
                    "city",
                    "location_name",
                    "ministry_setting",
                    "position_type",
                )
            ).lower()
        ):
            continue
        # Drop the audience flags from the payload — they were only for gating.
        o.pop("open_students", None)
        o.pop("open_alumni", None)
        results.append(o)
    return results


def _decorate(openings: list[dict]) -> None:
    """Attach organization_name, partner_type, location_name and a display city to
    each row (bulk lookups, no N+1)."""
    org_names = {o["partner_org"] for o in openings if o.get("partner_org")}
    loc_names = {o["location"] for o in openings if o.get("location")}

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

    for o in openings:
        org = orgs.get(o.get("partner_org"))
        loc = locs.get(o.get("location"))
        o["organization_name"] = org.organization_name if org else o.get("partner_org")
        o["partner_type"] = org.partner_type if org else None
        o["location_name"] = loc.location_name if loc else None
        o["city"] = loc.city if loc and loc.city else (org.city if org else None)


def _applied_opening_names() -> set[str]:
    """Openings the current user has a *submitted* application to (Draft excluded)."""
    person = _current_person()
    if not person:
        return set()
    return set(
        frappe.get_all(
            "Partner Job Application",
            filters={"applicant": person, "status": ["!=", "Draft"]},
            pluck="job_opening",
        )
    )


@frappe.whitelist()
def get_my_applications(status: str = "Open") -> list[dict]:
    """The logged-in applicant's own applications for the side panel, newest first,
    decorated with the opening + organization for display.

    `status` is a bucket key from APPLICANT_BUCKETS (default "Open" = active);
    pass an empty string for every application across all buckets, including Drafts."""
    _require_login()
    person = _current_person()
    if not person:
        return []

    filters = {"applicant": person}
    bucket = APPLICANT_BUCKETS.get(status)
    if bucket:
        filters["status"] = ["in", list(bucket)]

    apps = frappe.get_all(
        "Partner Job Application",
        fields=["name", "job_opening", "status", "submission_date"],
        filters=filters,
        order_by="submission_date desc, modified desc",
        limit_page_length=0,
    )
    if not apps:
        return []

    opening_names = {a["job_opening"] for a in apps if a.get("job_opening")}
    openings = {
        r.name: r
        for r in frappe.get_all(
            "Partner Job Opening",
            fields=["name", "job_title", "partner_org", "status"],
            filters={"name": ["in", list(opening_names)]},
        )
    }
    org_names = {o.partner_org for o in openings.values() if o.partner_org}
    orgs = (
        {
            r.name: r
            for r in frappe.get_all(
                "Partner Organization",
                fields=["name", "organization_name", "city"],
                filters={"name": ["in", list(org_names)]},
            )
        }
        if org_names
        else {}
    )

    for a in apps:
        opening = openings.get(a["job_opening"])
        org = orgs.get(opening.partner_org) if opening else None
        a["job_title"] = opening.job_title if opening else a["job_opening"]
        a["opening_status"] = opening.status if opening else None
        a["organization_name"] = org.organization_name if org else None
        a["city"] = org.city if org else None
    return apps


def _own_application(name: str) -> "frappe._dict":
    """Load (applicant, status) for an application and confirm it belongs to the
    caller — the permission boundary for applicant-side mutations."""
    person = _current_person()
    app = frappe.db.get_value(
        "Partner Job Application", name, ["applicant", "status"], as_dict=True
    )
    if not app or not person or app.applicant != person:
        frappe.throw(_("That application isn't yours."), frappe.PermissionError)
    return app


@frappe.whitelist(methods=["POST"])
def withdraw_application(name: str) -> dict:
    """Applicant withdraws their own live application. Allowed only from the "Open"
    bucket; a Draft (not yet submitted) or an already-terminal application
    (Rejected/Accepted/Withdrawn) cannot be withdrawn."""
    _require_login()
    app = _own_application(name)
    if app.status not in WITHDRAWABLE_STATUSES:
        frappe.throw(_("This application can no longer be withdrawn."))
    doc = frappe.get_doc("Partner Job Application", name)
    doc.status = "Withdrawn"
    doc.save(ignore_permissions=True)  # runs vacancy sync via on_update
    return {"name": name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def discard_draft(name: str) -> dict:
    """Applicant deletes their own in-progress Draft. Submitted applications are
    permanent and must be withdrawn instead."""
    _require_login()
    app = _own_application(name)
    if app.status != "Draft":
        frappe.throw(_("Only a draft application can be discarded."))
    frappe.delete_doc("Partner Job Application", name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def get_partner_types() -> list[str]:
    """Active Partner Type names for the job-board filter. Exposed via the API
    because portal users (students/alumni) don't hold read permission on the
    Partner Type doctype directly."""
    _require_login()
    return frappe.get_all(
        "Partner Type", filters={"is_active": 1}, pluck="name", order_by="name asc"
    )


@frappe.whitelist()
def get_job_opening(name: str) -> dict:
    """Full detail for one published opening, plus eligibility flags driving the
    Apply button (eligible / already_applied / can_apply) and the Web Form route."""
    _require_login()

    if not frappe.db.exists("Partner Job Opening", name):
        frappe.throw(_("Job opening not found."))
    doc = frappe.get_doc("Partner Job Opening", name)
    if not doc.publish:
        frappe.throw(_("This job opening is not published."), frappe.PermissionError)

    org = (
        frappe.db.get_value(
            "Partner Organization",
            doc.partner_org,
            [
                "organization_name",
                "website",
                "image",
                "about_us",
                "doctrinal_statement",
                "city",
                "state",
            ],
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
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "pincode",
                    "country",
                    "ministry_setting",
                    "congregation_size",
                ],
                as_dict=True,
            )
            or {}
        )

    is_student, is_alumni = _audience()
    person = _current_person()
    existing_status = (
        frappe.db.get_value(
            "Partner Job Application",
            {"job_opening": doc.name, "applicant": person},
            "status",
        )
        if person
        else None
    )
    submitted = bool(existing_status and existing_status != "Draft")
    has_draft = existing_status == "Draft"
    eligible = _is_visible(doc.as_dict(), is_student, is_alumni)
    # Can still act (apply or continue a draft) as long as not already submitted.
    can_apply = bool(doc.status == "Open" and eligible and not submitted)

    # Application count is shown only when the opening opts into publishing it, and
    # only counts submitted applications (Drafts are private to the applicant).
    show_application_count = bool(doc.publish_applications_received)
    application_count = (
        frappe.db.count(
            "Partner Job Application",
            {"job_opening": doc.name, "status": ["!=", "Draft"]},
        )
        if show_application_count
        else None
    )

    return {
        "name": doc.name,
        "job_title": doc.job_title,
        "status": doc.status,
        "employment_type": doc.employment_type,
        "position_type": doc.position_type,
        "ministry_setting": doc.ministry_setting,
        "require_doctrinal_alignment": bool(doc.require_doctrinal_alignment),
        "posted_on": doc.posted_on,
        "closes_on": doc.closes_on,
        "vacancies": doc.vacancies,
        "planned_vacancies": doc.planned_vacancies,
        "description": doc.description,
        "qualifications": doc.qualifications,
        "skills": [s.skill_tag for s in doc.skills],
        "partner_org": doc.partner_org,
        "organization": org,
        "location": location,
        "eligible": eligible,
        "already_applied": submitted,
        "has_draft": has_draft,
        "can_apply": can_apply,
        "show_application_count": show_application_count,
        "application_count": application_count,
    }


@frappe.whitelist()
def get_apply_context(name: str) -> dict:
    """Everything the in-portal apply page needs: the opening header, the
    applicant's prefilled identity, and their stored résumé default."""
    detail = get_job_opening(name)
    person = _current_person()
    applicant = {}
    if person:
        applicant = (
            frappe.db.get_value(
                "Person",
                person,
                [
                    "full_name",
                    "primary_email",
                    "primary_mobile",
                    "resume",
                    "preferred_application_email",
                    "preferred_application_phone",
                ],
                as_dict=True,
            )
            or {}
        )
        if applicant.get("resume"):
            applicant["resume_name"] = (
                frappe.db.get_value(
                    "File", {"file_url": applicant["resume"]}, "file_name"
                )
                or applicant["resume"].rsplit("/", 1)[-1]
            )
    # Load an in-progress draft (if any) so the page resumes where they left off.
    draft = None
    if person:
        existing = frappe.db.get_value(
            "Partner Job Application",
            {"job_opening": name, "applicant": person},
            [
                "name",
                "status",
                "cover_letter",
                "resume",
                "doctrinal_alignment",
                "alignment_explanation",
            ],
            as_dict=True,
        )
        if existing and existing.status == "Draft":
            draft = existing

    return {
        "opening": {
            "name": detail["name"],
            "job_title": detail["job_title"],
            "position_type": detail["position_type"],
            "organization": detail["organization"],
            "status": detail["status"],
            "require_doctrinal_alignment": detail["require_doctrinal_alignment"],
            "doctrinal_statement": detail["organization"].get("doctrinal_statement"),
            "can_apply": detail["can_apply"],
            "already_applied": detail["already_applied"],
            "has_draft": detail["has_draft"],
            "eligible": detail["eligible"],
        },
        "applicant": applicant,
        "draft": draft,
        "has_person": bool(person),
    }


@frappe.whitelist(methods=["POST"])
def apply_to_job(
    job_opening: str,
    cover_letter: str = "",
    resume: str = "",
    preferred_email: str | None = None,
    preferred_phone: str | None = None,
    doctrinal_alignment: str = "",
    alignment_explanation: str = "",
    submit: str = "",
) -> dict:
    """Save or submit a Partner Job Application for the logged-in user.

    `submit` falsy → saved as a Draft (incomplete is fine); truthy → moves to Open,
    entering the partner's queue, and the controller enforces the cover-letter and
    doctrinal-response requirements. Re-saving reuses the existing Draft, so there's
    never a duplicate. This whitelisted endpoint is the permission boundary (portal
    applicants don't hold create rights on the doctype).

    Preferred application contact is saved back to the applicant's Person first
    (blank clears it, falling back to the primary), so the controller snapshots the
    right channel onto the application."""
    _require_login()
    person = _current_person()
    if not person:
        frappe.throw(
            _("Your profile isn't set up to apply yet. Please contact the registrar.")
        )

    do_submit = str(submit).strip().lower() in ("1", "true", "yes")

    if preferred_email is not None or preferred_phone is not None:
        frappe.db.set_value(
            "Person",
            person,
            {
                "preferred_application_email": (preferred_email or "").strip() or None,
                "preferred_application_phone": (preferred_phone or "").strip() or None,
            },
        )

    # Resume an existing Draft if there is one; a submitted application is final.
    existing = frappe.db.get_value(
        "Partner Job Application",
        {"job_opening": job_opening, "applicant": person},
        ["name", "status"],
        as_dict=True,
    )
    if existing and existing.status != "Draft":
        frappe.throw(_("You have already applied to this opening."))

    if existing:
        doc = frappe.get_doc("Partner Job Application", existing.name)
    else:
        doc = frappe.new_doc("Partner Job Application")
        doc.job_opening = job_opening
        doc.applicant = person

    doc.cover_letter = cover_letter or None
    doc.resume = resume or None
    doc.doctrinal_alignment = doctrinal_alignment or None
    doc.alignment_explanation = alignment_explanation or None
    doc.status = "Open" if do_submit else "Draft"
    doc.save(ignore_permissions=True)
    # The application controller attaches the résumé File to the application on
    # submit so partner reviewers inherit read access (ADR 043).

    return {"name": doc.name, "status": doc.status, "submitted": do_submit}
