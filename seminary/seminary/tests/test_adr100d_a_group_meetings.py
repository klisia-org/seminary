# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/100d-a: group meetings for oral activities, and students' time zones."""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_system_timezone, today

from seminary.seminary import oral_groups, oral_meetings, school_meetings, time_zones
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr082_deadlines import _row, _scale, _section

THIS = "seminary.seminary.tests.test_adr100d_a_group_meetings"
CALLS = []


class FakeBot:
	needs_managed = False
	rooms = False

	def arm(self, capture):
		CALLS.append(("arm", capture["name"], capture["meeting_url"]))
		return f"BOT-{len(CALLS)}"

	def disarm(self, ref, capture=None):
		CALLS.append(("disarm", ref))


class FakeZoom:
	def create(self, account, meeting):
		CALLS.append(("create", account["name"], meeting["start"]))
		n = len(CALLS)
		return {
			"join_url": f"https://z.example/{n}",
			"meeting_id": f"Z{n}",
			"host_key": None,
		}

	def update(self, account, meeting_id, meeting):
		CALLS.append(("update", meeting_id, meeting["start"]))
		return {}

	def delete(self, account, meeting_id):
		CALLS.append(("delete", meeting_id))


@contextmanager
def _fakes():
	with (
		patch.object(oral_meetings, "capture_methods", return_value={"bot": f"{THIS}.FakeBot"}),
		patch.object(school_meetings, "providers", return_value={"Fake": f"{THIS}.FakeZoom"}),
	):
		yield


def _student(name, tz=None, cs=None):
	student = fx.make_student()
	frappe.db.set_value("Student", student.name, "student_name", name)
	if tz:
		frappe.db.set_value("User", student.user, "time_zone", tz)
	if cs:
		frappe.get_doc(
			{
				"doctype": "Scheduled Course Roster",
				"name": f"{cs}-{student.name}",
				"course_sc": cs,
				"student": student.name,
				"stuname_roster": name,
				"active": 1,
				"audit_bool": 0,
			}
		).db_insert()
	return student


def _local(site_text, tz):
	site = datetime.strptime(site_text, "%Y-%m-%d %H:%M:%S")
	return site.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(ZoneInfo(tz)).replace(tzinfo=None)


class GroupCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		CALLS.clear()
		self.cs = _section(_scale(), modality="Virtual")
		frappe.db.set_value("Course Schedule", self.cs, "title", fx.uid("Preaching"))
		activity = frappe.get_doc(
			{
				"doctype": "Oral Activity",
				"title": fx.uid("Sermon"),
				"course": fx.uid("C"),
				"mode": "Conversation",
				"capture": "Virtual meeting",
			}
		)
		activity.flags.ignore_links = True
		activity.insert(ignore_permissions=True)
		self.activity = activity.name
		self.scac = _row(self.cs, add_days(today(), 30), kind="Oral", oral=self.activity)
		frappe.db.set_value("Web Meeting Account", {"name": ["is", "set"]}, "enabled", 0)
		# The instructor works in the site's zone here, so times read plainly.
		frappe.db.set_value("User", "Administrator", "time_zone", get_system_timezone())
		self.day = add_days(today(), 3)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def constraints(self, **kw):
		c = {
			"date_from": self.day,
			"date_to": self.day,
			"weekdays": [0, 1, 2, 3, 4, 5, 6],
			"hours_from": "09:00",
			"hours_to": "17:00",
			"length": 60,
			"gap": 0,
			"attend": 0,
			"use_accounts": 0,
		}
		c.update(kw)
		return frappe.as_json(c)

	def account(self, limit=1):
		with _fakes():
			return (
				frappe.get_doc(
					{
						"doctype": "Web Meeting Account",
						"label": fx.uid("Licence"),
						"provider": "Fake",
						"host_id": "host@example.com",
						"max_concurrent": limit,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)


class TestTimeZones(IntegrationTestCase):
	def test_the_browser_zone_replaces_the_site_default_and_asks_otherwise(self):
		student = fx.make_student()
		frappe.db.set_value("User", student.user, "time_zone", get_system_timezone())
		frappe.set_user(student.user)
		try:
			self.assertEqual(time_zones.report("Asia/Shanghai"), {"time_zone": "Asia/Shanghai"})
			out = time_zones.report("Europe/London")
			self.assertEqual((out["ask"], out["time_zone"]), (True, "Asia/Shanghai"))
			self.assertEqual(time_zones.report("Not/AZone"), {})
			time_zones.set_my_time_zone("Europe/London")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(time_zones.own_zone(student.user), "Europe/London")


class TestGroups(GroupCase):
	def test_by_size_keeps_nearby_zones_together(self):
		zones = ["Asia/Shanghai", "America/Chicago"] * 3
		students = {_student(f"S{i}", tz, self.cs).name: tz for i, tz in enumerate(zones)}
		groups = oral_groups.propose_groups(self.cs, self.activity, 3, keep_zones=1)
		self.assertEqual(len(groups), 2)
		for g in groups:
			self.assertEqual(len({students[s] for s in g["students"]}), 1)


class TestSuggesting(GroupCase):
	def test_a_lone_far_member_gets_the_averaged_slot_and_a_note(self):
		a = _student("Ana", "America/Chicago", self.cs)
		b = _student("Bea", "America/Chicago", self.cs)
		li = _student("Li", "Asia/Shanghai", self.cs)
		group = [{"label": "G1", "students": [a.name, b.name, li.name]}]
		# Chicago's day and Shanghai's do not meet: the least total time outside wins.
		frappe.db.set_value("Course Schedule", self.cs, "c_dateend", add_days(today(), 9))
		out = oral_groups.suggest(
			self.cs,
			self.activity,
			frappe.as_json(group),
			self.constraints(date_to=add_days(self.day, 2)),
		)[0]
		self.assertEqual(out["cost"], 180)
		self.assertEqual(_local(out["start"], "America/Chicago").hour, 16)
		self.assertIn("Li (Asia/Shanghai)", out["note"])
		self.assertIn("No time fits all 3", out["note"])

	def test_a_members_other_class_is_avoided(self):
		a = _student("Ana", get_system_timezone(), self.cs)
		other = _section(_scale())
		frappe.get_doc(
			{
				"doctype": "Scheduled Course Roster",
				"name": f"{other}-{a.name}",
				"course_sc": other,
				"student": a.name,
				"active": 1,
				"audit_bool": 0,
			}
		).db_insert()
		frappe.get_doc(
			{
				"doctype": "Course Schedule Meeting Dates",
				"name": frappe.generate_hash(length=10),
				"parent": other,
				"parenttype": "Course Schedule",
				"parentfield": "cs_meetinfo",
				"cs_meetdate": self.day,
				"cs_fromtime": "00:00:00",
				"cs_totime": "12:00:00",
			}
		).db_insert()
		out = oral_groups.suggest(
			self.cs,
			self.activity,
			frappe.as_json([{"label": "G", "students": [a.name]}]),
			self.constraints(attend=1),
		)[0]
		self.assertGreaterEqual(datetime.strptime(out["start"], "%Y-%m-%d %H:%M:%S").hour, 12)

	def test_attending_puts_meetings_one_after_another(self):
		site = get_system_timezone()
		groups = [{"label": f"G{i}", "students": [_student(f"S{i}", site, self.cs).name]} for i in range(3)]
		out = oral_groups.suggest(
			self.cs,
			self.activity,
			frappe.as_json(groups),
			self.constraints(attend=1, gap=15),
		)
		starts = [datetime.strptime(o["start"], "%Y-%m-%d %H:%M:%S") for o in out]
		self.assertEqual([s.strftime("%H:%M") for s in starts], ["09:00", "10:15", "11:30"])

	def test_an_account_runs_one_group_at_a_time(self):
		self.account()
		site = get_system_timezone()
		groups = [{"label": f"G{i}", "students": [_student(f"S{i}", site, self.cs).name]} for i in range(2)]
		with _fakes():
			out = oral_groups.suggest(
				self.cs,
				self.activity,
				frappe.as_json(groups),
				self.constraints(use_accounts=1),
			)
		self.assertNotEqual(out[0]["start"], out[1]["start"])


class TestCreatingAndSeeing(GroupCase):
	def make(self):
		self.account()
		site = get_system_timezone()
		self.a = _student("Ana", site, self.cs)
		self.b = _student("Ben", site, self.cs)
		slots = [
			{
				"label": "G1",
				"students": [self.a.name],
				"start": f"{self.day} 10:00:00",
				"end": f"{self.day} 10:30:00",
			},
			{
				"label": "G2",
				"students": [self.b.name],
				"start": f"{self.day} 11:00:00",
				"end": f"{self.day} 11:30:00",
			},
		]
		with _fakes():
			return oral_groups.create_meetings(self.cs, self.activity, frappe.as_json(slots), "bot")

	def test_meetings_are_created_armed_and_told_only_to_their_group(self):
		out = self.make()
		self.assertEqual((len(out["created"]), out["skipped"]), (2, []))
		first = frappe.get_doc(oral_meetings.OAM, out["created"][0])
		self.assertEqual(
			(first.kind, first.meeting_status, first.status),
			("Group", "Created", "Armed"),
		)
		self.assertTrue(first.link.startswith("https://z.example/"))
		self.assertIn(("arm", first.name, first.link), CALLS)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"for_user": self.a.user, "document_name": first.name},
			)
		)
		mine = oral_groups.my_meetings(self.a.user, self.cs)
		self.assertEqual([m["name"] for m in mine], [first.name])
		self.assertEqual(mine[0]["link"], first.link)
		# The shared section feed never carries group meetings.
		self.assertFalse(oral_meetings.captured_rows(self.cs) - {None})

	def test_a_slot_that_now_clashes_is_skipped_and_named(self):
		self.make()
		again = [
			{
				"label": "G9",
				"students": [self.a.name],
				"start": f"{self.day} 10:15:00",
				"end": f"{self.day} 10:45:00",
			}
		]
		with _fakes():
			out = oral_groups.create_meetings(self.cs, self.activity, frappe.as_json(again), "bot")
		self.assertEqual(out["created"], [])
		self.assertIn("Ana", out["skipped"][0]["reason"])

	def test_moving_updates_the_provider_and_rearms(self):
		name = self.make()["created"][0]
		with _fakes():
			oral_groups.move_meeting(name, f"{self.day} 13:00:00", f"{self.day} 13:30:00")
		doc = frappe.get_doc(oral_meetings.OAM, name)
		self.assertEqual(str(doc.from_time), "13:00:00")
		self.assertTrue(any(c[0] == "update" for c in CALLS))
		self.assertEqual(doc.status, "Armed")

	def test_cancelling_deletes_the_meeting_and_the_recorder(self):
		name = self.make()["created"][0]
		ref = frappe.db.get_value(oral_meetings.OAM, name, "capture_ref")
		with _fakes():
			oral_groups.cancel_meeting(name)
		self.assertIn(("disarm", ref), CALLS)
		self.assertTrue(any(c[0] == "delete" for c in CALLS))
		self.assertEqual(oral_groups.my_meetings(self.a.user, self.cs), [])
