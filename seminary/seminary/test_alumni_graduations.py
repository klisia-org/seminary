# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""Alumni academic history (ADR 069).

A person has one Alumni Profile and may graduate more than once. The three flat
fields that used to hold "the" completed program could not say that, and what
happened on a second graduation was not an overwrite — `mark_as_alumni`
returned early on the existing profile, so the second degree was recorded
nowhere *and* the second enrollment never got its conclusion date, because the
return sat above that line.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from seminary.alumni.doctype.alumni_profile.alumni_profile import class_year_for
from seminary.seminary.tests.cohort_fixtures import make_person, make_user

# Deliberately outside the doctype folder. `IntegrationTestCase.setUpClass`
# only calls `make_test_records` when the module sits in a doctype directory,
# and Alumni Profile's link graph reaches erpnext's `Company` several ways over
# (via User, via Student, via Program) — whose test module bootstraps the
# standard price lists at import and collides with any site that has them.
# Per-doctype ignore lists only cover a doctype's *own* direct links, so
# cutting one path just exposes the next. `test_cohort_policy.py` sits here for
# the same reason.


class TestGraduationsAreRows(IntegrationTestCase):
    def _profile(self, label):
        from seminary.seminary import intake

        person = make_person(label, user=make_user().name)
        return intake.make_alumni_profile(person)

    def test_the_flat_academic_fields_are_gone(self):
        meta = frappe.get_meta("Alumni Profile")
        for field in ("program_completed", "class_year", "graduated_from_enrollment"):
            with self.subTest(field=field):
                self.assertFalse(
                    meta.get_field(field),
                    "%s is still on Alumni Profile; a person may graduate more "
                    "than once" % field,
                )
        self.assertTrue(meta.get_field("graduations"))

    def test_a_second_graduation_adds_a_row(self):
        profile = self._profile("TwoDegrees")
        first = frappe._dict(
            name=None,
            program="ZZT Program A",
            date_of_conclusion="2018-06-30",
            academic_term=None,
        )
        second = frappe._dict(
            name=None,
            program="ZZT Program B",
            date_of_conclusion="2022-06-30",
            academic_term=None,
        )
        profile.record_graduation(first, getdate("2018-06-30"))
        profile.record_graduation(second, getdate("2022-06-30"))
        self.assertEqual(len(profile.graduations), 2)
        self.assertEqual(
            [g.program for g in profile.graduations],
            ["ZZT Program A", "ZZT Program B"],
        )

    def test_recording_the_same_enrollment_twice_is_idempotent(self):
        profile = self._profile("Idempotent")
        pe = frappe._dict(
            name="ZZT-PE-1",
            program="ZZT Program A",
            date_of_conclusion="2018-06-30",
            academic_term=None,
        )
        self.assertFalse(profile.record_graduation(pe, getdate("2018-06-30")))
        self.assertTrue(profile.record_graduation(pe, getdate("2018-06-30")))
        self.assertEqual(len(profile.graduations), 1)


class TestClassYear(IntegrationTestCase):
    """`Academic Year.name` is free-form Data (`2017-2018`, or `DEMO-2025-26`),
    so the class year is a separate number — and it comes from the academic
    year's end, not from the calendar year on the certificate."""

    def test_an_autumn_graduate_belongs_to_the_closing_year(self):
        year = frappe.get_doc(
            {
                "doctype": "Academic Year",
                "academic_year_name": "ZZT 2017-2018",
                "year_start_date": "2017-08-01",
                "year_end_date": "2018-07-31",
            }
        ).insert(ignore_permissions=True)

        # December conclusion: the old `getdate(...).year` called this 2017.
        self.assertEqual(class_year_for(year.name, getdate("2017-12-15")), 2018)

    def test_it_falls_back_to_the_conclusion_date(self):
        """An alumnus imported from before this system has no academic year."""
        self.assertEqual(class_year_for(None, getdate("1998-05-20")), 1998)

    def test_it_is_none_when_nothing_is_known(self):
        self.assertIsNone(class_year_for(None, None))
