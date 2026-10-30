# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""Finding and merging duplicate Persons (privatedocs/p022)."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import duplicates
from seminary.seminary.tests.cohort_fixtures import make_person, make_student, make_user

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


def _pair(a, b, doctype="Person"):
    return frappe.db.get_value(
        "Possible Duplicate", {"pair_key": duplicates.pair_key(doctype, a, b)}
    )


def _twins(**values):
    """Two Persons for one human: same name, different emails."""
    a = make_person("Twin", last="Dupe" + frappe.generate_hash(length=6))
    b = make_person("Twin", last=a.last_name)
    for p in (a, b):
        p.update(values)
        p.save(ignore_permissions=True)
    return a, b


class TestFindingPairs(IntegrationTestCase):
    def test_same_name_and_birth_date_is_proposed(self):
        a, b = _twins(date_of_birth="1980-02-03")
        duplicates.refresh_pairs("Person")
        name = _pair(a.name, b.name)
        self.assertTrue(name)
        self.assertIn(
            "date of birth", frappe.db.get_value("Possible Duplicate", name, "reasons")
        )

    def test_an_email_on_both_is_proposed(self):
        a = make_person("Mail")
        b = make_person("Other")
        b.append(
            "channel_addresses", {"channel": "Email", "value": a.primary_email.upper()}
        )
        b.save(ignore_permissions=True)
        duplicates.refresh_pairs("Person")
        self.assertTrue(_pair(a.name, b.name))

    def test_not_the_same_is_remembered(self):
        a, b = _twins(date_of_birth="1980-02-03")
        duplicates.refresh_pairs("Person")
        duplicates.not_the_same(_pair(a.name, b.name))
        duplicates.refresh_pairs("Person")
        self.assertEqual(
            frappe.db.get_value("Possible Duplicate", _pair(a.name, b.name), "status"),
            "Not the Same",
        )

    def test_an_open_pair_that_stops_matching_goes(self):
        a, b = _twins(date_of_birth="1980-02-03")
        duplicates.refresh_pairs("Person")
        b.date_of_birth = "1981-02-03"
        b.save(ignore_permissions=True)
        duplicates.refresh_pairs("Person")
        self.assertFalse(_pair(a.name, b.name))


class TestMerging(IntegrationTestCase):
    def _merge(self, keep, remove, choices=None):
        duplicates.refresh_pairs("Person")
        pair = _pair(keep.name, remove.name)
        first = frappe.db.get_value("Possible Duplicate", pair, "first")
        picks = {
            k: "first" if v == first else "second" for k, v in (choices or {}).items()
        }
        return duplicates.merge(pair, keep.name, picks)

    def test_links_move_blanks_fill_and_choices_hold(self):
        a, b = _twins(date_of_birth="1980-02-03")
        a.db_set("city", "Recife")
        b.db_set({"city": "Olinda", "position": "Pastor"})
        org = frappe.get_doc(
            {
                "doctype": "Partner Organization",
                "organization_name": "Dupe Church " + frappe.generate_hash(length=6),
            }
        )
        org.append("contacts", {"person": b.name, "relationship_status": "Active"})
        org.insert(ignore_permissions=True)
        b_email = b.primary_email

        self._merge(a, b, {"city": b.name})

        self.assertFalse(frappe.db.exists("Person", b.name))
        kept = frappe.get_doc("Person", a.name)
        self.assertEqual(kept.city, "Olinda")
        self.assertEqual(kept.position, "Pastor")
        self.assertIn(
            b_email, [r.value for r in kept.channel_addresses if r.channel == "Email"]
        )
        self.assertEqual(
            frappe.get_doc("Partner Organization", org.name).contacts[0].person, a.name
        )
        log = frappe.get_doc("Record Merge Log", {"removed": b.name})
        self.assertEqual(log.kept, a.name)
        self.assertFalse(_pair(a.name, b.name))

    def test_an_opt_out_on_either_holds(self):
        a, b = _twins(date_of_birth="1980-02-03")
        a.append(
            "consents",
            {"channel": "Email", "category": "Promotional", "status": "Opted In"},
        )
        a.save(ignore_permissions=True)
        b.append(
            "consents",
            {"channel": "Email", "category": "Promotional", "status": "Opted Out"},
        )
        b.save(ignore_permissions=True)
        self._merge(a, b)
        rows = [
            r
            for r in frappe.get_doc("Person", a.name).consents
            if r.category == "Promotional"
        ]
        self.assertEqual([r.status for r in rows], ["Opted Out"])

    def test_one_login_survives_and_the_other_is_disabled(self):
        ua, ub = make_user(), make_user()
        a = make_person("Login", user=ua.name)
        b = make_person("Login", last=a.last_name, user=ub.name)
        for p in (a, b):
            p.db_set("date_of_birth", "1979-01-01")
        self._merge(a, b, {"user": b.name})
        self.assertEqual(frappe.db.get_value("Person", a.name, "user"), ub.name)
        self.assertEqual(frappe.db.get_value("User", ua.name, "enabled"), 0)
        self.assertEqual(frappe.db.get_value("User", ub.name, "enabled"), 1)

    def test_two_students_cannot_be_merged(self):
        a = make_student().person
        b = make_student().person
        frappe.db.set_value(
            "Person", b, "last_name", frappe.db.get_value("Person", a, "last_name")
        )
        frappe.db.set_value(
            "Person", b, "first_name", frappe.db.get_value("Person", a, "first_name")
        )
        for p in (a, b):
            frappe.db.set_value("Person", p, "date_of_birth", "1990-05-05")
        duplicates.refresh_pairs("Person")
        pair = _pair(a, b)
        preview = duplicates.merge_preview(pair)
        self.assertTrue(preview["conflicts"])
        with self.assertRaises(frappe.ValidationError):
            duplicates.merge(pair, a)


class TestWhoMerges(IntegrationTestCase):
    def setUp(self):
        self.officer = make_user(roles=("Desk User",))

    def _can(self, a, b):
        pair = frappe._dict(reference_doctype="Person", first=a, second=b)
        with patch.object(duplicates, "app_merge_roles", return_value={"Desk User"}):
            return duplicates.can_merge(pair, self.officer.name)[0]

    def test_an_app_role_merges_people_who_are_only_its_own(self):
        a, b = _twins()
        self.assertTrue(self._can(a.name, b.name))

    def test_a_student_is_the_registrars(self):
        a = make_person("Plain")
        self.assertFalse(self._can(a.name, make_student().person))
