# Copyright (c) 2015, Frappe Technologies and contributors

import frappe
from frappe import _


class OverlapError(frappe.ValidationError):
	pass


def validate_overlap_for(doc, doctype, fieldname, value=None):
	"""Checks overlap for specified field.

	:param fieldname: Checks Overlap for this field
	"""

	existing = get_overlap_for(doc, doctype, fieldname, value)
	if existing:
		frappe.throw(
			_("This {0} conflicts with {1} for {2} {3}").format(
				doc.doctype,
				existing.name,
				doc.meta.get_label(fieldname) if not value else fieldname,
				value or doc.get(fieldname),
			),
			OverlapError,
		)


def get_overlap_for(doc, doctype, fieldname, value=None):
	"""Returns overlaping document for specified field.

	:param fieldname: Checks Overlap for this field
	"""

	existing = frappe.db.sql(
		"""select name, from_time, to_time from `tab{0}`
		where `{1}`=%(val)s and schedule_date = %(schedule_date)s and
		(
			(from_time > %(from_time)s and from_time < %(to_time)s) or
			(to_time > %(from_time)s and to_time < %(to_time)s) or
			(%(from_time)s > from_time and %(from_time)s < to_time) or
			(%(from_time)s = from_time and %(to_time)s = to_time))
		and name!=%(name)s and docstatus!=2""".format(
			doctype, fieldname
		),
		{
			"schedule_date": doc.schedule_date,
			"val": value or doc.get(fieldname),
			"from_time": doc.from_time,
			"to_time": doc.to_time,
			"name": doc.name or "No Name",
		},
		as_dict=True,
	)

	return existing[0] if existing else None


def validate_duplicate_student(students):
	unique_students = []
	for stud in students:
		if stud.student in unique_students:
			frappe.throw(
				_("Student {0} - {1} appears Multiple times in row {2} & {3}").format(
					stud.student, stud.student_name, unique_students.index(stud.student) + 1, stud.idx
				)
			)
		else:
			unique_students.append(stud.student)

	return None


# LMS Utils

@frappe.whitelist(allow_guest=True)
def get_user_info():
	if frappe.session.user == "Guest":
		return None

	user = frappe.db.get_value(
		"User",
		frappe.session.user,
		["name", "email", "enabled", "user_image", "full_name", "user_type", "username"],
		as_dict=1,
	)
	user["roles"] = frappe.get_roles(user.name)
	user.is_instructor = "Academics User" in user.roles
	user.is_moderator = "Seminary Manager" in user.roles
	user.is_evaluator = "Instructor" in user.roles
	user.is_student = "Student" in user.roles
	user.is_system_manager = "System Manager" in user.roles
	return user

def has_course_moderator_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Seminary Manager"},
		"name",
	)


def has_course_evaluator_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Instructor"},
		"name",
	)


def has_student_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Student"},
		"name",
	)
@frappe.whitelist(allow_guest=True)
def get_courses_for_student(student):
	courses =frappe.db.sql(
		"""select cei.coursesc_ce as name, cei.course_data as course, cei.stu_user, cei.student_ce, cei.student_name, cs.course_image, cs.course_description_for_lms, cs.published, cs. academic_term, cs.syllabus, cs.modality, cs.c_datestart
from `tabCourse Enrollment Individual` cei, `tabCourse Schedule` cs
where cs.name = cei.coursesc_ce
and cei.stu_user = %s""", student, as_dict=True
	)
	return courses

@frappe.whitelist(allow_guest=True)
def get_courses(filters=None, start=0, page_length=20):
	print("get_courses called")
	"""Returns the list of courses."""

	if not filters:
		filters = {}

	
	fields = get_course_fields()

	courses = frappe.get_all(
		"Course Schedule",
		filters=filters,
		fields=fields,
		start=start,
		page_length=page_length,
	)
	courses = get_enrollment_details(courses)
	courses = get_course_card_details(courses)
	print(courses)
	return courses


def get_course_card_details(courses):
	for course in courses:
		course.instructors = get_instructors(course.name)
	return courses

def get_instructors(course):
	instructor_details = []
	instructors = frappe.get_all(
		"Course Schedule Instructors", {"parent": course}, order_by="idx", pluck="instructor"
	)

	for instructor in instructors:
		instructor_details.append(
			frappe.db.get_value(
				"Instructor",
				instructor,
				["instructor_name", "user", "image", "shortbio"],
				as_dict=True,
			)
		)
	return instructor_details
	
def get_course_or_filters(filters):
	or_filters = {}
	or_filters.update({"title": filters.get("title")})
	or_filters.update({"course_description_for_lms": filters.get("title")})
	return or_filters





def get_enrollment_details(courses):
	for course in courses:
		filters = {
			"course_sc": course.name,
			"stuemail_rc": frappe.session.user,
			"active": 1
		}

		course.membership = frappe.db.get_value(
				"Scheduled Course Roster",
				filters,
				["stuname_roster", "stuimage", "audit_bool", "course_sc", "current_lesson", "progress", "stuemail_rc"],
				as_dict=1,
			)

	return courses





def get_course_fields():
	return [
		"name",
		"course",
		"course_image",
		"course_description_for_lms",
		"published",
		"syllabus",
		"modality",
		"academic_term",
		"c_datestart",
		"c_dateend",
	]




@frappe.whitelist(allow_guest=True)
def get_course_outline(course, progress=False):
	"""Returns the course outline."""
	outline = []
	chapters = frappe.get_all(
		"Course Schedule Chapter Reference", {"parent": course}, ["chapter", "idx"], order_by="idx"
	)
	for chapter in chapters:
		chapter_details = frappe.db.get_value(
			"Course Schedule Course Chapter",
			chapter.chapter,
			["name", "chapter_title", "is_scorm_package", "launch_file", "scorm_package"],
			as_dict=True,
		)
		chapter_details["idx"] = chapter.idx
		chapter_details.lessons = get_lesson(course, chapter_details, progress=progress)

		if chapter_details.is_scorm_package:
			chapter_details.scorm_package = frappe.db.get_value(
				"File",
				chapter_details.scorm_package,
				["file_name", "file_size", "file_url"],
				as_dict=1,
			)

		outline.append(chapter_details)
	return outline

def get_membership(course, member=None):
	if not member:
		member = frappe.session.user

	filters = {"member": member, "course": course}

	if frappe.db.exists("Scheduled Course Roster", filters):
		membership = frappe.db.get_value(
			"Scheduled Course Roster",
			filters,
			[
				"stuname_roster",
				"current_lesson",
				"progress",
				"student",
				"program",
				
			],
			as_dict=True,
		)
		return membership

	return False

@frappe.whitelist(allow_guest=True)
def get_lesson(course, chapter, lesson):
	chapter_name = frappe.db.get_value(
		"Course Schedule Chapter Reference", {"parent": course, "idx": chapter}, "chapter"
	)
	lesson_name = frappe.db.get_value(
		"Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson"
	)
	lesson_details = frappe.db.get_value(
		"Course Schedule Course Lesson",
		lesson_name,
		["title", "is_scorm_package"],
		as_dict=1,
	)
	if not lesson_details or lesson_details.is_scorm_package:
		return {}

	membership = get_membership(course)
	course_info = frappe.db.get_value(
		"Course Schedule", course, ["course"], as_dict=1
	)

	if (
		not membership
		and not has_course_moderator_role()
		and not is_instructor(course)
	):
		return {
			"no_preview": 1,
			"title": lesson_details.title,
			"course_title": course_info.title,
		}

	lesson_details = frappe.db.get_value(
		"Course Schedule Lesson",
		lesson_name,
		[
			"name",
			"lesson_title",
			"body",
			"creation",
			"youtube",
			"quiz_id",
			"question",
			"file_type",
			"instructor_notes",
			"course",
			"content",
			"instructor_content",
		],
		as_dict=True,
	)

	if frappe.session.user == "Guest":
		progress = 0
	else:
		progress = get_progress(course, lesson_details.name)

	lesson_details.rendered_content = render_html(lesson_details)
	neighbours = get_neighbour_lesson(course, chapter, lesson)
	lesson_details.next = neighbours["next"]
	lesson_details.progress = progress
	lesson_details.prev = neighbours["prev"]
	lesson_details.membership = membership
	lesson_details.instructors = get_instructors(course)
	lesson_details.course_title = course_info.title
	return lesson_details

def get_progress(course, lesson, member=None):
	if not member:
		member = frappe.session.user

	return frappe.db.exists(
		"Course Schedule Progress",
		{"course": course, "member": member, "lesson": lesson},
		["status"],
	)
def render_html(lesson):
	youtube = lesson.youtube
	quiz_id = lesson.quiz_id
	body = lesson.body

	if youtube and "/" in youtube:
		youtube = youtube.split("/")[-1]

	quiz_id = "{{ Quiz('" + quiz_id + "') }}" if quiz_id else ""
	youtube = "{{ YouTubeVideo('" + youtube + "') }}" if youtube else ""
	text = youtube + body + quiz_id

	if lesson.question:
		assignment = "{{ Assignment('" + lesson.question + "-" + lesson.file_type + "') }}"
		text = text + assignment

	return text

def get_neighbour_lesson(course, chapter, lesson):
	numbers = []
	current = f"{chapter}.{lesson}"
	chapters = frappe.get_all("Course Schedule Chapter Reference", {"parent": course}, ["idx", "chapter"])
	for chapter in chapters:
		lessons = frappe.get_all("Course Schedule Lesson Reference", {"parent": chapter.chapter}, pluck="idx")
		for lesson in lessons:
			numbers.append(f"{chapter.idx}.{lesson}")

	tuples_list = [tuple(int(x) for x in s.split(".")) for s in numbers]
	sorted_tuples = sorted(tuples_list)
	sorted_numbers = [".".join(str(num) for num in t) for t in sorted_tuples]
	index = sorted_numbers.index(current)

	return {
		"prev": sorted_numbers[index - 1] if index - 1 >= 0 else None,
		"next": sorted_numbers[index + 1] if index + 1 < len(sorted_numbers) else None,
	}

def is_instructor(course):
	return (
		len(list(filter(lambda x: x.name == frappe.session.user, get_instructors(course))))
		> 0
	)

def get_current_student():
	"""Returns current student from frappe.session.user

	Returns:
	        object: Student Document
	"""
	email = frappe.session.user
	if email in ("Administrator", "Guest"):
		return None
	try:
		student_id = frappe.get_all("Student", {"student_email_id": email}, ["name"])[0].name
		return frappe.get_doc("Student", student_id)
	except (IndexError, frappe.DoesNotExistError):
		return None


def get_enrollment(master, document, student):
	"""Gets enrollment for course or program

	Args:
	        master (string): can either be program or course
	        document (string): program or course name
	        student (string): Student ID

	Returns:
	        string: Enrollment Name if exists else returns empty string
	"""
	if master == "program":
		enrollments = frappe.get_all(
			"Program Enrollment",
			filters={"student": student, "program": document, "docstatus": 1},
		)
	if master == "course":
		enrollments = frappe.get_all(
			"Course Enrollment", filters={"student": student, "course": document}
		)

	if enrollments:
		return enrollments[0].name
	else:
		return None


@frappe.whitelist()
def enroll_in_program(program_name, student=None):
	"""Enroll student in program

	Args:
	        program_name (string): Name of the program to be enrolled into
	        student (string, optional): name of student who has to be enrolled, if not
	                provided, a student will be created from the current user

	Returns:
	        string: name of the program enrollment document
	"""
	if has_super_access():
		return

	if not student == None:
		student = frappe.get_doc("Student", student)
	else:
		# Check if self enrollment in allowed
		program = frappe.get_doc("Program", program_name)
		if not program.allow_self_enroll:
			return frappe.throw(_("You are not allowed to enroll for this course"))

		student = get_current_student()
		if not student:
			student = create_student_from_current_user()

	# Check if student is already enrolled in program
	enrollment = get_enrollment("program", program_name, student.name)
	if enrollment:
		return enrollment

	# Check if self enrollment in allowed
	program = frappe.get_doc("Program", program_name)
	if not program.allow_self_enroll:
		return frappe.throw(_("You are not allowed to enroll for this course"))

	# Enroll in program
	program_enrollment = student.enroll_in_program(program_name)
	return program_enrollment.name


def has_super_access():
	"""Check if user has a role that allows full access to LMS

	Returns:
	        bool: true if user has access to all lms content
	"""
	current_user = frappe.get_doc("User", frappe.session.user)
	roles = set([role.role for role in current_user.roles])
	return bool(
		roles
		& {
			"Administrator",
			"Instructor",
			"Seminary Manager",
			"System Manager",
			"Academic User",
		}
	)



def create_student_from_current_user():
	user = frappe.get_doc("User", frappe.session.user)

	student = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": user.first_name,
			"last_name": user.last_name,
			"student_email_id": user.email,
			"user": frappe.session.user,
		}
	)

	student.save(ignore_permissions=True)
	return student









