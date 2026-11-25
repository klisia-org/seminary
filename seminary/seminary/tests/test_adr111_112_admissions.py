# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/111 (application questions) and 112 (review and decisions)."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import admissions
from seminary.seminary import application_form as af
from seminary.seminary import requirements as req
from seminary.seminary.doctype.student_applicant.test_student_applicant import make_applicant
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.identity_cleanup import module_hooks

# A 1x1 transparent PNG.
PNG = (
	"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
	"nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg=="
)

setUpModule, tearDownModule = module_hooks()


def _question(question=None, answer_type="Short text", **kw):
	return frappe.get_doc(
		{
			"doctype": "Application Question",
			"question": question or fx.uid("Question"),
			"answer_type": answer_type,
			**kw,
		}
	).insert(ignore_permissions=True)


def _program(questions=(), director=None, mode="Reviewed", rules=()):
	program = fx.make_program()
	for q, required in questions:
		program.append("application_questions", {"question": q.name, "required": required})
	for r in rules:
		program.append("enrollment_requirements", r)
	program.program_director = director
	program.admission_mode = mode
	program.save(ignore_permissions=True)
	return program


def _answers(**by_question):
	return [{"question": q, "answer": a} for q, a in by_question.items()]


def _director():
	return fx.make_user(roles=("Instructor",))


class AdmissionsCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.savepoint("adr111_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="adr111_test")
		super().tearDown()


# --------------------------------------------------------------------------- #
# 111
# --------------------------------------------------------------------------- #
class TestQuestionPool(AdmissionsCase):
	def test_seeding_is_idempotent_and_fills_only_empty_programs(self):
		first = af.seed_questions()
		self.assertEqual(af.seed_questions(), first)
		self.assertEqual(len(first), len(af.SEED))
		empty = fx.make_program()
		own = _program([(_question(), 0)])
		af.link_to_programs(first, programs=[empty.name, own.name])
		self.assertEqual(len(frappe.get_doc("Program", empty.name).application_questions), len(first))
		self.assertEqual(len(frappe.get_doc("Program", own.name).application_questions), 1)

	def test_the_form_gets_the_programs_questions_and_tables(self):
		church = _question(group_label="Church")
		refs = _question(answer_type="Table section", table_section="References")
		program = _program([(church, 1), (refs, 1)])
		data = af.application_questions(program.name)
		self.assertEqual([q["question"] for q in data["questions"]], [church.name])
		self.assertEqual(data["questions"][0]["group"], "Church")
		self.assertEqual(data["tables"]["references"]["required"], 1)
		self.assertNotIn("education", data["tables"])

	def test_an_inactive_question_is_not_asked(self):
		q = _question(is_active=0)
		program = _program([(q, 1)])
		self.assertEqual(af.application_questions(program.name)["questions"], [])


class TestAnswers(AdmissionsCase):
	def test_a_required_answer_is_enforced(self):
		q = _question()
		program = _program([(q, 1)])
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name)
		applicant = make_applicant(program=program.name, answers=_answers(**{q.name: "Grace Church"}))
		self.assertEqual(applicant.answers[0].answer, "Grace Church")

	def test_the_label_is_kept_as_the_applicant_saw_it(self):
		q = _question("Name of your church", group_label="Church")
		program = _program([(q, 0)])
		applicant = make_applicant(program=program.name, answers=_answers(**{q.name: "Grace"}))
		q.question = "Home church"
		q.save(ignore_permissions=True)
		row = frappe.get_doc("Student Applicant", applicant.name).answers[0]
		self.assertEqual((row.question_label, row.group_label), ("Name of your church", "Church"))

	def test_answers_to_other_questions_are_dropped_and_choices_are_checked(self):
		pick = _question(answer_type="Select", options="Yes\nNo")
		stray = _question()
		program = _program([(pick, 0)])
		applicant = make_applicant(
			program=program.name, answers=_answers(**{pick.name: "Yes", stray.name: "x"})
		)
		self.assertEqual([r.question for r in applicant.answers], [pick.name])
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name, answers=_answers(**{pick.name: "Maybe"}))

	def test_a_required_table_needs_a_row(self):
		refs = _question(answer_type="Table section", table_section="References")
		program = _program([(refs, 1)])
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name)
		applicant = make_applicant(program=program.name, references=[{"full_name": "Pastor Lee"}])
		self.assertEqual(len(applicant.references), 1)

	def test_answers_lock_once_in_review(self):
		q = _question()
		program = _program([(q, 0)])
		applicant = make_applicant(program=program.name, answers=_answers(**{q.name: "one"}))
		admissions.set_status(applicant.name, "In Review")
		applicant.reload()
		applicant.answers[0].answer = "two"
		with self.assertRaises(frappe.ValidationError):
			applicant.save(ignore_permissions=True)

	def test_an_answered_question_cannot_be_deleted(self):
		q = _question()
		program = _program([(q, 0)])
		make_applicant(program=program.name, answers=_answers(**{q.name: "yes"}))
		program.set("application_questions", [])
		program.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Application Question", q.name)


class TestPersonFacts(AdmissionsCase):
	def test_education_and_emergency_contacts_reach_the_person(self):
		program = _program(
			[
				(_question(answer_type="Table section", table_section="Education history"), 0),
				(_question(answer_type="Table section", table_section="Emergency contacts"), 0),
			]
		)
		applicant = make_applicant(
			program=program.name,
			education=[{"institution": "Austin College", "degree": "BA History", "level": "Bachelor's"}],
			contacts=[{"contact_name": "Ana Vasquez", "relation": "Spouse", "phone": "5125550100"}],
		)
		row = applicant.education[0]
		self.assertTrue(row.person_education)
		edu = frappe.get_doc("Person Education", row.person_education)
		self.assertEqual(
			(edu.person, edu.institution, edu.student_applicant),
			(applicant.person, "Austin College", applicant.name),
		)
		person = frappe.get_doc("Person", applicant.person)
		self.assertEqual([c.contact_name for c in person.emergency_contacts], ["Ana Vasquez"])
		applicant.save(ignore_permissions=True)
		person.reload()
		self.assertEqual(len(person.emergency_contacts), 1)
		self.assertEqual(frappe.db.count("Person Education", {"person": applicant.person}), 1)

	def test_a_person_reads_only_their_own_education(self):
		owner_user = fx.make_user(roles=("Student",))
		owner = fx.make_person("Own", user=owner_user.name)
		other_user = fx.make_user(roles=("Student",))
		edu = frappe.get_doc(
			{"doctype": "Person Education", "person": owner.name, "institution": "X"}
		).insert(ignore_permissions=True)
		self.assertTrue(frappe.has_permission("Person Education", "read", edu, user=owner_user.name))
		self.assertFalse(frappe.has_permission("Person Education", "write", edu, user=owner_user.name))
		self.assertFalse(frappe.has_permission("Person Education", "read", edu, user=other_user.name))


class TestAgreementsOnTheApplication(AdmissionsCase):
	def _template(self):
		return frappe.get_doc(
			{
				"doctype": "Agreement Template",
				"title": fx.uid("Doctrine"),
				"body": "<p>I affirm the statement for {{ program.program_name }}.</p><p>{{ signature }}</p>",
			}
		).insert(ignore_permissions=True)

	def _rule(self, template):
		return {
			"kind": "Agreement",
			"agreement_template": template.name,
			"ask_on_application": 1,
			"renewal": "Not needed",
			"due_days": 10,
		}

	def test_signing_on_the_form_satisfies_the_enrollment(self):
		t = self._template()
		program = _program(rules=[self._rule(t)])
		preview = req.application_agreements(program.name)
		self.assertEqual(preview[0]["agreement_template"], t.name)
		self.assertIn(program.program_name, preview[0]["html"])
		with self.assertRaises(frappe.ValidationError):
			make_applicant(program=program.name)
		applicant = make_applicant(
			program=program.name,
			agreements=[
				{
					"agreement_template": t.name,
					"agreed": 1,
					"signer_name": "Aurelia Vasquez",
					"signature": PNG,
				}
			],
		)
		sa = applicant.agreements[0].signed_agreement
		self.assertTrue(sa)
		self.assertEqual(
			frappe.db.get_value("Signed Agreement", sa, ["reference_doctype", "person", "docstatus"]),
			("Student Applicant", applicant.person, 1),
		)
		student = fx.make_student(frappe.get_doc("Person", applicant.person))
		pe = fx.make_enrollment(student, program)
		status = frappe.db.get_value(
			"Person Requirement", {"reference_name": pe.name, "agreement_template": t.name}, "status"
		)
		self.assertEqual(status, "Satisfied")


# --------------------------------------------------------------------------- #
# 112
# --------------------------------------------------------------------------- #
class TestReviewStarts(AdmissionsCase):
	def test_a_complete_application_goes_to_the_director(self):
		director = _director()
		program = _program(director=director.name)
		applicant = make_applicant(program=program.name)
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "In Review"
		)
		reviews = frappe.get_all(
			"Application Review", filters={"student_applicant": applicant.name}, pluck="reviewer"
		)
		self.assertEqual(reviews, [director.name])
		self.assertTrue(
			frappe.db.exists("ToDo", {"allocated_to": director.name, "reference_type": "Application Review"})
		)

	def test_a_missing_document_holds_review_until_it_arrives(self):
		dt = frappe.get_doc(
			{"doctype": "Document Type", "type_name": fx.uid("ID"), "allowed_extensions": "txt"}
		).insert(ignore_permissions=True)
		program = _program(
			director=_director().name,
			rules=[{"kind": "Document", "document_type": dt.name, "ask_on_application": 1, "due_days": 5}],
		)
		applicant = make_applicant(program=program.name, documents=[{"document_type": dt.name}])
		self.assertEqual(applicant.application_status, "Applied")
		self.assertEqual(admissions.missing(applicant), [f"Document: {dt.name}"])
		f = frappe.get_doc(
			{"doctype": "File", "file_name": "id.txt", "content": b"id", "is_private": 1}
		).insert(ignore_permissions=True)
		applicant.documents[0].file = f.file_url
		applicant.save(ignore_permissions=True)
		self.assertEqual(applicant.application_status, "In Review")

	def test_an_automatic_program_admits_at_once(self):
		program = _program(mode="Automatic")
		applicant = make_applicant(program=program.name)
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "Approved"
		)
		self.assertEqual(admissions.latest_decision(applicant.name).decision, "Admit")

	def test_the_status_cannot_be_set_by_hand(self):
		applicant = make_applicant(program=_program(director=_director().name).name)
		applicant.application_status = "Approved"
		with self.assertRaises(frappe.ValidationError):
			applicant.save(ignore_permissions=True)


class TestReviewing(AdmissionsCase):
	def _scale(self):
		return frappe.get_doc(
			{
				"doctype": "Rubric Scale",
				"scale_name": fx.uid("RS"),
				"levels": [
					{"label": "Strong", "percent": 100, "meets_expectations": 1},
					{"label": "Weak", "percent": 50},
				],
			}
		).insert(ignore_permissions=True)

	def _rubric(self, program):
		rubric = frappe.get_doc(
			{
				"doctype": "Rubric",
				"activity_doctype": "Program",
				"activity": program.name,
				"scale": self._scale().name,
				"criteria": [{"title": "Calling", "weight": 75}, {"title": "Writing"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Program", program.name, "admission_rubric", rubric.name)
		return rubric

	def test_scores_give_the_overall_percent_and_are_required(self):
		director = _director()
		program = _program(director=director.name)
		rubric = self._rubric(program)
		applicant = make_applicant(program=program.name)
		review = frappe.get_value("Application Review", {"student_applicant": applicant.name})
		frappe.set_user(director.name)
		with self.assertRaises(frappe.ValidationError):
			admissions.submit_review(review, "Admit")
		codes = [c.criterion_code for c in rubric.criteria]
		admissions.save_review_scores(review, [{"criterion_code": codes[0], "level": "Strong"}])
		out = admissions.save_review_scores(review, [{"criterion_code": codes[1], "level": "Weak"}])
		self.assertEqual(out["overall_percent"], 87.5)
		self.assertEqual(admissions.submit_review(review, "Admit"), "Submitted")

	def test_others_reviews_stay_hidden_until_your_own_is_in(self):
		a, b = _director(), _director()
		program = _program()
		applicant = make_applicant(program=program.name)
		for user in (a, b):
			admissions.assign_review(applicant, user.name)
		ra = frappe.get_value("Application Review", {"student_applicant": applicant.name, "reviewer": a.name})
		rb = frappe.get_value("Application Review", {"student_applicant": applicant.name, "reviewer": b.name})
		frappe.set_user(a.name)
		admissions.submit_review(ra, "Decline")
		frappe.set_user(b.name)
		self.assertFalse(
			frappe.has_permission("Application Review", "read", frappe.get_doc("Application Review", ra))
		)
		self.assertTrue(
			frappe.has_permission(
				"Student Applicant", "read", frappe.get_doc("Student Applicant", applicant.name)
			)
		)
		admissions.recuse(rb, "My nephew")
		self.assertTrue(
			frappe.has_permission("Application Review", "read", frappe.get_doc("Application Review", ra))
		)

	def test_an_unrelated_desk_user_cannot_read_the_application(self):
		applicant = make_applicant(program=_program(director=_director().name).name)
		stranger = _director()
		self.assertFalse(frappe.has_permission("Student Applicant", "read", applicant, user=stranger.name))


class TestAdmissionsUnit(AdmissionsCase):
	"""112 §1a: a program's admissions panel is its own Program Admissions unit."""

	def _person(self, user):
		return frappe.db.get_value("Person", {"user": user}) or fx.make_person(user=user).name

	def _unit(self, members=(), chair=None, unit_type="Program Admissions"):
		unit = frappe.get_doc(
			{
				"doctype": "Academic Unit",
				"unit_name": fx.uid("Admissions"),
				"unit_type": unit_type,
				"chair": self._person(chair) if chair else None,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
		for user in members:
			frappe.get_doc(
				{
					"doctype": "Academic Unit Membership",
					"unit": unit.name,
					"person": self._person(user),
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
		return unit

	def test_the_units_members_and_chair_review_and_the_chair_decides(self):
		a, b, chair, director = (_director().name for _ in range(4))
		program = _program(director=director)
		program.admissions_unit = self._unit(members=(a, b), chair=chair).name
		program.save(ignore_permissions=True)
		applicant = make_applicant(program=program.name)
		reviewers = frappe.get_all(
			"Application Review", filters={"student_applicant": applicant.name}, pluck="reviewer"
		)
		self.assertEqual(sorted(reviewers), sorted([a, b, chair]))
		self.assertTrue(admissions.may_decide(program.name, chair))
		self.assertFalse(admissions.may_decide(program.name, a))
		decision = frappe.new_doc("Admission Decision")
		decision.update({"student_applicant": applicant.name, "program": program.name})
		self.assertTrue(admissions.decision_has(decision, "read", chair))

	def test_a_unit_without_members_leaves_review_with_the_director(self):
		director = _director().name
		program = _program(director=director)
		program.admissions_unit = self._unit().name
		program.save(ignore_permissions=True)
		applicant = make_applicant(program=program.name)
		self.assertEqual(
			frappe.get_all(
				"Application Review", filters={"student_applicant": applicant.name}, pluck="reviewer"
			),
			[director],
		)

	def test_only_a_program_admissions_unit_is_accepted_and_only_when_reviewed(self):
		program = _program()
		program.admissions_unit = self._unit(unit_type="Program Committee").name
		with self.assertRaises(frappe.ValidationError):
			program.save(ignore_permissions=True)
		program.reload()
		program.admissions_unit = self._unit().name
		program.admission_mode = "Automatic"
		program.save(ignore_permissions=True)
		self.assertIsNone(program.admissions_unit)


class TestDeciding(AdmissionsCase):
	def _in_review_with(self, *recommendations):
		program = _program(director=_director().name)
		applicant = make_applicant(program=program.name)
		for rec in recommendations:
			user = _director()
			name = admissions.assign_review(applicant, user.name)
			frappe.set_user(user.name)
			admissions.submit_review(name, rec)
			frappe.set_user("Administrator")
		return applicant

	def _decide(self, applicant, decision, **kw):
		doc = frappe.get_doc(
			{"doctype": "Admission Decision", "student_applicant": applicant.name, "decision": decision, **kw}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_going_against_the_majority_needs_a_rationale(self):
		applicant = self._in_review_with("Decline", "Decline", "Admit")
		with self.assertRaises(frappe.ValidationError):
			self._decide(applicant, "Admit")
		doc = self._decide(applicant, "Admit", rationale="Strong pastoral reference")
		self.assertEqual(doc.majority, "Decline")
		self.assertIn("Decline: 2", doc.tally)
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "Approved"
		)
		doc.cancel()
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "In Review"
		)

	def test_conditions_travel_to_the_enrollment(self):
		from seminary.seminary.api import enroll_student

		applicant = self._in_review_with("Admit with conditions")
		with self.assertRaises(frappe.ValidationError):
			enroll_student(applicant.name)
		self._decide(
			applicant, "Admit with conditions", conditions="Two leveling courses", requires_leveling=1
		)
		pe = enroll_student(applicant.name)
		self.assertEqual(pe.admission_conditions, "Two leveling courses")
		self.assertTrue(frappe.db.exists("ToDo", {"reference_name": applicant.name, "status": "Open"}))

	def test_a_claimed_program_is_decided_only_through_record_decision(self):
		reviewer = _director()
		claim = {"reviewers": [reviewer.name], "due_date": "2030-01-01", "label": "Admissions Committee"}
		with patch.object(admissions, "claim", return_value=frappe._dict(claim)):
			program = _program(director=_director().name)
			applicant = make_applicant(program=program.name)
			review = frappe.get_doc("Application Review", {"student_applicant": applicant.name})
			self.assertEqual((review.reviewer, str(review.due_date)), (reviewer.name, "2030-01-01"))
			with self.assertRaises(frappe.ValidationError):
				self._decide(applicant, "Admit")
			name = admissions.record_decision(
				applicant.name, "Waitlist", decided_through=("User", reviewer.name)
			)
		doc = frappe.get_doc("Admission Decision", name)
		self.assertEqual((doc.decided_through_doctype, doc.decided_through), ("User", reviewer.name))
		self.assertEqual(
			frappe.db.get_value("Student Applicant", applicant.name, "application_status"), "Waitlisted"
		)

	def test_the_applicant_page_shows_status_never_reviews(self):
		applicant = self._in_review_with("Admit")
		self._decide(applicant, "Admit with conditions", conditions="Greek first")
		key = frappe.db.get_value("Student Applicant", applicant.name, "access_key")
		self.assertIsNone(admissions.public_status(applicant.name, "wrong"))
		shown = admissions.public_status(applicant.name, key)
		self.assertEqual((shown.status, shown.conditions), ("Approved", "Greek first"))
