import frappe
from frappe import _
from frappe.utils import getdate, today

from seminary.seminary.api import get_program_audit

DIRECTORY_FIELDS = (
    "name",
    "full_name",
    "image",
    "program_completed",
    "class_year",
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
    if program:
        filters.append(["program_completed", "=", program])
    if class_year:
        filters.append(["class_year", "=", int(class_year)])

    or_filters = None
    if query:
        like = f"%{query}%"
        or_filters = [
            ["full_name", "like", like],
            ["current_role", "like", like],
            ["current_organization", "like", like],
            ["city", "like", like],
        ]

    return frappe.get_all(
        "Alumni Profile",
        fields=list(DIRECTORY_FIELDS),
        filters=filters,
        or_filters=or_filters,
        limit_page_length=min(int(limit), 100),
        limit_start=int(offset),
        order_by="class_year desc, full_name asc",
    )


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
    if "Academics User" not in frappe.get_roles() and not frappe.has_permission(
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

    existing = frappe.db.get_value("Alumni Profile", {"user": student.user}, "name")
    if existing:
        return {"name": existing, "already_existed": True}

    if not pe.date_of_conclusion:
        pe.db_set("date_of_conclusion", today(), update_modified=True)

    conclusion_date = getdate(pe.date_of_conclusion)

    profile = frappe.get_doc(
        {
            "doctype": "Alumni Profile",
            "user": student.user,
            "email": student.user,
            "full_name": student.student_name,
            "student": student.name,
            "program_completed": pe.program,
            "class_year": conclusion_date.year,
            "graduated_from_enrollment": pe.name,
        }
    )
    profile.insert(ignore_permissions=True)
    profile.db_set("owner", student.user, update_modified=False)

    user_doc = frappe.get_doc("User", student.user)
    user_doc.add_roles("Alumni")

    return {"name": profile.name, "already_existed": False}


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
