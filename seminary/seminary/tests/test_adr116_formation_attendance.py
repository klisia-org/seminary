# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/116: cohort meetings and chapel count toward graduation, by count
or percentage, with Excused and leave left out of the base."""

import json
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, getdate, now_datetime, today

from seminary.seminary import chapel as chapel_service
from seminary.seminary import formation_attendance as fa
from seminary.seminary import oral_groups
from seminary.seminary.discipleship import meetings as mt
from seminary.seminary.program_status import LEAVE_STATUS, return_from_leave, set_program_status
from seminary.seminary.tests import cohort_fixtures as fx

D = getdate("2026-03-02")


def _pct(target, period=fa.WHOLE, minimum=0):
	return frappe._dict(
		attendance_measure=fa.PERCENTAGE,
		required_percentage=target,
		percentage_period=period,
		minimum_held=minimum,
	)


class TestEvaluate(UnitTestCase):
	def test_count(self):
		row = frappe._dict(attendance_measure=fa.COUNT, required_count=2)
		self.assertEqual(fa.evaluate(row, [])["status"], "Not Started")
		self.assertEqual(fa.evaluate(row, [(D, "Present"), (D, "Absent")])["status"], "In Progress")
		out = fa.evaluate(row, [(D, "Present"), (D, "Present")])
		self.assertEqual((out["status"], out["attended_count"]), ("Fulfilled", 2))

	def test_excused_is_not_attended_for_a_count(self):
		row = frappe._dict(attendance_measure=fa.COUNT, required_count=1)
		self.assertEqual(fa.evaluate(row, [(D, "Excused")])["status"], "Not Started")

	def test_percentage_leaves_excused_and_leave_out_of_the_base(self):
		occasions = [(D, "Present"), (D, "Present"), (D, "Absent"), (D, "Excused"), (D, "Absent", True)]
		out = fa.evaluate(_pct(60), occasions)
		self.assertEqual(out["attendance_rate"], 66.7)
		self.assertEqual(out["status"], "Fulfilled")
		self.assertEqual(fa.evaluate(_pct(70), occasions)["status"], "In Progress")

	def test_minimum_held_before_judging(self):
		self.assertEqual(fa.evaluate(_pct(50, minimum=3), [(D, "Present")])["status"], "In Progress")
		self.assertEqual(fa.evaluate(_pct(50, minimum=1), [(D, "Present")])["status"], "Fulfilled")

	def test_each_term_needs_every_judged_term(self):
		terms = [("Spring", "2026-01-01", "2026-05-31"), ("Fall", "2026-08-01", "2026-12-15")]
		spring, fall = getdate("2026-03-02"), getdate("2026-09-07")
		good = [(spring, "Present"), (spring, "Present"), (fall, "Present"), (fall, "Absent")]
		out = fa.evaluate(_pct(50, fa.EACH_TERM), good, terms)
		self.assertEqual(out["status"], "Fulfilled")
		self.assertEqual(out["term_rates"], "Spring: 100%\nFall: 50%")
		self.assertEqual(out["attendance_rate"], 50.0)

		bad = [(spring, "Absent"), (spring, "Present"), (spring, "Absent"), (fall, "Present")]
		self.assertEqual(fa.evaluate(_pct(50, fa.EACH_TERM), bad, terms)["status"], "In Progress")

	def test_each_term_skips_a_term_below_the_minimum(self):
		terms = [("Spring", "2026-01-01", "2026-05-31")]
		out = fa.evaluate(_pct(50, fa.EACH_TERM, minimum=2), [(D, "Absent")], terms)
		self.assertIsNone(out["term_rates"])
		self.assertEqual(out["status"], "In Progress")


def _gri(requirement_type, **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Graduation Requirement Item",
			"requirement_name": fx.uid("Formation"),
			"requirement_type": requirement_type,
			"mandatory": 1,
			**kw,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _add_requirement(pe, gri):
	row = {
		"requirement_name": gri.requirement_name,
		"requirement_type": gri.requirement_type,
		"mandatory": 1,
		"status": "Not Started",
		"grad_requirement_item": gri.name,
		**fa.snapshot_fields(gri),
	}
	pe.append("graduation_requirements", row)
	pe.save(ignore_permissions=True)
	return pe.graduation_requirements[-1].name


def _row(name):
	return frappe.db.get_value(
		"Student Graduation Requirement",
		name,
		["status", "attended_count", "attendance_rate", "required_count", "required_percentage"],
		as_dict=True,
	)


class ADR116Case(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.program = fx.make_program()
		self.student = fx.make_student()
		self.pe = fx.make_enrollment(self.student, self.program)
		self.pe.db_set("enrollment_date", add_days(today(), -60))
		self.pe.reload()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()


class TestGRIValidation(ADR116Case):
	def test_cohort_type_needs_types_and_a_sane_percentage(self):
		with self.assertRaises(frappe.ValidationError):
			_gri("Cohort Meeting Attendance", default_quantity=5)
		ctype = fx.make_cohort_type()
		with self.assertRaises(frappe.ValidationError):
			_gri(
				"Chapel Attendance",
				attendance_measure="Percentage",
				default_quantity=150,
			)
		gri = _gri(
			"Cohort Meeting Attendance",
			attendance_measure="Percentage",
			default_quantity=75,
			minimum_held=4,
			cohort_types=[{"cohort_type": ctype.name}],
		)
		snap = fa.snapshot_fields(gri)
		self.assertEqual(snap["required_percentage"], 75)
		self.assertEqual(snap["minimum_held"], 4)
		self.assertEqual(snap["counted_cohort_types"], ctype.name)
		self.assertNotIn("required_count", snap)


class TestCohortMeetings(ADR116Case):
	def setUp(self):
		super().setUp()
		self.ctype = fx.make_cohort_type()
		other = fx.make_cohort_type()
		leader_user = fx.make_user(roles=("Cohort Participant",))
		self.leader = fx.make_person("Leader", user=leader_user.name)
		self.cohort = fx.make_cohort(self.ctype.name, self.leader.name).name
		self.other_cohort = fx.make_cohort(other.name, self.leader.name).name
		self.person = frappe.db.get_value("Student", self.student.name, "person")
		for c in (self.cohort, self.other_cohort):
			if not frappe.db.exists("Cohort Membership", {"cohort": c, "person": self.leader.name}):
				fx.add_member(c, self.leader.name, is_leader=1, role="Leader")
			fx.add_member(c, self.person)
		gri = _gri(
			"Cohort Meeting Attendance",
			attendance_measure="Percentage",
			default_quantity=60,
			cohort_types=[{"cohort_type": self.ctype.name}],
		)
		self.sgr = _add_requirement(self.pe, gri)

	def _held(self, cohort, days_ago, status):
		frappe.set_user(self.leader.user)
		start = now_datetime() + timedelta(days=2)
		name = mt.schedule(
			cohort,
			"Group",
			oral_groups._utc_iso(start),
			oral_groups._utc_iso(start + timedelta(hours=1)),
			link="https://meet.example.test/g",
		)["created"][0]
		frappe.db.set_value(mt.MEETING, name, "starts_on", now_datetime() - timedelta(days=days_ago))
		mt.mark_attendance(name, json.dumps([{"person": self.person, "status": status}]))
		frappe.set_user("Administrator")
		return name

	def test_the_leaders_roll_moves_the_requirement(self):
		self._held(self.cohort, 20, "Present")
		self.assertEqual(_row(self.sgr).status, "Fulfilled")
		self._held(self.cohort, 15, "Absent")
		row = _row(self.sgr)
		self.assertEqual((row.status, row.attendance_rate), ("In Progress", 50.0))
		self._held(self.cohort, 10, "Excused")
		self.assertEqual(_row(self.sgr).attendance_rate, 50.0)
		self._held(self.cohort, 5, "Present")
		row = _row(self.sgr)
		self.assertEqual((row.status, row.attendance_rate, row.attended_count), ("Fulfilled", 66.7, 2))

	def test_only_the_counted_cohort_types(self):
		self._held(self.other_cohort, 10, "Absent")
		self._held(self.cohort, 5, "Present")
		self.assertEqual(_row(self.sgr).attendance_rate, 100.0)

	def test_absences_on_leave_are_left_out(self):
		self._held(self.cohort, 20, "Present")
		self._held(self.cohort, 8, "Absent")
		self.assertEqual(_row(self.sgr).status, "In Progress")
		set_program_status(
			self.pe.name, LEAVE_STATUS, category="Medical/LOA", effective_date=add_days(today(), -10)
		)
		return_from_leave(self.pe.name, effective_date=add_days(today(), -6))
		row = _row(self.sgr)
		self.assertEqual((row.status, row.attendance_rate), ("Fulfilled", 100.0))

	def test_a_cancelled_meeting_no_longer_counts(self):
		self._held(self.cohort, 20, "Present")
		absent = self._held(self.cohort, 8, "Absent")
		frappe.set_user(self.leader.user)
		mt.cancel_meeting(absent)
		frappe.set_user("Administrator")
		self.assertEqual(_row(self.sgr).status, "Fulfilled")


class TestChapelRoll(ADR116Case):
	def setUp(self):
		super().setUp()
		chaplain = fx.make_user(roles=("Chaplain",))
		self.chaplain = chaplain.name
		self.count_sgr = _add_requirement(self.pe, _gri("Chapel Attendance", default_quantity=2))
		self.pct_sgr = _add_requirement(
			self.pe,
			_gri("Chapel Attendance", attendance_measure="Percentage", default_quantity=50),
		)

	def _chapel(self, days):
		doc = frappe.get_doc(
			{
				"doctype": "Chapel",
				"chapel_topic": fx.uid("Chapel"),
				"starts_on": now_datetime() + timedelta(days=days),
				"ends_on": now_datetime() + timedelta(days=days, hours=1),
				"confirmed": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _roll(self, chapel, status):
		frappe.set_user(self.chaplain)
		try:
			return chapel_service.save_roll(chapel, [{"student": self.student.name, "status": status}])
		finally:
			frappe.set_user("Administrator")

	def test_a_student_cannot_take_the_roll(self):
		chapel = self._chapel(-1)
		frappe.set_user(self.student.user)
		with self.assertRaises(frappe.PermissionError):
			chapel_service.save_roll(chapel, [{"student": self.student.name, "status": "Present"}])

	def _held_since_enrollment(self):
		# Every confirmed chapel on the site is in the base, not only ours.
		return len(fa.chapel_occasions(self.student.name, getdate(self.pe.enrollment_date)))

	def test_roll_present_excused_and_removal(self):
		past, ahead = self._chapel(-3), self._chapel(2)
		with self.assertRaises(frappe.ValidationError):
			self._roll(ahead, "Present")
		self._roll(ahead, "Excused")
		self._roll(past, "Present")
		count, pct = _row(self.count_sgr), _row(self.pct_sgr)
		self.assertEqual((count.status, count.attended_count), ("In Progress", 1))
		held = self._held_since_enrollment()
		self.assertEqual(pct.attendance_rate, round(100.0 / held, 1))
		self.assertEqual(pct.status, "Fulfilled" if held <= 2 else "In Progress")

		roll = {r["student"]: r for r in self._roll(past, "")}
		self.assertEqual(roll[self.student.name]["status"], "")
		self.assertEqual(_row(self.count_sgr).attended_count, 0)
		self.assertEqual(_row(self.pct_sgr).status, "In Progress")

	def test_excused_does_not_count_and_check_in_turns_it_present(self):
		frappe.db.set_single_value("Seminary Settings", "require_chapel_checkin_code", 0)
		frappe.db.set_single_value("Seminary Settings", "chapel_checkin_opens_before_mins", 0)
		frappe.db.set_single_value("Seminary Settings", "chapel_checkin_closes_after_mins", 0)
		frappe.clear_document_cache("Seminary Settings", "Seminary Settings")
		chapel = self._chapel(-1)
		self._roll(chapel, "Excused")
		self.assertEqual(_row(self.count_sgr).attended_count, 0)
		frappe.set_user(self.student.user)
		chapel_service.check_in(chapel)
		frappe.set_user("Administrator")
		record = frappe.get_value(
			"Chapel Attendance", {"chapel": chapel, "student": self.student.name}, ["status", "method"]
		)
		self.assertEqual(record, ("Present", "Self check-in"))
		self.assertEqual(_row(self.count_sgr).attended_count, 1)
