# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Term advancement for Time-based programs (decisions/084).

`Program Enrollment.current_std_term` is the curriculum stage: which term's
planned courses the student may take. Send Grades moves it. When a student's
last grade of an Academic Term is sent, `Program.progression_rule` decides
whether they go on to the next stage. The stage only moves forward, stops at
`terms_complete`, and moves at most once per Academic Term: `advanced_from_term`
records the term a student last left. A registrar changes one student's stage
by hand with `change_term`.

A student who advances in a program where staff enroll students, with
`auto_enroll_next_term` on, is enrolled in the new stage's courses in the next
Academic Term; a course with no open section yet is enrolled when one opens.
"""

import frappe
from frappe import _
from frappe.utils import cint, today

from seminary.seminary.term_plan import expected_courses

AT_LEAST_ONE = "At least one course is passed"
EVERY_COURSE = "Every course is passed"
REGISTRAR = "The registrar advances"
REMOVE_FROM_COHORT = "Remove from the current program cohort"
CHANGE_ROLES = ["Registrar", "Seminary Manager", "System Manager"]


# -- Send Grades --------------------------------------------------------------


def after_grades_sent(course_schedule, pe_names):
    """Called by both Send Grades paths once the section's grades are final.
    A failure here is logged and never undoes the grades."""
    term = frappe.db.get_value("Course Schedule", course_schedule, "academic_term")
    if not term:
        return
    for pe_name in pe_names or []:
        try:
            evaluate(pe_name, term)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Term advancement failed (pe={pe_name}, term={term})",
            )


def evaluate(pe_name, academic_term):
    """Advance or hold one student, once their grades for the term are all in.
    Returns "advanced", "held" or None (nothing to decide yet)."""
    pe = frappe.db.get_value(
        "Program Enrollment",
        pe_name,
        [
            "name",
            "student",
            "program",
            "current_std_term",
            "advanced_from_term",
            "pgmenrol_active",
            "docstatus",
        ],
        as_dict=True,
    )
    if not pe or pe.docstatus != 1 or not pe.pgmenrol_active:
        return None
    program = frappe.get_cached_doc("Program", pe.program)
    if program.program_type != "Time-based" or program.is_ongoing:
        return None
    if pe.advanced_from_term == academic_term:
        return None
    if _still_being_graded(pe, academic_term):
        return None

    passed, graded = _results(pe.name, academic_term)
    if not graded:
        return None
    rule = program.progression_rule or AT_LEAST_ONE
    if rule == REGISTRAR:
        return None
    moves = passed >= 1 if rule == AT_LEAST_ONE else passed == graded

    stage = cint(pe.current_std_term) or 1
    if moves:
        if program.terms_complete and stage >= program.terms_complete:
            return None  # the final term: they graduate, not advance
        _set_stage(pe.name, stage + 1, academic_term)
        _comment(
            pe.name,
            _("Advanced to term {0} after the grades for {1}.").format(
                stage + 1, academic_term
            ),
        )
        if program.auto_enroll_next_term and program.staff_enroll_only:
            auto_enroll(pe.name, academic_term)
        return "advanced"

    _comment(
        pe.name,
        _("Stays in term {0}: {1} of {2} courses passed in {3}.").format(
            stage, passed, graded, academic_term
        ),
        once=True,
    )
    if program.cohort_failure_policy == REMOVE_FROM_COHORT:
        remove_from_program_cohorts(pe)
    return "held"


def _still_being_graded(pe, academic_term):
    """True while the student has a seated enrollment in a dated section of the
    term whose grades are not sent. An open-ended section never holds this back."""
    return bool(
        frappe.db.sql(
            """SELECT 1
               FROM `tabScheduled Course Roster` scr
               INNER JOIN `tabCourse Schedule` cs ON cs.name = scr.course_sc
               WHERE scr.student = %(student)s
                 AND scr.program_std_scr = %(program)s
                 AND scr.active = 1
                 AND scr.audit_bool = 0
                 AND cs.academic_term = %(term)s
                 AND COALESCE(cs.open_ended, 0) = 0
                 AND COALESCE(cs.workflow_state, '') != 'Cancelled'
               LIMIT 1""",
            {"student": pe.student, "program": pe.program, "term": academic_term},
        )
    )


def _results(pe_name, academic_term):
    """(passed, graded) among the student's courses with a final grade in the term."""
    rows = frappe.db.sql(
        """SELECT pec.status
           FROM `tabProgram Enrollment Course` pec
           INNER JOIN `tabCourse Schedule` cs ON cs.name = pec.course
           WHERE pec.parent = %(pe)s
             AND pec.parenttype = 'Program Enrollment'
             AND cs.academic_term = %(term)s
             AND pec.pec_finalgradecode IS NOT NULL
             AND pec.pec_finalgradecode != ''""",
        {"pe": pe_name, "term": academic_term},
        as_dict=True,
    )
    passed = sum(1 for r in rows if r.status != "Fail")
    return passed, len(rows)


def _set_stage(pe_name, stage, from_term):
    frappe.db.set_value(
        "Program Enrollment",
        pe_name,
        {
            "current_std_term": stage,
            "advanced_from_term": from_term,
            "advanced_on": today(),
        },
    )


def _comment(pe_name, text, once=False):
    if once and frappe.db.exists(
        "Comment",
        {
            "reference_doctype": "Program Enrollment",
            "reference_name": pe_name,
            "content": text,
        },
    ):
        return
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Program Enrollment",
            "reference_name": pe_name,
            "content": text,
        }
    ).insert(ignore_permissions=True)


# -- held back: the program's cohort -------------------------------------------


def remove_from_program_cohorts(pe):
    """Close the student's active membership in the program's Paced Program
    cohorts. Staff place them again by hand or with the Cohort Planner. A leader
    is never removed by this, as on withdrawal (066)."""
    person = frappe.db.get_value("Student", pe.student, "person")
    if not person:
        return []
    types = frappe.get_all(
        "Cohort Type",
        filters={"category": "Paced Program", "program": pe.program},
        pluck="name",
    )
    if not types:
        return []
    cohorts = frappe.get_all(
        "Cohort", filters={"cohort_type": ("in", types)}, pluck="name"
    )
    if not cohorts:
        return []
    closed = []
    for name in frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1, "cohort": ("in", cohorts)},
        pluck="name",
    ):
        doc = frappe.get_doc("Cohort Membership", name)
        if doc.is_leader:
            continue
        doc.invite_status = "Removed"
        doc.left_on = today()
        doc.flags.ignore_permissions = True
        doc.save()
        closed.append(doc.name)
    return closed


# -- the registrar's exception ---------------------------------------------------


@frappe.whitelist()
def change_term(program_enrollment, term, reason):
    """Set one student's stage by hand, with a reason for the timeline. Moving
    up marks the student's latest graded Academic Term as left (else the latest
    ended one), so that term's grades can't advance them a second time."""
    frappe.only_for(CHANGE_ROLES)
    term = cint(term)
    reason = (reason or "").strip()
    if term < 1:
        frappe.throw(_("The term must be 1 or more."))
    if not reason:
        frappe.throw(_("Give a reason for changing the term."))
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    pe.check_permission("write")
    old = cint(pe.current_std_term)
    if term == old:
        frappe.throw(_("The student is already in term {0}.").format(term))
    values = {"current_std_term": term}
    if term > old:
        left = _latest_graded_term(pe.name) or _latest_ended_term()
        if left:
            values.update(advanced_from_term=left, advanced_on=today())
    frappe.db.set_value("Program Enrollment", pe.name, values)
    _comment(
        pe.name,
        _("Term changed from {0} to {1} by {2}. Reason: {3}").format(
            old, term, frappe.session.user, frappe.utils.escape_html(reason)
        ),
    )
    return term


def _latest_graded_term(pe_name):
    rows = frappe.db.sql(
        """SELECT cs.academic_term
           FROM `tabProgram Enrollment Course` pec
           INNER JOIN `tabCourse Schedule` cs ON cs.name = pec.course
           INNER JOIN `tabAcademic Term` at ON at.name = cs.academic_term
           WHERE pec.parent = %s AND pec.parenttype = 'Program Enrollment'
             AND COALESCE(pec.pec_finalgradecode, '') != ''
           ORDER BY at.term_end_date DESC
           LIMIT 1""",
        (pe_name,),
    )
    return rows[0][0] if rows else None


def _latest_ended_term():
    rows = frappe.get_all(
        "Academic Term",
        filters={"term_end_date": ["<=", today()]},
        order_by="term_end_date desc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


# -- auto-enrollment ---------------------------------------------------------------


def next_academic_term(academic_term):
    start = frappe.db.get_value("Academic Term", academic_term, "term_start_date")
    if not start:
        return None
    rows = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": [">", start]},
        order_by="term_start_date asc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def auto_enroll(pe_name, from_term):
    """Enroll a student who just advanced in the new stage's courses, in the
    Academic Term after `from_term`. Courses with no open section wait for one
    (on_course_schedule_update); anything refused shows in the gaps report."""
    target = next_academic_term(from_term)
    if not target:
        return
    pe = frappe.db.get_value(
        "Program Enrollment",
        pe_name,
        ["name", "student", "program", "current_std_term"],
        as_dict=True,
    )
    for c in expected_courses(pe):
        section = _open_section(c.course, target)
        if section:
            _enroll_quietly(pe.name, c.course, section)


def _open_section(course, academic_term):
    from seminary.seminary.required_enrollment import _pick_offering

    offerings = frappe.get_all(
        "Course Schedule",
        filters={
            "course": course,
            "academic_term": academic_term,
            "workflow_state": "Open for Enrollment",
        },
        fields=["name", "academic_term", "modality", "c_datestart"],
    )
    return _pick_offering(offerings, academic_term)


def _enroll_quietly(pe_name, course, section):
    from seminary.seminary.api import enroll_in_section
    from seminary.seminary.required_enrollment import (
        _already_covered,
        unmet_prerequisites,
    )

    if _already_covered(pe_name, course) or unmet_prerequisites(pe_name, course):
        return
    frappe.db.savepoint("auto_enroll_next_term")
    try:
        enroll_in_section(pe_name, section, submit_blocked=True)
    except Exception:
        frappe.db.rollback(save_point="auto_enroll_next_term")
        frappe.clear_messages()
        frappe.log_error(
            frappe.get_traceback(),
            f"Next-term enrollment failed (pe={pe_name}, section={section})",
        )


def on_course_schedule_update(doc, method=None):
    if doc.workflow_state == "Open for Enrollment" and doc.has_value_changed(
        "workflow_state"
    ):
        _backfill(doc)


def on_course_schedule_insert(doc, method=None):
    if doc.workflow_state == "Open for Enrollment":
        _backfill(doc)


def _backfill(cs):
    """A section just opened: enroll students who advanced into the term before
    it and whose new stage plans its course."""
    if not cs.course or not cs.academic_term:
        return
    start = frappe.db.get_value("Academic Term", cs.academic_term, "term_start_date")
    if not start:
        return
    previous = frappe.get_all(
        "Academic Term",
        filters={"term_start_date": ["<", start]},
        order_by="term_start_date desc",
        pluck="name",
        limit=1,
    )
    if not previous:
        return
    programs = frappe.get_all(
        "Program",
        filters={
            "program_type": "Time-based",
            "staff_enroll_only": 1,
            "auto_enroll_next_term": 1,
        },
        pluck="name",
    )
    if not programs:
        return
    pes = frappe.get_all(
        "Program Enrollment",
        filters={
            "program": ("in", programs),
            "advanced_from_term": previous[0],
            "pgmenrol_active": 1,
            "docstatus": 1,
        },
        fields=["name", "student", "program", "current_std_term"],
    )
    for pe in pes:
        if any(c.course == cs.course for c in expected_courses(pe)):
            _enroll_quietly(pe.name, cs.course, cs.name)
