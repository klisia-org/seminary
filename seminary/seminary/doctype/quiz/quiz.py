# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import json
import frappe
import re
from frappe import _, safe_decode
from frappe.model.document import Document
from frappe.utils import cstr, comma_and, cint
from fuzzywuzzy import fuzz
from seminary.seminary.doctype.course_lesson.course_lesson import save_progress
from seminary.seminary.utils import (
	generate_slug,
	# has_course_moderator_role,
	# has_course_instructor_role,
)
from binascii import Error as BinasciiError
from frappe.utils.file_manager import safe_b64decode
from frappe.core.doctype.file.utils import get_random_filename


class seminaryQuiz(Document):
	def validate(self):
		self.validate_duplicate_questions()
		self.validate_limit()
		self.calculate_total_points()
		

	def validate_duplicate_questions(self):
		questions = [row.question for row in self.questions]
		rows = [i + 1 for i, x in enumerate(questions) if questions.count(x) > 1]
		if len(rows):
			frappe.throw(
				_("Rows {0} have duplicate questions.").format(frappe.bold(comma_and(rows)))
			)

	def validate_limit(self):
		if self.limit_questions_to and cint(self.limit_questions_to) >= len(self.questions):
			frappe.throw(
				_("Limit cannot be greater than or equal to the number of questions in the quiz. Use limit to offer a subset of questions.")
			)

		if self.limit_questions_to and cint(self.limit_questions_to) < len(self.questions):
			points = [question.points for question in self.questions]
			if len(set(points)) > 1:
				frappe.throw(_("All questions should have the same points if a limit is set, as students will receive a subset of questions."))

	def calculate_total_points(self):
		if self.limit_questions_to:
			self.total_points = sum(
				question.points for question in self.questions[: cint(self.limit_questions_to)]
			)
		else:
			self.total_points = sum(cint(question.points) for question in self.questions)

	

	def autoname(self):
		if not self.name:
			self.name = generate_slug(self.title, "Quiz")

	def get_last_submission_details(self):
		"""Returns the latest submission for this user."""
		user = frappe.session.user
		if not user or user == "Guest":
			return

		result = frappe.get_all(
			"Quiz Submission",
			fields="*",
			filters={"owner": user, "quiz": self.name},
			order_by="creation desc",
			page_length=1,
		)

		if result:
			return result[0]


def set_total_points(questions):
	points = 0
	for question in questions:
		points += question.get("points")
	return points


@frappe.whitelist()
def quiz_summary(quiz, results):
	score = 0
	results = results and json.loads(results)
	percentage = 0

	quiz_details = frappe.db.get_value(
		"Quiz",
		quiz,
		["total_points", "passing_percentage", "lesson", "course"],
		as_dict=1,
	)

	score_out_of = quiz_details.total_points

	for result in results:
		question_details = frappe.db.get_value(
			"Quiz Question",
			{"parent": quiz, "question": result["question_name"]},
			["question", "points", "question_detail", "type"],
			as_dict=1,
		)

		result["question_name"] = question_details.question
		result["question"] = question_details.question_detail
		result["points_out_of"] = question_details.points

		if question_details.type != "Open Ended":
			correct = result["is_correct"][0]
			for point in result["is_correct"]:
				correct = correct and point
			result["is_correct"] = correct

			points = question_details.points if correct else 0
			result["points"] = points
			score += points

		else:
			result["is_correct"] = 0
			

		percentage = (score / score_out_of) * 100
		result["answer"] = re.sub(
			r'<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']', _save_file, result["answer"]
		)

	submission = frappe.new_doc("Quiz Submission")
	# Score and percentage are calculated by the controller function
	submission.update(
		{
			"doctype": "Quiz Submission",
			"quiz": quiz,
			"result": results,
			"score": 0,
			"score_out_of": score_out_of,
			"member": frappe.session.user,
			"percentage": 0,
			"passing_percentage": quiz_details.passing_percentage,
		}
	)
	submission.save(ignore_permissions=True)

	if (
		percentage >= quiz_details.passing_percentage
		and quiz_details.lesson
		and quiz_details.course
	):
		save_progress(quiz_details.lesson, quiz_details.course)
	elif not quiz_details.passing_percentage:
		save_progress(quiz_details.lesson, quiz_details.course)

	return {
		"score": score,
		"score_out_of": score_out_of,
		"submission": submission.name,
		"pass": percentage == quiz_details.passing_percentage,
		"percentage": percentage,
		
	}


def _save_file(match):
	data = match.group(1).split("data:")[1]
	headers, content = data.split(",")
	mtype = headers.split(";", 1)[0]

	if isinstance(content, str):
		content = content.encode("utf-8")
	if b"," in content:
		content = content.split(b",")[1]

	try:
		content = safe_b64decode(content)
	except BinasciiError:
		frappe.flags.has_dataurl = True
		return f'<img src="#broken-image" alt="{get_corrupted_image_msg()}"'

	if "filename=" in headers:
		filename = headers.split("filename=")[-1]
		filename = safe_decode(filename).split(";", 1)[0]

	else:
		filename = get_random_filename(content_type=mtype)

	_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"decode": False,
			"is_private": False,
		}
	)
	_file.save(ignore_permissions=True)
	file_url = _file.unique_url
	frappe.flags.has_dataurl = True

	return f'<img src="{file_url}"'


def get_corrupted_image_msg():
	return _("Image: Corrupted Data Stream")


@frappe.whitelist()
def get_question_details(question):
	if frappe.db.exists("Quiz Question", question):
		fields = ["name", "question", "type"]
		for num in range(1, 5):
			fields.append(f"option_{cstr(num)}")
			fields.append(f"is_correct_{cstr(num)}")
			fields.append(f"explanation_{cstr(num)}")
			fields.append(f"possibility_{cstr(num)}")

		return frappe.db.get_value("Quiz Question", question, fields, as_dict=1)
	return


@frappe.whitelist()
def check_answer(question, type, answers):
	answers = json.loads(answers)
	if type == "Choices":
		return check_choice_answers(question, answers)
	else:
		return check_input_answers(question, answers[0])


def check_choice_answers(question, answers):
	fields = ["multiple"]
	is_correct = []
	for num in range(1, 5):
		fields.append(f"option_{cstr(num)}")
		fields.append(f"is_correct_{cstr(num)}")

	question_details = frappe.db.get_value("Question", question, fields, as_dict=1)

	for num in range(1, 5):
		if question_details[f"option_{num}"] in answers:
			is_correct.append(question_details[f"is_correct_{num}"])
		elif question_details[f"is_correct_{num}"]:
			is_correct.append(2)
		else:
			is_correct.append(0)

	return is_correct


def check_input_answers(question, answer):
	fields = []
	for num in range(1, 5):
		fields.append(f"possibility_{cstr(num)}")

	question_details = frappe.db.get_value("Question", question, fields, as_dict=1)
	for num in range(1, 5):
		current_possibility = question_details[f"possibility_{num}"]
		if current_possibility and fuzz.token_sort_ratio(current_possibility, answer) > 85:
			return 1

	return 0