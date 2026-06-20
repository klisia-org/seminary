# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Generic faculty capability routing (ADR 059).

One capacity-aware claim/release that replaces the per-subsystem advisor pools.
It reads ``Academic Unit Membership`` rows (and their ``Academic Unit Capability``
children) wired to a given capability ``route`` (a ``Faculty Capability.routes_to``
machine key), generalizing the internship ``claim_advisor_slot`` round-robin.

For an Academic Interdepartment the eligible faculty are resolved **transitively**
from its member units at query time — never copied in.

"Manual entry wins" is the caller's job (auto-assign only when the human field is
blank, e.g. ``internship_application._assign_faculty``); these helpers just claim
and release the capacity counter.
"""

import frappe
from frappe import _

# routes_to machine keys (must match Faculty Capability.routes_to / seeds).
PLACEMENT_EXAMINER_ROUTE = "Placement Examiner"
MANUAL_VERIFICATION_ROUTE = "Manual-Verification Verifier"
THESIS_CP_ADVISOR_ROUTE = "Thesis/CP Advisor"

# Roles that see every unit's worklist (mirrors utils.COURSE_FULL_ACCESS_ROLES).
FACULTY_FULL_ACCESS_ROLES = {
    "Program Chair",
    "Seminary Manager",
    "System Manager",
    "Administrator",
}


def _resolve_units(unit: str) -> list[str]:
    """The unit itself, plus — for an Academic Interdepartment — its member units
    (transitive resolution, one level)."""
    units = [unit]
    if (
        frappe.db.get_value("Academic Unit", unit, "unit_type")
        == "Academic Interdepartment"
    ):
        units += frappe.get_all(
            "Academic Unit Constituent",
            filters={"parent": unit, "parentfield": "member_units"},
            pluck="member_unit",
        )
    return units


def _remaining(row) -> float:
    """max_students 0 means unlimited — treat as infinite capacity."""
    cap = row.max_students or 0
    return float("inf") if cap == 0 else cap - (row.current_students or 0)


def _capability_rows(unit: str, route: str):
    """Active, instructor-bearing capability rows in ``unit`` (resolved
    transitively) wired to ``route``."""
    units = _resolve_units(unit)
    if not units:
        return []
    return frappe.db.sql(
        """
        SELECT m.name AS membership, m.instructor AS instructor, m.unit AS unit,
               c.name AS cap_row, c.max_students, c.current_students
        FROM `tabAcademic Unit Membership` m
        JOIN `tabAcademic Unit Capability` c ON c.parent = m.name
        JOIN `tabFaculty Capability` fc ON fc.name = c.capability
        WHERE m.unit IN %(units)s
          AND m.is_active = 1
          AND m.instructor IS NOT NULL AND m.instructor != ''
          AND fc.routes_to = %(route)s
          AND fc.is_active = 1
        """,
        {"units": tuple(units), "route": route},
        as_dict=True,
    )


def eligible_instructors(unit: str, route: str) -> list[dict]:
    """Instructors in ``unit`` (transitive for an interdepartment) wired to
    ``route`` and with remaining capacity, most-available first. One entry per
    instructor (their best-remaining capability row)."""
    best: dict[str, frappe._dict] = {}
    for row in _capability_rows(unit, route):
        if _remaining(row) <= 0:
            continue
        current = best.get(row.instructor)
        if current is None or _remaining(row) > _remaining(current):
            best[row.instructor] = row
    rows = sorted(best.values(), key=_remaining, reverse=True)
    return [
        {
            "instructor": r.instructor,
            "membership": r.membership,
            "unit": r.unit,
            "remaining": _remaining(r),
        }
        for r in rows
    ]


def claim_capability(unit: str, route: str) -> str | None:
    """Pick the instructor with the most remaining capacity for ``route``,
    increment their counter, and return the instructor — or None when no one is
    eligible. Caller decides whether to auto-assign (manual entry wins)."""
    candidates = [r for r in _capability_rows(unit, route) if _remaining(r) > 0]
    if not candidates:
        return None
    chosen = max(candidates, key=_remaining)
    frappe.db.set_value(
        "Academic Unit Capability",
        chosen.cap_row,
        "current_students",
        (chosen.current_students or 0) + 1,
    )
    return chosen.instructor


def claim_for(unit: str, route: str, instructor: str) -> bool:
    """Increment a *specific* instructor's capacity counter for (unit, route) —
    used when a human picks the assignee (e.g. a CP advisor) instead of
    round-robin. Returns True if a capacity row was found and incremented; False
    when the instructor holds no such capability (assignment still proceeds, just
    untracked)."""
    if not (unit and instructor):
        return False
    for row in _capability_rows(unit, route):
        if row.instructor == instructor:
            frappe.db.set_value(
                "Academic Unit Capability",
                row.cap_row,
                "current_students",
                (row.current_students or 0) + 1,
            )
            return True
    return False


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def instructors_in_unit(doctype, txt, searchfield, start, page_len, filters):
    """Link-picker query: instructors who are active members of a unit (transitive
    for an interdepartment). Used to scope CP reader pickers to the project's unit."""
    unit = (filters or {}).get("unit")
    units = _resolve_units(unit) if unit else []
    if not units:
        return []
    return frappe.db.sql(
        """
        SELECT DISTINCT m.instructor, i.instructor_name
        FROM `tabAcademic Unit Membership` m
        JOIN `tabInstructor` i ON i.name = m.instructor
        WHERE m.unit IN %(units)s AND m.is_active = 1
          AND m.instructor IS NOT NULL AND m.instructor != ''
          AND (m.instructor LIKE %(txt)s OR i.instructor_name LIKE %(txt)s)
        ORDER BY i.instructor_name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "units": tuple(units),
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def capability_holders(doctype, txt, searchfield, start, page_len, filters):
    """Link-picker query: instructors who hold a capability (filters.route) with
    remaining capacity. Wide net across ALL units by default; pass filters.unit to
    narrow to that unit (transitive). Used for the CP advisor picker — the gate is
    'qualified' (holds the capability), optionally narrowed to the unit."""
    f = filters or {}
    route = f.get("route")
    if not route:
        return []
    unit = f.get("unit")
    params = {"route": route, "txt": f"%{txt}%", "start": start, "page_len": page_len}
    unit_clause = ""
    if unit:
        params["units"] = tuple(_resolve_units(unit))
        unit_clause = "AND m.unit IN %(units)s"
    return frappe.db.sql(
        f"""
        SELECT DISTINCT m.instructor, i.instructor_name
        FROM `tabAcademic Unit Membership` m
        JOIN `tabAcademic Unit Capability` c ON c.parent = m.name
        JOIN `tabFaculty Capability` fc ON fc.name = c.capability
        JOIN `tabInstructor` i ON i.name = m.instructor
        WHERE fc.routes_to = %(route)s AND fc.is_active = 1 AND m.is_active = 1
          AND m.instructor IS NOT NULL AND m.instructor != ''
          AND (c.max_students = 0 OR c.current_students < c.max_students)
          {unit_clause}
          AND (m.instructor LIKE %(txt)s OR i.instructor_name LIKE %(txt)s)
        ORDER BY i.instructor_name
        LIMIT %(start)s, %(page_len)s
        """,
        params,
    )


def holds_capability(instructor: str, route: str, unit: str | None = None) -> bool:
    """True if the instructor holds an active capability for ``route`` — anywhere,
    or within ``unit`` (transitive) when given. The 'qualified' gate for advisor
    assignment."""
    if not instructor:
        return False
    params = {"instructor": instructor, "route": route}
    unit_clause = ""
    if unit:
        params["units"] = tuple(_resolve_units(unit))
        unit_clause = "AND m.unit IN %(units)s"
    return bool(
        frappe.db.sql(
            f"""
            SELECT 1
            FROM `tabAcademic Unit Membership` m
            JOIN `tabAcademic Unit Capability` c ON c.parent = m.name
            JOIN `tabFaculty Capability` fc ON fc.name = c.capability
            WHERE m.instructor = %(instructor)s AND m.is_active = 1
              AND fc.routes_to = %(route)s AND fc.is_active = 1 {unit_clause}
            LIMIT 1
            """,
            params,
        )
    )


def is_member(unit: str, instructor: str) -> bool:
    """True if the instructor has an active membership in the unit (transitive
    for an interdepartment). Used for reader-scope checks."""
    if not (unit and instructor):
        return False
    units = _resolve_units(unit)
    return bool(
        frappe.db.exists(
            "Academic Unit Membership",
            {"unit": ("in", units), "instructor": instructor, "is_active": 1},
        )
    )


def release_capability(unit: str, instructor: str, route: str) -> None:
    """Decrement an instructor's assigned count for ``route`` when an assignment
    is withdrawn or changed."""
    if not (unit and instructor):
        return
    for row in _capability_rows(unit, route):
        if row.instructor == instructor and (row.current_students or 0) > 0:
            frappe.db.set_value(
                "Academic Unit Capability",
                row.cap_row,
                "current_students",
                row.current_students - 1,
            )
            return


# ---------------------------------------------------------------------------
# Authorization & portal worklist (ADR 059 §5, ADR 060)
# ---------------------------------------------------------------------------


def current_instructor(user: str | None = None) -> str | None:
    return frappe.db.get_value(
        "Instructor", {"user": user or frappe.session.user}, "name"
    )


def has_full_access(user: str | None = None) -> bool:
    return bool(
        FACULTY_FULL_ACCESS_ROLES & set(frappe.get_roles(user or frappe.session.user))
    )


def wired_instructors(unit: str, route: str) -> set:
    """Every instructor wired to (unit, route), ignoring capacity (transitive for
    an interdepartment). Used for authorization and worklist routing."""
    return {r.instructor for r in _capability_rows(unit, route)}


def require_capability(unit: str, route: str) -> None:
    """Raise PermissionError unless the caller may perform ``route`` for ``unit``
    — a full-access role, or an instructor wired to the unit with that capability."""
    if has_full_access():
        return
    inst = current_instructor()
    if unit and inst and inst in wired_instructors(unit, route):
        return
    frappe.throw(
        _("You are not authorized to perform this for this academic unit."),
        frappe.PermissionError,
    )


@frappe.whitelist()
def get_unit_roster(unit: str, public: bool = False) -> list:
    """Read-only roster of a unit's faculty and their capabilities — for an
    Academic Interdepartment this is the transitive union of its member units
    (ADR 059). Display only: this never stores or copies any rows.

    With public=True (the website "Our Team" page, ADR 061), people flagged
    `Person.block_from_web` are excluded and each entry is enriched with the
    member's photo, short bio, and whether they chair the unit — for rich cards.
    """
    public = frappe.parse_json(public) if isinstance(public, str) else public
    units = _resolve_units(unit)
    if not units:
        return []

    chair_by_unit = dict(
        frappe.get_all(
            "Academic Unit",
            filters={"name": ("in", units)},
            fields=["name", "chair"],
            as_list=True,
        )
    )

    rows = frappe.db.sql(
        """
        SELECT m.unit, m.person, m.person_name, m.instructor, m.web_order AS member_order,
               i.instructor_name, i.profileimage, i.shortbio, p.image AS person_image,
               p.salutation, p.position, p.web_bio,
               COALESCE(p.block_from_web, 0) AS block_from_web,
               fc.capability_name, fc.routes_to, c.max_students, c.current_students
        FROM `tabAcademic Unit Membership` m
        LEFT JOIN `tabInstructor` i ON i.name = m.instructor
        LEFT JOIN `tabPerson` p ON p.name = m.person
        LEFT JOIN `tabAcademic Unit Capability` c ON c.parent = m.name
        LEFT JOIN `tabFaculty Capability` fc ON fc.name = c.capability
        WHERE m.unit IN %(units)s AND m.is_active = 1
        ORDER BY m.person_name
        """,
        {"units": tuple(units)},
        as_dict=True,
    )
    roster = {}
    for r in rows:
        if public and r.block_from_web:
            continue
        entry = roster.setdefault(
            (r.unit, r.person),
            {
                "unit": r.unit,
                "person": r.person,
                "person_name": r.person_name,
                "salutation": r.salutation,
                "position": r.position,
                "instructor": r.instructor,
                "member_order": r.member_order or 0,
                "photo": r.profileimage or r.person_image,
                "short_bio": r.web_bio or r.shortbio,
                "is_chair": bool(
                    r.instructor and r.instructor == chair_by_unit.get(r.unit)
                ),
                "capabilities": [],
            },
        )
        if r.capability_name:
            entry["capabilities"].append(
                {
                    "capability": r.capability_name,
                    "routes_to": r.routes_to,
                    "max_students": r.max_students,
                    "current_students": r.current_students,
                }
            )

    # Members with an explicit web_order come first in that order; the rest fall
    # back to chair-first, then alphabetical (SQL already ordered by name).
    def _sort_key(e):
        if e["member_order"] > 0:
            return (0, e["member_order"], e["person_name"] or "")
        return (1, 0 if e["is_chair"] else 1, e["person_name"] or "")

    return sorted(roster.values(), key=_sort_key)


def faculty_context(user: str | None = None) -> dict:
    """The caller's faculty footprint for the portal: the units they are wired to
    and the capability routes they hold. Drives which worklist tabs show."""
    inst = current_instructor(user)
    if not inst:
        return {"instructor": None, "units": [], "capabilities": []}
    rows = frappe.db.sql(
        """
        SELECT DISTINCT m.unit, fc.routes_to
        FROM `tabAcademic Unit Membership` m
        JOIN `tabAcademic Unit Capability` c ON c.parent = m.name
        JOIN `tabFaculty Capability` fc ON fc.name = c.capability
        WHERE m.instructor = %s AND m.is_active = 1 AND fc.is_active = 1
        """,
        inst,
        as_dict=True,
    )
    return {
        "instructor": inst,
        "units": sorted({r.unit for r in rows}),
        "capabilities": sorted({r.routes_to for r in rows}),
    }


@frappe.whitelist()
def get_my_faculty_worklist(route: str | None = None) -> dict:
    """Open items routed to the caller: pending Manual-Verification SGRs and
    pending Placement Assessments in the units they are wired to. Full-access
    roles see all. Pass a route to scope to one."""
    full = has_full_access()
    inst = current_instructor()
    out = {}
    if route in (None, MANUAL_VERIFICATION_ROUTE):
        out[MANUAL_VERIFICATION_ROUTE] = _manual_verification_worklist(full, inst)
    if route in (None, PLACEMENT_EXAMINER_ROUTE):
        out[PLACEMENT_EXAMINER_ROUTE] = _placement_worklist(full, inst)
    return out


def _filter_routed(rows, full, inst, route):
    """Keep rows whose owning unit routes to the caller (cache wired sets per unit)."""
    if full:
        return rows
    if not inst:
        return []
    cache, out = {}, []
    for r in rows:
        unit = r.get("unit")
        if unit not in cache:
            cache[unit] = wired_instructors(unit, route)
        if inst in cache[unit]:
            out.append(r)
    return out


def _manual_verification_worklist(full, inst):
    rows = frappe.db.sql(
        """
        SELECT sgr.parent AS program_enrollment, sgr.name AS sgr,
               sgr.requirement_name, sgr.status, gri.academic_unit AS unit,
               gri.default_staff_evidence_required AS staff_evidence_required,
               gri.default_staff_evidence_label AS staff_evidence_label
        FROM `tabStudent Graduation Requirement` sgr
        JOIN `tabGraduation Requirement Item` gri
          ON gri.name = sgr.grad_requirement_item
        WHERE gri.requirement_type = 'Manual Verification'
          AND gri.academic_unit IS NOT NULL AND gri.academic_unit != ''
          AND sgr.status NOT IN ('Fulfilled', 'Waived')
          AND IFNULL(sgr.waived, 0) = 0
        """,
        as_dict=True,
    )
    return _filter_routed(rows, full, inst, MANUAL_VERIFICATION_ROUTE)


def _placement_worklist(full, inst):
    rows = frappe.db.sql(
        """
        SELECT pa.parent AS program_enrollment, pa.assessment,
               pa.status, a.academic_unit AS unit,
               a.default_staff_evidence_required AS staff_evidence_required,
               a.default_staff_evidence_label AS staff_evidence_label
        FROM `tabProgram Enrollment Placement Assessment` pa
        JOIN `tabPlacement Assessment` a ON a.name = pa.assessment
        WHERE a.academic_unit IS NOT NULL AND a.academic_unit != ''
          AND pa.status != 'Scored'
        """,
        as_dict=True,
    )
    return _filter_routed(rows, full, inst, PLACEMENT_EXAMINER_ROUTE)
