# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, get_link_to_form, today


class ProgramGraduationRequirement(Document):
    def validate(self):
        self._sync_lifecycle_fields()
        self._validate_date_window()
        self._validate_no_active_overlap()
        self._validate_linked_doc_status_values()

    def on_update_after_submit(self):
        self._spawn_successor_on_supersede()

    def _sync_lifecycle_fields(self):
        """`active` is derived from the workflow state, never set by hand.
        A policy is live only in the 'Active' state; retiring it (state
        'Superseded') clears the flag and stamps 'Active Until'. Drafts are
        inactive so they never collide with the live policy in
        _validate_no_active_overlap or get handed out by resolve_policy.
        """
        if not self.workflow_state:
            return
        if self.workflow_state == "Active":
            self.active = 1
        elif self.workflow_state == "Superseded":
            self.active = 0
            if not self.active_until:
                self.active_until = today()
        else:  # Draft or any other intermediate state
            self.active = 0

    def _spawn_successor_on_supersede(self):
        """When this policy enters 'Superseded' via the 'Change Version'
        action, spawn a Draft clone for the registrar to edit and submit.
        Idempotent: guarded by `superseded_by`. The doc is never cancelled,
        so back-links from submitted Program Enrollments stay valid.
        """
        if self.workflow_state != "Superseded" or self.superseded_by:
            return

        # Retire in place. `active`/`active_until` aren't allow_on_submit, so a
        # validate-time assignment is dropped on a submitted-doc save — persist
        # the retirement directly. The doc is never cancelled, so back-links
        # from submitted Program Enrollments stay valid.
        self.db_set("active", 0, update_modified=False)
        if not self.active_until:
            self.db_set("active_until", today(), update_modified=False)

        successor = frappe.copy_doc(self)
        successor.workflow_state = "Draft"
        successor.active = 0
        successor.active_from = add_days(today(), 1)
        successor.active_until = None
        successor.supersedes = self.name
        successor.insert(ignore_permissions=True)

        self.db_set("superseded_by", successor.name, update_modified=False)
        frappe.msgprint(
            _(
                "Draft version {0} created. Edit and submit it to activate the new policy."
            ).format(get_link_to_form(self.doctype, successor.name)),
            indicator="green",
            alert=True,
        )

    def _validate_date_window(self):
        if (
            self.active_from
            and self.active_until
            and self.active_until < self.active_from
        ):
            frappe.throw(_("Active Until cannot be earlier than Active From."))

    def _validate_no_active_overlap(self):
        if not self.active or not self.program_name:
            return

        filters = {
            "program_name": self.program_name,
            "active": 1,
            "name": ("!=", self.name or ""),
        }
        others = frappe.get_all(
            "Program Graduation Requirement",
            filters=filters,
            fields=["name", "active_from", "active_until"],
        )

        for other in others:
            if _windows_overlap(
                self.active_from,
                self.active_until,
                other.active_from,
                other.active_until,
            ):
                frappe.throw(
                    _(
                        "Active date window overlaps with {0}. "
                        "Two policies for the same program cannot be active simultaneously."
                    ).format(other.name)
                )

    def _validate_linked_doc_status_values(self):
        """Catch typos in linked_doc_status at policy authoring time."""
        for row in self.pgr_items or []:
            if row.activation_mode != "On Document Status":
                continue
            if not row.on_document or not row.linked_doc_status:
                continue
            if not _status_value_exists(row.on_document, row.linked_doc_status):
                frappe.throw(
                    _(
                        "Row {0}: '{1}' is not a valid workflow_state or status value on {2}."
                    ).format(row.idx, row.linked_doc_status, row.on_document)
                )


def _windows_overlap(a_start, a_end, b_start, b_end):
    """Closed-interval overlap with open ends (None means open-ended)."""
    if a_end and b_start and a_end < b_start:
        return False
    if b_end and a_start and b_end < a_start:
        return False
    return True


def _status_value_exists(doctype, value):
    """Check value exists as a Workflow State or as a Select option on workflow_state/status."""
    workflow_name = frappe.db.get_value(
        "Workflow", {"document_type": doctype, "is_active": 1}, "name"
    )
    if workflow_name:
        states = frappe.get_all(
            "Workflow Document State",
            filters={"parent": workflow_name},
            pluck="state",
        )
        if value in states:
            return True

    meta = frappe.get_meta(doctype)
    for fieldname in ("workflow_state", "status"):
        field = meta.get_field(fieldname)
        if field and field.fieldtype == "Select" and field.options:
            if value in [
                opt.strip() for opt in field.options.split("\n") if opt.strip()
            ]:
                return True

    return False
