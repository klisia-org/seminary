# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# A project has exactly two named reader slots (Second + Third Reader); further
# reviewers go on the committee.
MAX_NAMED_READERS = 2


class CulminatingProjectType(Document):
    def validate(self):
        if (self.readers_required or 0) > MAX_NAMED_READERS:
            frappe.throw(
                _(
                    "A project carries at most {0} named readers (Second and Third). "
                    "Set Readers Required to {0} or fewer; put additional reviewers on "
                    "the committee."
                ).format(MAX_NAMED_READERS)
            )
