# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""The demo calendar must never be in the past.

The academic years and terms used to be two JSON files of fixed 2024–2026
dates. A demo installed after those dates has no term covering today: nothing
is open for enrollment, no course schedule is live, and every screen that asks
"what term is it" answers nothing. It degraded a little more every month, and
the only way to notice was to install it.

So the calendar is generated from today, and these tests walk a simulated year
rather than trusting the day the suite happens to run on.
"""

from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from seminary.demo import demo_data

EXTRA_TEST_RECORD_DEPENDENCIES = []

#: Every 11th day across three years — cheap, and it lands inside each term and
#: on both sides of the 1 August rollover.
PROBES = [date(2026, 1, 1) + timedelta(days=11 * i) for i in range(100)]


class TestTheDemoCalendarIsAlwaysCurrent(IntegrationTestCase):
    def test_some_term_always_covers_today(self):
        for today in PROBES:
            with self.subTest(today=today):
                term = demo_data.current_demo_term(today)
                self.assertLessEqual(getdate(term["term_start_date"]), today)
                self.assertGreaterEqual(getdate(term["term_end_date"]), today)

    def test_exactly_one_term_covers_any_day(self):
        """Overlapping terms are not a richer answer, they are no answer:
        `tasks._update_term_flags` picks the earliest and the rest of the app
        reads a single `iscurrent_acterm`."""
        for today in PROBES:
            _years, terms = demo_data.demo_calendar(today)
            covering = [
                t
                for t in terms
                if getdate(t["term_start_date"]) <= today <= getdate(t["term_end_date"])
            ]
            with self.subTest(today=today):
                self.assertEqual(len(covering), 1, covering)

    def test_the_terms_are_contiguous_and_ordered(self):
        _years, terms = demo_data.demo_calendar(date(2026, 9, 4))
        for earlier, later in zip(terms, terms[1:]):
            with self.subTest(after=earlier["term_name"]):
                self.assertEqual(
                    getdate(later["term_start_date"]),
                    getdate(earlier["term_end_date"]) + timedelta(days=1),
                )

    def test_there_is_history_and_a_future(self):
        """A demo with only a current term shows nothing about progression —
        no completed enrollment to look at, nothing to register for."""
        today = date(2026, 9, 4)
        _years, terms = demo_data.demo_calendar(today)
        self.assertTrue([t for t in terms if getdate(t["term_end_date"]) < today])
        self.assertTrue([t for t in terms if getdate(t["term_start_date"]) > today])

    def test_every_term_sits_inside_its_academic_year(self):
        """`Academic Term.validate_term_against_year` rejects anything else, so
        a generator that drifted would fail at install time, mid-way."""
        for today in (date(2026, 1, 15), date(2026, 9, 4)):
            years, terms = demo_data.demo_calendar(today)
            spans = {
                y["academic_year_name"]: (
                    getdate(y["year_start_date"]),
                    getdate(y["year_end_date"]),
                )
                for y in years
            }
            for term in terms:
                start, end = spans[term["academic_year"]]
                with self.subTest(term=term["term_name"]):
                    self.assertGreaterEqual(getdate(term["term_start_date"]), start)
                    self.assertLessEqual(getdate(term["term_end_date"]), end)

    def test_the_term_docname_matches_how_frappe_names_it(self):
        """`Academic Term.autoname` builds `{academic_year} ({term_name})`, and
        the demo has to predict it to link enrollments and schedules."""
        _years, terms = demo_data.demo_calendar(date(2026, 9, 4))
        term = terms[0]
        doc = frappe.new_doc("Academic Term")
        doc.update(term)
        doc.autoname()
        self.assertEqual(doc.name, demo_data.demo_term_docname(term))


class TestTheDemoLinksNothingByDocname(IntegrationTestCase):
    def test_the_instructor_is_resolved_not_hardcoded(self):
        """`"Martin Luther"` was a valid Instructor docname until ADR 068 §5
        made it `INST-.#####`. The literal then named nothing, and the demo
        install died at the course schedules — but only on a site built after
        the change, which is why an existing site never showed it."""
        source = frappe.read_file(
            frappe.get_app_path("seminary", "demo", "demo_data.py")
        )
        self.assertNotIn('"instructor": "Martin Luther"', source)
