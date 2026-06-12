"""Scoped read access to Communication Log for portal users (ADR 043).

Portal roles get a permlevel-0 read DocPerm on Communication Log purely so
Frappe's native /private/files ACL will authorize them for files attached to
their own logs (the inbox listing itself uses frappe.get_all, which ignores
permissions). These two hooks narrow that capability to the rows the user
actually owns — the message was sent TO them (person) or BY them (triggered_by).

Staff (Seminary Manager / Registrar / Program Chair / System Manager) and
Administrator are unrestricted. A restricted user with no linked Person can
still see their Sent box (triggered_by). The query condition must NEVER resolve
to empty for a restricted user — that is the entire enumeration boundary.
"""

import frappe

from seminary.seminary.person import find_person

# Roles whose holders may only read their own Communication Logs.
PORTAL_ROLES = {"Student", "Alumni", "Instructor"}
# Roles that bypass the restriction entirely (full ledger visibility).
STAFF_BYPASS = {"Seminary Manager", "Registrar", "Program Chair", "System Manager"}


def _should_restrict(user):
    if not user or user == "Administrator":
        return False
    roles = set(frappe.get_roles(user))
    if roles & STAFF_BYPASS:
        return False
    return bool(roles & PORTAL_ROLES)


def has_permission(doc, ptype=None, user=None):
    """Deny-only single-doc gate (also drives the private-file download check
    via File.has_permission -> ref_doc.has_permission('read'))."""
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return True
    if getattr(doc, "triggered_by", None) == user:
        return True
    person = find_person(user=user)
    return bool(person) and getattr(doc, "person", None) == person


def get_permission_query_conditions(user=None):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return ""
    u = frappe.db.escape(user)
    person = find_person(user=user)
    if not person:
        # Never empty for a restricted user — fall back to the Sent box only.
        return f"(`tabCommunication Log`.triggered_by = {u})"
    p = frappe.db.escape(person)
    return (
        f"(`tabCommunication Log`.person = {p} "
        f"OR `tabCommunication Log`.triggered_by = {u})"
    )
