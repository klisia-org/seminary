# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/120: group work, topics, peer review and teammate ratings."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, now_datetime, today

from seminary.seminary import group_work, peer_reviews
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import _row, _scale, _section

ASSIGNMENT = group_work.ASSIGNMENT
ORAL = group_work.ORAL


def _student(name):
	student = fx.make_student()
	frappe.db.set_value("Student", student.name, "student_name", name)
	student.reload()
	return student


def _enrol(cs, student):
	frappe.get_doc(
		{
			"doctype": "Scheduled Course Roster",
			"name": f"{cs}-{student.name}",
			"course_sc": cs,
			"student": student.name,
			"stuname_roster": student.student_name,
			"stuemail_rc": student.user,
			"active": 1,
			"audit_bool": 0,
		}
	).db_insert()


def _assignment(**values):
	doc = frappe.get_doc(
		{
			"doctype": ASSIGNMENT,
			"title": fx.uid("Paper"),
			"type": "Text",
			"question": "Write it.",
			"grade_assignment": 1,
			**values,
		}
	)
	doc.flags.ignore_links = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name


class GroupWorkCase(IntegrationTestCase):
	n_students = 4

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.cs = _section(_scale(), published=1)
		self.students = [_student(f"Student {chr(65 + i)} {fx.uid('')}") for i in range(self.n_students)]
		for s in self.students:
			_enrol(self.cs, s)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def activity(self, due=None, **values):
		act = _assignment(**values)
		self.scac = _row(self.cs, due or add_days(today(), 7), kind="Assignment", assignment=act)
		return act

	def submit(self, student, act, answer="My answer"):
		frappe.set_user(student.user)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Assignment Submission",
					"assignment": act,
					"member": student.user,
					"course": self.cs,
					"answer": answer,
				}
			)
			doc.insert(ignore_permissions=True)
			return doc.name
		finally:
			frappe.set_user("Administrator")

	def sub_of(self, student, act):
		return frappe.db.get_value(
			"Assignment Submission", {"assignment": act, "student": student.name, "course": self.cs}, "name"
		)

	def grade(self, name, grade):
		doc = frappe.get_doc("Assignment Submission", name)
		doc.grade = grade
		doc.status = "Graded"
		doc.comments = "Good work"
		doc.save(ignore_permissions=True)
		return doc


class TestGroupSubmission(GroupWorkCase):
	def setUp(self):
		super().setUp()
		self.act = self.activity(group_work=1, group_source="By hand")
		a, b, _c, _d = self.students
		self.group = group_work.make_group(self.cs, ASSIGNMENT, self.act, "Team 1", [a.name, b.name]).name

	def test_one_submission_saved_on_every_member(self):
		a, b, c, _d = self.students
		self.submit(a, self.act, "Our paper")
		twin = self.sub_of(b, self.act)
		self.assertTrue(twin, "the teammate gets a record of the group's work")
		self.assertEqual(
			frappe.db.get_value("Assignment Submission", twin, "answer"),
			frappe.db.get_value("Assignment Submission", self.sub_of(a, self.act), "answer"),
		)
		self.assertEqual(frappe.db.get_value("Assignment Submission", twin, "activity_group"), self.group)
		self.assertEqual(
			frappe.db.get_value("Assignment Submission", twin, "owner"),
			b.user,
			"the member owns their record",
		)
		for name in (twin, self.sub_of(a, self.act)):
			self.assertEqual(frappe.db.get_value("Assignment Submission", name, "group_name"), "Team 1")
		self.assertFalse(self.sub_of(c, self.act), "students outside the group get nothing")

	def test_grade_copied_unless_graded_separately(self):
		a, b, _c, _d = self.students
		self.submit(a, self.act)
		self.grade(self.sub_of(a, self.act), 80)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(b, self.act), "grade"), 80)
		peer_reviews.set_separate_grade(self.sub_of(b, self.act), 1)
		self.grade(self.sub_of(b, self.act), 40)
		self.grade(self.sub_of(a, self.act), 90)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(b, self.act), "grade"), 40)
		peer_reviews.set_separate_grade(self.sub_of(b, self.act), 0)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(b, self.act), "grade"), 90)

	def test_joiner_gets_work_leaver_keeps_theirs(self):
		a, b, c, _d = self.students
		self.submit(a, self.act, "v1")
		self.grade(self.sub_of(a, self.act), 70)
		group_work.remove_member(self.group, b.name)
		group_work.add_member(self.group, c.name)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(c, self.act), "grade"), 70)
		self.grade(self.sub_of(a, self.act), 95)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(b, self.act), "grade"), 70)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(c, self.act), "grade"), 95)

	def test_one_member_in_one_group(self):
		a, _b, _c, _d = self.students
		other = group_work.make_group(self.cs, ASSIGNMENT, self.act, "Team 2", [a.name])
		self.assertEqual(group_work.group_of(self.cs, ASSIGNMENT, self.act, a.name), other.name)
		self.assertNotIn(a.name, group_work.active_members(self.group))

	def test_group_dates_need_every_member_extended(self):
		a, _b, _c, _d = self.students
		row = frappe._dict(
			frappe.db.get_value("Scheduled Course Assess Criteria", self.scac, ["*"], as_dict=True)
		)
		later = add_days(today(), 20)
		frappe.get_doc(
			{
				"doctype": "Student Due Date Override",
				"course_schedule": self.cs,
				"course_assess": self.scac,
				"student": a.name,
				"due_date": later,
				"reason": "Own accommodation",
			}
		).insert(ignore_permissions=True)
		dates = group_work.group_dates(row, self.group)
		self.assertEqual(
			str(dates.due_date)[:10], str(row.due_date)[:10], "one member's override does not move the group"
		)
		group_work.extend_group(self.group, add_days(today(), 10))
		dates = group_work.group_dates(row, self.group)
		self.assertEqual(str(dates.due_date)[:10], add_days(today(), 10))


class TestTopics(GroupWorkCase):
	def test_students_choose_within_capacity(self):
		act = self.activity(topic_mode="Students choose")
		peer_reviews.save_topics(
			self.cs, ASSIGNMENT, act, json.dumps([{"title": "Genesis 1"}, {"title": "Exodus 3"}])
		)
		t1, _t2 = [t.name for t in group_work.topics(self.cs, ASSIGNMENT, act)]
		a, b, _c, _d = self.students
		frappe.set_user(a.user)
		peer_reviews.choose_topic(self.cs, ASSIGNMENT, act, t1)
		frappe.set_user(b.user)
		with self.assertRaises(frappe.ValidationError):
			peer_reviews.choose_topic(self.cs, ASSIGNMENT, act, t1)
		frappe.set_user("Administrator")
		self.submit(a, act)
		self.assertEqual(frappe.db.get_value("Assignment Submission", self.sub_of(a, act), "topic"), t1)

	def test_closed_choice_refused(self):
		act = self.activity(topic_mode="Students choose")
		peer_reviews.save_topics(self.cs, ASSIGNMENT, act, json.dumps([{"title": "Romans 8"}]))
		frappe.db.set_value(
			"Scheduled Course Assess Criteria", self.scac, "topics_close_on", add_days(now_datetime(), -1)
		)
		topic = group_work.topics(self.cs, ASSIGNMENT, act)[0].name
		frappe.set_user(self.students[0].user)
		with self.assertRaises(frappe.ValidationError):
			peer_reviews.choose_topic(self.cs, ASSIGNMENT, act, topic)

	def test_random_fills_every_holder(self):
		act = self.activity(group_work=1, group_source="Random", group_size=2, topic_mode="Random")
		group_work.ensure_groups(self.cs, ASSIGNMENT, act)
		peer_reviews.save_topics(
			self.cs, ASSIGNMENT, act, json.dumps([{"title": "A"}, {"title": "B"}, {"title": "C"}])
		)
		self.assertEqual(group_work.random_topics(self.cs, ASSIGNMENT, act), 2)
		groups = group_work.group_rows(self.cs, ASSIGNMENT, act)
		self.assertEqual(len(groups), 2)
		self.assertTrue(all(g.topic for g in groups))
		self.assertEqual(len({g.topic for g in groups}), 2)

	def test_import_copies_topics_unheld(self):
		act = self.activity(topic_mode="By hand")
		peer_reviews.save_topics(self.cs, ASSIGNMENT, act, json.dumps([{"title": "Psalm 23", "capacity": 2}]))
		target = _section(_scale(), published=1)
		_row(target, add_days(today(), 7), kind="Assignment", assignment=act)
		group_work.copy_topics(self.cs, target)
		copied = group_work.topics(target, ASSIGNMENT, act)
		self.assertEqual([(t.title, t.capacity, t.taken) for t in copied], [("Psalm 23", 2, 0)])


class TestSelfSignUp(GroupWorkCase):
	def test_join_respects_size_and_window(self):
		act = self.activity(group_work=1, group_source="Self sign-up", group_size=2)
		peer_reviews.make_groups(self.cs, ASSIGNMENT, act, "Empty", count=2)
		g1 = group_work.group_rows(self.cs, ASSIGNMENT, act)[0].name
		a, b, c, _d = self.students
		for s in (a, b):
			frappe.set_user(s.user)
			peer_reviews.join_group(self.cs, ASSIGNMENT, act, g1)
		frappe.set_user(c.user)
		with self.assertRaises(frappe.ValidationError):
			peer_reviews.join_group(self.cs, ASSIGNMENT, act, g1)
		frappe.set_user("Administrator")
		frappe.db.set_value(
			"Scheduled Course Assess Criteria", self.scac, "signup_closes_on", add_days(now_datetime(), -1)
		)
		g2 = group_work.group_rows(self.cs, ASSIGNMENT, act)[1].name
		frappe.set_user(c.user)
		with self.assertRaises(frappe.ValidationError):
			peer_reviews.join_group(self.cs, ASSIGNMENT, act, g2)


class TestStartGroup(GroupWorkCase):
	def test_student_starts_a_group_with_no_groups_made(self):
		act = self.activity(
			group_work=1, group_source="Self sign-up", group_size=1, topic_mode="Students choose"
		)
		peer_reviews.save_topics(self.cs, ASSIGNMENT, act, json.dumps([{"title": "Ruth"}]))
		a, b, _c, _d = self.students
		frappe.set_user(a.user)
		panel = peer_reviews.get_panel(self.cs, ASSIGNMENT, act)
		self.assertTrue(panel["may_sign_up"])
		self.assertIsNone(panel["group"])
		peer_reviews.start_group(self.cs, ASSIGNMENT, act)
		panel = peer_reviews.get_panel(self.cs, ASSIGNMENT, act)
		self.assertTrue(panel["group"])
		self.assertEqual([t["title"] for t in panel["topics"]], ["Ruth"], "a group may now choose its topic")
		frappe.set_user(b.user)
		with self.assertRaises(frappe.ValidationError):
			peer_reviews.join_group(self.cs, ASSIGNMENT, act, panel["group"]["name"])
		peer_reviews.start_group(self.cs, ASSIGNMENT, act)
		self.assertEqual(len(group_work.group_rows(self.cs, ASSIGNMENT, act)), 2)


class TestPeerReview(GroupWorkCase):
	n_students = 5

	def open(self, act):
		s = group_work.settings(ASSIGNMENT, act)
		return peer_reviews.open_round(peer_reviews._row(self.scac), s)

	def test_allocation_is_even_and_never_own(self):
		act = self.activity(peer_review=1, reviews_per_student=2)
		for s in self.students:
			self.submit(s, act)
		self.open(act)
		reviews = frappe.get_all(
			"Peer Review", filters={"course_assess": self.scac}, fields=["reviewer", "author"]
		)
		self.assertEqual(len(reviews), 10)
		self.assertFalse([r for r in reviews if r.reviewer == r.author])
		per_reviewer, per_author = {}, {}
		for r in reviews:
			per_reviewer[r.reviewer] = per_reviewer.get(r.reviewer, 0) + 1
			per_author[r.author] = per_author.get(r.author, 0) + 1
		self.assertEqual(set(per_reviewer.values()), {2})
		self.assertEqual(set(per_author.values()), {2})

	def test_group_work_reviewed_by_other_groups(self):
		act = self.activity(group_work=1, group_source="By hand", peer_review=1, reviews_per_student=1)
		a, b, c, d, e = self.students
		g1 = group_work.make_group(self.cs, ASSIGNMENT, act, "G1", [a.name, b.name]).name
		g2 = group_work.make_group(self.cs, ASSIGNMENT, act, "G2", [c.name, d.name, e.name]).name
		self.submit(a, act)
		self.submit(c, act)
		self.open(act)
		for r in frappe.get_all(
			"Peer Review", filters={"course_assess": self.scac}, fields=["reviewer", "activity_group"]
		):
			mine = g1 if r.reviewer in (a.name, b.name) else g2
			self.assertNotEqual(r.activity_group, mine)
		self.assertEqual(frappe.db.count("Peer Review", {"course_assess": self.scac}), 5)

	def test_credit_is_part_of_the_grade(self):
		act = self.activity(peer_review=1, reviews_per_student=2, review_share=20)
		for s in self.students:
			self.submit(s, act)
		self.open(act)
		a = self.students[0]
		mine = frappe.get_all(
			"Peer Review", filters={"reviewer": a.name, "course_assess": self.scac}, pluck="name"
		)
		frappe.set_user(a.user)
		peer_reviews.save_review(mine[0], comments="Clear argument; cite the text.", submit=1)
		frappe.set_user("Administrator")
		doc = self.grade(self.sub_of(a, act), 80)
		self.assertEqual(doc.review_credit, 50)
		self.assertAlmostEqual(doc.percentage, 80 * 0.8 + 0.2 * 50, places=2)
		peer_reviews.set_review_credit("Assignment Submission", doc.name, 100)
		self.assertAlmostEqual(
			frappe.db.get_value("Assignment Submission", doc.name, "percentage"), 84, places=2
		)

	def test_anonymous_reviews_hide_names(self):
		act = self.activity(peer_review=1, reviews_per_student=1, review_anonymous=1)
		for s in self.students:
			self.submit(s, act)
		self.open(act)
		a = self.students[0]
		review = frappe.get_all("Peer Review", filters={"reviewer": a.name}, fields=["name", "author"])[0]
		frappe.set_user(a.user)
		out = peer_reviews.get_review(review.name)
		author_name = frappe.db.get_value("Student", review.author, "student_name")
		self.assertNotIn(author_name, json.dumps(out, default=str))
		peer_reviews.save_review(review.name, comments="Helpful", submit=1)
		frappe.set_user("Administrator")
		peer_reviews.release_now(self.cs, ASSIGNMENT, act)
		author = next(s for s in self.students if s.name == review.author)
		frappe.set_user(author.user)
		received = peer_reviews.get_panel(self.cs, ASSIGNMENT, act)["received"]
		self.assertEqual(len(received), 1)
		self.assertIsNone(received[0]["reviewer"])

	def test_only_the_reviewer_reads_the_review(self):
		act = self.activity(peer_review=1, reviews_per_student=1)
		for s in self.students:
			self.submit(s, act)
		self.open(act)
		review = frappe.get_all(
			"Peer Review", filters={"course_assess": self.scac}, fields=["name", "reviewer"]
		)[0]
		stranger = next(s for s in self.students if s.name != review.reviewer)
		frappe.set_user(stranger.user)
		with self.assertRaises(frappe.PermissionError):
			peer_reviews.get_review(review.name)
		with self.assertRaises(frappe.PermissionError):
			peer_reviews.download(review.name, "work")

	def test_hourly_opens_and_releases(self):
		act = self.activity(
			due=add_to_date(now_datetime(), hours=-1), peer_review=1, reviews_per_student=1, review_due_days=1
		)
		for s in self.students:
			frappe.db.set_value(
				"Scheduled Course Assess Criteria", self.scac, "due_date", add_days(now_datetime(), 1)
			)
			self.submit(s, act)
		frappe.db.set_value(
			"Scheduled Course Assess Criteria", self.scac, "due_date", add_to_date(now_datetime(), hours=-1)
		)
		peer_reviews.hourly()
		row = peer_reviews._row(self.scac)
		self.assertTrue(row.review_opened_on)
		self.assertEqual(frappe.db.count("Peer Review", {"course_assess": self.scac}), 5)
		peer_reviews.hourly(at=add_days(now_datetime(), 2))
		self.assertTrue(peer_reviews._row(self.scac).reviews_released_on)


class TestTeammateRatings(GroupWorkCase):
	def test_ratings_count_and_show_as_set(self):
		act = self.activity(
			group_work=1,
			group_source="By hand",
			teammate_ratings=1,
			ratings_shown="Anonymous",
			review_share=10,
		)
		a, b, c, _d = self.students
		group = group_work.make_group(self.cs, ASSIGNMENT, act, "Team", [a.name, b.name, c.name]).name
		self.submit(a, act)
		s = group_work.settings(ASSIGNMENT, act)
		peer_reviews.open_round(peer_reviews._row(self.scac), s)
		crit = peer_reviews.criteria()
		frappe.set_user(a.user)
		peer_reviews.save_ratings(
			self.cs,
			ASSIGNMENT,
			act,
			json.dumps(
				[
					{"student": b.name, "scores": {k: 5 for k in crit}, "comment": "Carried the research"},
					{"student": c.name, "scores": {k: 2 for k in crit}},
				]
			),
		)
		frappe.set_user("Administrator")
		self.assertEqual(peer_reviews.credit(peer_reviews._row(self.scac), s, a.name), 100)
		self.assertEqual(peer_reviews.credit(peer_reviews._row(self.scac), s, b.name), 0)
		summary = peer_reviews.ratings_summary(group)
		self.assertEqual(summary[b.name]["average"], 5)
		self.assertEqual(summary[c.name]["average"], 2)
		peer_reviews.release_now(self.cs, ASSIGNMENT, act)
		frappe.set_user(b.user)
		mine = peer_reviews.get_panel(self.cs, ASSIGNMENT, act)["ratings_received"]
		self.assertEqual(mine["average"], 5)
		self.assertIsNone(mine["comments"][0]["rater"], "anonymous ratings hide the rater")

	def test_instructor_only_ratings_stay_hidden(self):
		act = self.activity(
			group_work=1, group_source="By hand", teammate_ratings=1, ratings_shown="Instructor only"
		)
		a, b, _c, _d = self.students
		group_work.make_group(self.cs, ASSIGNMENT, act, "Team", [a.name, b.name])
		self.submit(a, act)
		peer_reviews.open_round(peer_reviews._row(self.scac), group_work.settings(ASSIGNMENT, act))
		frappe.set_user(a.user)
		peer_reviews.save_ratings(
			self.cs,
			ASSIGNMENT,
			act,
			json.dumps([{"student": b.name, "scores": {k: 4 for k in peer_reviews.criteria()}}]),
		)
		frappe.set_user("Administrator")
		peer_reviews.release_now(self.cs, ASSIGNMENT, act)
		frappe.set_user(b.user)
		self.assertIsNone(peer_reviews.get_panel(self.cs, ASSIGNMENT, act)["ratings_received"])


class TestOralConversationGroups(GroupWorkCase):
	def test_conversations_use_activity_groups(self):
		from seminary.seminary import oral_activities

		oral = frappe.get_doc(
			{
				"doctype": ORAL,
				"title": fx.uid("Debate"),
				"course": fx.uid("C"),
				"mode": "Conversation",
				"group_size": 2,
			}
		)
		oral.flags.ignore_links = True
		oral.insert(ignore_permissions=True)
		_row(self.cs, add_days(today(), 7), kind="Oral", oral=oral.name)
		groups = oral_activities.conversation_groups(self.cs, oral)
		self.assertEqual(len(groups), 2)
		self.assertTrue(all(frappe.db.exists("Activity Group", g) for g in groups))
		self.assertFalse(
			frappe.db.exists("Student Group", {"group_name": ["like", f"{oral.title}%"]}),
			"no section student groups are made any more",
		)
