# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class WebMeetingAccount(Document):
    def validate(self):
        from seminary.seminary.school_meetings import providers

        if self.provider not in providers():
            frappe.throw(
                _("No installed app offers meetings on {0}.").format(self.provider)
            )
        self.host_id = (self.host_id or "").strip()
        if cint(self.max_concurrent) < 1:
            self.max_concurrent = 1
