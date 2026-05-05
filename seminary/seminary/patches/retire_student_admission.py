"""Retire the Student Admission / Student Admission Program doctypes.

Replaced by the per-Academic-Term `Term Admission` flow, with per-program
enrollment cadence (Continuous vs Timed) declared on Program. Existing
Student Applicant records carried a now-meaningless `student_admission`
link and a chunk of legacy admission config disappears with the doctypes.

Steps:
1. Null out the legacy `student_admission` column on Student Applicant if
   it still exists (the field has been removed from the doctype JSON, but
   Frappe leaves the column behind for safety).
2. Delete every Student Admission and Student Admission Program record so
   the doctype tables drop cleanly when the JSON files are removed.

Idempotent.
"""

import frappe


def execute():
    if frappe.db.has_column("Student Applicant", "student_admission"):
        frappe.db.sql("UPDATE `tabStudent Applicant` SET student_admission = NULL")
        print("Cleared student_admission on Student Applicant.")

    if frappe.db.exists("DocType", "Student Admission Program"):
        frappe.db.sql("DELETE FROM `tabStudent Admission Program`")
        print("Cleared Student Admission Program records.")

    if frappe.db.exists("DocType", "Student Admission"):
        frappe.db.sql("DELETE FROM `tabStudent Admission`")
        print("Cleared Student Admission records.")

    frappe.db.commit()
