"""Resolve recipients for a Seminary Announcement at send time.

All queries are evaluated against live data — recipients are never snapshotted
on the draft; they are computed when the announcement is submitted or previewed.
"""

import json

import frappe


def resolve_recipients(doc) -> list[dict]:
    """Return a de-duplicated list of recipient dicts.

    Each dict has: party_type, party, party_name, email, user.
    """
    term = doc.academic_term
    program_names = [p.program for p in (doc.programs or []) if p.program]
    course_schedules = [
        c.course_schedule for c in (doc.courses or []) if c.course_schedule
    ]
    seen: set[str] = set()
    out: list[dict] = []

    if doc.audience_students_enrolled or course_schedules:
        out.extend(_students_for_term(term, program_names, course_schedules, seen))

    if doc.audience_instructors_teaching:
        out.extend(_instructors_for_term(term, course_schedules, seen))

    if doc.custom_filter_doctype:
        filters_raw = doc.custom_filters or "[]"
        try:
            filters = json.loads(filters_raw)
        except (ValueError, TypeError):
            frappe.throw(f"Custom filter JSON is not valid: {filters_raw}")
        out.extend(
            _from_custom_filter(
                doc.custom_filter_doctype,
                filters,
                doc.custom_email_field or "email",
                seen,
            )
        )

    return out


def _students_for_term(term, program_names, course_schedules, seen):
    """Students with a non-withdrawn Course Enrollment Individual for a Course
    Schedule in the given term. Optionally narrowed by programs or specific
    course schedules.
    """
    params = {"term": term}
    where = [
        "cs.academic_term = %(term)s",
        "cei.docstatus = 1",
        "cei.withdrawn = 0",
    ]

    if course_schedules:
        placeholders = ", ".join([f"%(cs_{i})s" for i in range(len(course_schedules))])
        where.append(f"cs.name IN ({placeholders})")
        for i, cs in enumerate(course_schedules):
            params[f"cs_{i}"] = cs

    if program_names:
        placeholders = ", ".join([f"%(prog_{i})s" for i in range(len(program_names))])
        where.append(f"pe.program IN ({placeholders})")
        for i, prog in enumerate(program_names):
            params[f"prog_{i}"] = prog

    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            s.name AS student,
            s.student_name,
            s.student_email_id AS email,
            s.user
        FROM `tabCourse Enrollment Individual` cei
        JOIN `tabCourse Schedule` cs ON cei.coursesc_ce = cs.name
        JOIN `tabStudent` s ON cei.student_ce = s.name
        JOIN `tabProgram Enrollment` pe ON cei.program_ce = pe.name
        WHERE {' AND '.join(where)}
        """,
        params,
        as_dict=True,
    )

    out = []
    for r in rows:
        if not r.email:
            continue
        key = r.email.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "party_type": "Student",
                "party": r.student,
                "party_name": r.student_name,
                "email": r.email,
                "user": r.user,
            }
        )
    return out


def _instructors_for_term(term, course_schedules, seen):
    """Distinct instructors on Course Schedules in the given term. Narrowed by
    course_schedules if provided.
    """
    params = {"term": term}
    where = ["cs.academic_term = %(term)s"]

    if course_schedules:
        placeholders = ", ".join([f"%(cs_{i})s" for i in range(len(course_schedules))])
        where.append(f"cs.name IN ({placeholders})")
        for i, cs in enumerate(course_schedules):
            params[f"cs_{i}"] = cs

    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            i.name AS instructor,
            i.instructor_name,
            i.prof_email AS email,
            i.user
        FROM `tabCourse Schedule Instructors` csi
        JOIN `tabCourse Schedule` cs ON csi.parent = cs.name
        JOIN `tabInstructor` i ON csi.instructor = i.name
        WHERE {' AND '.join(where)}
        """,
        params,
        as_dict=True,
    )

    out = []
    for r in rows:
        if not r.email:
            continue
        key = r.email.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "party_type": "Instructor",
                "party": r.instructor,
                "party_name": r.instructor_name,
                "email": r.email,
                "user": r.user,
            }
        )
    return out


def _from_custom_filter(doctype, filters, email_field, seen):
    meta = frappe.get_meta(doctype)
    if not meta.get_field(email_field) and email_field != "name":
        frappe.throw(
            f"Email field '{email_field}' does not exist on doctype '{doctype}'."
        )

    fields = ["name", email_field]
    user_field = "user" if meta.get_field("user") else None
    name_field = None
    for candidate in ("student_name", "instructor_name", "full_name", "title"):
        if meta.get_field(candidate):
            name_field = candidate
            break
    if user_field:
        fields.append(user_field)
    if name_field:
        fields.append(name_field)

    rows = frappe.get_all(doctype, filters=filters or [], fields=fields)

    out = []
    for r in rows:
        email = r.get(email_field)
        if not email:
            continue
        key = email.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "party_type": _party_type_for(doctype),
                "party": r.get("name"),
                "party_name": r.get(name_field) if name_field else r.get("name"),
                "email": email,
                "user": r.get(user_field) if user_field else None,
            }
        )
    return out


def _party_type_for(doctype):
    if doctype == "Student":
        return "Student"
    if doctype == "Instructor":
        return "Instructor"
    if doctype == "User":
        return "User"
    return "Other"
