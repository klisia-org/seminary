# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Child table: a mentor assigned to a student for part or all of a program.

Rows are appended and closed with a To Date rather than deleted, so a mid-program
mentor change leaves a trail. Row logic lives on the parent per ADR 023.
"""

from frappe.model.document import Document


class ProgramEnrollmentMentor(Document):
    pass
