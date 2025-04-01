# Copyright (c) 2015, Frappe Technologies and contributors

import frappe
from frappe import _
import re
import string
import frappe
import hashlib
import json
import requests


from frappe.desk.doctype.dashboard_chart.dashboard_chart import get_result
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.desk.search import get_user_groups
from frappe.desk.notifications import extract_mentions
from frappe.utils import (
	add_months,
	cint,
	cstr,
	ceil,
	flt,
	fmt_money,
	format_date,
	get_datetime,
	getdate,
	validate_phone_number,
	get_fullname,
	pretty_date,
	get_time_str,
	nowtime,
	format_datetime,
)
from frappe.utils.dateutils import get_period
from seminary.seminary.md import find_macros, markdown_to_html

class OverlapError(frappe.ValidationError):
	pass

RE_SLUG_NOTALLOWED = re.compile("[^a-z0-9]+")


def slugify(title, used_slugs=None):
	"""Converts title to a slug.

	If a list of used slugs is specified, it will make sure the generated slug
	is not one of them.

	    >>> slugify("Hello World!")
	    'hello-world'
	    >>> slugify("Hello World!", ['hello-world'])
	    'hello-world-2'
	    >>> slugify("Hello World!", ['hello-world', 'hello-world-2'])
	    'hello-world-3'
	"""
	if not used_slugs:
		used_slugs = []

	slug = RE_SLUG_NOTALLOWED.sub("-", title.lower()).strip("-")
	used_slugs = set(used_slugs)

	if slug not in used_slugs:
		return slug

	count = 2
	while True:
		new_slug = f"{slug}-{count}"
		if new_slug not in used_slugs:
			return new_slug
		count = count + 1

def generate_slug(title, doctype):
	result = frappe.get_all(doctype, fields=["name"])
	slugs = {row["name"] for row in result}
	return slugify(title, used_slugs=slugs)


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

@frappe.whitelist()
def get_all_users():
	frappe.only_for(["Academics User", "Instructor", "Seminary Manager"])
	users = frappe.get_all(
		"User",
		{
			"enabled": 1,
		},
		["name", "full_name", "user_image"],
	)

	return {user.name: user for user in users}

@frappe.whitelist(allow_guest=True)
def has_course_moderator_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Seminary Manager"},
		"name",
	)
@frappe.whitelist(allow_guest=True)
def has_course_instructor_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Academics User"},
		"name",
	)
@frappe.whitelist(allow_guest=True)
def has_course_evaluator_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Instructor"},
		"name",
	)

@frappe.whitelist(allow_guest=True)
def has_student_role(member=None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "Student"},
		"name",
	)
@frappe.whitelist(allow_guest=True)
def get_courses_for_student(student):
	courses =frappe.db.sql(
		"""select cei.coursesc_ce as name, cei.course_data as course, cs.course_image, cs.course_description_for_lms, cs.short_introduction, cs. academic_term
from `tabCourse Enrollment Individual` cei, `tabCourse Schedule` cs
where cs.name = cei.coursesc_ce and cs.published = 1
and cei.stu_user = %s""", student, as_dict=True
	)
	
	return courses

@frappe.whitelist(allow_guest=True)
def get_courses(filters=None, start=0, page_length=20):
	
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
	
	return courses


def get_course_card_details(courses):
	for course in courses:
		course.instructors = get_instructors(course.name)
	return courses

@frappe.whitelist(allow_guest=True)
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
				["instructor_name", "user", "profileimage", "shortbio", "bio"],
				as_dict=True,
			)
		)
	return instructor_details

@frappe.whitelist(allow_guest=True)
def get_instructor(instructorName):
	instructor = frappe.db.get_value(
				"Instructor",
				instructorName,
				["instructor_name", "user", "profileimage", "shortbio", "bio"],
				as_dict=True,
			)
	print(instructor)
	return instructor
	
def get_course_or_filters(filters):
	or_filters = {}
	or_filters.update({"title": filters.get("title")})
	or_filters.update({"course_description_for_lms": filters.get("title")})
	return or_filters



@frappe.whitelist(allow_guest=True)
def get_course_outline(course, progress=False):
	"""Returns the course outline."""
	outline = []
	
	chapters = frappe.get_all(
		"Course Schedule Chapter Reference", {"parent": course}, ["chapter", "idx"], order_by="idx"
	)
	for chapter in chapters:
		chapter_details = frappe.db.get_value(
			"Course Schedule Chapter",
			chapter.chapter,
			["name", "chapter_title", "is_scorm_package", "launch_file", "scorm_package"],
			as_dict=True,
		)
		chapter_details["idx"] = chapter.idx
				
		chapter_details.lessons = get_lessons(course, chapter_details, progress=progress)

		if chapter_details.is_scorm_package:
			chapter_details.scorm_package = frappe.db.get_value(
				"File",
				chapter_details.scorm_package,
				["file_name", "file_size", "file_url"],
				as_dict=1,
			)

		
		outline.append(chapter_details)
	return outline

@frappe.whitelist(allow_guest=True)
def get_course_title(course):
	return frappe.db.get_value("Course Schedule", course, "course")

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
		"short_introduction",
		"course_description_for_lms",
		"published",
		"syllabus",
		"modality",
		"academic_term",
		"c_datestart",
		"c_dateend",
	]

@frappe.whitelist(allow_guest=True)
def get_course_details(course):
	course_details = frappe.db.get_value(
		"Course Schedule",
		course,
		[
		"name",
		"course",
		"course_image",
		"short_introduction",
		"course_description_for_lms",
		"published",
		"syllabus",
		"modality",
		"academic_term",
		"c_datestart",
		"c_dateend",
		"enrollments",
		"lessons"
		],
		as_dict=1,
	)
	
	course_details.instructors = get_instructors(course_details.name)
	
	if frappe.session.user == "Guest":
		course_details.membership = None
		course_details.is_instructor = False
	else:
		course_details.membership = frappe.db.get_value(
			"Scheduled Course Roster",
			{"stuemail_rc": frappe.session.user, "course_sc": course_details.name},
			["name", "course_sc", "current_lesson", "progress", "stuemail_rc"],
			as_dict=1,
		)

	if course_details.membership and course_details.membership.current_lesson:
		course_details.current_lesson = get_lesson_index(
			course_details.membership.current_lesson
		)

	return course_details

def get_lesson_index(lesson_name):
	"""Returns the {chapter_index}.{lesson_index} for the lesson."""
	lesson = frappe.db.get_value(
		"Course Schedule Lesson Reference", {"lesson": lesson_name}, ["idx", "parent"], as_dict=True
	)
	if not lesson:
		return "1-1"

	chapter = frappe.db.get_value(
		"Course Schedule Chapter Reference", {"chapter": lesson.parent}, ["idx"], as_dict=True
	)
	if not chapter:
		return "1-1"

	return f"{chapter.idx}-{lesson.idx}"


def get_lesson_url(course, lesson_number):
	if not lesson_number:
		return
	return f"/courses/{course}/learn/{lesson_number}"



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

def get_chapters(course):
	"""Returns all chapters of this course."""
	if not course:
		return []
	chapters = frappe.get_all(
		"Course Schedule Chapter Reference", {"parent": course}, ["idx", "chapter"], order_by="idx"
	)
	for chapter in chapters:
		chapter_details = frappe.db.get_value(
			"Course Schedule Chapter",
			{"name": chapter.chapter},
			["name", "chapter_title"],
			as_dict=True,
		)
		chapter.update(chapter_details)
	return chapters

@frappe.whitelist(allow_guest=True)
def get_lesson(course, chapter, lesson):
	chapter_name = frappe.db.get_value(
		"Course Schedule Chapter Reference", {"parent": course, "idx": chapter}, "chapter"
	)
	print(f"Chapter Name: {chapter_name}")  # Debug print

	lesson_name = frappe.db.get_value(
		"Course Schedule Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson"
	)
	print(f"Lesson Name: {lesson_name}")  # Debug print

	if not lesson_name:
		return {}
		
	lesson_details = frappe.db.get_value(
		"Course Lesson",
		lesson_name,
		["lesson_title", "is_scorm_package"],
		as_dict=1,
	)
	print(f"Lesson Details (first): {lesson_details}")  # Debug print

	# if not lesson_details:
	# 	return {}

	# membership = get_membership(course)
	
	# if (
	# 	not membership
	# 	and not has_course_moderator_role()
	# 	and not is_instructor(course)
	# ):
	# 	return {
	# 		"lesson_title": lesson_details.lesson_title,
	# 		"course_title": course,
	# 	}
	

	print(f"Fetching detailed lesson info for: {lesson_name}")  # Debug print

	lesson_details = frappe.db.get_value(
		"Course Lesson",
		lesson_name,
		[
			"name",
			"allow_discuss",
			"lesson_title",
			"preview",	
			"body",
			"creation",
			"youtube",
			"quiz_id",
			"exam",
			"assessment_criteria",
			"assignment_id",
			"course_sc",
			"content",
			"instructor_content",
			"instructor_notes",
		],
		as_dict=True,
	)
	print(f"Lesson Details (second): {lesson_details}")  # Debug print

	

	if frappe.session.user == "Guest":
		progress = 0
	else:
		progress = get_progress(course, lesson_details.name)

	lesson_details.rendered_content = render_html(lesson_details)
	neighbours = get_neighbour_lesson(course, chapter, lesson)
	lesson_details.next = neighbours["next"]
	lesson_details.progress = progress
	lesson_details.prev = neighbours["prev"]
	# lesson_details.membership = membership
	lesson_details.instructors = get_instructors(course)
	lesson_details.course_title = frappe.db.get_value("Course Schedule", course, "course")
	print(f"Lesson Details (third): {lesson_details}")  # Debug print
	
	return lesson_details

def get_course_progress(course, member=None):
	"""Returns the course progress of the session user"""
	lesson_count = get_lessons(course, get_details=False)
	if not lesson_count:
		return 0
	completed_lessons = frappe.db.count(
		"Course Schedule Progress",
		{"course": course, "member": member or frappe.session.user, "status": "Complete"},
	)
	precision = cint(frappe.db.get_default("float_precision")) or 3
	return flt(((completed_lessons / lesson_count) * 100), precision)

def get_progress(course, lesson, member=None):
	if not member:
		member = frappe.session.user

	return frappe.db.exists(
		"Course Schedule Progress",
		{"course": course, "member": member, "lesson": lesson},
		["status"],
	)

def get_lessons(course, chapter=None, get_details=True, progress=False):
	"""If chapter is passed, returns lessons of only that chapter.
	Else returns lessons of all chapters of the course"""
	lessons = []
	lesson_count = 0
	if chapter:
		if get_details:
			return get_lesson_details(chapter, progress=progress)
		else:
			return frappe.db.count("Course Schedule Lesson Reference", {"parent": chapter.name})

	for chapter in get_chapters(course):
		if get_details:
			lessons += get_lesson_details(chapter, progress=progress)
		else:
			lesson_count += frappe.db.count("Course Schedule Lesson Reference", {"parent": chapter.name})

	return lessons if get_details else lesson_count

def get_lesson_details(chapter, progress=False):
	lessons = []
	lesson_list = frappe.get_all(
		"Course Schedule Lesson Reference", {"parent": chapter.name}, ["lesson", "idx"], order_by="idx"
	)
	for row in lesson_list:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			row.lesson,
			[
				"name",
				"lesson_title",
				"preview",
				"content",
				"body",
				"creation",
				"youtube",
				"assessment_criteria",
				"quiz_id",
				"assignment_id",
				"exam",
				"instructor_content",
				"course_sc"
				
			],
			as_dict=True,
		)
		lesson_details.number = f"{chapter.idx}.{row.idx}"
		lesson_details.icon = get_lesson_icon(lesson_details.body, lesson_details.content)

		if progress:
			lesson_details.is_complete = get_progress(lesson_details.course, lesson_details.name)

		lessons.append(lesson_details)
	return lessons


def get_lesson_icon(body, content):
	if content:
		print("Content: ", content)
		try:
			content = json.loads(content)
			print("Content JSONfied: ", content)
		except json.JSONDecodeError:
			print("Invalid JSON content")
			return "icon-list"

		for block in content.get("blocks"):
			if block.get("type") == "upload" and block.get("data").get("file_type").lower() in [
				"mp4",
				"webm",
				"ogg",
				"mov",
			]:
				return "icon-youtube"

			if block.get("type") == "embed" and block.get("data").get("service") in [
				"youtube",
				"vimeo",
			]:
				return "icon-youtube"

			if block.get("type") == "quiz":
				return "icon-quiz"

		return "icon-list"

	macros = find_macros(body)
	for macro in macros:
		if macro[0] == "YouTubeVideo" or macro[0] == "Video":
			return "icon-youtube"
		elif macro[0] == "Quiz":
			return "icon-quiz"

	return "icon-list"



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
	
def get_lesson_count(course):
	lesson_count = 0
	chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["chapter"])
	for chapter in chapters:
		lesson_count += frappe.db.count("Lesson Reference", {"parent": chapter.chapter})

	return lesson_count

@frappe.whitelist()
def get_lesson_creation_details(course, chapter, lesson):
	chapter_name = frappe.db.get_value(
		"Course Schedule Chapter Reference", {"parent": course, "idx": chapter}, "chapter"
	)
	lesson_name = frappe.db.get_value(
		"Course Schedule Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson"
	)

	if lesson_name:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			lesson_name,
			[
				"name",
				"lesson_title",
				"preview",
				"body",
				"content",
				"instructor_notes",
				"instructor_content",
				"assessment_criteria",
				"youtube",
				"quiz_id",
				"assignment_id",
				"exam",
			],
			as_dict=1,
		)

	return {
		"course_title": frappe.db.get_value("Course Schedule", course, "course"),
		"chapter": frappe.db.get_value(
			"Course Schedule Chapter", chapter_name, ["chapter_title", "name"], as_dict=True
		),
		"lesson": lesson_details if lesson_name else None,
	}

@frappe.whitelist()
def get_question_details(question):
	fields = ["question", "type", "multiple"]
	for i in range(1, 5):
		fields.append(f"option_{i}")
		fields.append(f"explanation_{i}")

	question_details = frappe.db.get_value("Question", question, fields, as_dict=1)
	return question_details

@frappe.whitelist()
def get_all_questions_details(questions):
	
	questions_str = "', '".join(questions)
	all_question_details =  frappe.db.sql(
			f"""select distinct qq.name, qq.points, qq.question_detail, q.name as question, q.type, q.option_1, q.option_2, q.option_3, q.option_4, q.explanation_1, q.explanation_2, q.explanation_3, q.explanation_4 
from `tabQuestion` q, `tabQuiz Question` qq
where q.name = qq.question and qq.name in ('{questions_str}')""", as_dict=1)			
	return all_question_details

@frappe.whitelist()
def get_open_question_details(question):
	fields = ["question", "explanation"]
	question_details = frappe.db.get_value("Open Question", question, fields, as_dict=1)
	return question_details

@frappe.whitelist()
def get_all_open_questions_details(questions):
	if not questions:
		frappe.throw(_("Questions parameter is required"))

	    # Ensure questions is a list
	if isinstance(questions, str):
		questions = frappe.parse_json(questions)
	all_question_details =  frappe.db.sql(
			f"""select distinct qq.name, qq.points, qq.question_detail, q.name as question_name, q.explanation
from `tabOpen Question` q, `tabExam Question` qq
where q.name = qq.question and qq.name in ({', '.join(frappe.db.escape(q) for q in questions)})""", as_dict=1)			
	print("All questions details: " + str(all_question_details))
	return all_question_details

@frappe.whitelist()
def get_assessments(course):
	assessments = frappe.get_all(
		"Scheduled Course Assess Criteria",
		filters={"parent": course},
		fields=["*"],
	)
	print(assessments)
	return assessments

@frappe.whitelist()
def get_gradebook(course):
	students = frappe.get_all(
		"Scheduled Course Roster",
		filters={"course_sc": course},
		fields=["name", "stuname_roster", "stuemail_rc", "audit_bool", "active", "stuemail_rc", "program_std_scr", "progress"],
	)
	for student in students:
		student["assessments"] = frappe.db.sql(
			f"""select r.name, r.rawscore_card, r.actualextrapt_card, scar.weight_scac, scar.extracredit_scac, scar.fudgepoints_scac, r.assessment_criteria, scar.title, scar.type, scar.due_date, scar.quiz, scar.exam, scar.assignment  
	from  `tabCourse Assess Results Detail` r, `tabScheduled Course Assess Criteria` scar
	where r.assessment_criteria = scar.name and r.parent ='{student.name}'""",
			as_dict=1,)
		
	print(students)
	return students

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


@frappe.whitelist()
def get_discussion_topics(doctype, docname, single_thread):
	if single_thread:
		filters = {
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
		topic = frappe.db.exists("Discussion Topic", filters)
		if topic:
			return frappe.db.get_value("Discussion Topic", topic, ["name"], as_dict=1)
		else:
			return create_discussion_topic(doctype, docname)
	topics = frappe.get_all(
		"Discussion Topic",
		{
			"reference_doctype": doctype,
			"reference_docname": docname,
		},
		["name", "title", "owner", "creation", "modified"],
		order_by="creation desc",
	)

	for topic in topics:
		topic.user = frappe.db.get_value(
			"User", topic.owner, ["full_name", "user_image"], as_dict=True
		)

	return topics


def create_discussion_topic(doctype, docname):
	doc = frappe.new_doc("Discussion Topic")
	doc.update(
		{
			"title": docname,
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
	)
	doc.insert()
	return doc


@frappe.whitelist()
def get_discussion_replies(topic):
	replies = frappe.get_all(
		"Discussion Reply",
		{
			"topic": topic,
		},
		["name", "owner", "creation", "modified", "reply"],
		order_by="creation",
	)

	for reply in replies:
		reply.user = frappe.db.get_value(
			"User", reply.owner, ["full_name", "user_image"], as_dict=True
		)

	return replies

@frappe.whitelist()
def ensure_single_topic(doctype, docname, title):
	print("Ensuring single topic for:", doctype, docname, title)
	existing_topic = frappe.get_all(
		"Discussion Topic",
		filters={"reference_doctype": doctype, "reference_docname": docname},
		fields=["name", "title"],
		limit=1,
	)

	if existing_topic:
		print("Existing topic found:", existing_topic)
		return existing_topic[0]

	# Create a new topic if none exists
	new_topic = frappe.get_doc({
		"doctype": "Discussion Topic",
		"reference_doctype": doctype,
		"reference_docname": docname,
		"title": title,
	})
	print("Creating new topic:", new_topic)
	new_topic.insert(ignore_permissions=True)
	return new_topic




