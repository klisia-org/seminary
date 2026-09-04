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
            # `Person.primary_email` is unique, and a per-process counter is
            # not: it restarts at zero every run, so any fixture record that
            # escapes a rollback poisons every later run with a duplicate. The
            # random suffix makes the address unique across runs, not just
            # within one.
            "primary_email": email
            or (frappe.db.get_value("User", user, "email") if user else None)
            or (
                "%s.person.%d.%s@example.test"
                % (PREFIX.lower(), _seq[0], frappe.generate_hash(length=6))
            ),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def make_user(roles=(), email=None):
    # Unique across runs, not merely within one — see make_person. A User that
    # survives a rollback would otherwise be silently reused by a later test.
    email = email or (
        "%s.%d.%s@example.test"
        % (PREFIX.lower(), _seq[0] + 1, frappe.generate_hash(length=6))
    )
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
        # A conclusion date even though these tests only care about the
        # program: `class_year` is derived from the academic year or this, and
        # a row with neither is refused rather than saved as Class of 0.
        doc.append(
            "graduations",
            {"program": program_completed, "conclusion_date": today()},
        )
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


# ----------------------------------------------------------------- org / pool


COHORT_MENTORSHIP_ROUTE = "Program Cohort Mentorship"


def mentorship_capability():
    """The seeded capability wired to the cohort-mentorship route.

    Seeded by `install.seed_faculty_capabilities`, so it exists on any migrated
    site; a school may rename the display name freely, which is exactly why the
    lookup is on `routes_to` and not on the name.
    """
    rows = frappe.get_all(
        "Faculty Capability",
        filters={"routes_to": COHORT_MENTORSHIP_ROUTE, "is_active": 1},
        limit=1,
        pluck="name",
    )
    return rows[0] if rows else None


def make_mentoring_unit(chair=None, is_active=1):
    doc = frappe.get_doc(
        {
            "doctype": "Academic Unit",
            "unit_name": uid("Mentoring"),
            "unit_type": "Mentoring Department",
            "chair": chair,
            "is_active": is_active,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def seat_mentor(unit, instructor=None, max_students=0, current_students=0):
    """An instructor in `unit`, wired to the mentorship route with a ceiling.

    `max_students = 0` means unlimited, which is `faculty._remaining`'s own
    convention -- so a fixture that wants a *full* mentor has to give them a
    real ceiling and meet it.
    """
    if instructor is None:
        instructor = make_instructor()
    capability = mentorship_capability()
    doc = frappe.get_doc(
        {
            "doctype": "Academic Unit Membership",
            "unit": unit if isinstance(unit, str) else unit.name,
            "person": instructor.person,
            "instructor": instructor.name,
            "is_active": 1,
            "capabilities": [
                {
                    "capability": capability,
                    "tracks_capacity": 1,
                    "max_students": max_students,
                    "current_students": current_students,
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
