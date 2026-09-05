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
from seminary.seminary.tests.cohort_fixtures import make_person, make_program, make_user

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


class TestTheClassYearIsDerivedOnEveryPath(IntegrationTestCase):
    """A hand-added row is the common case, not the exotic one.

    `record_graduation` computed the class year, and it is only reached from a
    completed Program Enrollment. A registrar entering an alumnus of another
    institution, or one whose studies predate this system, adds the row in Desk
    — and got nothing. `class_year` is an `Int`, which Frappe stores `NOT NULL
    DEFAULT 0`, so the field did not read as empty. It read as *Class of 0*.
    """

    def _profile(self, label):
        from seminary.seminary import intake

        person = make_person(label, user=make_user().name)
        return intake.make_alumni_profile(person)

    def _academic_year(self, label, start, end):
        name = "ZZT %s" % label
        if frappe.db.exists("Academic Year", name):
            return name
        return (
            frappe.get_doc(
                {
                    "doctype": "Academic Year",
                    "academic_year_name": name,
                    "year_start_date": start,
                    "year_end_date": end,
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    def test_a_hand_added_row_gets_its_class_year(self):
        year = self._academic_year("2014-2015", "2014-08-01", "2015-07-31")
        profile = self._profile("HandEntered")
        profile.append(
            "graduations",
            {
                "program": make_program().name,
                "academic_year": year,
                "conclusion_date": getdate("2014-12-12"),
            },
        )
        profile.save(ignore_permissions=True)

        self.assertEqual(profile.graduations[-1].class_year, 2015)

    def test_editing_the_academic_year_moves_the_class_year(self):
        """Derived, not filled-once: the row's academic year stays editable, so
        a stale class year would be the same defect in a different disguise."""
        early = self._academic_year("2014-2015", "2014-08-01", "2015-07-31")
        later = self._academic_year("2017-2018", "2017-08-01", "2018-07-31")
        profile = self._profile("Corrected")
        program = make_program().name
        profile.append("graduations", {"program": program, "academic_year": early})
        profile.save(ignore_permissions=True)
        self.assertEqual(profile.graduations[-1].class_year, 2015)

        profile.graduations[-1].academic_year = later
        profile.save(ignore_permissions=True)
        self.assertEqual(profile.graduations[-1].class_year, 2018)

    def test_a_legacy_row_keeps_the_class_year_it_was_imported_with(self):
        """An alumnus from before this system may have a class year and no
        academic year or conclusion date at all — that is exactly what the old
        flat `class_year` column held, and what the ADR 069 migration carried
        across. Recomputing those to 0 and refusing the save would have made
        every imported profile unsaveable."""
        profile = self._profile("Legacy")
        profile.append(
            "graduations", {"program": make_program().name, "class_year": 1998}
        )
        profile.save(ignore_permissions=True)
        profile.reload()

        row = profile.graduations[-1]
        self.assertEqual(row.class_year, 1998)
        self.assertFalse(row.academic_year)
        self.assertFalse(row.conclusion_date)

    def test_a_derivable_year_still_wins_over_a_stored_one(self):
        """Preserving a legacy value must not turn the field into a free
        column: where a source exists it is authoritative."""
        year = self._academic_year("2014-2015", "2014-08-01", "2015-07-31")
        profile = self._profile("Both")
        profile.append(
            "graduations",
            {"program": make_program().name, "academic_year": year, "class_year": 1998},
        )
        profile.save(ignore_permissions=True)

        self.assertEqual(profile.graduations[-1].class_year, 2015)

    def test_a_row_with_nothing_to_derive_from_is_refused(self):
        """Rather than saving a row that displays Class of 0 — an integer
        column cannot say "not known", so the misleading value has to be
        prevented instead of represented."""
        profile = self._profile("Undatable")
        # A complete row apart from the two fields the class year comes from,
        # so the mandatory check cannot pass this test for the wrong reason.
        profile.append("graduations", {"program": make_program().name})
        with self.assertRaisesRegex(frappe.ValidationError, "class year"):
            profile.save(ignore_permissions=True)
