# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Delete the identity fixtures a test class builds in ``setUpClass``.

Frappe's ``IntegrationTestCase`` rolls back per test, and its own
``setUpClass`` ends with ``frappe.db.commit()`` ("flush changes done so far to
avoid flake"); ``User.insert`` commits again on top of that. So the Users,
Persons, Students and Instructors a suite needs *before* any test runs are on
disk by the time the class-level rollback happens, and they stay there.

Left alone this grows without bound. testable.localhost had accumulated 1414
Users, 822 Students, 456 Instructors, 431 rosters and 5285 gradebook cells from
``zzt…@example.test`` across hundreds of runs. That is not merely untidy: the
fixtures in these suites pick arbitrary *existing* rows to hang themselves on
(``_any_course_schedule`` takes the two oldest sections on the site), so a site
that drifts changes what the tests actually exercise — and a test site whose
results depend on how many times it has been run is not a test site.

Usage — list the mixin first so its ``setUpClass`` snapshots before the
subclass builds anything::

    class TestSomething(IdentityCleanup, IntegrationTestCase):
        ...
"""

import frappe

# Every fixture identity in this app is an @example.test address; no real
# record can collide with it.
TEST_EMAIL_LIKE = "%@example.test"


def existing_test_users():
    """The test identities already on the site, as a set of User names."""
    return set(
        frappe.get_all(
            "User", filters={"name": ["like", TEST_EMAIL_LIKE]}, pluck="name"
        )
    )


def purge_test_identities(exclude=()):
    """Delete every test identity except the ones named in `exclude`.

    Commits, because the class-level rollback Frappe queues with
    ``addClassCleanup`` runs *after* ``tearDownClass`` and would otherwise undo
    the deletes along with everything else.
    """
    exclude = set(exclude or ())
    emails = [e for e in existing_test_users() if e not in exclude]
    if not emails:
        return 0

    students = frappe.get_all("Student", filters={"user": ["in", emails]}, pluck="name")
    instructors = frappe.get_all(
        "Instructor", filters={"user": ["in", emails]}, pluck="name"
    )

    # Rows hanging off the identities, innermost first. Child tables whose
    # parent is *not* being deleted have to go by hand — deleting an Instructor
    # does not touch the Course Schedule Instructors row that lists them.
    if instructors:
        frappe.db.delete(
            "Course Schedule Instructors", {"instructor": ["in", instructors]}
        )
    if students:
        for roster in frappe.get_all(
            "Scheduled Course Roster",
            filters={"student": ["in", students]},
            pluck="name",
        ):
            _delete("Scheduled Course Roster", roster)
        for doctype in ("Assignment Submission", "Quiz Submission", "Exam Submission"):
            if not frappe.db.exists("DocType", doctype):
                continue
            for name in frappe.get_all(
                doctype, filters={"student": ["in", students]}, pluck="name"
            ):
                _delete(doctype, name)

    for name in instructors:
        _delete("Instructor", name)
    for name in students:
        _delete("Student", name)
    for name in frappe.get_all(
        "Person", filters={"primary_email": ["in", emails]}, pluck="name"
    ):
        _delete("Person", name)
    for email in emails:
        _delete("User", email)

    frappe.db.commit()
    return len(emails)


def _delete(doctype, name):
    """Force-delete one fixture row, and never fail the suite over cleanup."""
    try:
        frappe.delete_doc(
            doctype,
            name,
            force=True,
            ignore_permissions=True,
            ignore_missing=True,
            delete_permanently=True,
        )
    except Exception:
        # Cleanup is best-effort: a fixture row wedged behind a link is worth a
        # skipped delete, never a failed suite.
        frappe.clear_last_message()


def module_hooks():
    """``setUpModule`` / ``tearDownModule`` for a whole test module.

    Use this instead of the mixin wherever classes *share* fixtures through a
    common base. Frappe's ``_integration_test_case_class_setup_done`` flag is
    set on the class and therefore inherited, so a base like
    ``test_cohort_planner.PlannerCase`` builds its fixtures exactly once and
    every subclass reuses them. A per-class teardown there deletes rows the next
    class still needs — 58 errors' worth, in cohort_policy alone.

    Wire it in at module scope::

        setUpModule, tearDownModule = module_hooks()
    """
    state = {}

    def setUpModule():
        state["snapshot"] = existing_test_users()
        state["armed"] = True

    def tearDownModule():
        # Fail safe. An unarmed teardown means the baseline was never observed,
        # which is NOT the same as "the site had nothing" — and purging against
        # an empty exclude set deletes every test identity on the site, not just
        # this module's. It did exactly that once.
        if not state.get("armed"):
            return
        # Discard pending work before the purge commits, or every uncommitted
        # fixture is promoted to permanent (see the mixin).
        frappe.db.rollback()
        purge_test_identities(exclude=state["snapshot"])

    return setUpModule, tearDownModule


class IdentityCleanup:
    """Mixin: remove the identities this class created when it finishes."""

    @classmethod
    def setUpClass(cls):
        cls._identity_snapshot = existing_test_users()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Discard the class's *uncommitted* work before deleting the committed
        # part, because the purge has to commit to survive Frappe's own
        # class-level rollback — and a bare commit here would promote every
        # pending fixture to permanent instead. That is not hypothetical: the
        # ZZT Cohort Types and Programs `cohort_fixtures.uid` names off a
        # per-process counter, so committing them made the *next* run collide on
        # "ZZT Type 25" and friends.
        if not hasattr(cls, "_identity_snapshot"):
            return  # unarmed: see module_hooks
        frappe.db.rollback()
        purge_test_identities(exclude=cls._identity_snapshot)
