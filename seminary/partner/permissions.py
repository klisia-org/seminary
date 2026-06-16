"""Record-level scoping for the partner portal (ADR 053).

A user holding only the `Partner` role may access just their own organization's
records. Resolution: a `Partner Contact` row with `portal_user` = the user and
`portal_access` = 1; its `parent` is the org. Staff roles bypass entirely; a
partner with no resolvable org sees nothing (`1=0`).

These hooks defend Desk / `get_list` access; the portal API in seminary.partner.portal
is the primary path and scopes every query itself.
"""

import frappe

RESTRICTED_ROLE = "Partner"
STAFF_BYPASS = {"System Manager", "Seminary Manager", "Registrar", "Program Chair"}


def my_partner_org(user=None):
    """The Partner Organization a portal user belongs to, or None."""
    if not user:
        user = frappe.session.user
    return frappe.db.get_value(
        "Partner Contact", {"portal_user": user, "portal_access": 1}, "parent"
    )


def _should_restrict(user):
    if not user or user == "Administrator":
        return False
    roles = set(frappe.get_roles(user))
    if roles & STAFF_BYPASS:
        return False
    return RESTRICTED_ROLE in roles


def _conditions(user, table, field):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return ""
    org = my_partner_org(user)
    if not org:
        return "1=0"
    return f"(`tab{table}`.`{field}` = {frappe.db.escape(org)})"


def _has(doc, user, field):
    if not user:
        user = frappe.session.user
    if not _should_restrict(user):
        return True
    org = my_partner_org(user)
    return bool(org) and getattr(doc, field, None) == org


# --- Partner Organization (scoped by its own name) ---
def org_query(user=None):
    return _conditions(user, "Partner Organization", "name")


def org_has(doc, ptype=None, user=None):
    return _has(doc, user, "name")


# --- Partner Organization Location ---
def location_query(user=None):
    return _conditions(user, "Partner Organization Location", "partner_org")


def location_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


# --- Partner Job Opening ---
def opening_query(user=None):
    return _conditions(user, "Partner Job Opening", "partner_org")


def opening_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


# --- Partner Job Application (carries partner_org, fetched from the opening) ---
def application_query(user=None):
    return _conditions(user, "Partner Job Application", "partner_org")


def application_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


# --- Internship subsystem (every doctype carries partner_org, ADR 054) ---
def internship_position_query(user=None):
    return _conditions(user, "Internship Position", "partner_org")


def internship_position_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


def internship_application_query(user=None):
    return _conditions(user, "Internship Application", "partner_org")


def internship_application_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


def internship_placement_query(user=None):
    return _conditions(user, "Internship Placement", "partner_org")


def internship_placement_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


def internship_hours_log_query(user=None):
    return _conditions(user, "Internship Hours Log", "partner_org")


def internship_hours_log_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


def internship_requirement_query(user=None):
    return _conditions(user, "Internship Requirement", "partner_org")


def internship_requirement_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")


def internship_supervisor_evaluation_query(user=None):
    return _conditions(user, "Internship Supervisor Evaluation", "partner_org")


def internship_supervisor_evaluation_has(doc, ptype=None, user=None):
    return _has(doc, user, "partner_org")
