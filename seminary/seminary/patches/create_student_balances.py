# Copyright (c) 2026, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt

"""One-time migration: create Student Balance docs for existing students
and populate them with their outstanding invoices.

Run via: bench execute seminary.seminary.patches.create_student_balances.execute
"""

import frappe
from frappe.utils import flt, nowdate


def execute():
    settings = frappe.get_cached_doc("Seminary Settings")
    company = settings.get("company") or frappe.defaults.get_defaults().get("company")
    if not company:
        print("No company configured in Seminary Settings or defaults. Aborting.")
        return

    currency = frappe.db.get_value("Company", company, "default_currency")

    students = frappe.get_all("Student", fields=["name", "customer"])
    created = 0
    skipped = 0

    for student in students:
        # Skip if already has an open balance
        existing = frappe.db.get_value(
            "Student Balance",
            {"student": student.name, "is_open": 1},
            "name",
        )
        if existing:
            skipped += 1
            continue

        sb = frappe.new_doc("Student Balance")
        sb.update(
            {
                "student": student.name,
                "customer": student.customer,
                "company": company,
                "currency": currency,
                "posting_date": nowdate(),
                "is_open": 1,
                "status": "Open",
            }
        )

        # Get all submitted invoices for this student
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"custom_student": student.name, "docstatus": 1},
            fields=[
                "name",
                "posting_date",
                "due_date",
                "grand_total",
                "outstanding_amount",
                "is_return",
                "return_against",
            ],
        )

        for inv in invoices:
            # Only include invoices with outstanding balance or credit notes
            if flt(inv.outstanding_amount) != 0 or inv.is_return:
                sb.append(
                    "invoices",
                    {
                        "sales_invoice": inv.name,
                        "posting_date": inv.posting_date,
                        "due_date": inv.due_date,
                        "grand_total": inv.grand_total,
                        "outstanding_amount": inv.outstanding_amount,
                        "allocated_amount": 0,
                        "is_return": inv.is_return,
                        "return_against": inv.return_against,
                    },
                )

        sb.insert(ignore_permissions=True)
        created += 1

    frappe.db.commit()
    print(
        f"Created {created} Student Balance docs. Skipped {skipped} (already existed)."
    )
