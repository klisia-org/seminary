# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import erpnext



class PayersFeeCategoryPE(Document):
	@frappe.whitelist()
	def get_inv_data_pe(self):
		today = frappe.utils.today()
		company = frappe.defaults.get_defaults().company
		currency = erpnext.get_company_currency(company)
		receivable_account = frappe.db.get_single_value('Seminary Settings', 'receivable_account')
		submittable = frappe.db.get_single_value('Seminary Settings', 'auto_submit_sales_invoice')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Seminary Settings', 'company')
		cost_center = frappe.db.get_single_value('Seminary Settings', 'cost_center') or None
		stulink = self.stu_link
		inv_data = []
		inv_data = frappe.db.sql("""select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate 
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pep.pep_event = 'Program Enrollment' and
		pfc.pf_student = %s""", self.pf_student, as_list=1)
		rows = frappe.db.sql("""select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pep.pep_event = 'Program Enrollment' and
		pfc.pf_student = %s""", self.pf_student) [0] [0]
		
		
		i = 0
		while i < rows:
			print("Creating Invoice - " + str(i) + " of " + str(rows) + " rows")
			print(income_account)
			

			items= []
			items.append({
				"doctype:": "Sales Invoice Item",
				"item_name": inv_data[i][9],
				"qty": inv_data[i][4]/100,
				"rate": 0,
				"description": "Fee for " + inv_data[i][1],
				"income_account": income_account,
				"cost_center": cost_center,
				"base_rate": 0,
				"price_list_rate": inv_data[i][11]
			})		

			sales_invoice = frappe.get_doc(
				{"doctype": "Sales Invoice",
				"naming_series": "ACC-SINV-.YYYY.-",
				"posting_date": today,
				"company": company,
				"currency": currency,
				"debit_to": receivable_account,
				"income_account": income_account,
				"conversion_rate": 1,
				"customer": inv_data[i][2],
				"selling_price_list": inv_data[i][10],
				"base_grand_total": inv_data[i][11],
				"payment_terms_template": inv_data[i][5],
				"items": items,
				"student": stulink,
				})
			sales_invoice.run_method("set_missing_values")
			sales_invoice.insert()
			sales_invoice.save()
			if submittable == 1:
				sales_invoice.submit()
			i += 1
			print("Invoice Created")

	@frappe.whitelist()
	# Method to check if the sum of the percentages is equal to 100 
	def check_percentages(self):
		pay_data = []
		pay_data = frappe.db.sql("""select pep.fee_category, sum(pep.pay_percent) as percentage 
		from `tabpgm_enroll_payers` pep
		where pep.parent = %s
		group by pep.fee_category
		having percentage != 100""", self.name, as_list=1)
		
		
		if pay_data:
			frappe.throw("The sum of the percentages paid for a Fee Category is not equal to 100")

	@frappe.whitelist()
	def add_scholarship(self):
		print("Add Scholarship called")
		program_enrollment = self.pf_pe
		student = self.pf_student
		scholarship = self.scholarship
		
		# Fetch scholarship payer
		sch_payer = frappe.db.sql(
			"""Select value from `tabSingles` where doctype = 'Seminary Settings' and field = 'scholarship_cust'""", as_list=1)
		sch_payer = sch_payer[0][0] if sch_payer else None
		print("Scholarship payer:", sch_payer)
		if not sch_payer:
			frappe.throw("Scholarship payer not found in Seminary Settings")
		
		if scholarship:
			print("Scholarship exists:", scholarship)
			scholarship_discs = frappe.db.sql(
				"""select pgm_fee, discount_ from `tabScholarship Discounts` where parent = %s""", (scholarship)
			)
			print("Scholarship discounts:", scholarship_discs)
			
			student_fees = frappe.db.sql(
				"""select fee_category, pay_percent, payterm_payer, pep_event from `tabpgm_enroll_payers` where parent = %s and payer = %s""", (program_enrollment, student)
			)
			print("Student fees:", student_fees)
			
			for fee in student_fees:
				for disc in scholarship_discs:
					if fee[0] == disc[0]:
						stu_pay = fee[1]
						discount = disc[1]
						
						# Check if scholarship already exists
						existing_scholarship = frappe.db.sql(
							"""select pay_percent from `tabpgm_enroll_payers` where parent = %s and fee_category = %s and payer = %s""", (program_enrollment, fee[0], sch_payer)
						)
						
						if existing_scholarship:
							sch_pay = existing_scholarship[0][0]
							new_stu_pay = float(stu_pay) + sch_pay - discount
							print("category: " + fee[0] + ", new fee after change: " + str(new_stu_pay))
							
							frappe.db.set_value("pgm_enroll_payers", {"parent": program_enrollment, "fee_category": fee[0], "payer": student}, "pay_percent", new_stu_pay)
							
							frappe.db.set_value("pgm_enroll_payers", {"parent": program_enrollment, "fee_category": fee[0], "payer": sch_payer}, "pay_percent", discount)
						else:
							new_stu_pay = float(stu_pay) - discount
							print("category: " + fee[0] + ", new fee: " + str(new_stu_pay))
							
							frappe.db.set_value("pgm_enroll_payers", {"parent": program_enrollment, "fee_category": fee[0], "payer": student}, "pay_percent", new_stu_pay)
							
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
			#Check if scholarship existed before and remove it, first adding % back to student
			scholarship_exists = frappe.db.sql(
				"""select name, fee_category, pay_percent from `tabpgm_enroll_payers` where parent = %s and payer = %s""", (program_enrollment, sch_payer)
			)
			student_fees = frappe.db.sql(
				"""select fee_category, pay_percent, payterm_payer, pep_event from `tabpgm_enroll_payers` where parent = %s and payer = %s""", (program_enrollment, student)
			)
			if scholarship_exists:
				for fee in student_fees:
					for sch in scholarship_exists:
						if fee[0] == sch[1]:
							new_stu_pay = float(fee[1]) + sch[2]
							frappe.db.set_value("pgm_enroll_payers", {"parent": program_enrollment, "fee_category": fee[0], "payer": student}, "pay_percent", new_stu_pay)
							
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



