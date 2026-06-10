# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.communication_triggers import clear_trigger_cache


class CommunicationTrigger(Document):
    def validate(self):
        meta = frappe.get_meta(self.reference_doctype)
        for cond in self.conditions:
            if not meta.get_field(cond.fieldname) and cond.fieldname not in (
                "name",
                "owner",
                "docstatus",
            ):
                frappe.throw(
                    _("Condition field {0} does not exist on {1}.").format(
                        cond.fieldname, self.reference_doctype
                    )
                )
        for r in self.recipients:
            if r.recipient_type == "Document Field" and not meta.get_field(
                r.document_field
            ):
                frappe.throw(
                    _("Recipient field {0} does not exist on {1}.").format(
                        r.document_field, self.reference_doctype
                    )
                )
            template = frappe.get_doc("Communication Template", self.template)
            if not template.get_version(r.channel):
                frappe.throw(
                    _("Template {0} has no version for channel {1}.").format(
                        self.template, r.channel
                    )
                )

    def on_update(self):
        clear_trigger_cache()

    def on_trash(self):
        clear_trigger_cache()
