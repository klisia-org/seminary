"""Seed discipleship cohorts from a course's student groups.

This is the reverse of the retired cohort→course auto-enroll: course registration
is the entry point. Students enroll in a cohort-forming course (e.g. Spiritual
Formation), get organized into student groups, and staff spin up self-managing
Community Cohorts from those groups. Once created a cohort is independently
managed — student-group edits no longer sync.

This module holds the pure resolution helpers; the whitelisted orchestration
(`cohort_seed_preview`, `cohort_placement_status`, `create_cohorts_from_student_groups`)
lives in `discipleship/api.py`.
"""

import frappe
from frappe.utils import today


def course_cohort_binding(course_schedule):
    """Return (course, cohort_type) for a Course Schedule whose Course forms
    community cohorts. `cohort_type` is None when the course is not cohort-forming
    (or has no type set); `course` is None only when the schedule is unknown."""
    course = frappe.db.get_value("Course Schedule", course_schedule, "course")
    if not course:
        return None, None
    binding = frappe.db.get_value(
        "Course", course, ["forms_community_cohort", "cohort_type"], as_dict=True
    )
    if not binding or not (binding.forms_community_cohort and binding.cohort_type):
        return course, None
    return course, binding.cohort_type


def student_person(student):
    """Resolve a Student to its Person (ADR 042 spine), or None."""
    return frappe.db.get_value("Student", student, "person")


def instructor_person(instructor):
    """Resolve an Instructor to its Person, or None."""
    return frappe.db.get_value("Instructor", instructor, "person")


def active_cohort_of_type(person, cohort_type):
    """The cohort (name) of `cohort_type` in which this person has an active
    membership, if any — the dedup key across a 1→2→3 course sequence."""
    if not (person and cohort_type):
        return None
    cohorts = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1},
        pluck="cohort",
    )
    if not cohorts:
        return None
    return frappe.db.get_value(
        "Cohort", {"name": ["in", cohorts], "cohort_type": cohort_type}, "name"
    )


def pending_cohort_of_type(person, cohort_type):
    """The cohort (name) of `cohort_type` this person has a pending (Invited)
    membership in, if any — used to report placement status."""
    if not (person and cohort_type):
        return None
    cohorts = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "invite_status": "Invited"},
        pluck="cohort",
    )
    if not cohorts:
        return None
    return frappe.db.get_value(
        "Cohort", {"name": ["in", cohorts], "cohort_type": cohort_type}, "name"
    )


def cohorts_persist(cohort_type):
    """Do members of this kind of cohort stay in it once the course ends?

    A statement about a *kind* of cohort, so it lives on the type (ADR 066
    section 2): a school may reasonably want its formation cohorts to persist
    and its practicum cohorts not to, which a site-wide switch could not say.

    Persistence is what stops a later course in a sequence re-placing a student
    who already belongs -- SF1 to SF2 keeps the group, whichever session of SF2
    they land in -- which is why course-scoped types answer the question this way
    rather than through `graduates_to`.
    """
    if not cohort_type:
        return False
    return bool(
        frappe.db.get_value("Cohort Type", cohort_type, "persists_across_courses")
    )


# Every way of leaving a program short of finishing it. The three are one case
# here: whoever decided and for whatever reason, the student is no longer in the
# program the cohort is bound to. Graduation is deliberately absent -- that is
# `graduates_to`, a move rather than a removal.
SEPARATION_STATUSES = ("Withdrawn", "Transferred", "Dismissed")


def release_from_program_cohorts(pe_doc, to_status, effective_date=None):
    """Close a separated student's memberships where the type asks for it.

    Whether a withdrawal should empty a student's chair is a policy question,
    not a fact -- some schools keep a withdrawn student in their formation group
    while the pastoral conversation continues -- so it is answered once per
    kind of cohort by `Cohort Type.remove_on_withdrawal` (ADR 066 section 7.3).
    Types that do not ask are left entirely alone.

    Returns the memberships closed, for the caller to report.
    """
    if to_status not in SEPARATION_STATUSES or not pe_doc.program:
        return []
    person = frappe.db.get_value("Student", pe_doc.student, "person")
    if not person:
        return []

    types = _types_releasing_on_separation(pe_doc)
    if not types:
        return []

    mine = frappe.get_all(
        "Cohort Membership",
        filters={"person": person, "active": 1},
        fields=["name", "cohort"],
    )
    if not mine:
        return []
    releasable = set(
        frappe.get_all(
            "Cohort",
            filters={
                "name": ("in", [m.cohort for m in mine]),
                "cohort_type": ("in", types),
            },
            pluck="name",
        )
    )

    closed = []
    for m in mine:
        if m.cohort not in releasable:
            continue
        doc = frappe.get_doc("Cohort Membership", m.name)
        # A leader is not removed by their own enrollment ending: the cohort
        # still needs someone, and who replaces them is a decision, not a
        # consequence. It surfaces on the leaderless-cohort view instead.
        if doc.is_leader:
            continue
        doc.invite_status = "Removed"
        doc.left_on = effective_date or today()
        doc.flags.ignore_permissions = True
        doc.save()
        closed.append(doc.name)
    return closed


def _types_releasing_on_separation(pe_doc):
    """Cohort types bound to this program (or its level) that release on exit.

    A level-bound type is only released when the student is leaving the level
    altogether. Someone withdrawing from one master's degree while active in
    another has not left the cohort of master's students, and pulling them out
    of it would be wrong (ADR 066 section 7.10).
    """
    types = frappe.get_all(
        "Cohort Type",
        filters={"remove_on_withdrawal": 1, "program": pe_doc.program},
        pluck="name",
    )

    level = frappe.db.get_value("Program", pe_doc.program, "program_level")
    if not level:
        return types

    level_types = frappe.get_all(
        "Cohort Type",
        filters={"remove_on_withdrawal": 1, "program_level": level},
        pluck="name",
    )
    if not level_types:
        return types

    siblings = frappe.get_all(
        "Program",
        filters={"program_level": level, "name": ("!=", pe_doc.program)},
        pluck="name",
    )
    still_here = siblings and frappe.db.exists(
        "Program Enrollment",
        {
            "student": pe_doc.student,
            "program": ("in", siblings),
            "pgmenrol_active": 1,
            "docstatus": 1,
        },
    )
    return types if still_here else types + level_types


def live_cei_for_student_course(student, course):
    """The student's live Course Enrollment Individual for `course` (via any
    active Program Enrollment), for recording the audit tie on the membership.
    Optional — returns None when there is no live enrollment."""
    pe_name = frappe.db.get_value(
        "Program Enrollment",
        {"student": student, "pgmenrol_active": 1, "docstatus": 1},
        "name",
    )
    if not pe_name:
        return None
    return frappe.db.get_value(
        "Course Enrollment Individual",
        {
            "program_ce": pe_name,
            "course_data": course,
            "docstatus": ["!=", 2],
            "withdrawn": 0,
            "course_cancelled": 0,
        },
        "name",
    )
