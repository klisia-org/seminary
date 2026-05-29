# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Shared fee-billing helpers.

The Sales-Invoice construction core is extracted here so every fee-charging
path (Course Enrollment Individual, Culminating Project Extension, ...) builds
invoices the same way. Payer resolution (who pays which share) still lives with
each caller because the join filters differ per event; this module owns the
"given one payer line, create the invoice" step (ADR 024).
"""

import erpnext
import frappe
from frappe import _


def build_and_create_invoice(
    *,
    customer,
    item_code,
    qty,
    price_list_rate,
    selling_price_list,
    payment_terms_template,
    summary,
    student,
    link_field=None,
    link_value=None,
    is_scholarship=False,
):
    """Create (and optionally submit) one Sales Invoice for a single payer.

    Mirrors the invoice built by Course Enrollment Individual.get_inv_data_ce:
    line rate is 0 with price_list_rate carrying the amount, scholarship payers
    get a 100% discount and the scholarship cost center. `link_field` lets the
    caller stamp a back-reference (e.g. custom_cei) onto the invoice.
    """
    company = frappe.defaults.get_defaults().company
    currency = erpnext.get_company_currency(company)
    receivable_account = frappe.db.get_single_value(
        "Seminary Settings", "receivable_account"
    )
    income_account = frappe.db.get_value("Company", company, "default_income_account")
    cost_center = frappe.db.get_single_value("Seminary Settings", "cost_center") or None
    sch_cost_center = frappe.db.get_single_value("Seminary Settings", "scholarship_cc")
    submit_invoice = frappe.db.get_single_value(
        "Seminary Settings", "auto_submit_sales_invoice"
    )

    if is_scholarship:
        cost_center = sch_cost_center
    discount = 100 if is_scholarship else 0
    grand_total = (qty or 0) * (price_list_rate or 0)

    invoice_data = {
        "doctype": "Sales Invoice",
        "naming_series": "ACC-SINV-.YYYY.-",
        "posting_date": frappe.utils.today(),
        "company": company,
        "currency": currency,
        "debit_to": receivable_account,
        "income_account": income_account,
        "conversion_rate": 1,
        "customer": customer,
        "selling_price_list": selling_price_list,
        "base_grand_total": grand_total,
        "payment_terms_template": payment_terms_template,
        "remarks": summary,
        "items": [
            {
                "doctype": "Sales Invoice Item",
                "item_code": item_code,
                "qty": qty,
                "rate": 0,
                "description": summary,
                "income_account": income_account,
                "cost_center": cost_center,
                "base_rate": 0,
                "price_list_rate": price_list_rate,
            }
        ],
        "cost_center": cost_center,
        "custom_student": student,
        "additional_discount_percentage": discount,
        "seminary_summary": summary,
    }
    if link_field:
        invoice_data[link_field] = link_value

    sales_invoice = frappe.get_doc(invoice_data)
    # System-authored on the payer's behalf, so bypass docperms here.
    sales_invoice.flags.ignore_permissions = True
    sales_invoice.insert()
    sales_invoice.save()
    if submit_invoice == 1:
        sales_invoice.submit()
    return sales_invoice.name


def create_extension_invoices(program_enrollment, student, summary):
    """Bill whatever Fee Category is wired to the 'Culminating Project Extension'
    event to the program enrollment's configured payers.

    The fee is fully driven by configuration: the Fee Category carrying the
    'Culminating Project Extension' trigger and the Payers Fee Category PE split
    keyed to that event — there is no per-extension fee or quantity. Reuses the
    same payer split as course enrollment, but creates NO Program Enrollment
    Course row, so extensions never affect credits, grade, GPA, or transcript.
    Returns the list of created Sales Invoice names.
    """
    payers = frappe.db.sql(
        """select pep.payer, pep.pay_percent, pep.payterm_payer,
                  cg.default_price_list, ip.price_list_rate, fc.item
           from `tabpgm_enroll_payers` pep,
                `tabPayers Fee Category PE` pfc,
                `tabFee Category` fc,
                `tabCustomer Group` cg,
                `tabItem Price` ip
           where pfc.pf_pe = %s and
                 pep.parent = pfc.name and
                 pep.fee_category = fc.name and
                 pep.pep_event = 'Culminating Project Extension' and
                 pfc.pf_custgroup = cg.customer_group_name and
                 cg.default_price_list = ip.price_list and
                 ip.item_code = fc.item""",
        (program_enrollment,),
        as_dict=True,
    )

    if not payers:
        frappe.throw(
            _(
                "No payer is configured for the 'Culminating Project Extension' "
                "event on this enrollment. Configure a Fee Category with that "
                "trigger and add a payer row (Payers Fee Category PE) for it first."
            )
        )

    sch_customer = frappe.db.get_single_value("Seminary Settings", "scholarship_cust")
    created = []
    for payer in payers:
        # Flat charge of the configured fee, split by the payer's share.
        line_qty = (payer.pay_percent or 0) / 100
        created.append(
            build_and_create_invoice(
                customer=payer.payer,
                item_code=payer.item,
                qty=line_qty,
                price_list_rate=payer.price_list_rate,
                selling_price_list=payer.default_price_list,
                payment_terms_template=payer.payterm_payer,
                summary=summary,
                student=student,
                is_scholarship=payer.payer == sch_customer,
            )
        )
    return created
