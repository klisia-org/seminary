"""Who is staff (decisions/085).

`Person.is_staff` is derived, never typed: true when the person's user is
enabled and holds at least one staff role. Seminary's roles are below; other
apps add theirs through a `staff_roles` hook. Student, Alumni, Partner and
Cohort Participant are not staff roles, so an employee who is also an alumnus
is staff and a student is not.

When a person's flag changes, every `person_staff_changed` hook is called with
(person, is_staff), so an app can react to someone leaving without polling.
"""

import frappe

SEMINARY_STAFF_ROLES = (
    "Instructor",
    "Program Chair",
    "Registrar",
    "Seminary Manager",
    "System Manager",
)


def staff_roles() -> set:
    roles = set(SEMINARY_STAFF_ROLES)
    for role in frappe.get_hooks("staff_roles") or []:
        roles.add(role)
    return roles


def staff_users() -> set:
    """Enabled users holding a staff role."""
    holders = set(
        frappe.get_all(
            "Has Role",
            filters={"role": ("in", list(staff_roles())), "parenttype": "User"},
            pluck="parent",
        )
    )
    if not holders:
        return set()
    return set(
        frappe.get_all(
            "User",
            filters={"name": ("in", list(holders)), "enabled": 1},
            pluck="name",
        )
    ) - {"Administrator", "Guest"}


def is_staff_user(user) -> bool:
    if not user or user in ("Administrator", "Guest"):
        return False
    if not frappe.db.get_value("User", user, "enabled"):
        return False
    return bool(staff_roles() & set(frappe.get_roles(user)))


def refresh(persons=None) -> int:
    """Recompute the flag for the given persons (all with a user, by default).
    Writes only the rows that change, and announces each change. Returns the
    number changed."""
    filters = (
        {"user": ("is", "set")} if persons is None else {"name": ("in", list(persons))}
    )
    rows = frappe.get_all(
        "Person", filters=filters, fields=["name", "user", "is_staff"]
    )
    staff = staff_users()
    changed = 0
    for row in rows:
        value = 1 if row.user and row.user in staff else 0
        if bool(row.is_staff) == bool(value):
            continue
        frappe.db.set_value(
            "Person", row.name, "is_staff", value, update_modified=False
        )
        _announce(row.name, value)
        changed += 1
    return changed


def _announce(person, value):
    for method in frappe.get_hooks("person_staff_changed") or []:
        try:
            frappe.get_attr(method)(person, bool(value))
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"person_staff_changed failed: {method}"
            )


def on_user_update(doc, method=None):
    """A user's roles or enabled state changed: refresh the persons on it."""
    persons = frappe.get_all("Person", filters={"user": doc.name}, pluck="name")
    if persons:
        refresh(persons)


def on_person_update(doc, method=None):
    if doc.has_value_changed("user") or doc.is_new():
        refresh([doc.name])


def daily():
    """Roles also change without a User save (role profiles, direct grants), so
    a daily pass catches what the events missed."""
    changed = refresh()
    frappe.db.commit()
    return changed
