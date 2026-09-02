# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Cohort Membership: where a person and their cohort type's policy meet.

`Cohort Type` states the rules once (ADR 066 section 2); they are checked here,
against the person in front of them, rather than trusted at setup. A membership
is the only record that knows both halves.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

# Leadership is a cohort-scoped capability, not a global role (ADR 064 section 1),
# so several concurrent rows may carry `is_leader` -- a mentor pair, or a
# professor over student-led sub-cohorts. What follows constrains *who* may hold
# it, never how many.
ANYONE = "Anyone"
INSTRUCTOR = "Instructor"
ALUMNUS = "Alumnus of the bound program or level"
STAFF = "Staff"

# Only a live membership is checked. A closed row records who led at the time,
# and re-checking history against today's policy would refuse to save the past.
OPEN_STATUSES = ("Invited", "Active")


class CohortMembership(Document):
    def validate(self):
        # `active` is derived from invite_status — it is the single field the
        # roster and permission queries filter on, so keep it in lock-step.
        self.active = 1 if self.invite_status == "Active" else 0
        if self.invite_status == "Active" and not self.joined_on:
            self.joined_on = today()
        if self.invite_status in ("Left", "Removed") and not self.left_on:
            self.left_on = today()
        self._guard_single_active()
        self.validate_leader_eligibility()

    def _guard_single_active(self):
        """At most one active membership per (cohort, person)."""
        if not self.active:
            return
        clash = frappe.db.exists(
            "Cohort Membership",
            {
                "cohort": self.cohort,
                "person": self.person,
                "active": 1,
                "name": ["!=", self.name or ""],
            },
        )
        if clash:
            frappe.throw(
                _("{0} is already an active member of this cohort.").format(
                    frappe.bold(self.person)
                )
            )

    # ------------------------------------------------------------- eligibility

    def validate_leader_eligibility(self):
        """Who may lead is the type's rule, checked against this person."""
        if not self.is_leader or self.invite_status not in OPEN_STATUSES:
            return

        cohort_type = frappe.db.get_value("Cohort", self.cohort, "cohort_type")
        if not cohort_type:
            return
        policy = frappe.db.get_value(
            "Cohort Type",
            cohort_type,
            ["leader_eligibility", "program", "program_level"],
            as_dict=True,
        )
        rule = (policy or {}).get("leader_eligibility") or ANYONE
        if rule == ANYONE:
            return

        if rule == INSTRUCTOR and not self._is_active_instructor():
            self._refuse(rule, _("an active Instructor record"))
        elif rule == STAFF and not self._holds_a_staff_role():
            self._refuse(rule, _("a user account with a staff role"))
        elif rule == ALUMNUS and not self._is_alumnus_of(policy):
            self._refuse(
                rule,
                _("an enabled Alumni Profile for {0}").format(
                    frappe.bold(
                        policy.get("program")
                        or policy.get("program_level")
                        or _("any program")
                    )
                ),
            )

    def _refuse(self, rule, needed):
        frappe.throw(
            _(
                "{0} cannot lead this cohort: its type allows leaders who are "
                "{1}, and that needs {2}. Add them as a member instead, or "
                "change the type's Leader Eligibility."
            ).format(frappe.bold(self._person_label()), rule, needed)
        )

    def _person_label(self):
        return frappe.db.get_value("Person", self.person, "full_name") or self.person

    def _is_active_instructor(self):
        return bool(
            frappe.db.exists("Instructor", {"person": self.person, "status": "Active"})
        )

    def _holds_a_staff_role(self):
        """Staff is a role the person's user holds, not a separate record.

        `auth.STAFF_ROLES` is already the app's answer to "is this staff" -- the
        set that keeps someone out of a portal home on login -- and a second
        definition here is a second thing to keep in step.
        """
        from seminary.seminary.auth import STAFF_ROLES

        user = frappe.db.get_value("Person", self.person, "user")
        return bool(user and STAFF_ROLES & set(frappe.get_roles(user)))

    def _is_alumnus_of(self, policy):
        """An enabled Alumni Profile, of the bound program or of the level.

        An unbound type (no program, no level) asks only that they be an alumnus
        of somewhere: the type has said nothing about which program, and
        inventing one here would be policy this record is not allowed to make.
        """
        filters = {"person": self.person, "enabled": 1}
        if policy.get("program"):
            filters["program_completed"] = policy["program"]
        elif policy.get("program_level"):
            programs = frappe.get_all(
                "Program",
                filters={"program_level": policy["program_level"]},
                pluck="name",
            )
            if not programs:
                return False
            filters["program_completed"] = ("in", programs)
        return bool(frappe.db.exists("Alumni Profile", filters))
