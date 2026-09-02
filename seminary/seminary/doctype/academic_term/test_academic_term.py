# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
"""The single-current-term invariant.

`Academic Term.iscurrent_acterm` is the app-wide answer to "what term is it",
read by the portal, the withdrawal window, the dashboards, self-enrollment and
the term-scoped reports. Two terms carrying it is not a richer answer, it is no
answer — whichever row a query happened to return first.

It used to be writable from three places at once: the daily task, an
`api.first_term` call fired from the form's `after_save` (which `break`ed out of
its loop on finding the covering term already current, leaving every later
term's stale flag in place), and the check box itself. These tests pin the
invariant to the two writers that remain.

The writer tests run against a synthetic date in a year no real term occupies,
because `_update_term_flags` is global by nature: asserting "exactly one term is
flagged" only means something if the test owns every term that could compete.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary.api import current_academic_term
from seminary.tasks import _update_term_flags

# Far enough out that no site term covers it, so "exactly one flagged" is a
# statement about this test's data rather than about the site's calendar.
ISOLATED_TODAY = getdate("2099-06-15")
YEAR_NAME = "ZZT 2099"


def _year(name, start, end):
    if frappe.db.exists("Academic Year", name):
        return name
    frappe.get_doc(
        {
            "doctype": "Academic Year",
            "academic_year_name": name,
            "year_start_date": start,
            "year_end_date": end,
        }
    ).insert(ignore_permissions=True)
    return name


def _term(year, term_name, start, end, current=0, is_open=1):
    doc = frappe.get_doc(
        {
            "doctype": "Academic Term",
            "academic_year": year,
            "term_name": term_name,
            "term_start_date": start,
            "term_end_date": end,
            "iscurrent_acterm": current,
            "open": is_open,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _clear_test_terms():
    for name in frappe.get_all(
        "Academic Term", filters={"academic_year": YEAR_NAME}, pluck="name"
    ):
        frappe.delete_doc("Academic Term", name, force=True, ignore_permissions=True)


def _flagged():
    return set(
        frappe.get_all("Academic Term", filters={"iscurrent_acterm": 1}, pluck="name")
    )


class TestCurrentTermIsSingular(IntegrationTestCase):
    """The writer: `tasks._update_term_flags`, on a calendar the test owns."""

    def setUp(self):
        super().setUp()
        # Wide enough to hold a term starting 200 days before the isolated date
        # and one ending 180 days after it — a term may not fall outside its year.
        self.year = _year(YEAR_NAME, "2098-01-01", "2100-12-31")
        # IntegrationTestCase rolls back once per class, not per test, so rows
        # from the previous test are still here. These assertions are about a
        # *global* property — exactly one term flagged — so the previous test's
        # terms would compete with this one's. Clear them explicitly.
        _clear_test_terms()

    def tearDown(self):
        _clear_test_terms()
        super().tearDown()

    def _make_three(self):
        past = _term(
            self.year,
            "ZZT Past",
            add_days(ISOLATED_TODAY, -200),
            add_days(ISOLATED_TODAY, -100),
        )
        present = _term(
            self.year,
            "ZZT Present",
            add_days(ISOLATED_TODAY, -10),
            add_days(ISOLATED_TODAY, 10),
        )
        future = _term(
            self.year,
            "ZZT Future",
            add_days(ISOLATED_TODAY, 100),
            add_days(ISOLATED_TODAY, 180),
        )
        return past, present, future

    def test_the_task_flags_exactly_the_covering_term(self):
        _past, present, _future = self._make_three()
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), {present.name})

    def test_a_stale_flag_on_a_future_term_is_cleared(self):
        """The gap in the old task: it only cleared a term whose end had passed,
        so a flag on a term that had not started yet survived indefinitely."""
        _past, present, future = self._make_three()
        frappe.db.set_value(
            "Academic Term", future.name, "iscurrent_acterm", 1, update_modified=False
        )
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), {present.name})

    def test_a_stale_flag_on_a_past_term_is_cleared(self):
        past, present, _future = self._make_three()
        frappe.db.set_value(
            "Academic Term", past.name, "iscurrent_acterm", 1, update_modified=False
        )
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), {present.name})

    def test_two_stale_flags_collapse_to_one(self):
        """What the retired `api.first_term` could leave behind."""
        past, present, future = self._make_three()
        for t in (past, future):
            frappe.db.set_value(
                "Academic Term", t.name, "iscurrent_acterm", 1, update_modified=False
            )
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), {present.name})

    def test_a_gap_between_terms_flags_nothing(self):
        """No term covers the date, so nothing claims to be current — the
        reader's fallback handles the display rather than a flag lying."""
        _term(
            self.year,
            "ZZT Before",
            add_days(ISOLATED_TODAY, -200),
            add_days(ISOLATED_TODAY, -100),
        )
        _term(
            self.year,
            "ZZT After",
            add_days(ISOLATED_TODAY, 100),
            add_days(ISOLATED_TODAY, 180),
        )
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), set())

    def test_the_running_term_is_open_and_ended_terms_are_closed(self):
        past, present, _future = self._make_three()
        frappe.db.set_value("Academic Term", present.name, "open", 0)
        _update_term_flags(ISOLATED_TODAY)
        self.assertTrue(frappe.db.get_value("Academic Term", present.name, "open"))
        self.assertFalse(frappe.db.get_value("Academic Term", past.name, "open"))

    def test_the_flag_is_derived_from_the_dates_not_typed(self):
        """Setting it by hand does not stick, and that is the design.

        Saving an Academic Term runs `refresh_term_flags_on_save`, which
        re-derives the flag from the dates — so a tick on a term that does not
        contain today is corrected on the same save. The field is read-only on
        the form to say so rather than let someone set a value that evaporates.
        """
        _past, _present, future = self._make_three()
        doc = frappe.get_doc("Academic Term", future.name)
        doc.iscurrent_acterm = 1
        doc.save(ignore_permissions=True)
        self.assertFalse(
            frappe.db.get_value("Academic Term", future.name, "iscurrent_acterm")
        )

    def test_the_exclusivity_guard_clears_the_others(self):
        """The guard for the programmatic path, where the date-driven writer is
        not what set the flag."""
        _past, present, future = self._make_three()
        _update_term_flags(ISOLATED_TODAY)
        self.assertEqual(_flagged(), {present.name})

        doc = frappe.get_doc("Academic Term", future.name)
        doc.iscurrent_acterm = 1
        doc.enforce_single_current_term()
        self.assertEqual(_flagged(), set())  # every other term cleared

    def test_the_flag_is_read_only_on_the_form(self):
        self.assertTrue(
            frappe.get_meta("Academic Term").get_field("iscurrent_acterm").read_only
        )

    def test_the_second_writer_is_gone(self):
        """`api.first_term` was the one that could leave two terms flagged."""
        from seminary.seminary import api

        self.assertFalse(hasattr(api, "first_term"))


class TestCurrentTermReader(IntegrationTestCase):
    """The reader: one definition, `api.current_academic_term`."""

    def test_the_reader_answers_from_the_flag(self):
        _update_term_flags(getdate(today()))
        flagged = _flagged()
        if not flagged:
            self.skipTest("no term covers today on this site")
        self.assertEqual(current_academic_term(), flagged.pop())

    def test_the_reader_falls_back_when_no_flag_is_set(self):
        """A fresh site whose daily task has not run yet still gets an answer,
        rather than the portal blanking out."""
        covering = frappe.get_all(
            "Academic Term",
            filters={
                "term_start_date": ("<=", today()),
                "term_end_date": (">=", today()),
            },
            pluck="name",
        )
        if not covering:
            self.skipTest("no term covers today on this site")
        for name in _flagged():
            frappe.db.set_value(
                "Academic Term", name, "iscurrent_acterm", 0, update_modified=False
            )
        self.assertIn(current_academic_term(), covering)

    def test_the_reader_is_what_self_enrollment_uses(self):
        """One definition means the enrollment path reads the same function."""
        from seminary.seminary.doctype.student.student import _current_academic_term

        self.assertEqual(_current_academic_term(), current_academic_term())
