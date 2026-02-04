# Copyright (c) 2025, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    scholarship_cc = frappe.db.get_single_value("Seminary Settings", "scholarship_cc")
    sch_payer = frappe.db.get_single_value("Seminary Settings", "scholarship_cust")
    columns = [
        {
            "fieldname": "Customer",
            "label": "Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 200,
        },
        {
            "fieldname": "Invoice",
            "label": "Invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 200,
        },
        {
            "fieldname": "Income",
            "label": "Income",
            "fieldtype": "Currency",
            "width": 200,
        },
        {
            "fieldname": "Expenditure",
            "label": "Expenditure",
            "fieldtype": "Currency",
            "width": 200,
        },
        {"fieldname": "Date", "label": "Date", "fieldtype": "Date", "width": 200},
    ]

    # Set default date filters if not provided
    if not filters:
        filters = {}
    start_date = filters.get("start_date", "1900-01-01")
    end_date = filters.get("end_date", "2100-12-31")

    si_data = frappe.db.sql(
        """
		select si.customer as Customer, si.name as Invoice, 0 as Income, (-1 * si.base_total) as Expenditure, si.posting_date as Date
		from `tabSales Invoice` si
		where si.cost_center = %s and si.customer = %s and si.posting_date between %s and %s
		UNION
		select si.customer as Customer, si.name as Invoice, si.base_total as Income, 0 as Expenditure, si.posting_date as Date
		from `tabSales Invoice` si
		where si.cost_center = %s and si.customer != %s and si.posting_date between %s and %s
	""",
        (
            scholarship_cc,
            sch_payer,
            start_date,
            end_date,
            scholarship_cc,
            sch_payer,
            start_date,
            end_date,
        ),
        as_list=1,
    )

    return columns, si_data
