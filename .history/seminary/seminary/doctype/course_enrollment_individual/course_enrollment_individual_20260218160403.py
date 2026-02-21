# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.csvutils import getlink
import erpnext


class CourseEnrollmentIndividual(Document):
    def validate(self):
        self.validate_duplicate()
        self.validate_duplicate_course()

    def validate_duplicate(self):
        CEI = frappe.get_list(
            "Course Enrollment Individual",
            filters={
                "program_ce": (self.program_ce),
                "coursesc_ce": self.coursesc_ce,
                "docstatus": ("=", 1),
                "audit": ("=", 0),
            },
        )
        if CEI:
            frappe.throw(
                _("This Course Enrollment {0} already exists.").format(
                    getlink("Course Enrollment Individual", CEI[0].name)
                )
            )
    def validate_duplicate_course(self):
        CEI = frappe.db.sql("""select c.coursesc_ce
                from `tabProgram Course` a, `tabCourse Enrollment Individual` c, `tabProgram Enrollment Course` p
                where c.course_data = a.course AND
                a.repeatable = '0' AND
                c.docstatus = '1' AND
                c.audit = '0' AND
                c.course_data = %s AND
                c.program_ce = p.parent AND
                p.course_name = c.course_data AND
                p.status = "Pass" AND
                c.program_ce = %s""", (self.course_data, self.program_ce))
        if CEI:
            frappe.throw(
                _("Student already enrolled in {0} for credit. If students should be able to enroll again, please adjust the program course settings.").format(
                    getlink("Course Enrollment Individual", CEI[0][0])
                )
            )

    @frappe.whitelist()
    def get_credits(self):
        pe = self.program_data
        ce = self.course_data
        audit = self.audit
        if audit == 1:
            credits = 0
        else:
            print("Audit is not 1")
            credits = frappe.db.sql(
                """select pgmcourse_credits from `tabProgram Course` where parent = %s and course = %s""",
                (pe, ce),
            )
            if credits:
                credits = credits[0][0]
                print(credits)
            else:
                credits = 0

        return credits

    @frappe.whitelist()
    def get_credits2(self):
        pe = self.program_data
        ce = self.course_data
        audit = self.audit
        if audit == 1:
            credits = 0
        else:
            print("Audit is not 1")
            credits = frappe.db.sql(
                """select pgmcourse_credits from `tabProgram Course` where parent = %s and course = %s""",
                (pe, ce),
            )
            credits = credits[0][0] if credits else 0
            print(credits)
            doc = frappe.get_doc("Course Enrollment Individual", self.name)
            doc.credits = credits
        return credits

    @frappe.whitelist()
    def get_inv_data_ce(self):
        today = frappe.utils.today()
        company = frappe.defaults.get_defaults().company
        currency = erpnext.get_company_currency(company)
        receivable_account = frappe.db.get_single_value(
            "Seminary Settings", "receivable_account"
        )
        audithours = frappe.db.get_single_value("Seminary Settings", "auditcredit")
        submitinvoice = frappe.db.get_single_value(
            "Seminary Settings", "auto_submit_sales_invoice"
        )
        is_audit = self.audit
        income_account = frappe.db.sql(
            """select default_income_account from `tabCompany` where name=%s""", company
        )[0][0]
        cost_center = (
            frappe.db.get_single_value("Seminary Settings", "cost_center") or None
        )
        sch_cost_center = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cc"
        )
        sch_customer = frappe.db.get_single_value(
            "Seminary Settings", "scholarship_cust"
        )
        stulink = self.student_ce
        inv_data = []
        inv_data = frappe.db.sql(
            """select cei.student_ce, cei.audit, cei.credits, cei.program_data,  pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate
		from `tabCourse Enrollment Individual` cei,  `tabFee Category` fc, `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabCustomer Group` cg, `tabItem Price` ip
		where cei.name = %s and
		cei.program_ce = pfc.pf_pe and
		pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		cei.cei_si =0 and
		fc.is_audit = %s and
		pep.pep_event = 'Course Enrollment'""",
            (self.name, is_audit),
            as_list=1,
        )
        rows = frappe.db.sql(
            """select count(pep.payer)
		from `tabCourse Enrollment Individual` cei,  `tabFee Category` fc, `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabCustomer Group` cg, `tabItem Price` ip
		where cei.name = %s and
		cei.program_ce = pfc.pf_pe and
		pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		cei.cei_si =0 and
		fc.is_audit = %s and
		pep.pep_event = 'Course Enrollment'""",
            (self.name, is_audit),
        )[0][0]

        i = 0
        while i < rows:

            items = []
            if inv_data[i][11] == 1:
                qty = inv_data[i][2] * inv_data[i][7] / 100
            elif is_audit == 1 and audithours == 1:
                qty = inv_data[i][2] * inv_data[i][7] / 100
            else:
                qty = inv_data[i][7] / 100

            gt = qty * inv_data[i][14]
            print(qty)
            cost_center = (
                cost_center if inv_data[i][5] != sch_customer else sch_cost_center
            )
            discount = 0 if inv_data[i][5] != sch_customer else 100
            items.append(
                {
                    "doctype:": "Sales Invoice Item",
                    "item_name": inv_data[i][12],
                    "qty": qty,
                    "rate": 0,
                    "description": "Fee for " + self.name,
                    "income_account": income_account,
                    "cost_center": cost_center,
                    "base_rate": 0,
                    "price_list_rate": inv_data[i][14],
                }
            )

            sales_invoice = frappe.get_doc(
                {
                    "doctype": "Sales Invoice",
                    "naming_series": "ACC-SINV-.YYYY.-",
                    "posting_date": today,
                    "company": company,
                    "currency": currency,
                    "debit_to": receivable_account,
                    "income_account": income_account,
                    "conversion_rate": 1,
                    "customer": inv_data[i][5],
                    "selling_price_list": inv_data[i][13],
                    "base_grand_total": gt,
                    "payment_terms_template": inv_data[i][8],
                    "remarks": "Fee for " + self.name,
                    "items": items,
                    "cost_center": cost_center,
                    "custom_student": stulink,
                    "additional_discount_percentage": discount,
                }
            )
            sales_invoice.insert()
            sales_invoice.save()
            if submitinvoice == 1:
                sales_invoice.submit()
            i += 1
            print("Invoice Created")
