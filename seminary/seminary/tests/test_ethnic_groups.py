# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Ethnic groups are a list each school keeps (ADR 086)."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import ethnic_groups as eg

PREFIX = "ZZ-ETH"


class TestEthnicGroups(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        eg.seed_ethnic_groups()

    def tearDown(self):
        frappe.db.rollback()

    def _person(self, **kw):
        return frappe.get_doc(
            {
                "doctype": "Person",
                "first_name": f"{PREFIX} {frappe.generate_hash(length=5)}",
                **kw,
            }
        )

    def test_the_seed_is_the_former_list(self):
        for name in eg.DEFAULT_GROUPS:
            self.assertTrue(frappe.db.exists(eg.DOCTYPE, name))

    def test_stored_values_are_kept(self):
        person = self._person()
        person.insert(ignore_permissions=True)
        frappe.db.set_value("Person", person.name, "ethnicity", f"{PREFIX} Quechua")
        eg.keep_existing_values()
        self.assertTrue(frappe.db.exists(eg.DOCTYPE, f"{PREFIX} Quechua"))

    def test_only_active_groups_are_chosen(self):
        frappe.get_doc(
            {"doctype": eg.DOCTYPE, "group_name": f"{PREFIX} Old", "is_active": 0}
        ).insert()
        with self.assertRaises(frappe.ValidationError):
            self._person(ethnicity=f"{PREFIX} Old").insert(ignore_permissions=True)
        person = self._person(ethnicity="Other")
        person.insert(ignore_permissions=True)
        frappe.db.set_value("Person", person.name, "ethnicity", f"{PREFIX} Old")
        person.reload()
        person.middle_name = "Kept"
        person.save(ignore_permissions=True)  # an old value is left alone
