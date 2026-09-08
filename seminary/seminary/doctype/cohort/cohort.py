# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class Cohort(Document):
    def validate(self):
        if self.parent_cohort and self.parent_cohort == self.name:
            frappe.throw(_("A cohort cannot be its own parent."))
        self._guard_inactive_type()
        self._apply_type_defaults()

    def _guard_inactive_type(self):
        """A deactivated type stops producing cohorts (ADR 066 section 7.7).

        Only on creation. Deactivating a type is how a school retires a kind of
        cohort -- and the students already in one are mid-relationship, so their
        cohorts keep working, keep their leaders and keep their channels. What
        stops is the making of new ones.
        """
        if not self.is_new() or not self.cohort_type:
            return
        if frappe.db.get_value("Cohort Type", self.cohort_type, "is_active"):
            return
        frappe.throw(
            _(
                "Cohort Type {0} is not active, so no new cohorts of it may be "
                "created. Reactivate it, or choose another type. Cohorts that "
                "already exist are unaffected."
            ).format(frappe.bold(self.cohort_type))
        )

    def _apply_type_defaults(self):
        if not self.cohort_type:
            return
        ct = frappe.get_cached_doc("Cohort Type", self.cohort_type)
        if not self.visibility:
            self.visibility = ct.default_visibility or "cohort_only"
        if not self.max_size:
            # The portal limit stands in when no size was suggested, so a cohort
            # the portal will refuse to grow says so on its face instead of
            # showing no ceiling until someone hits one.
            self.max_size = ct.default_max_size or ct.portal_size_limit or 0

    def on_update(self):
        """Archiving is a lifecycle event, not a flag, so it has consequences.

        On the Cohort rather than in the portal API because a chair flipping
        Status in the desk is doing the same thing as a leader pressing Archive,
        and a rule that only one of them passes through is not a rule.
        """
        before = self.get_doc_before_save()
        if not before or before.status == self.status:
            return
        if self.status == "Archived":
            self._release_members()
        elif before.status == "Archived" and self.status == "Active":
            self._restore_members()

    def _release_members(self):
        """End the memberships of a cohort that has ended, where the type says so.

        Everyone, the leader included -- unlike a student's withdrawal, which
        leaves the leader in place because the cohort still needs one. An
        archived cohort needs nobody, and the leader is precisely the person who
        must be free to begin again.
        """
        from seminary.seminary.doctype.cohort_type.cohort_type import (
            releases_on_archive,
        )
        from seminary.seminary.doctype.cohort_membership.cohort_membership import (
            OPEN_STATUSES,
        )

        if not releases_on_archive(self.cohort_type):
            return
        for name in frappe.get_all(
            "Cohort Membership",
            filters={"cohort": self.name, "invite_status": ["in", list(OPEN_STATUSES)]},
            pluck="name",
        ):
            row = frappe.get_doc("Cohort Membership", name)
            row.invite_status = "Left"
            row.closed_by_archive = 1
            row.flags.ignore_permissions = True
            row.save()

    def _restore_members(self):
        """Reactivating is the way back, so it has to actually lead back.

        Only the memberships this cohort's own archiving closed -- somebody who
        had left before it was archived left for their own reasons, and
        reopening the group is not an invitation to them.

        Anyone who has joined another cohort of this type in the meantime is
        left closed rather than restored: they made a newer commitment, and the
        type's own limit says they may not hold both. Asked before the write,
        not discovered by catching the refusal, so the cohort never comes back
        half-restored.
        """
        from seminary.seminary.doctype.cohort_membership.cohort_membership import (
            lineages_that_would_block,
        )

        blocked = []
        for name in frappe.get_all(
            "Cohort Membership",
            filters={"cohort": self.name, "closed_by_archive": 1},
            pluck="name",
        ):
            row = frappe.get_doc("Cohort Membership", name)
            if lineages_that_would_block(row.person, self.name, ignoring=row.name):
                blocked.append(row.person)
                continue
            row.invite_status = "Active"
            row.left_on = None
            row.closed_by_archive = 0
            row.flags.ignore_permissions = True
            row.save()

        if blocked:
            names = [
                frappe.db.get_value("Person", p, "full_name") or p for p in blocked
            ]
            frappe.msgprint(
                _(
                    "{0} joined another cohort of this type while this one was "
                    "archived, so they were not put back. Invite them again if "
                    "they should return."
                ).format(frappe.bold(", ".join(sorted(names)))),
                indicator="orange",
            )

    def after_insert(self):
        # Denormalize lineage once, immutably: a root cohort is its own root at
        # distance 0; a split-off child inherits its parent's root and sits one
        # generation deeper. Makes "this whole cohort family" a single filtered
        # query, sortable by depth (ADR 064).
        if self.parent_cohort:
            parent = frappe.db.get_value(
                "Cohort",
                self.parent_cohort,
                ["lineage_root", "root_distance"],
                as_dict=True,
            )
            root = parent.lineage_root
            distance = (parent.root_distance or 0) + 1
        else:
            root = self.name
            distance = 0
        self.db_set("lineage_root", root, update_modified=False)
        self.db_set("root_distance", distance, update_modified=False)
        self._ensure_leader_membership()

    def _ensure_leader_membership(self):
        """The leader is always an active, leading member of their own cohort."""
        if not self.leader:
            return
        if frappe.db.exists(
            "Cohort Membership",
            {"cohort": self.name, "person": self.leader, "active": 1},
        ):
            return
        frappe.get_doc(
            {
                "doctype": "Cohort Membership",
                "cohort": self.name,
                "person": self.leader,
                "role": "Mentor",
                "is_leader": 1,
                "invite_status": "Active",
                "active": 1,
                "joined_on": today(),
            }
        ).insert(ignore_permissions=True)
