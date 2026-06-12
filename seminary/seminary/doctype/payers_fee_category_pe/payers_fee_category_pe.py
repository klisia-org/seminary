# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import erpnext


class PayersFeeCategoryPE(Document):
    def validate(self):
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before:
            return
        if self._payer_rows_changed(before) and not (self.change_reason or "").strip():
            frappe.throw(
                _(
                    "Payer shares changed. Enter a Change reason before saving "
                    "(e.g. who requested the change and why)."
                )
            )

    def on_update(self):
        # Clear the reason after it's captured in the Version log, so the next
        # edit forces a fresh reason rather than re-using a stale one.
        if self.change_reason:
            frappe.db.set_value(
                self.doctype,
                self.name,
                "change_reason",
                "",
                update_modified=False,
            )

    def _payer_rows_changed(self, before):
        def sig(doc):
            return sorted(
                (r.fee_category, r.payer, float(r.pay_percent or 0), r.pep_event)
                for r in (doc.pf_payers or [])
            )

        return sig(self) != sig(before)

    @frappe.whitelist()
    def get_inv_data_pe(self):
        today = frappe.utils.today()
        company = frappe.db.get_single_value("Seminary Settings", "company")
        currency = erpnext.get_company_currency(company)
        receivable_account = frappe.db.get_single_value(
            "Seminary Settings", "receivable_account"
        )
        submittable = frappe.db.get_single_value(
            "Seminary Settings", "auto_submit_sales_invoice"
        )
        income_account = frappe.db.get_value(
            "Company", company, "default_income_account"
        )
        base_cost_center = (
            frappe.db.get_single_value("Seminary Settings", "cost_center") or None
        )
        stulink = self.stu_link
        pe_meta = (
            frappe.db.get_value(
                "Program Enrollment",
                self.pf_pe,
                ["program", "academic_term"],
                as_dict=True,
            )
            or frappe._dict()
        )
        program_label = pe_meta.program or ""
        academic_term = pe_meta.academic_term
        # The student's payer rows are billed against this customer; only those rows
        # get a scholarship applied (never church/other payers).
        student_customer = (
            frappe.db.get_value("Student", stulink, "customer") or stulink
        )

        rows = frappe.db.sql(
            """
            SELECT pep.name AS pep_name, pep.fee_category,
                   pep.payer AS customer, pep.pay_percent,
                   pep.payterm_payer, fc.item,
                   cg.default_price_list, ip.price_list_rate
            FROM `tabpgm_enroll_payers` pep
            INNER JOIN `tabPayers Fee Category PE` pfc ON pep.parent = pfc.name
            INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
            INNER JOIN `tabCustomer Group` cg ON pfc.pf_custgroup = cg.customer_group_name
            INNER JOIN `tabItem Price` ip
                    ON cg.default_price_list = ip.price_list AND ip.item_code = fc.item
            WHERE pfc.name = %s
              AND fc.docstatus = 1
              AND pep.pep_event = 'Program Enrollment'
            """,
            (self.name,),
            as_dict=True,
        )

        if not rows:
            # Nothing to bill. Distinguish "no PE rows at all" from "PE rows exist
            # but their Fee Categories aren't submitted" so the registrar knows
            # which to fix.
            unsubmitted = frappe.db.sql(
                """
                SELECT DISTINCT pep.fee_category, fc.docstatus
                FROM `tabpgm_enroll_payers` pep
                INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
                WHERE pep.parent = %s
                  AND pep.pep_event = 'Program Enrollment'
                  AND fc.docstatus != 1
                """,
                (self.name,),
                as_dict=True,
            )
            if unsubmitted:
                names = ", ".join(
                    f"{r.fee_category} (docstatus={r.docstatus})" for r in unsubmitted
                )
                frappe.throw(
                    _(
                        "No Sales Invoices were created. The following Fee Categories are not submitted: {0}. Submit them from the Fee Category list and try again."
                    ).format(names)
                )
            frappe.throw(
                _(
                    "No Sales Invoices were created. There are no active Program-Enrollment payer rows for this Payers Fee Category PE, or the matching Item Prices / Customer Groups are not configured."
                )
            )

        from seminary.seminary.billing import (
            create_scholarship_invoice,
            resolve_scholarship,
        )

        counts = {"created": 0, "skipped": 0, "failed": 0}
        for r in rows:
            tag = f"PE:{r.pep_name}"
            if frappe.db.exists(
                "Sales Invoice",
                {"seminary_trigger": tag, "docstatus": ["<", 2]},
            ):
                counts["skipped"] += 1
                continue

            # Scholarships are computed at invoice time and only ever reduce the
            # student's own line; the forgiveness is booked to a separate invoice.
            forgiven, award = 0, None
            if r.customer == student_customer:
                student_gross = round(
                    (r.pay_percent or 0) / 100 * (r.price_list_rate or 0), 2
                )
                forgiven, award = resolve_scholarship(
                    program_enrollment=self.pf_pe,
                    fee_category=r.fee_category,
                    student_gross=student_gross,
                    academic_term=academic_term,
                )

            summary = (
                _("Program Enrollment \u2014 {0} ({1})").format(
                    r.fee_category, program_label
                )
                if program_label
                else _("Program Enrollment \u2014 {0}").format(r.fee_category)
            )

            try:
                items = [
                    {
                        "doctype": "Sales Invoice Item",
                        "item_code": r.item,
                        "qty": (r.pay_percent or 0) / 100,
                        "rate": 0,
                        "description": summary,
                        "income_account": income_account,
                        "cost_center": base_cost_center,
                        "base_rate": 0,
                        "price_list_rate": r.price_list_rate,
                    }
                ]

                invoice_data = {
                    "doctype": "Sales Invoice",
                    "naming_series": "ACC-SINV-.YYYY.-",
                    "posting_date": today,
                    "company": company,
                    "currency": currency,
                    "debit_to": receivable_account,
                    "income_account": income_account,
                    "conversion_rate": 1,
                    "customer": r.customer,
                    "selling_price_list": r.default_price_list,
                    "base_grand_total": r.price_list_rate,
                    "payment_terms_template": r.payterm_payer,
                    "items": items,
                    "custom_student": stulink,
                    "seminary_trigger": tag,
                    "seminary_summary": summary,
                }
                if forgiven and award:
                    invoice_data["apply_discount_on"] = "Grand Total"
                    invoice_data["discount_amount"] = forgiven

                si = frappe.get_doc(invoice_data)
                si.run_method("set_missing_values")
                si.insert()
                if submittable == 1:
                    si.submit()
                counts["created"] += 1

                if forgiven and award:
                    create_scholarship_invoice(
                        award=award,
                        fee_category=r.fee_category,
                        academic_term=academic_term,
                        scope="PE",
                        forgiven=forgiven,
                        item_code=r.item,
                        selling_price_list=r.default_price_list,
                        payment_terms_template=r.payterm_payer,
                        summary=summary,
                        student=stulink,
                    )
            except Exception:
                counts["failed"] += 1
                frappe.log_error(frappe.get_traceback(), f"get_inv_data_pe tag {tag}")

        if counts["created"] == 0 and counts["failed"] > 0:
            frappe.throw(
                _(
                    "No Sales Invoices were created. {0} row(s) failed \u2014 see Error Log for details."
                ).format(counts["failed"])
            )
        return counts

    @frappe.whitelist()
    # Method to check if the sum of the percentages is equal to 100
    def check_percentages(self):
        pay_data = []
        pay_data = frappe.db.sql(
            """select pep.fee_category, sum(pep.pay_percent) as percentage
		from `tabpgm_enroll_payers` pep
		where pep.parent = %s
		group by pep.fee_category
		having percentage != 100""",
            self.name,
            as_list=1,
        )

        if pay_data:
            frappe.throw(
                "The sum of the percentages paid for a Fee Category is not equal to 100"
            )
