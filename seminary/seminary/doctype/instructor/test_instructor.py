# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt

import unittest

import frappe

# Two instructors is what the old fixture offered and what callers that ask for
# `_Test Instructor 2` expect; the identities behind them are new.
TEST_INSTRUCTORS = (
    ("_Test Instructor", "_test.instructor@example.com"),
    ("_Test Instructor 2", "_test.instructor.2@example.com"),
)


def _make_test_records():
    """Build the Instructor test records Person-first (ADR 068).

    This replaces `test_records.json`, which was ERPNext's: a `naming_series`
    the doctype stopped using when it moved to `INST-.#####`, and an `employee`
    link standing in for identity. `Instructor.user` and `.person` are both
    `reqd` now, and neither can be expressed in a static JSON fixture — a User
    and a Person have to be created first, and `Person` ships no test records to
    link to. Frappe's `_make_test_records` hook is the escape hatch for exactly
    this case, and it takes priority over the JSON.

    Until this existed, `bench run-tests --app seminary` died in record
    generation with `MandatoryError: [Instructor, INST-#####]: user, person`
    for every doctype that links to Instructor — before a single integration
    test in the app ran.

    Deterministic identities on purpose. Frappe journals these per site and
    reuses them across runs, which is the opposite of the per-test fixtures in
    `tests/` — those randomise precisely so a row surviving a rollback is never
    silently reused.
    """
    from seminary.seminary import intake
    from seminary.seminary import person as person_spine

    for instructor_name, email in TEST_INSTRUCTORS:
        existing = frappe.db.get_value("Instructor", {"user": email})
        if existing:
            yield ("loaded", frappe.get_doc("Instructor", existing))
            continue

        if not frappe.db.exists("User", email):
            user = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": instructor_name,
                    "send_welcome_email": 0,
                }
            )
            user.flags.no_welcome_mail = True
            user.insert(ignore_permissions=True)

        # The spine carries the email the mirrors fetch from; an Instructor
        # whose Person has no primary_email is refused by assert_reachable.
        person = person_spine.ensure_person(
            email=email,
            user=email,
            first_name=instructor_name,
        )
        yield ("created", intake.make_instructor(person, user=email, status="Active"))


class TestInstructor(unittest.TestCase):
    pass
