# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.api import sanitize_html


class CohortPostComment(Document):
    def validate(self):
        if self.content:
            self.content = sanitize_html(self.content)
        if self.parent_comment:
            parent_post = frappe.db.get_value(
                "Cohort Post Comment", self.parent_comment, "post"
            )
            if parent_post != self.post:
                frappe.throw(_("A reply must stay on the same post as its parent."))

    def after_insert(self):
        frappe.publish_realtime(
            "cohort_thread_update",
            {"post": self.post, "comment": self.name},
            after_commit=True,
        )
