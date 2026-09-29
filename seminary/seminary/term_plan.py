# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""What a Time-based student should be taking in a term (ADR 083).

A Time-based program states each term's courses through `Program Course.course_term`,
and an emphasis adds its own through `Program Track Courses.term`. A student's term
index is `Program Enrollment.current_std_term`. Bulk Course Enrollment and the
enrollment check report both read the plan from here, so they cannot disagree.
"""

import frappe


def term_start(academic_term):
    return frappe.db.get_value("Academic Term", academic_term, "term_start_date")


def time_based_enrollments(
    academic_term, programs=None, student_term=None, intake_term=None, names=None
):
    """Active Time-based Program Enrollments that belong in `academic_term`.

    A student whose intake term starts after `academic_term` is left out: they
    have not started yet, so nothing is expected of them in that term.
    """
    conditions = [
        "pe.docstatus = 1",
        "pe.pgmenrol_active = 1",
        "p.program_type = 'Time-based'",
        "(intake.term_start_date IS NULL OR %(start)s IS NULL"
        " OR intake.term_start_date <= %(start)s)",
    ]
    params = {"start": term_start(academic_term)}
    if programs:
        conditions.append("pe.program IN %(programs)s")
        params["programs"] = tuple(programs)
    if student_term:
        conditions.append("pe.current_std_term = %(student_term)s")
        params["student_term"] = int(student_term)
    if intake_term:
        conditions.append("pe.academic_term = %(intake_term)s")
        params["intake_term"] = intake_term
    if names is not None:
        if not names:
            return []
        conditions.append("pe.name IN %(names)s")
        params["names"] = tuple(names)
    return frappe.db.sql(
        f"""SELECT pe.name, pe.student, pe.student_name, pe.program,
                   pe.current_std_term, pe.academic_term AS intake_term
            FROM `tabProgram Enrollment` pe
            INNER JOIN `tabProgram` p ON p.name = pe.program
            LEFT JOIN `tabAcademic Term` intake ON intake.name = pe.academic_term
            WHERE {" AND ".join(conditions)}
            ORDER BY pe.program, pe.current_std_term, pe.student_name""",  # nosec B608 -- clauses are constants from this function
        params,
        as_dict=True,
    )


def expected_courses(pe):
    """[{course, course_name, track}] the plan expects of `pe` at its term index:
    the program's courses for that term (track None) plus those of its active
    emphases (track = the emphasis). A course in both counts once, as the
    program's."""
    term = pe.current_std_term or 0
    if not term:
        return []
    rows = frappe.get_all(
        "Program Course",
        filters={"parent": pe.program, "course_term": term, "disabled": 0},
        fields=["course", "course_name"],
        order_by="idx",
    )
    for r in rows:
        r.track = None
    tracks = frappe.get_all(
        "Program Enrollment Emphasis",
        filters={
            "parent": pe.name,
            "parenttype": "Program Enrollment",
            "status": "Active",
        },
        pluck="emphasis_track",
    )
    if tracks:
        for t in frappe.get_all(
            "Program Track Courses",
            filters={
                "parent": pe.program,
                "parenttype": "Program",
                "program_track": ["in", tracks],
                "term": term,
            },
            fields=["program_track_course", "program_track"],
            order_by="idx",
        ):
            rows.append(
                frappe._dict(
                    course=t.program_track_course,
                    course_name=None,
                    track=t.program_track,
                )
            )
    seen, out = set(), []
    for r in rows:
        if r.course in seen:
            continue
        seen.add(r.course)
        r.course_name = r.course_name or frappe.db.get_value(
            "Course", r.course, "course_name"
        )
        out.append(r)
    return out


def active_holds(student):
    """Types of the student's active holds, e.g. ['Financial']."""
    return frappe.get_all(
        "Student Hold",
        filters={
            "parent": student,
            "parenttype": "Student",
            "parentfield": "student_holds",
            "is_active": 1,
        },
        pluck="hold_type",
    )
