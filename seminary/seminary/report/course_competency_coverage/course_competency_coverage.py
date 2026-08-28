# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Course Competency Coverage (ADR 065).

A course is competency-based because its grading scale says so, but it is only
*assessable* once it carries competencies and those competencies say how each
dimension is demonstrated. Nothing forces the second half: a course can sit on a
competency-based scale with no competencies at all, and the gap only shows up
when an instructor opens the competency gradebook and finds it empty.

This report is that check, one line per course. It is deliberately not limited
to competency-based scales: a course that has competencies on an ordinary scale
is just as broken, in the other direction, and would be invisible if the report
only looked where competencies are expected.
"""

import frappe
from frappe import _

CBE = "Competency-based education"


def execute(filters=None):
    filters = filters or {}
    return columns(), rows(filters)


def columns():
    return [
        {
            "label": _("Course"),
            "fieldname": "course",
            "fieldtype": "Link",
            "options": "Course",
            "width": 150,
        },
        {
            "label": _("Course Name"),
            "fieldname": "course_name",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Code"),
            "fieldname": "coursecode",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Academic Unit"),
            "fieldname": "academic_unit",
            "fieldtype": "Link",
            "options": "Academic Unit",
            "width": 150,
        },
        {
            "label": _("Grading Scale"),
            "fieldname": "grading_scale",
            "fieldtype": "Link",
            "options": "Grading Scale",
            "width": 160,
        },
        {
            "label": _("Scale Type"),
            "fieldname": "scale_type",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Active"),
            "fieldname": "active_competencies",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Inactive"),
            "fieldname": "inactive_competencies",
            "fieldtype": "Int",
            "width": 80,
        },
        {
            "label": _("Scale Dimensions"),
            "fieldname": "scale_dimensions",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": _("Incomplete"),
            "fieldname": "incomplete_competencies",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Retired"),
            "fieldname": "disabled",
            "fieldtype": "Check",
            "width": 70,
        },
        {"label": _("Issue"), "fieldname": "issue", "fieldtype": "Data", "width": 340},
    ]


def _scales():
    """Every grading scale's type and dimension count, fetched once."""
    scales = {
        s.name: {"type": s.grscale_type, "dimensions": set()}
        for s in frappe.get_all("Grading Scale", fields=["name", "grscale_type"])
    }
    for d in frappe.get_all(
        "Grading Scale Dimensions",
        fields=["parent", "dimension_code"],
        filters={"parenttype": "Grading Scale"},
    ):
        if d.parent in scales:
            scales[d.parent]["dimensions"].add(d.dimension_code)
    return scales


def _course_filters(filters):
    cf = {}
    if filters.get("course"):
        cf["name"] = filters["course"]
    if filters.get("academic_unit"):
        cf["academic_unit"] = filters["academic_unit"]
    if filters.get("grading_scale"):
        cf["default_grading_scale"] = filters["grading_scale"]
    if not filters.get("include_retired"):
        cf["disabled"] = 0
    return cf


def _competencies(course_names):
    """Competencies of the given courses, with the dimension codes each covers."""
    by_course = {}
    if not course_names:
        return by_course

    comps = frappe.get_all(
        "Course Competency",
        filters={"course": ("in", course_names)},
        fields=["name", "course", "competency_name", "is_active"],
        order_by="course asc, sequence asc, competency_name asc",
    )
    if not comps:
        return by_course

    covered = {}
    for d in frappe.get_all(
        "Course Competency Dimension",
        filters={"parent": ("in", [c.name for c in comps])},
        fields=["parent", "dimension_code"],
    ):
        covered.setdefault(d.parent, set()).add(d.dimension_code)

    for c in comps:
        c.dimension_codes = covered.get(c.name, set())
        by_course.setdefault(c.course, []).append(c)
    return by_course


def rows(filters):
    courses = frappe.get_all(
        "Course",
        filters=_course_filters(filters),
        fields=[
            "name",
            "course_name",
            "coursecode",
            "academic_unit",
            "default_grading_scale",
            "disabled",
        ],
        order_by="academic_unit asc, course_name asc",
    )
    if not courses:
        return []

    scales = _scales()
    by_course = _competencies([c.name for c in courses])

    out = []
    for course in courses:
        scale = scales.get(course.default_grading_scale) or {}
        scale_type = scale.get("type") or ""
        scale_dimensions = scale.get("dimensions") or set()
        comps = by_course.get(course.name, [])
        is_cbe = scale_type == CBE

        # A course with neither a competency-based scale nor any competency has
        # nothing to say here. Everything else is either configured or
        # misconfigured, and both are worth a line.
        if not is_cbe and not comps and not filters.get("include_all_courses"):
            continue

        active = [c for c in comps if c.is_active]
        # Only active competencies are assessed, so only they can be incomplete.
        incomplete = [c for c in active if scale_dimensions - c.dimension_codes]

        row = {
            "course": course.name,
            "course_name": course.course_name,
            "coursecode": course.coursecode,
            "academic_unit": course.academic_unit,
            "grading_scale": course.default_grading_scale,
            "scale_type": scale_type,
            "active_competencies": len(active),
            "inactive_competencies": len(comps) - len(active),
            "scale_dimensions": len(scale_dimensions),
            "incomplete_competencies": len(incomplete),
            "disabled": course.disabled,
            "issue": _issue(
                course, is_cbe, scale_dimensions, comps, active, incomplete
            ),
        }
        if filters.get("only_issues") and not row["issue"]:
            continue
        out.append(row)
    return out


def _issue(course, is_cbe, scale_dimensions, comps, active, incomplete):
    if not course.default_grading_scale:
        return _("No grading scale on the course")
    if comps and not is_cbe:
        return _(
            "{0} competencies defined but grading scale {1} is not " "competency-based"
        ).format(len(comps), course.default_grading_scale)
    if not is_cbe:
        return ""
    if not scale_dimensions:
        return _("Grading scale {0} defines no dimensions").format(
            course.default_grading_scale
        )
    if not comps:
        return _("Competency-based scale with no competencies")
    if not active:
        return _("All {0} competencies are inactive").format(len(comps))
    if incomplete:
        names = ", ".join(c.competency_name for c in incomplete[:3])
        if len(incomplete) > 3:
            names = _("{0} and {1} more").format(names, len(incomplete) - 3)
        return _("Missing dimension descriptors: {0}").format(names)
    return ""
