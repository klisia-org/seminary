# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One matching rule on a Cohort Type, and where it comes in the order.

`idx` *is* the precedence, which is why this is a child Table and not a Table
MultiSelect: two rankings are only meaningful in an order, and a MultiSelect
neither shows one nor preserves it stably (ADR 067 section 8).
"""

from frappe.model.document import Document


class CohortTypeCriterion(Document):
    pass
