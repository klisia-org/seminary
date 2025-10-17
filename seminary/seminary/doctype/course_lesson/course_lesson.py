# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.telemetry import capture
from seminary.seminary.utils import get_course_progress
from ...md import find_macros
import json


class CourseLesson(Document):
	def validate(self):
		# self.check_and_create_folder()
		self.validate_quiz_id()
		self.updates_lessons()

	def validate_quiz_id(self):
		if self.quiz_id and not frappe.db.exists("Quiz", self.quiz_id):
			frappe.throw(_("Invalid Quiz ID"))

	def updates_lessons(self):
		if self.is_new():
			lesson_count = frappe.db.count("Course Lesson", filters={"course_sc": self.course_sc}) + 1
		else:
			lesson_count = frappe.db.count("Course Lesson", filters={"course_sc": self.course_sc})
		print(lesson_count)
		frappe.db.set_value("Course Schedule", self.course_sc, "lessons", lesson_count)
		

	def on_update(self):
		dynamic_documents = ["Exam", "Quiz", "Assignment", "Discussion"]
		for section in dynamic_documents:
			self.update_lesson_assessments(section)

	def update_lesson_assessments(self, section):
		"""
		Updates the lesson's assessment criteria fields (quiz, assignment, exam, discussion)
		by linking them to the corresponding Scheduled Course Assess Criteria.
		"""
		 # Check if the Course Lesson document exists
		if not frappe.db.exists("Course Lesson", self.name):
			print(f"Course Lesson {self.name} does not exist. Skipping updates for {section}.")
			return

		doctype_map = {"Exam": "Exam Activity", "Quiz": "Quiz", "Assignment": "Assignment Activity", "Discussion": "Discussion Activity"}

		# Parse lesson.content as JSON
		documents = []
		if self.content:
			content = json.loads(self.content)
			for block in content.get("blocks", []):
				block_type = block.get("type")
				block_data = block.get("data", {})

				if section == "Discussion":
					if block_type in {"discussion", "discussionActivity"}:
						documents.append(block_data.get("discussion") or block_data.get("discussionID"))
				elif block_type == section.lower():  # Match section type (e.g., "quiz", "assignment", "exam")
					documents.append(block_data.get(section.lower()))


		for name in documents:
			if section == "Quiz":
				# Update quiz_id and assessment_criteria_quiz
				frappe.db.set_value("Course Lesson", self.name, "quiz_id", name)
				scheduled_criteria = frappe.db.get_value(
					"Scheduled Course Assess Criteria",
					{"quiz": name, "parent": self.course_sc},
					"name",
				)
				frappe.db.set_value("Course Lesson", self.name, "assessment_criteria_quiz", scheduled_criteria)
				print(f"Updated Quiz: {name}, Criteria: {scheduled_criteria}")
				frappe.db.set_value("Scheduled Course Assess Criteria", scheduled_criteria, "lesson", self.name)

			elif section == "Assignment":
				# Update assignment_id and assessment_criteria_assignment
				frappe.db.set_value("Course Lesson", self.name, "assignment_id", name)
				scheduled_criteria = frappe.db.get_value(
					"Scheduled Course Assess Criteria",
					{"assignment": name, "parent": self.course_sc},
					"name",
				)
				frappe.db.set_value("Course Lesson", self.name, "assessment_criteria_assignment", scheduled_criteria)
				print(f"Updated Assignment: {name}, Criteria: {scheduled_criteria}")
				frappe.db.set_value("Scheduled Course Assess Criteria", scheduled_criteria, "lesson", self.name)
				print(f"Updated Scheduled Course Assess Criteria: {scheduled_criteria} with lesson: {self.name}")

			elif section == "Exam":
				# Update exam and assessment_criteria_exam
				frappe.db.set_value("Course Lesson", self.name, "exam", name)
				scheduled_criteria = frappe.db.get_value(
					"Scheduled Course Assess Criteria",
					{"exam": name, "parent": self.course_sc},
					"name",
				)
				frappe.db.set_value("Course Lesson", self.name, "assessment_criteria_exam", scheduled_criteria)
				print(f"Updated Exam: {name}, Criteria: {scheduled_criteria}")
				frappe.db.set_value("Scheduled Course Assess Criteria", scheduled_criteria, "lesson", self.name)
				print(f"Updated Scheduled Course Assess Criteria: {scheduled_criteria} with lesson: {self.name}")
			
			elif section == "Discussion":
				# Update discussion and assessment_criteria_discussion
				frappe.db.set_value("Course Lesson", self.name, "discussion_id", name)
				scheduled_criteria = frappe.db.get_value(
					"Scheduled Course Assess Criteria",
					{"discussion": name, "parent": self.course_sc},
					"name",
				)
				frappe.db.set_value("Course Lesson", self.name, "assessment_criteria_discussion", scheduled_criteria)
				print(f"Updated Discussion: {name}, Criteria: {scheduled_criteria}")
				frappe.db.set_value("Scheduled Course Assess Criteria", scheduled_criteria, "lesson", self.name)
				print(f"Updated Scheduled Course Assess Criteria: {scheduled_criteria} with lesson: {self.name}")

		


	# def update_orphan_documents(self, doctype, documents):
	# 	"""Updates the documents that were previously part of this lesson,
	# 	but not any more.
	# 	"""
	# 	linked_documents = {
	# 		row["name"] for row in frappe.get_all(doctype, {"lesson": self.name})
	# 	}
	# 	active_documents = set(documents)
	# 	orphan_documents = linked_documents - active_documents
	# 	for name in orphan_documents:
	# 		ex = frappe.get_doc(doctype, name)
	# 		ex.lesson = None
	# 		ex.course = None
	# 		ex.index_ = 0
	# 		ex.save(ignore_permissions=True)

	def check_and_create_folder(self):
		args = {
			"doctype": "File",
			"is_folder": True,
			"file_name": f"{self.name} {self.course}",
		}
		if not frappe.db.exists(args):
			folder = frappe.get_doc(args)
			folder.save(ignore_permissions=True)

	# def get_exercises(self):
	# 	if not self.body:
	# 		return []

	# 	macros = find_macros(self.body)
	# 	exercises = [value for name, value in macros if name == "Exercise"]
	# 	return [frappe.get_doc("LMS Exercise", name) for name in exercises]


@frappe.whitelist()
def save_progress(lesson, course):
	membership = frappe.db.exists(
		"Scheduled Course Roster", {"course_sc": course, "stuemail_rc": frappe.session.user}
	)
	if not membership:
		return 0

	frappe.db.set_value("Scheduled Course Roster", membership, "current_lesson", lesson)
	already_completed = frappe.db.exists(
		"Course Schedule Progress", {"lesson": lesson, "member": frappe.session.user}
	)

	quiz_completed = get_quiz_progress(lesson)
	assignment_completed = get_assignment_progress(lesson)
	discussion_completed = get_discussion_progress(lesson)
	#when uncomment, add (and quiz_completed and assignment_completed and discussion_completed) to the if condition below

	if not already_completed and quiz_completed and assignment_completed and discussion_completed:
		frappe.get_doc(
			{
				"doctype": "Course Schedule Progress",
				"lesson": lesson,
				"status": "Complete",
				"member": frappe.session.user,
			}
		).save(ignore_permissions=True)

	progress = get_course_progress(course)
	# capture_progress_for_analytics(progress, course)

	# Had to get doc, as on_change doesn't trigger when you use set_value. The trigger is necesary for badge to get assigned.
	enrollment = frappe.get_doc("Scheduled Course Roster", membership)
	enrollment.progress = progress
	enrollment.save()
	enrollment.run_method("on_change")

	return progress


# def capture_progress_for_analytics(progress, course):
# 	if progress in [25, 50, 75, 100]:
# 		capture("course_progress", "lms", properties={"course": course, "progress": progress})


def get_quiz_progress(lesson):
	lesson_details = frappe.db.get_value(
		"Course Lesson", lesson, ["body", "content"], as_dict=1
	)
	quizzes = []

	if lesson_details.content:
		content = json.loads(lesson_details.content)

		for block in content.get("blocks"):
			if block.get("type") == "quiz":
				quizzes.append(block.get("data").get("quiz"))

	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		quizzes = [value for name, value in macros if name == "Quiz"]

	for quiz in quizzes:
		passing_percentage = frappe.db.get_value("Quiz", quiz, "passing_percentage")
		if not frappe.db.exists(
			"Quiz Submission",
			{
				"quiz": quiz,
				"member": frappe.session.user,
				"percentage": [">=", passing_percentage],
			},
		):
			return False
	return True


def get_assignment_progress(lesson):
	lesson_details = frappe.db.get_value(
		"Course Lesson", lesson, ["body", "content"], as_dict=1
	)
	assignments = []

	if lesson_details.content:
		content = json.loads(lesson_details.content)

		for block in content.get("blocks"):
			if block.get("type") == "assignment":
				assignments.append(block.get("data").get("assignment"))

	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		assignments = [value for name, value in macros if name == "Assignment"]

	for assignment in assignments:
		if not frappe.db.exists(
			"Assignment Submission",
			{"assignment": assignment, "member": frappe.session.user},
		):
			return False
		else:
			print("getting assignment")
			assignment_doc = frappe.get_doc(
				"Assignment Submission",
				{"assignment": assignment, "member": frappe.session.user},
			)
			assignment_doc.lesson = lesson
			assignment_doc.course_schedule = frappe.db.get_value("Course Lesson", lesson, "course_sc")
			assignment_doc.save(ignore_permissions=True)
	return True

def get_discussion_progress(lesson):
	lesson_details = frappe.db.get_value(
		"Course Lesson", lesson, ["body", "content"], as_dict=1
	)
	discussions = []

	if lesson_details.content:
		content = json.loads(lesson_details.content)

		for block in content.get("blocks", []):
			block_type = block.get("type")
			block_data = block.get("data", {})

			if block_type == "discussion":
				discussion_id = block_data.get("discussion")
			elif block_type == "discussionActivity":
				discussion_id = block_data.get("discussionID")
			else:
				discussion_id = None

			if discussion_id:
				discussions.append(discussion_id)

	elif lesson_details.body:
		macros = find_macros(lesson_details.body)
		discussions = [value for name, value in macros if name == "Discussion"]

	for discussion in discussions:
		if not frappe.db.exists(
			"Discussion Submission",
			{"disc_activity": discussion, "member": frappe.session.user},
		):
			return False
	return True

@frappe.whitelist()
def get_lesson_info(chapter):
	return frappe.db.get_value("Course Schedule Chapter", chapter, "course")