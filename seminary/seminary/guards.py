"""Role gates shared by seminary's whitelisted endpoints (privatedocs p006 §2.0).

Three gates wrap the role sets that already exist in ``api.py`` so doctype
controllers can import them without importing ``api.py``. Each raises
``frappe.PermissionError``. ``Administrator`` passes every gate through its
roles; no new roles are introduced.
"""

import frappe
from frappe import _

# Who may grade, record attendance, and read gradebooks (api._GRADER_ROLES).
GRADER_ROLES = {"Instructor", "Program Chair", "Seminary Manager", "System Manager"}
# Who may add/delete chapters and lessons (api.OUTLINE_EDIT_ROLES).
OUTLINE_EDIT_ROLES = {
    "Instructor",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
}
# Who may act on enrollment, standing and separation (api.GRADE_SEND_ROLES minus Instructor).
REGISTRAR_ROLES = {"Program Chair", "Registrar", "Seminary Manager", "System Manager"}


def _roles(user=None):
    return set(frappe.get_roles(user or frappe.session.user))


def registrar_has_academic_records() -> bool:
    """Seminary Settings switch: may the Registrar record attendance and open
    gradebooks? On by default; a school where a student acts as registrar turns
    it off (p006 §2.4)."""
    value = frappe.db.get_single_value(
        "Seminary Settings", "registrar_academic_records"
    )
    # A Single that was never saved after the field was added reads None: the
    # field's default (on) applies until an administrator turns it off.
    return True if value is None else bool(value)


def is_grader(user=None, include_registrar=False) -> bool:
    roles = _roles(user)
    if roles & GRADER_ROLES:
        return True
    if include_registrar and "Registrar" in roles and registrar_has_academic_records():
        return True
    return False


def require_grader(include_registrar=False):
    if not is_grader(include_registrar=include_registrar):
        frappe.throw(_("Only teaching staff can do this."), frappe.PermissionError)


def require_outline_editor():
    if not _roles() & OUTLINE_EDIT_ROLES:
        frappe.throw(
            _("Only teaching staff can edit the course outline."),
            frappe.PermissionError,
        )


def require_registrar():
    if not _roles() & REGISTRAR_ROLES:
        frappe.throw(
            _("Only the registrar or academic administration can do this."),
            frappe.PermissionError,
        )
