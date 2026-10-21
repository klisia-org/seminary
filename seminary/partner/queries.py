# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Link-field search queries for the partner subsystem.

These back `frm.set_query(..., {query: ...})` calls so a link field only offers
records scoped to the right organization (e.g. a placement's site supervisor must
be a contact of that organization).
"""

import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def org_contact_person_query(doctype, txt, searchfield, start, page_len, filters):
    """Persons who are contacts of the given Partner Organization. Returns
    nothing until an organization is chosen.

    filters: `partner_org`; `supervisors_only` (default on: a site supervisor
    must be able to supervise); `active_only` (only Active contacts, e.g. an
    organisation's giving contacts in koinonia)."""
    filters = filters or {}
    org = filters.get("partner_org")
    if not org:
        return []
    return frappe.db.sql(
        """
        SELECT p.name, p.full_name
        FROM `tabPerson` p
        WHERE p.name IN (
            SELECT pc.person FROM `tabPartner Contact` pc
            WHERE pc.parenttype = 'Partner Organization'
              AND pc.parent = %(org)s
              AND pc.person IS NOT NULL
              AND (%(supervisors_only)s = 0 OR pc.can_supervise = 1)
              AND (%(active_only)s = 0 OR pc.relationship_status = 'Active')
        )
        AND (p.full_name LIKE %(txt)s OR p.name LIKE %(txt)s)
        ORDER BY p.full_name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "org": org,
            "supervisors_only": 1 if filters.get("supervisors_only", 1) else 0,
            "active_only": 1 if filters.get("active_only") else 0,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
