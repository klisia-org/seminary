# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The roles that may enroll a student without the course's prerequisites are
a Seminary Settings choice; the built-in list stands when the school names none."""

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.doctype.course_enrollment_individual import (
    course_enrollment_individual as cei,
)
from seminary.seminary.tests import cohort_fixtures as fx


def _role(name):
    if not frappe.db.exists("Role", name):
        frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(
            ignore_permissions=True
        )
    return name


class TestPrerequisiteOverrideRoles(IntegrationTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.set_single_value("Seminary Settings", "prerequisite_override_roles", "")
        super().tearDown()

    def test_the_built_in_roles_stand_when_the_school_names_none(self):
        frappe.db.set_single_value("Seminary Settings", "prerequisite_override_roles", "")
        self.assertEqual(cei.prerequisite_override_roles(), cei._PREREQ_OVERRIDE_ROLES)

    def test_only_the_named_role_may_override(self):
        _role("Chief Academic Officer")
        frappe.db.set_single_value(
            "Seminary Settings", "prerequisite_override_roles", "Chief Academic Officer"
        )
        frappe.set_user(fx.make_user(roles=["Registrar"]).name)
        self.assertFalse(cei._user_can_override_prereqs())
        frappe.set_user("Administrator")
        frappe.set_user(fx.make_user(roles=["Chief Academic Officer"]).name)
        self.assertTrue(cei._user_can_override_prereqs())

    def test_the_list_tolerates_spaces_and_blanks(self):
        frappe.db.set_single_value(
            "Seminary Settings", "prerequisite_override_roles", " Registrar , ,Dean "
        )
        self.assertEqual(cei.prerequisite_override_roles(), {"Registrar", "Dean"})
