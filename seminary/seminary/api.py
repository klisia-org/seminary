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
from datetime import datetime

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
	#This is a complex method, as it triggers many others in case there is a change in Academic Term
	#Refer to the other methods for their functionality in detail.
	#Essentially, students will be enrolled in courses for time-based programs, and invoices triggered by New Academic Term (and Year, if applicable) will be generated
	academic_terms = frappe.get_all("Academic Term", filters={}, fields=["name", "term_start_date", "term_end_date"])
	today = getdate()
	currentterm = frappe.db.sql("""select name from `tabAcademic Term` where iscurrent_acterm = 1""")
	currentyear = frappe.db.sql("""select academic_year from `tabAcademic Term` where iscurrent_acterm = 1""")
	
	for term in academic_terms:
		if term.term_start_date <= today <= term.term_end_date:
			if term.name != currentterm[0][0]:
				frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
				newyear = frappe.db.get_value("Academic Term", term.name, "academic_year")
				roll_pe()
				get_inv_data_nat()
				if newyear != currentyear:
					get_inv_data_nayear()
			else:
				break
	
		else:
			frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)
	return "Term rolled successfully"

@frappe.whitelist()
def roll_pe():
	# Students' academic terms will advance. In case enrolled in a time-based program, petb_enroll will try to enroll them in courses 
	tb = frappe.db.get_single_value("Seminary Settings", "advancetb")
	pes = frappe.get_all("Program Enrollment", filters={"pgmenrol_active": 1, "docstatus": 1}, fields=["name", "current_std_term"])
	for pe in pes:
		pe_name = pe.name
		pe_term = pe.current_std_term
		pe_program = frappe.db.get_value("Program Enrollment", pe_name, "program")
		pe_program_type = frappe.db.get_value("Program", pe_program, "program_type")
		pe_term = pe_term + 1
		frappe.db.set_value("Program Enrollment", pe_name, "current_std_term", pe_term)
		if pe_program_type == "Time-based" and tb==1:
			petb_enroll(pe_name, pe_term)	
		else:
			continue


@frappe.whitelist()
def petb_enroll(pe_name, pe_term):
	#This will try to enroll all active students from time-based programs in courses scheduled for the new academic term and open for enrollment
	currentterm = frappe.db.sql("""select name from `tabAcademic Term` where iscurrent_acterm = 1""")
	program = frappe.db.get_value("Program Enrollment", pe_name, "program")
	pecs = frappe.get_all("Program Course", filters={"parent": program, "course_term": pe_term}, fields=["name", "course"])
	cs = frappe.get_all("Course Schedule", filters={"academic_term":currentterm, "open_enroll":1}, fields=["name", "course"])
	for pec in pecs:
		for cs_course in cs:
			if pec.course == cs_course.course:
				course = pec.course
				try:
					course_enroll(pe_name, course)
				except Exception as e:
					# Handle the error here
					print(f"An error occurred: {str(e)}")
				
			else:
				continue
	return "No course to enroll"

@frappe.whitelist()	
def course_enroll(pe_name, course):
	#This is called for each student in petb_enroll
	student = frappe.get_value("Program Enrollment", pe_name, "student")
	cs = frappe.db.sql("""select distinct name from `tabCourse Schedule` 
	where academic_term in (select name from `tabAcademic Term` where iscurrent_acterm = 1) and open_enroll = 1 and
	course = %s""", course)[0][0]
	doc = frappe.new_doc("Course Enrollment Individual")
	doc.program_ce = pe_name
	doc.student_ce = student
	doc.coursesc_ce = cs
	doc.docstatus = 0
	doc.insert()


@frappe.whitelist()
def credits_pe_track():
	pe = frappe.get_all("Program Enrollment", filters={"pgmenrol_active": 1}, fields=["name", "program", "emphasis_program_track"])
	
	for p in pe:
		pe_name = p.name
		credits = frappe.db.sql("""select coalesce(sum(pec.credits), 0) from
		`tabProgram Enrollment Course` pec, `tabProgram Track Courses` ptc, `tabProgram Enrollment` pe
		where pe.name = pec.parent and
		ptc.parent = pe.program and 
		ptc.program_track = pe.emphasis_program_track and pec.status = "Pass" and
		ptc.program_track_course = pec.course_name and pe.name = %s""", pe_name)[0][0]
		if credits:
			frappe.db.set_value("Program Enrollment", pe_name, "trackcredits", credits)
		else:
			continue
	return 

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
	"""Check if Attendance Records are made against the specified Course Schedule

	:param course_schedule: Course Schedule.
	
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
def get_student_contacts(student):
	"""Returns List of contacts of a Student.

	:param student: Student.
	"""
	contacts = frappe.get_all(
		"Student Contacts", fields=["contact"], filters={"parent": student}
	)
	return contacts





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
def get_current_enrollment(student, academic_term=None):
	current_academic_term = academic_term or frappe.defaults.get_defaults().academic_term
	program_enrollment_list = frappe.db.sql(
		"""
		select
			name as program_enrollment, student_name, program, 
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
	student_name = doc.student_name
	student_email = doc.stu_user
	image = doc.stuimage

	if coursesc_ce and student_ce:
		items = []
		criteria = []
		criteria = frappe.db.sql(
			"""select distinct scac.assesscriteria_scac, scac.weight_scac, extracredit_scac, fudgepoints_scac from `tabScheduled Course Assess Criteria` scac
			where scac.docstatus = 0 and
			scac.parent = %s""", coursesc_ce, as_list=1)
		rows = frappe.db.sql(
			"""select count(distinct scac.assesscriteria_scac) from `tabScheduled Course Assess Criteria` scac
			where scac.docstatus = 0 and
			scac.parent = %s""", coursesc_ce)[0][0]
		i = 0
		while i < rows:
			if criteria:
				items.append({
					"doctype": "Course Assess Results Detail",
					"student_card": student_ce,
					"assessment_criteria": criteria[i][0],
					"maximum_score": criteria[i][1],
					"extracredit_card": criteria[i][2],
					"maxextrapoints_card": criteria[i][3],
				})
				i += 1

		roster = frappe.get_doc({
			"doctype": "Scheduled Course Roster",
			"course_sc": coursesc_ce,
			"stuname_roster": student_name,
			"student": student_ce,
			"stuemail_rc": student_email,
			"program_std_scr": program,
			"audit_bool": audit,
			"active": 1,
			"stuimage": image,
			"fscore": "",
			"fgrade": "",
			"stdroster_grade": items
		})
		roster.insert()
		roster.save()
	return

@frappe.whitelist()
def copy_data_to_program_enrollment_course(doc, method):
		cei = doc.program_ce
		course_lnk = doc.coursesc_ce
		course = doc.course_data
		ac_term = doc.academic_term
		credits = doc.credits
		 
		if cei:
			program_enrollment_course = frappe.new_doc("Program Enrollment Course")
			program_enrollment_course.parent = cei
			program_enrollment_course.parenttype = "Program Enrollment"
			program_enrollment_course.parentfield = "courses"
			program_enrollment_course.course = course_lnk
			program_enrollment_course.course_name = course
			program_enrollment_course.academic_term = ac_term
			program_enrollment_course.credits = credits
			program_enrollment_course.status = "Enrolled"
			program_enrollment_course.insert()


@frappe.whitelist()
def get_inv_data_nat():
		print("Method called")
		today = frappe.utils.today()
		company = frappe.defaults.get_defaults().company
		currency = erpnext.get_company_currency(company)
		receivable_account = frappe.db.get_single_value('Seminary Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Seminary Settings', 'company')
		cost_center = frappe.db.get_single_value('Seminary Settings', 'cost_center') or None
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
		receivable_account = frappe.db.get_single_value('Seminary Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Seminary Settings', 'company')
		cost_center = frappe.db.get_single_value('Seminary Settings', 'cost_center') or None
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
		receivable_account = frappe.db.get_single_value('Seminary Settings', 'receivable_account')
		income_account = frappe.db.sql("""select default_income_account from `tabCompany` where name=%s""", company)[0][0]
		company = frappe.db.get_single_value('Seminary Settings', 'company')
		cost_center = frappe.db.get_single_value('Seminary Settings', 'cost_center') or None
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
		return 
	else:
		return program_enrollments

@frappe.whitelist()
def get_course_rosters(name):
	course_rosters = []
	course_rosters = frappe.get_all(
		"Scheduled Course Roster",
		filters={"course_sc": name},
		fields=["course_sc", "stuname_roster", "stuimage", "student", "stuemail_rc", "program_std_scr", "audit_bool", "active"],
		)
	if not course_rosters:
		print("No course rosters found")
		return []
	else:
		return course_rosters
	
@frappe.whitelist()
def grade_thisstudent(name):
		
	csr = frappe.get_doc("Scheduled Course Roster", name)
	cs = csr.course_sc
	course = frappe.get_doc("Course Schedule", cs)
	gscale = course.gradesc_cs
	grading_scale = frappe.get_doc("Grading Scale", gscale)
	gmax = grading_scale.maxnumgrade
	detail = csr.stdroster_grade
	if grading_scale.grscale_type == "Points":
		for row in detail:
			score = row.rawscore_card
			maxscore = row.maximum_score
			named = row.name
			extracredit = row.extracredit_card
			if score is not None  and extracredit == 0:
				wscore = round((score / gmax) * maxscore, 2)
				row.grade = get_grade(grading_scale, score)
				row.score = wscore
				
			frappe.db.set_value("Course Assess Results Detail", named, {
				"grade": row.grade,
				"score": row.score
			}
			)
		csr.save()
		return "done"
	
@frappe.whitelist()
def get_gradepass(grading_scale, percentage):
	"""Returns Grade based on the Grading Scale and Score.

	:param Grading Scale: Grading Scale
	:param Percentage: Score Percentage Percentage
	"""
	grading_scale_intervals = {}
	if not hasattr(frappe.local, "grading_scale_pass"):
		grading_scale = frappe.get_all(
			"Grading Scale Interval",
			fields=["grade_pass", "threshold"],
			filters={"parent": grading_scale},
		)
		frappe.local.grading_scale = grading_scale
	for d in frappe.local.grading_scale:
		grading_scale_intervals.update({d.threshold: d.grade_pass})
	intervals = sorted(grading_scale_intervals.keys(), key=float, reverse=True)
	for interval in intervals:
		if flt(percentage) >= interval:
			gradepass = grading_scale_intervals.get(interval)
			print(gradepass)
			break
		else:
			gradepass = ""
	return gradepass

@frappe.whitelist()
def fgrade_this_std(name):
	print("fgrade_this_std called")
	csr = frappe.get_doc("Scheduled Course Roster", name)
	cs = csr.course_sc
	course = frappe.get_doc("Course Schedule", cs)
	gscale = course.gradesc_cs
	grading_scale = frappe.get_doc("Grading Scale", gscale)
	if grading_scale.grscale_type == "Points":
		fscore1 = frappe.db.sql("""select sum(score) from `tabCourse Assess Results Detail` where parent = %s""", (name))
		fscore1 = fscore1[0][0] if fscore1 and fscore1[0][0] is not None else 0
		fscore2 = frappe.db.sql("""select sum(actualextrapt_card) from `tabCourse Assess Results Detail` where extracredit_card = 1 and parent = %s""", (name))
		fscore2 = fscore2[0][0] if fscore2 and fscore2[0][0] is not None else 0
		fscore = fscore1 + fscore2
		if fscore >=100:
			fscore = 100
		else: 
			fscore = fscore
		frappe.db.set_value("Scheduled Course Roster", name, "fscore", fscore)
		print(fscore)
		fgrade = get_grade(grading_scale, fscore)
		frappe.db.set_value("Scheduled Course Roster", name, "fgrade", fgrade)
		fgradepass = get_gradepass(grading_scale, fscore)
		print(fgradepass)
		frappe.db.set_value("Scheduled Course Roster", name, "fgradepass", fgradepass)
		return "done"

@frappe.whitelist()
def send_grades(doc=None,**kwargs):
	
	if isinstance(doc, str):
    # Parse the JSON string if it's a string
		document_data = json.loads(doc)
		docname = document_data.get("name")
	else:
    # Use doc.get("name") if it's already a dictionary (fallback)
		docname = doc.get("name")
	print(docname)
	records = frappe.get_all("Scheduled Course Roster", filters={"course_sc": docname}, fields=["name", "course_sc", "stuname_roster", "student", "program_std_scr", "audit_bool", "active"])
	for record in records:
		# Process each record here
		named = record.name
		print(named)
		course_sc = record.course_sc
		student = record.student
		program = record.program_std_scr
		audit_bool = record.audit_bool
		active = record.active
		pe = frappe.db.get_value("Program Enrollment", {"student": student, "program": program}, "name")
		totalcredits = frappe.db.get_value("Program Enrollment", pe, "totalcredits")
		# Perform further operations with the record
		if audit_bool == 0 and active == 1:
			grade_thisstudent(named)
			fgrade_this_std(named)
			fscore = frappe.db.get_value("Scheduled Course Roster", named, "fscore")
			fgrade = frappe.db.get_value("Scheduled Course Roster", named, "fgrade")
			fgradepass = frappe.db.get_value("Scheduled Course Roster", named, "fgradepass")
			pec = frappe.db.get_value("Program Enrollment Course", {"parent": pe, "course": course_sc}, "name")
			credits = frappe.db.get_value("Program Enrollment Course", pec, "credits")
			if fgradepass == "Fail":
				credits = 0
			newcredits = totalcredits + (int(credits) if credits is not None else 0)
			print(newcredits)
			frappe.db.set_value("Program Enrollment Course", pec, 
					   {"pec_finalgradenum": fscore,
		 				 "pec_finalgradecode": fgrade,
						 "status": fgradepass})
			frappe.db.set_value("Program Enrollment", pe, "totalcredits", newcredits)
			frappe.db.set_value("Scheduled Course Roster", named, 
					   {"active": "0",
		 				"docstatus": "1"})
		else: continue
	frappe.db.set_value("Course Schedule", docname, 
					 {"grades_sent": "1",
	   				"open_enroll": "0",
	   				"docstatus": "1"})		
	return "All grades sent"
	# Add a message to confirm to the user

@frappe.whitelist()	
def course_event(name):
	course = frappe.get_doc("Course Schedule", name)
	datest = str(course.c_datestart)  # Convert datest to a string
	timest = str(course.from_time)  # Convert timest to a string
	datetimest = datest + " " + timest
	datetimest = datetime.strptime(datetimest, "%Y-%m-%d %H:%M:%S") # Convert datetimest to a datetime object
	print(datetimest)
	datef = str(course.c_dateend)  # Convert datef to a string
	timef = str(course.to_time)  # Convert timef to a string
	datetimef = datef + " " + timef
	datetimef = datetime.strptime(datetimef, "%Y-%m-%d %H:%M:%S")
	datetimef2 = datest + " " + timef
	datetimef2 = datetime.strptime(datetimef2, "%Y-%m-%d %H:%M:%S")
	dateend = course.c_dateend
	print(datetimef)
	participants = []
	participants = course_rosters = frappe.get_all(
		"Scheduled Course Roster",
		filters={"course_sc": name})
	event_participants = []  # Create an empty list for event participants
	for participant in participants:
		event_participants.append({
			"reference_doctype": "Scheduled Course Roster",
			"reference_docname": participant.name,
			"email": participant.stuemail_rc
		})
	if datef == datest:
		# Create a new calendar event
		event = frappe.get_doc({
			"doctype": "Event",
			"subject": name,
			"starts_on": datetimest,
			"ends_on": datetimef,
			"event_type": "Public",
			"event_category": "Event",
			"description": name + " Room: " + (course.room or "N/A"),
			"event_participants": event_participants
		})
	elif datef > datest:
		# Create a new calendar event
		event = frappe.get_doc({
			"doctype": "Event",
			"subject": name,
			"starts_on": datetimest,
			"ends_on": datetimef2,
			"repeat_this_event": 1,
			"repeat_on": "Weekly",
			"repeat_till": dateend,
			"monday": course.monday,
			"tuesday": course.tuesday,
			"wednesday": course.wednesday,
			"thursday": course.thursday,
			"friday": course.friday,
			"saturday": course.saturday,
			"sunday": course.sunday,
			"event_type": "Public",
			"event_category": "Event",
			"description": name + " Room: " + (course.room or "N/A"),
			"event_participants": event_participants
		})
	event.insert()
	print(event)


	return "event created"
			
			
		
@frappe.whitelist()
def get_doctrinal_statement():
	print("Method DS called")
	doctrinal_statement = frappe.get_doc('Doctrinal Statement')
	doctrinal_statement = doctrinal_statement.doctrinalst
	print(doctrinal_statement)
	return doctrinal_statement

	
	

	