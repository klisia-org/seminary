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
    discount_amount=0,
    seminary_trigger=None,
    scholarship_cost_center=None,
):
    """Create (and optionally submit) one Sales Invoice for a single payer.

    Mirrors the invoice built by Course Enrollment Individual.get_inv_data_ce:
    line rate is 0 with price_list_rate carrying the amount, scholarship payers
    get a 100% discount and the scholarship cost center. `link_field` lets the
    caller stamp a back-reference (e.g. custom_cei) onto the invoice.

    `discount_amount` applies an absolute discount on the student's invoice (used
    to net out a scholarship award computed at invoice time). `seminary_trigger`
    stamps an idempotency tag (e.g. the SCH:<award>:<fee>:<term>:<scope> tag on the
    forgiveness invoice).
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
        cost_center = scholarship_cost_center or sch_cost_center
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
    if discount_amount:
        invoice_data["apply_discount_on"] = "Grand Total"
        invoice_data["discount_amount"] = discount_amount
    if seminary_trigger:
        invoice_data["seminary_trigger"] = seminary_trigger
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


def _scholarship_flat_consumed(award, fee_category, academic_term):
    """Sum of what a flat award has already forgiven for one fee category in one
    term, read from the forgiveness invoices themselves (self-healing: cancel an
    invoice and the budget frees up). Tags are SCH:<award>:<fee>:<term>:<scope>."""
    sch_customer = frappe.db.get_single_value("Seminary Settings", "scholarship_cust")
    prefix = f"SCH:{award}:{fee_category}:{academic_term}:%"
    consumed = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sii.price_list_rate * sii.qty), 0)
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.customer = %s AND si.docstatus < 2
          AND si.seminary_trigger LIKE %s
        """,
        (sch_customer, prefix),
    )
    return float(consumed[0][0] or 0) if consumed else 0.0


def resolve_scholarship(
    *, program_enrollment, fee_category, student_gross, academic_term
):
    """Return ``(forgiven_amount, award_name)`` for the student's share of one fee
    category, or ``(0, None)`` when no active award covers it.

    Percent terms forgive a proportion of the student's gross; Flat terms forgive a
    fixed currency amount **capped per academic term** (so a flat award billed across
    several course invoices in a term is never over-applied). The student keeps their
    full payer percentage — the scholarship is computed here, not baked into payer
    rows. Only ever call this for the student's own payer line.
    """
    from seminary.seminary.doctype.scholarship_award.scholarship_award import (
        get_active_award,
    )

    student_gross = round(float(student_gross or 0), 2)
    if student_gross <= 0:
        return 0, None
    award = get_active_award(program_enrollment)
    if not award:
        return 0, None
    term = frappe.db.get_value(
        "Scholarship Award Term",
        {"parent": award, "fee_category": fee_category},
        ["mode", "value"],
        as_dict=True,
    )
    if not term:
        return 0, award
    value = float(term.value or 0)
    if value <= 0:
        return 0, award
    if term.mode == "Flat":
        consumed = _scholarship_flat_consumed(award, fee_category, academic_term)
        remaining = max(value - consumed, 0)
        forgiven = min(remaining, student_gross)
    else:  # Percent
        forgiven = student_gross * value / 100
    forgiven = min(round(forgiven, 2), student_gross)
    return (forgiven if forgiven > 0 else 0), award


def create_scholarship_invoice(
    *,
    award,
    fee_category,
    academic_term,
    scope,
    forgiven,
    item_code,
    selling_price_list,
    payment_terms_template,
    summary,
    student,
    link_field=None,
    link_value=None,
):
    """Create the forgiveness Sales Invoice (to the scholarship customer, booked to
    the scholarship cost center, 100% discounted) for a resolved award amount.

    `scope` segments the idempotency tag: 'PE' for the Program-Enrollment event, the
    CEI name for course enrollment, 'EXT' for culminating-project extensions.
    """
    tag = f"SCH:{award}:{fee_category}:{academic_term}:{scope}"
    if frappe.db.exists(
        "Sales Invoice", {"seminary_trigger": tag, "docstatus": ["<", 2]}
    ):
        return None
    return build_and_create_invoice(
        customer=frappe.db.get_single_value("Seminary Settings", "scholarship_cust"),
        item_code=item_code,
        qty=1,
        price_list_rate=forgiven,
        selling_price_list=selling_price_list,
        payment_terms_template=payment_terms_template,
        summary=summary,
        student=student,
        link_field=link_field,
        link_value=link_value,
        is_scholarship=True,
        seminary_trigger=tag,
        scholarship_cost_center=_scholarship_cost_center_for_award(award),
    )


def _scholarship_cost_center_for_award(award):
    """The cost center the forgiveness should book to: the scholarship template's
    own cost center when set, else the global Seminary Settings default."""
    scholarship = frappe.db.get_value("Scholarship Award", award, "scholarship")
    cc = scholarship and frappe.db.get_value("Scholarships", scholarship, "cost_center")
    return cc or frappe.db.get_single_value("Seminary Settings", "scholarship_cc")


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
        """select pep.payer, pep.fee_category, pep.pay_percent, pep.payterm_payer,
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

    student_customer = frappe.db.get_value("Student", student, "customer") or student
    academic_term = frappe.db.get_value(
        "Program Enrollment", program_enrollment, "academic_term"
    )
    created = []
    for payer in payers:
        # Flat charge of the configured fee, split by the payer's share.
        line_qty = (payer.pay_percent or 0) / 100
        forgiven, award = 0, None
        if payer.payer == student_customer:
            forgiven, award = resolve_scholarship(
                program_enrollment=program_enrollment,
                fee_category=payer.fee_category,
                student_gross=round(line_qty * (payer.price_list_rate or 0), 2),
                academic_term=academic_term,
            )
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
                discount_amount=(forgiven if (forgiven and award) else 0),
            )
        )
        if forgiven and award:
            sch = create_scholarship_invoice(
                award=award,
                fee_category=payer.fee_category,
                academic_term=academic_term,
                scope="EXT",
                forgiven=forgiven,
                item_code=payer.item,
                selling_price_list=payer.default_price_list,
                payment_terms_template=payer.payterm_payer,
                summary=summary,
                student=student,
            )
            if sch:
                created.append(sch)
    return created
