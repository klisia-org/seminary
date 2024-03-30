# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate
from frappe.model.document import Document
import calendar
from datetime import timedelta
from dateutil import relativedelta
import erpnext

@frappe.whitelist()
def get_course(program):
	"""Return list of courses for a particular program
	:param program: Program
	"""
	courses = frappe.db.sql(
		"""select course, course_name from `tabProgram Course` where parent=%s
		UNION select program_track_course from `tabProgram Track Courses` where parent=%s""",
		(program),
		as_dict=1,
	)
	return courses

@frappe.whitelist()
def set_iscurrent_acterm(academic_term=None):
	academic_terms = frappe.get_all("Academic Term", filters={}, fields=["name", "term_start_date", "term_end_date"])
	today = getdate()
	
	for term in academic_terms:
		if term.term_start_date <= today <= term.term_end_date:
			frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
		else:
			frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)

@frappe.whitelist()
def enroll_student(source_name):
	"""Creates a Student Record and returns a Program Enrollment.

	:param source_name: Student Applicant.
	"""
	frappe.publish_realtime(
		"enroll_student_progress", {"progress": [1, 4]}, user=frappe.session.user
	)
	student = get_mapped_doc(
		"Student Applicant",
		source_name,
		{
			"Student Applicant": {
				"doctype": "Student",
				"field_map": {
					"name": "student_applicant",
				},
			}
		},
		ignore_permissions=True,
	)
	student.save()

	student_applicant = frappe.db.get_value(
		"Student Applicant",
		source_name,
		["student_category", "program", "academic_term"],
		as_dict=True,
	)
	program_enrollment = frappe.new_doc("Program Enrollment")
	program_enrollment.student = student.name
	program_enrollment.student_category = student_applicant.student_category
	program_enrollment.student_name = student.student_name
	program_enrollment.program = student_applicant.program
	program_enrollment.academic_term = student_applicant.academic_term
	program_enrollment.save()

	frappe.publish_realtime(
		"enroll_student_progress", {"progress": [2, 4]}, user=frappe.session.user
	)
	return program_enrollment


@frappe.whitelist()
def check_attendance_records_exist(course_schedule=None, date=None):
	"""Check if Attendance Records are made against the specified Course Schedule or Student Group for given date.

	:param course_schedule: Course Schedule.
	:param student_group: Student Group.
	:param date: Date.
	"""
	if course_schedule:
		return frappe.get_list(
			"Student Attendance", filters={"course_schedule": course_schedule}
		)
	


@frappe.whitelist()
def mark_attendance(
	students_present, students_absent, course_schedule=None, date=None
):
	"""Creates Multiple Attendance Records.

	:param students_present: Students Present JSON.
	:param students_absent: Students Absent JSON.
	:param course_schedule: Course Schedule.
	:param student_group: Student Group.
	:param date: Date.
	"""

	if course_schedule:
		present = json.loads(students_present)
		absent = json.loads(students_absent)

	for d in present:
		make_attendance_records(
			d["student"], d["student_name"], "Present", course_schedule,  date
		)

	for d in absent:
		make_attendance_records(
			d["student"], d["student_name"], "Absent", course_schedule, date
		)

	frappe.db.commit()
	frappe.msgprint(_("Attendance has been marked successfully."))


def make_attendance_records(
	student, student_name, status, course_schedule=None, date=None
):
	"""Creates/Update Attendance Record.

	:param student: Student.
	:param student_name: Student Name.
	:param course_schedule: Course Schedule.
	:param status: Status (Present/Absent)
	"""
	student_attendance = frappe.get_doc(
		{
			"doctype": "Student Attendance",
			"student": student,
			"course_schedule": course_schedule,
			"date": date,
		}
	)
	if not student_attendance:
		student_attendance = frappe.new_doc("Student Attendance")
	student_attendance.student = student
	student_attendance.student_name = student_name
	student_attendance.course_schedule = course_schedule
	student_attendance.date = date
	student_attendance.status = status
	student_attendance.save()
	student_attendance.submit()


@frappe.whitelist()
def get_student_guardians(student):
	"""Returns List of Guardians of a Student.

	:param student: Student.
	"""
	guardians = frappe.get_all(
		"Student Guardian", fields=["guardian"], filters={"parent": student}
	)
	return guardians





@frappe.whitelist()
def get_course_schedule_events(start, end, filters=None):
	"""Returns events for Course Schedule Calendar view rendering.

	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	filters = json.loads(filters)
	from frappe.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Course Schedule", filters)

	return frappe.db.sql(
		"""SELECT CONCAT (cs.course, ' - ', COALESCE(cs.room, '')) as title, 
			cs.course as course,
			timestamp(cm.cs_meetdate, cm.cs_fromtime) as dtstart,
			timestamp(cm.cs_meetdate, cm.cs_totime) as dtend,
			0 as 'allDay'
		from `tabCourse Schedule Meeting Dates` cm, `tabCourse Schedule` cs
		where 
		cs.name = cm.parent and
		(cm.cs_meetdate between %(start)s and %(end)s )
		{conditions}""".format(
			conditions=conditions
		),
		{"start": start, "end": end},
		as_dict=True,
		update={"allDay": 0},
	)
	


@frappe.whitelist()
def get_assessment_criteria(course):
	"""Returns Assessmemt Criteria and their Weightage from Course Master.

	:param Course: Course
	"""
	return frappe.get_all(
		"Course Assessment Criteria",
		fields=["assessment_criteria", "weightage"],
		filters={"parent": course},
		order_by="idx",
	)


""" @frappe.whitelist()
def get_assessment_students(assessment_plan, student_group):
	student_list = get_student_group_students(student_group)
	for i, student in enumerate(student_list):
		result = get_result(student.student, assessment_plan)
		if result:
			student_result = {}
			for d in result.details:
				student_result.update({d.assessment_criteria: [cstr(d.score), d.grade]})
			student_result.update(
				{"total_score": [cstr(result.total_score), result.grade], "comment": result.comment}
			)
			student.update(
				{
					"assessment_details": student_result,
					"docstatus": result.docstatus,
					"name": result.name,
				}
			)
		else:
			student.update({"assessment_details": None})
	return student_list """


@frappe.whitelist()
def get_assessment_details(assessment_plan):
	"""Returns Assessment Criteria  and Maximum Score from Assessment Plan Master.

	:param Assessment Plan: Assessment Plan
	"""
	return frappe.get_all(
		"Assessment Plan Criteria",
		fields=["assessment_criteria", "maximum_score", "docstatus"],
		filters={"parent": assessment_plan},
		order_by="idx",
	)


@frappe.whitelist()
def get_result(student, assessment_plan):
	"""Returns Submitted Result of given student for specified Assessment Plan

	:param Student: Student
	:param Assessment Plan: Assessment Plan
	"""
	results = frappe.get_all(
		"Assessment Result",
		filters={
			"student": student,
			"assessment_plan": assessment_plan,
			"docstatus": ("!=", 2),
		},
	)
	if results:
		return frappe.get_doc("Assessment Result", results[0])
	else:
		return None


@frappe.whitelist()
def get_grade(grading_scale, percentage):
	"""Returns Grade based on the Grading Scale and Score.

	:param Grading Scale: Grading Scale
	:param Percentage: Score Percentage Percentage
	"""
	grading_scale_intervals = {}
	if not hasattr(frappe.local, "grading_scale"):
		grading_scale = frappe.get_all(
			"Grading Scale Interval",
			fields=["grade_code", "threshold"],
			filters={"parent": grading_scale},
		)
		frappe.local.grading_scale = grading_scale
	for d in frappe.local.grading_scale:
		grading_scale_intervals.update({d.threshold: d.grade_code})
	intervals = sorted(grading_scale_intervals.keys(), key=float, reverse=True)
	for interval in intervals:
		if flt(percentage) >= interval:
			grade = grading_scale_intervals.get(interval)
			break
		else:
			grade = ""
	return grade


@frappe.whitelist()
def mark_assessment_result(assessment_plan, scores):
	student_score = json.loads(scores)
	assessment_details = []
	for criteria in student_score.get("assessment_details"):
		assessment_details.append(
			{
				"assessment_criteria": criteria,
				"score": flt(student_score["assessment_details"][criteria]),
			}
		)
	assessment_result = get_assessment_result_doc(
		student_score["student"], assessment_plan
	)
	assessment_result.update(
		{
			"student": student_score.get("student"),
			"assessment_plan": assessment_plan,
			"comment": student_score.get("comment"),
			"total_score": student_score.get("total_score"),
			"details": assessment_details,
		}
	)
	assessment_result.save()
	details = {}
	for d in assessment_result.details:
		details.update({d.assessment_criteria: d.grade})
	assessment_result_dict = {
		"name": assessment_result.name,
		"student": assessment_result.student,
		"total_score": assessment_result.total_score,
		"grade": assessment_result.grade,
		"details": details,
	}
	return assessment_result_dict


""" @frappe.whitelist()
def submit_assessment_results(assessment_plan, student_group):
	total_result = 0
	student_list = get_student_group_students(student_group)
	for i, student in enumerate(student_list):
		doc = get_result(student.student, assessment_plan)
		if doc and doc.docstatus == 0:
			total_result += 1
			doc.submit()
	return total_result
 """

def get_assessment_result_doc(student, assessment_plan):
	assessment_result = frappe.get_all(
		"Assessment Result",
		filters={
			"student": student,
			"assessment_plan": assessment_plan,
			"docstatus": ("!=", 2),
		},
	)
	if assessment_result:
		doc = frappe.get_doc("Assessment Result", assessment_result[0])
		if doc.docstatus == 0:
			return doc
		elif doc.docstatus == 1:
			frappe.msgprint(_("Result already Submitted"))
			return None
	else:
		return frappe.new_doc("Assessment Result")


""" @frappe.whitelist()
def update_email_group(doctype, name):
	if not frappe.db.exists("Email Group", name):
		email_group = frappe.new_doc("Email Group")
		email_group.title = name
		email_group.save()
	email_list = []
	students = []
	if doctype == "Student Group":
		students = get_student_group_students(name)
	for stud in students:
		for guard in get_student_guardians(stud.student):
			email = frappe.db.get_value("Guardian", guard.guardian, "email_address")
			if email:
				email_list.append(email)
	add_subscribers(name, email_list) """


@frappe.whitelist()
def get_current_enrollment(student, academic_term=None):
	current_academic_term = academic_term or frappe.defaults.get_defaults().academic_term
	program_enrollment_list = frappe.db.sql(
		"""
		select
			name as program_enrollment, student_name, program, student_batch_name as student_batch,
			student_category, academic_term
		from
			`tabProgram Enrollment`
		where
			student = %s and academic_term = %s
		order by creation""",
		(student, current_academic_term),
		as_dict=1,
	)

	if program_enrollment_list:
		return program_enrollment_list[0]
	else:
		return None


""" @frappe.whitelist()
def get_instructors(student_group):
	return frappe.get_all(
		"Student Group Instructor", {"parent": student_group}, pluck="instructor"
	) """

@frappe.whitelist()
def get_payers(program_enrollment, method):
	pe = program_enrollment
	pen = pe.name
	active = pe.pgmenrol_active
	student = pe.student
	turn = 1
	while turn <= 2:
		if not frappe.db.exists({"doctype": "Payers Fee Category PE", "pf_pe": pen}) and turn == 1:
			print("Creating Payers Fee Category PE -turn "+ str(turn) + pen)
			pfc = frappe.new_doc("Payers Fee Category PE")
			pfc.pf_pe = pen
			pfc.pf_student = student
			pfc.pf_active = active
			pfc.pf_custgroup = "Student"
			pfc.insert()
			pfc.save()
			turn += 1
		elif frappe.db.exists({"doctype": "Payers Fee Category PE", "pf_pe": pen}) and turn == 2:
			print("Payers Fee Category PE already exists - turn " + str(turn))
			get_payers_fees(pen)
			break
	return
				
	
	
@frappe.whitelist()
def get_payers_fees(pen):
		
		pfc = frappe.get_doc({"doctype": "Payers Fee Category PE", "pf_pe": pen})
		
		doc =[]
		doc = frappe.db.sql(
		"""select pf.pgm_feecategory as feecat, pf.pgm_feeevent as event, s.customer, '1' as percentage, fc.payment_term_template as term
			from `tabProgram Enrollment`pe, `tabStudent` s, `tabProgram` p, `tabProgram Fees` pf, `tabFee Category` fc
			where pe.student = s.name and
			pe.program = p.name and
			p.name = pf.parent and
			pf.pgm_feecategory = fc.name and
			pe.name = %s""", (pen), as_list=1)
		row_count = frappe.db.sql(
		"""select count(pf.pgm_feecategory) from `tabProgram Enrollment`pe, `tabStudent` s, `tabProgram` p, `tabProgram Fees` pf, `tabFee Category` fc
			where pe.student = s.name and
			pe.program = p.name and
			p.name = pf.parent and
			pf.pgm_feecategory = fc.name and
			pe.name = %s""", (pen))[0][0]
		i = 0	
		while i < row_count:
			feecat = doc[i][0]
			event = doc[i][1]
			customer = doc[i][2]
			term = doc[i][3]
			percentage = doc[i][4]
			print(pen, feecat, event, customer, term, percentage)
			ppe = frappe.new_doc("pgm_enroll_payers")
			ppe.parent = pen
			ppe.parentfield = "pf_payers"
			ppe.parenttype = "Payers Fee Category PE"
			ppe.fee_category = feecat
			ppe.pep_event = event
			ppe.payer = customer
			ppe.payterm_payer = term
			ppe.pay_percent = "100"
			ppe.insert()
			ppe.save()
			i += 1
		return




@frappe.whitelist()
def get_student_invoices(student):
	student_sales_invoices = []

	sales_invoice_list = frappe.db.get_list(
		"Sales Invoice",
		filters={"student": student, "status": ["in", ["Paid", "Unpaid"]]},
		fields=["name", "status", "student", "due_date", "grand_total"],
	)

	for si in sales_invoice_list:
		student_program_invoice_status = {}
		student_program_invoice_status["status"] = si.status
		student_program_invoice_status["amount"] = si.grand_total

		if si.status == "Paid":
			student_program_invoice_status[
				"payment_date"
			] = get_posting_date_from_payment_entry_against_sales_invoice(si.name)
			student_program_invoice_status["due_date"] = ""
		else:
			student_program_invoice_status["due_date"] = si.due_date
			student_program_invoice_status["payment_date"] = ""

		student_sales_invoices.append(student_program_invoice_status)

	return student_sales_invoices


def get_posting_date_from_payment_entry_against_sales_invoice(sales_invoice):
	payment_entry = frappe.qb.DocType("Payment Entry")
	payment_entry_reference = frappe.qb.DocType("Payment Entry Reference")
	q = (
		frappe.qb.from_(payment_entry)
		.inner_join(payment_entry_reference)
		.on(payment_entry.name == payment_entry_reference.parent)
		.select(payment_entry.posting_date)
		.where(payment_entry_reference.reference_name == sales_invoice)
	).run(as_dict=1)
	payment_date = q[0].get("posting_date")
	return payment_date


@frappe.whitelist()
def courses_for_student(program_ce):
	
	pgen_name = program_ce
	#This query is to get the available scheduled courses for the student based on the program enrollment, program track and the academic term, checking for pre-requisites	 
	
	courses = frappe.db.sql(
		"""select cs.course 
		from `tabCourse Schedule` cs, `tabAcademic Term` aterm
		where aterm.name = cs.academic_term and
		cs.open_enroll = '1' and
		aterm.iscurrent_acterm = '1' and cs.course in 
		((select pc.course 
		from `tabProgram Enrollment` pe, `tabProgram Course` pc
		where pe.program = pc.parent and
		pe.name = %s)
		UNION
		(select ptc.program_track_course
		from `tabProgram Enrollment` pe, `tabProgram Track Courses` ptc
		where pe.pgmenrol_active = '1' and
		ptc.parent = pe.program and
		pe.emphasis_program_track = ptc.program_track and
		pe.name = %s)) and
		cs.course not in (select c.name 
		from `tabCourse` c, `tabCourse_prerequisite` cp
		where cp.parent = c.name and
		cp.prereq_mandatory = "Mandatory" and
		c.name not in 
		(select pec.course
		from `tabCourse_prerequisite` cp, `tabProgram Enrollment Course` pec
		where cp.parent = pec.course and
		pec.parent = %s and
		pec.pec_finalgradecode is not null)) and
		cs.course not in (select pc.course 
		from `tabProgram` p, `tabProgram Course` pc, `tabProgram Enrollment` pe
		where p.name = pc.parent and
		p.name = pe.program and
		pe.name = %s and
		p.program_type = 'Time-based' and
		pc.course_term > pe.current_std_term) and
		cs.course not in (select ptc.program_track_course 
		from `tabProgram` p, `tabProgram Track Courses` ptc, `tabProgram Enrollment` pe
		where p.name = ptc.parent and
		p.name = pe.program and
		pe.name = %s and
		p.program_type = 'Time-based' and
		ptc.term > pe.current_std_term) and cs.course not in
		(select course_data from `tabCourse Enrollment Individual` where audit = 0 and
		docstatus != '2' and program_ce = %s)""", (pgen_name, pgen_name, pgen_name, pgen_name, pgen_name, pgen_name), as_list=1)
	 # Flatten the list of tuples into a list of strings
	courses = [course[0] for course in courses]	
	return courses
	

@frappe.whitelist()
def copy_data_to_scheduled_course_roster(doc, method):
		student_ce = doc.student_ce
		program = doc.program_data
		coursesc_ce = doc.coursesc_ce
		audit = doc.audit
		
		
		student_email = frappe.db.sql(
			"""select distinct s.student_email_id from tabStudent s, `tabCourse Enrollment Individual` cei
			where cei.student_ce = s.student_name and
			cei.student_ce = %s""", student_ce, as_dict=0)

		if coursesc_ce and student_ce:
			doc = frappe.new_doc("Scheduled Course Roster")
			doc.parent = coursesc_ce,
			doc.parenttype = "Course Schedule",
			doc.parentfield = "cs_roster",
			doc.stuname_roster = student_ce,
			doc.stuemail_rc = student_email,
			doc.program_std_scr = program,
			doc.audit_bool = audit
			
			doc.insert().save()

@frappe.whitelist()
def copy_data_to_program_enrollment_course(doc, method):
		cei = doc.program_ce
		course_lnk = doc.coursesc_ce
		course = doc.course_data
		ac_term = doc.academic_term
		 
		if cei:
			doc = frappe.new_doc("Program Enrollment Course")
			doc.parent = cei,
			doc.parenttype = "Program Enrollment",
			doc.parentfield = "courses",
			doc.course = course_lnk,
			doc.course_name = course,
			doc.academic_term = ac_term
			
			doc.insert().save()

@frappe.whitelist()
def get_inv_data_nat():
		print("Method called")
		today = frappe.utils.today()
		company = frappe.defaults.get_defaults().company
		currency = erpnext.get_company_currency(company)
		receivable_account = frappe.db.get_single_value('Education Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Education Settings', 'company')
		cost_center = frappe.db.get_single_value('Education Settings', 'cost_center') or None
		inv_data = []
		inv_data = frappe.db.sql("""select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate 
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Term'""", as_list=1)
		rows = frappe.db.sql("""select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Term'""") [0] [0]
		
		
		i =0
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
				"items": items
				})
			sales_invoice.run_method("set_missing_values")
			sales_invoice.insert()
			sales_invoice.save()
			i += 1
			print("Invoice Created")
		return "done"
		
@frappe.whitelist()
def get_inv_data_nayear():
		print("Method called")
		today = frappe.utils.today()
		company = frappe.defaults.get_defaults().company
		currency = erpnext.get_company_currency(company)
		receivable_account = frappe.db.get_single_value('Education Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Education Settings', 'company')
		cost_center = frappe.db.get_single_value('Education Settings', 'cost_center') or None
		inv_data = []
		inv_data = frappe.db.sql("""select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate 
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Year'""", as_list=1)
		rows = frappe.db.sql("""select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Year'""") [0] [0]
		
		
		i =0
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
				"items": items
				})
			sales_invoice.run_method("set_missing_values")
			sales_invoice.insert()
			sales_invoice.save()
			i += 1
			print("Invoice Created")
		return "done"

@frappe.whitelist()
def get_inv_data_monthly():
		print("Method called")
		today = frappe.utils.today()
		company = frappe.defaults.get_defaults().company
		currency = erpnext.get_company_currency(company)
		receivable_account = frappe.db.get_single_value('Education Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Education Settings', 'company')
		cost_center = frappe.db.get_single_value('Education Settings', 'cost_center') or None
		inv_data = []
		inv_data = frappe.db.sql("""select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate 
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'Monthly'""", as_list=1)
		rows = frappe.db.sql("""select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg 
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'Monthly'""") [0] [0]
		
		
		i =0
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
				"student": inv_data[i][0],
				"customer": inv_data[i][2],
				"selling_price_list": inv_data[i][10],
				"base_grand_total": inv_data[i][11],
				"payment_terms_template": inv_data[i][5],
				"items": items
				})
			sales_invoice.run_method("set_missing_values")
			sales_invoice.insert()
			sales_invoice.save()
			i += 1
			print("Invoice Created")
		return "done"

@frappe.whitelist()
def get_pgmenrollments(name):
	program_enrollments = []
	program_enrollments = frappe.get_all(
		"Program Enrollment",
		filters={"student": name},
		fields=["program", "pgmenrol_active", "enrollment_date", "date_of_conclusion"],
		)
	if not program_enrollments:
		return "No Program Enrollments Found"
	else:
		return program_enrollments