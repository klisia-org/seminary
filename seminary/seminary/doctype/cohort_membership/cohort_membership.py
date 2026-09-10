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
ANY_ALUMNUS = "Any alumnus"
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
        self._guard_lineage_limit()
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

    def _guard_lineage_limit(self):
        """How many cohorts of one type a person may be in at once.

        Counted by lineage, not by cohort: a cohort and everything split off
        from it are one commitment, made once, and a group that multiplies
        should not gradually use up its members' allowance. `Cohort.lineage_root`
        already says this -- a root cohort is its own root -- so the question is
        just how many distinct roots the person is open in.

        Two things this deliberately does not do. It does not exempt staff: a
        size ceiling is advice about a room, but being mentored in two places at
        once is either the school's policy or it isn't, and a registrar in the
        desk is not better placed to decide that than the type is. And it does
        not re-check a membership that is already open, so lowering the setting
        never makes an existing row unsaveable while somebody edits it for an
        unrelated reason -- it applies as people are added, and what already
        stands, stands.
        """
        if self.invite_status not in OPEN_STATUSES:
            return
        before = self.get_doc_before_save()
        if before and before.invite_status in OPEN_STATUSES:
            return

        others = lineages_that_would_block(self.person, self.cohort, ignoring=self.name)
        if others is None:
            return

        frappe.throw(
            _(
                "{0} is already in {1} of these, which is as many as this kind of "
                "cohort allows at one time. Close the other membership first, or "
                "raise Cohorts Per Member on {2}."
            ).format(
                frappe.bold(self._person_label()),
                len(others),
                frappe.bold(
                    frappe.db.get_value("Cohort", self.cohort, "cohort_type") or ""
                ),
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
        elif rule == ANY_ALUMNUS and not self._alumni_profile():
            self._refuse(rule, _("an enabled Alumni Profile"))
        elif rule == ALUMNUS and not self._is_alumnus_of(policy):
            self._refuse(rule, self._alumnus_of_what(policy))

    def _alumnus_of_what(self, policy):
        """What the bound-alumnus rule was asking for, in the type's own terms."""
        bound = policy.get("program") or policy.get("program_level")
        if bound:
            return _("an enabled Alumni Profile for {0}").format(frappe.bold(bound))
        # The type is refused at save without a binding, so reaching this means
        # one was edited around validation. Say that, rather than name a program
        # there isn't one of.
        return _(
            "an enabled Alumni Profile for the program this type binds to -- and "
            "it binds to none, which its Leader Eligibility no longer allows"
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

    def _alumni_profile(self):
        return alumni_profile(self.person)

    def _is_alumnus_of(self, policy):
        return is_alumnus_of_bound(self.person, policy)


# ------------------------------------------------------------------ the rules
#
# Module level, because the portal has to ask the same questions *before* the
# fact -- which cohort types may this person start, which buttons should they be
# shown -- and a second implementation of "is this person an alumnus of that" is
# a second implementation that can drift from the one that refuses the save.


def lineages_that_would_block(person, cohort, ignoring=None):
    """The other cohort families of this type standing in this person's way.

    `None` when nothing does -- the type sets no limit, they are already in this
    family, or they are still under it. A set otherwise, so the caller can say
    how many. Shared rather than inlined because reactivating an archived cohort
    has to ask the same question *before* reopening a membership: a person freed
    by the archiving may have joined another group since, and finding that out
    by catching the refusal would leave a half-restored cohort behind.
    """
    row = frappe.db.get_value(
        "Cohort", cohort, ["cohort_type", "lineage_root"], as_dict=True
    )
    if not row:
        return None
    limit = (
        frappe.db.get_value("Cohort Type", row.cohort_type, "max_lineages_per_member")
        or 0
    )
    if not limit:
        return None

    # `lineage_root` is written in `Cohort.after_insert`, and the leader's own
    # membership is created there too -- after it is set, so this reads a real
    # root. Falling back to the cohort itself keeps a half-built record from
    # silently counting as everyone else's lineage.
    mine = row.lineage_root or cohort
    others = {
        r.lineage_root or r.name
        for r in frappe.db.sql(
            """
            SELECT c.name, c.lineage_root
            FROM `tabCohort Membership` m
            JOIN `tabCohort` c ON c.name = m.cohort
            WHERE m.person = %(person)s
              AND c.cohort_type = %(cohort_type)s
              AND m.invite_status IN %(open)s
              AND m.name != %(ignoring)s
            """,
            {
                "person": person,
                "cohort_type": row.cohort_type,
                "open": OPEN_STATUSES,
                "ignoring": ignoring or "",
            },
            as_dict=True,
        )
    }
    if mine in others or len(others) < limit:
        return None
    return others


def alumni_profile(person):
    """A graduate of this school, of nowhere in particular."""
    return frappe.db.get_value("Alumni Profile", {"person": person, "enabled": 1})


def is_alumnus_of_bound(person, policy):
    """An enabled Alumni Profile, of the bound program or of the level.

    An unbound type is refused rather than waved through. It used to return True
    -- the type had named no program, so any alumnus passed -- which read as
    leniency but was really a policy decision this record is not allowed to
    make. A school that means it now says so on the type, with `Any alumnus`.
    """
    profile = alumni_profile(person)
    if not profile:
        return False

    # Completed programs are rows, not a field — a graduate with two degrees
    # used to be an alumnus of only whichever one happened to be stored, which
    # silently withheld leadership of a cohort scoped to the other (ADR 069).
    if policy.get("program"):
        programs = [policy["program"]]
    elif policy.get("program_level"):
        programs = frappe.get_all(
            "Program",
            filters={"program_level": policy["program_level"]},
            pluck="name",
        )
    else:
        return False
    if not programs:
        return False
    return bool(
        frappe.db.exists(
            "Alumni Graduation",
            {
                "parenttype": "Alumni Profile",
                "parent": profile,
                "program": ("in", programs),
            },
        )
    )


def may_lead(person, policy):
    """Does this person satisfy an alumnus leadership rule?

    Only the two alumnus rules; the others are asked of a record that exists.
    """
    rule = (policy or {}).get("leader_eligibility")
    if rule == ANY_ALUMNUS:
        return bool(alumni_profile(person))
    if rule == ALUMNUS:
        return is_alumnus_of_bound(person, policy)
    return False
