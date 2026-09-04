# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Fixtures for the ADR 066 cohort/mentoring tests.

Everything these tests assert about is cheap to build -- a Person, a Cohort
Type, a Cohort, a membership. What is expensive is the academic spine behind a
competency mentorship: a Program with a framework, a Student, a submitted
Program Enrollment. Those are built once per test class and torn down with the
transaction.

Records are named with a `ZZT` prefix so a failed teardown is obvious rather
than mistaken for a school's data.
"""

import frappe
from frappe.utils import today

PREFIX = "ZZT"
_seq = [0]


def uid(label=""):
    _seq[0] += 1
    return "%s %s%d" % (PREFIX, (label + " ") if label else "", _seq[0])


# ------------------------------------------------------------------- identity


def make_person(first="Test", last=None, user=None, email=None):
    """A Person always has a primary email.

    `ensure_person` cannot create one without an email or a User, so a Person
    lacking both was never a state the app could reach — but these fixtures
    built one, which mattered from ADR 068 phase 4 on: the role addresses are
    `fetch_from person.primary_email`, and Frappe blanks a mirror whose source
    is null, so an email-less Person silently produced an email-less Student.
    """
    _seq[0] += 1
    doc = frappe.get_doc(
        {
            "doctype": "Person",
            "first_name": PREFIX + " " + first,
            "last_name": last or uid(),
            "user": user,
            "primary_email": email
            or (frappe.db.get_value("User", user, "email") if user else None)
            or ("%s.person.%d@example.test" % (PREFIX.lower(), _seq[0])),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def make_user(roles=(), email=None):
    email = email or ("%s.%d@example.test" % (PREFIX.lower(), _seq[0] + 1))
    _seq[0] += 1
    if frappe.db.exists("User", email):
        return frappe.get_doc("User", email)
    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": PREFIX,
            "last_name": "User",
            "send_welcome_email": 0,
        }
    )
    doc.flags.no_welcome_mail = True
    doc.insert(ignore_permissions=True)
    for role in roles:
        if frappe.db.exists("Role", role):
            doc.add_roles(role)
    return doc


def make_instructor(person=None, status="Active"):
    """Person first, then the role (ADR 068 §1).

    `instructor_name`, `prof_email` and the rest are `fetch_from person.*`
    mirrors, so setting them on the Instructor is pointless — they come from
    the spine. The User is created first because `Instructor.user` is reqd and
    the spine wants the link.
    """
    from seminary.seminary import intake

    if person is None:
        user = make_user()
        person = make_person("Instr", user=user.name)
    elif not person.user:
        person.db_set("user", make_user().name, update_modified=False)
        person.reload()
    return intake.make_instructor(person, user=person.user, status=status)


def make_student(person=None):
    """Person first, then the role (ADR 068 §1).

    The Student's identity fields are mirrors of the Person's, and `person` is
    required — so there is nothing left to type here.
    """
    from seminary.seminary import intake

    if person is None:
        user = make_user()
        person = make_person("Student", user=user.name)
    return intake.make_student(person, user=person.user)


def make_alumni_profile(person, program_completed=None, enabled=1):
    """Completed programs are rows on the profile (ADR 069)."""
    from seminary.seminary import intake

    if not person.user:
        person.db_set("user", make_user().name, update_modified=False)
        person.reload()
    doc = intake.make_alumni_profile(person, user=person.user, enabled=enabled)
    if program_completed:
        doc.append("graduations", {"program": program_completed})
        doc.save(ignore_permissions=True)
    return doc


# ------------------------------------------------------------------- academic


def current_term():
    """The app's own answer — one definition, read the same way everywhere."""
    from seminary.seminary.api import current_academic_term

    return current_academic_term()


def make_program(program_type="Time-based", program_level=None, framework=None):
    name = uid("Program")
    doc = frappe.get_doc(
        {
            "doctype": "Program",
            "program_name": name,
            "program_abbreviation": "Z%d" % _seq[0],
            "program_type": program_type,
            "program_level": program_level,
            "competency_framework": framework,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def make_program_level():
    rows = frappe.get_all("Program Level", limit=1, pluck="name")
    return rows[0] if rows else None


def make_enrollment(student, program, submit=True):
    doc = frappe.get_doc(
        {
            "doctype": "Program Enrollment",
            "student": student.name,
            "program": program.name,
            "academic_term": current_term(),
            "enrollment_date": today(),
        }
    )
    doc.insert(ignore_permissions=True)
    if submit:
        doc.submit()
        doc.reload()
    return doc


def cbe_grading_scale():
    rows = frappe.get_all(
        "Grading Scale",
        filters={"grscale_type": "Competency-based education"},
        limit=1,
        pluck="name",
    )
    return rows[0] if rows else None


def make_framework(cohort_type=None, instructor_category=None, status="Active"):
    """A framework with one cohort-sourced evaluator, per ADR 066 section 5.

    Returns None when the site has no competency-based grading scale, which is
    the one dependency these tests cannot reasonably build themselves.
    """
    scale = cbe_grading_scale()
    if not scale:
        return None
    category = (
        instructor_category
        or frappe.get_all("Instructor Category", limit=1, pluck="name")[0]
    )
    doc = frappe.get_doc(
        {
            "doctype": "Competency Framework",
            "framework_name": uid("Framework"),
            "grading_scale": scale,
            "status": status,
            "evaluators": [
                {
                    "instructor_category": category,
                    "assignment_source": "Program Cohort",
                    "cohort_type": cohort_type,
                    "grades_activities": 1,
                    "gives_competency_verdict": 1,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


# --------------------------------------------------------------------- cohort


def make_cohort_type(**kw):
    values = {
        "doctype": "Cohort Type",
        "type_name": uid("Type"),
        "category": "Unrestricted",
        "leader_eligibility": "Anyone",
    }
    values.update(kw)
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return doc


def make_cohort(cohort_type, leader, **kw):
    values = {
        "doctype": "Cohort",
        "cohort_name": uid("Cohort"),
        "cohort_type": cohort_type,
        "leader": leader,
        "status": "Active",
    }
    values.update(kw)
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return doc


def add_member(cohort, person, role="Member", is_leader=0, status="Active"):
    doc = frappe.get_doc(
        {
            "doctype": "Cohort Membership",
            "cohort": cohort,
            "person": person,
            "role": role,
            "is_leader": is_leader,
            "invite_status": status,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def bust_cbe_cache():
    """`cbe` caches resolution per request; a test changes the world mid-request."""
    frappe.local.cbe_cache = {}
    frappe.clear_cache(doctype="Competency Framework")
