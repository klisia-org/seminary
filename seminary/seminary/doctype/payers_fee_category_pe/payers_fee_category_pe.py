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
        sch_cost_center = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cc"
        )
        sch_customer = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cust"
        )
        stulink = self.stu_link
        program_label = (
            frappe.db.get_value("Program Enrollment", self.pf_pe, "program") or ""
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

        counts = {"created": 0, "skipped": 0, "failed": 0}
        for r in rows:
            tag = f"PE:{r.pep_name}"
            if frappe.db.exists(
                "Sales Invoice",
                {"seminary_trigger": tag, "docstatus": ["<", 2]},
            ):
                counts["skipped"] += 1
                continue

            is_scholarship = r.customer == sch_customer
            cost_center = sch_cost_center if is_scholarship else base_cost_center
            discount = 100 if is_scholarship else 0

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
                        "cost_center": cost_center,
                        "base_rate": 0,
                        "price_list_rate": r.price_list_rate,
                    }
                ]

                si = frappe.get_doc(
                    {
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
                        "additional_discount_percentage": discount,
                        "seminary_trigger": tag,
                        "seminary_summary": summary,
                    }
                )
                si.run_method("set_missing_values")
                si.insert()
                if submittable == 1:
                    si.submit()
                counts["created"] += 1
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

    @frappe.whitelist()
    def add_scholarship(self):
        print("Add Scholarship called")
        program_enrollment = self.pf_pe
        student = self.pf_student
        scholarship = self.scholarship

        # Fetch scholarship payer
        sch_payer = frappe.db.sql(
            """Select value from `tabSingles` where doctype = 'Seminary Settings' and field = 'scholarship_cust'""",
            as_list=1,
        )
        sch_payer = sch_payer[0][0] if sch_payer else None
        print("Scholarship payer:", sch_payer)
        if not sch_payer:
            frappe.throw("Scholarship payer not found in Seminary Settings")

        if scholarship:
            print("Scholarship exists:", scholarship)
            self.add_comment("Info", _("Scholarship {0} applied.").format(scholarship))
            scholarship_discs = frappe.db.sql(
                """select pgm_fee, discount_ from `tabScholarship Discounts` where parent = %s""",
                (scholarship),
            )
            print("Scholarship discounts:", scholarship_discs)

            student_fees = frappe.db.sql(
                """select fee_category, pay_percent, payterm_payer, pep_event from `tabpgm_enroll_payers` where parent = %s and payer = %s""",
                (program_enrollment, student),
            )
            print("Student fees:", student_fees)

            for fee in student_fees:
                for disc in scholarship_discs:
                    if fee[0] == disc[0]:
                        stu_pay = fee[1]
                        discount = disc[1]

                        # Check if scholarship already exists
                        existing_scholarship = frappe.db.sql(
                            """select pay_percent from `tabpgm_enroll_payers` where parent = %s and fee_category = %s and payer = %s""",
                            (program_enrollment, fee[0], sch_payer),
                        )

                        if existing_scholarship:
                            sch_pay = existing_scholarship[0][0]
                            new_stu_pay = float(stu_pay) + sch_pay - discount
                            print(
                                "category: "
                                + fee[0]
                                + ", new fee after change: "
                                + str(new_stu_pay)
                            )

                            frappe.db.set_value(
                                "pgm_enroll_payers",
                                {
                                    "parent": program_enrollment,
                                    "fee_category": fee[0],
                                    "payer": student,
                                },
                                "pay_percent",
                                new_stu_pay,
                            )

                            frappe.db.set_value(
                                "pgm_enroll_payers",
                                {
                                    "parent": program_enrollment,
                                    "fee_category": fee[0],
                                    "payer": sch_payer,
                                },
                                "pay_percent",
                                discount,
                            )
                        else:
                            new_stu_pay = float(stu_pay) - discount
                            print(
                                "category: " + fee[0] + ", new fee: " + str(new_stu_pay)
                            )

                            frappe.db.set_value(
                                "pgm_enroll_payers",
                                {
                                    "parent": program_enrollment,
                                    "fee_category": fee[0],
                                    "payer": student,
                                },
                                "pay_percent",
                                new_stu_pay,
                            )

                            doc = frappe.new_doc("pgm_enroll_payers")
                            doc.parent = program_enrollment
                            doc.parentfield = "pf_payers"
                            doc.parenttype = "Payers Fee Category PE"
                            doc.fee_category = fee[0]
                            doc.payer = sch_payer
                            doc.payterm_payer = fee[2]
                            doc.pep_event = fee[3]
                            doc.pay_percent = discount
                            doc.insert()
                            doc.save()
        else:
            # Check if scholarship existed before and remove it, first adding % back to student
            scholarship_exists = frappe.db.sql(
                """select name, fee_category, pay_percent from `tabpgm_enroll_payers` where parent = %s and payer = %s""",
                (program_enrollment, sch_payer),
            )
            student_fees = frappe.db.sql(
                """select fee_category, pay_percent, payterm_payer, pep_event from `tabpgm_enroll_payers` where parent = %s and payer = %s""",
                (program_enrollment, student),
            )
            if scholarship_exists:
                self.add_comment("Info", _("Scholarship removed."))
                for fee in student_fees:
                    for sch in scholarship_exists:
                        if fee[0] == sch[1]:
                            new_stu_pay = float(fee[1]) + sch[2]
                            frappe.db.set_value(
                                "pgm_enroll_payers",
                                {
                                    "parent": program_enrollment,
                                    "fee_category": fee[0],
                                    "payer": student,
                                },
                                "pay_percent",
                                new_stu_pay,
                            )

                            frappe.delete_doc("pgm_enroll_payers", sch[0])
                            print("Scholarship removed")

            else:
                print("No scholarship to remove")

    @frappe.whitelist()
    def get_scholarships(self):
        program_enrollment = self.pf_pe
        pe = frappe.get_doc("Program Enrollment", program_enrollment)
        program = pe.program
        scholarships = frappe.db.sql(
            """select name from `tabScholarships` where program = %s""", program
        )

        return scholarships
