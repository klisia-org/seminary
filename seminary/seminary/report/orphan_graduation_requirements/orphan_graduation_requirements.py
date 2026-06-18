# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Orphan Graduation Requirements (ADR 056).

Lists emphasis-scoped Student Graduation Requirement rows whose scoping
emphasis the student no longer holds (an emphasis was dropped after the
requirement was materialized). These are never auto-removed — registrar
judgement resolves each via the report's Cancel / Waive / Withdraw actions.
"""

import frappe

from seminary.seminary.graduation import emphasis_scope_for_pgr_item


def execute(filters=None):
    columns = [
        {
            "label": "Program Enrollment",
            "fieldname": "program_enrollment",
            "fieldtype": "Link",
            "options": "Program Enrollment",
            "width": 160,
        },
        {
            "label": "Student",
            "fieldname": "student_name",
            "fieldtype": "Data",
            "width": 170,
        },
        {"label": "Program", "fieldname": "program", "fieldtype": "Data", "width": 150},
        {
            "label": "Requirement",
            "fieldname": "requirement_name",
            "fieldtype": "Data",
            "width": 210,
        },
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {
            "label": "Scoped To Emphasis",
            "fieldname": "scoped_to",
            "fieldtype": "Data",
            "width": 230,
        },
        {
            "label": "Linked Document",
            "fieldname": "linked_doc",
            "fieldtype": "Dynamic Link",
            "options": "link_doctype",
            "width": 180,
        },
        {
            "label": "link_doctype",
            "fieldname": "link_doctype",
            "fieldtype": "Data",
            "hidden": 1,
        },
        {"label": "SGR", "fieldname": "sgr", "fieldtype": "Data", "hidden": 1},
    ]

    sgrs = frappe.get_all(
        "Student Graduation Requirement",
        filters={
            "emphasis_scoped": 1,
            "parenttype": "Program Enrollment",
            "status": ["!=", "Waived"],
        },
        fields=[
            "name",
            "parent",
            "requirement_name",
            "status",
            "pgr_item",
            "link_doctype",
            "linked_doc",
        ],
    )
    if not sgrs:
        return columns, []

    pe_names = list({s.parent for s in sgrs})
    pe_meta = {
        pe.name: pe
        for pe in frappe.get_all(
            "Program Enrollment",
            filters={"name": ["in", pe_names]},
            fields=["name", "student_name", "program"],
        )
    }

    # Active/Completed emphases per PE, excluding advisory-only tracks.
    emph_rows = frappe.get_all(
        "Program Enrollment Emphasis",
        filters={"parent": ["in", pe_names], "status": ["in", ("Active", "Completed")]},
        fields=["parent", "emphasis_track"],
    )
    all_tracks = {r.emphasis_track for r in emph_rows if r.emphasis_track}
    advisory = (
        set(
            frappe.get_all(
                "Program Track",
                filters={"name": ["in", list(all_tracks)], "advisory_only": 1},
                pluck="name",
            )
        )
        if all_tracks
        else set()
    )
    held_by_pe = {}
    for r in emph_rows:
        if r.emphasis_track and r.emphasis_track not in advisory:
            held_by_pe.setdefault(r.parent, set()).add(r.emphasis_track)

    scope_cache = {}
    rows = []
    for s in sgrs:
        if s.pgr_item not in scope_cache:
            scope_cache[s.pgr_item] = set(emphasis_scope_for_pgr_item(s.pgr_item))
        scope = scope_cache[s.pgr_item]
        if not scope:
            continue  # no policy-level scope (stale flag) — not an orphan
        if scope & held_by_pe.get(s.parent, set()):
            continue  # still applicable
        meta = pe_meta.get(s.parent)
        rows.append(
            {
                "program_enrollment": s.parent,
                "student_name": meta.student_name if meta else None,
                "program": meta.program if meta else None,
                "requirement_name": s.requirement_name,
                "status": s.status,
                "scoped_to": ", ".join(sorted(scope)),
                "linked_doc": s.linked_doc,
                "link_doctype": s.link_doctype,
                "sgr": s.name,
            }
        )
    return columns, rows
