import frappe
from frappe import _
from frappe.utils import getdate, today

from seminary.seminary.api import get_program_audit

DIRECTORY_FIELDS = (
    "name",
    "full_name",
    "image",
    "current_role",
    "current_organization",
    "linkedin_url",
    "city",
    "country",
)

PROFILE_EDITABLE_FIELDS = (
    "full_name",
    "current_role",
    "current_organization",
    "linkedin_url",
    "city",
    "country",
    "bio",
    "show_in_directory",
)


@frappe.whitelist()
def directory_search(
    query: str = "",
    program: str = "",
    class_year: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    if "Alumni" not in frappe.get_roles():
        frappe.throw(
            _("You do not have access to the alumni directory."), frappe.PermissionError
        )

    filters: list = [
        ["enabled", "=", 1],
        ["show_in_directory", "=", 1],
    ]
    # Completed programs are rows now (ADR 069), so the program and class-year
    # filters reach through the child table. Frappe's `[child_doctype, field,
    # op, value]` filter form does that join for us and keeps permissions.
    if program:
        filters.append(["Alumni Graduation", "program", "=", program])
    if class_year:
        filters.append(["Alumni Graduation", "class_year", "=", int(class_year)])

    or_filters = None
    if query:
        like = f"%{query}%"
        or_filters = [
            ["full_name", "like", like],
            ["current_role", "like", like],
            ["current_organization", "like", like],
            ["city", "like", like],
        ]

    rows = frappe.get_all(
        "Alumni Profile",
        fields=list(DIRECTORY_FIELDS),
        filters=filters,
        or_filters=or_filters,
        limit_page_length=min(int(limit), 100),
        limit_start=int(offset),
        # Ordered by name, not by class year. A person can hold several
        # graduations, so "their class year" is no longer a single sortable
        # value — ordering by one of them would silently pick a row.
        order_by="full_name asc",
        distinct=True,
    )
    _attach_graduations(rows)
    return rows


def _attach_graduations(rows):
    """One query for every listed profile's graduations, not one per row."""
    if not rows:
        return
    grads = frappe.get_all(
        "Alumni Graduation",
        filters={
            "parenttype": "Alumni Profile",
            "parent": ("in", [r["name"] for r in rows]),
        },
        fields=["parent", "program", "academic_year", "class_year"],
        order_by="class_year asc",
    )
    by_parent: dict = {}
    for grad in grads:
        by_parent.setdefault(grad.parent, []).append(grad)
    for row in rows:
        row["graduations"] = by_parent.get(row["name"], [])


@frappe.whitelist()
def get_my_profile() -> dict | None:
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)
    name = frappe.db.get_value("Alumni Profile", {"user": frappe.session.user}, "name")
    if not name:
        return None
    doc = frappe.get_doc("Alumni Profile", name)
    return doc.as_dict()


@frappe.whitelist()
def mark_as_alumni(program_enrollment: str) -> dict:
    staff_roles = {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}
    if not (staff_roles & set(frappe.get_roles())) and not frappe.has_permission(
        "Alumni Profile", "create"
    ):
        frappe.throw(
            _("Not permitted to mark students as alumni."), frappe.PermissionError
        )

    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    if pe.docstatus != 1:
        frappe.throw(
            _("Program Enrollment must be submitted before transitioning to alumni.")
        )

    if frappe.db.get_value("Program", pe.program, "is_ongoing"):
        frappe.throw(_("Ongoing programs do not transition to alumni status."))

    audit = get_program_audit(program_enrollment=program_enrollment)
    if not audit.get("graduation_eligible"):
        frappe.throw(
            _("Student is not yet eligible for graduation per the program audit.")
        )

    student = frappe.get_doc("Student", pe.student)
    if not student.user:
        frappe.throw(
            _(
                "Student {0} has no linked User account; cannot create alumni profile."
            ).format(student.name)
        )

    # A person has one Alumni Profile and may graduate more than once, so the
    # second degree is a row on the profile — not a second profile, and not a
    # silent no-op. This used to return here on the existing profile, which
    # dropped the second graduation entirely *and* skipped the
    # `date_of_conclusion` stamp below, because the return preceded it (ADR 069).
    if not pe.date_of_conclusion:
        pe.db_set("date_of_conclusion", today(), update_modified=True)
        pe.reload()

    conclusion_date = getdate(pe.date_of_conclusion)
    existing = frappe.db.get_value("Alumni Profile", {"person": student.person})

    if existing:
        profile = frappe.get_doc("Alumni Profile", existing)
        already = profile.record_graduation(pe, conclusion_date)
        if not already:
            profile.save(ignore_permissions=True)
    else:
        # Person first (ADR 068 §1): the graduate already has one — this is the
        # same human, not a new identity. `email` and `full_name` are
        # `fetch_from person.*` mirrors, so passing the Student's copies would
        # be writing a mirror of a mirror.
        from seminary.seminary import intake

        profile = intake.make_alumni_profile(
            student.person, user=student.user, student=student.name
        )
        profile.record_graduation(pe, conclusion_date)
        profile.save(ignore_permissions=True)
        profile.db_set("owner", student.user, update_modified=False)

    user_doc = frappe.get_doc("User", student.user)
    user_doc.add_roles("Alumni")

    return {
        "name": profile.name,
        "already_existed": bool(existing),
        "graduations": len(profile.graduations),
    }


@frappe.whitelist()
def update_profile(values: dict) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)

    name = frappe.db.get_value("Alumni Profile", {"user": frappe.session.user}, "name")
    if not name:
        frappe.throw(_("No alumni profile found for current user."))

    doc = frappe.get_doc("Alumni Profile", name)
    for field in PROFILE_EDITABLE_FIELDS:
        if field in values:
            doc.set(field, values[field])
    doc.save(ignore_permissions=True)
    return doc.as_dict()
