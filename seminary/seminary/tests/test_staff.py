"""Person.is_staff (decisions/085).

The flag is what staff pickers filter on and what tells an app someone left,
so the cases that matter are the mixed ones: an alumnus who is also an
employee, and an employee whose account is disabled.
"""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import staff

EMAIL = "zz_staff_flag@example.com"


class IntegrationTestStaff(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        if not frappe.db.exists("User", EMAIL):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": EMAIL,
                    "first_name": "Staff",
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        self.user = frappe.get_doc("User", EMAIL)
        self.user.set("roles", [])
        self.user.enabled = 1
        self.user.save(ignore_permissions=True)
        self.person = (
            frappe.db.get_value("Person", {"user": EMAIL}, "name")
            or frappe.get_doc(
                {"doctype": "Person", "first_name": "Staff", "user": EMAIL}
            )
            .insert(ignore_permissions=True)
            .name
        )

    def _flag(self):
        return frappe.db.get_value("Person", self.person, "is_staff")

    def _roles(self, *roles):
        self.user.reload()
        self.user.set("roles", [{"role": r} for r in roles])
        self.user.save(ignore_permissions=True)

    def test_alumnus_is_not_staff_until_given_a_staff_role(self):
        for role in ("Alumni", "Student"):
            if not frappe.db.exists("Role", role):
                frappe.get_doc({"doctype": "Role", "role_name": role}).insert(
                    ignore_permissions=True
                )
        self._roles("Alumni")
        self.assertFalse(self._flag())
        self._roles("Alumni", "Registrar")
        self.assertTrue(self._flag())

    def test_disabled_account_is_not_staff_and_is_announced(self):
        self._roles("Instructor")
        self.assertTrue(self._flag())
        seen = []
        original = staff._announce
        staff._announce = lambda person, value: seen.append((person, value))
        try:
            self.user.reload()
            self.user.enabled = 0
            self.user.save(ignore_permissions=True)
        finally:
            staff._announce = original
        self.assertFalse(self._flag())
        self.assertEqual(seen, [(self.person, 0)])

    def test_apps_extend_the_staff_roles(self):
        self.assertIn("Registrar", staff.staff_roles())
        if "aretenic" in frappe.get_installed_apps():
            self.assertIn("Institutional Quality Manager", staff.staff_roles())

    def test_daily_refresh_catches_direct_role_grants(self):
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": EMAIL,
                "parenttype": "User",
                "parentfield": "roles",
                "role": "Program Chair",
            }
        ).db_insert()
        frappe.clear_cache(user=EMAIL)
        self.assertFalse(self._flag())
        staff.refresh()
        self.assertTrue(self._flag())
