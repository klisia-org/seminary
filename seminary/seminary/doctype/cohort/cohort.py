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
        self._apply_type_defaults()

    def _apply_type_defaults(self):
        if not self.cohort_type:
            return
        ct = frappe.get_cached_doc("Cohort Type", self.cohort_type)
        if not self.visibility:
            self.visibility = ct.default_visibility or "cohort_only"
        if not self.max_size and ct.default_max_size:
            self.max_size = ct.default_max_size

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
