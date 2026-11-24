# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""LTI 1.3 and LTI Advantage (decisions/110).

The tool here is played by the test: it has an RSA key of its own, signs what a
tool signs (deep-link responses, client assertions) and reads what a tool reads
(the id_token, against this site's published key set). What the tests defend:

- an id_token goes only to a URL the tool registered, for the person the launch
  was minted for, once;
- a tool's score reaches the gradebook only through an instructor's mapping, and
  never over a grader's number;
- a tool reaches only the sections that have a lesson opening it.
"""

from __future__ import annotations

import json
import re
import time
from html import unescape
from unittest.mock import patch

import frappe
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from frappe.tests import IntegrationTestCase

from seminary.lti import (
	AGS_CLAIM,
	CLAIM,
	DL_CLAIM,
	NRPS_CLAIM,
	ROLE_INSTRUCTOR,
	ROLE_LEARNER,
	SCOPE_LINEITEM_READ,
	SCOPE_NRPS,
	SCOPE_SCORE,
	issuer,
	keys,
	launch,
	services,
	url,
)
from seminary.lti.services import Refused
from seminary.seminary.tests.identity_cleanup import module_hooks
from seminary.seminary.tests.test_p006_api import _make_user

setUpModule, tearDownModule = module_hooks()

TOOL_HOST = "https://tool.lti-test.example"


def _tool_key():
	private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	pem = (
		private.public_key()
		.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
		.decode()
	)
	return private, pem


def _form_fields(response) -> dict:
	body = response.get_data(as_text=True)
	return {k: unescape(v) for k, v in re.findall(r"name='([^']+)' value='([^']*)'", body)}


def _our_claims(id_token: str, client_id: str) -> dict:
	header = jwt.get_unverified_header(id_token)
	jwk = next(k for k in keys.published_jwks()["keys"] if k["kid"] == header["kid"])
	return jwt.decode(id_token, jwt.PyJWK(jwk).key, algorithms=["RS256"], audience=client_id, issuer=issuer())


class _LTICase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.student = _make_user("Student", "lti-student")
		cls.outsider = _make_user("Student", "lti-outsider")
		cls.tool_private, cls.tool_public = _tool_key()

	def setUp(self):
		from seminary.seminary.tests.test_p007_docperms import (
			_any_course_schedule,
			_roster,
			_student_for,
		)

		frappe.set_user("Administrator")
		frappe.local.request_ip = "127.0.0.1"
		self.addCleanup(lambda: frappe.set_user("Administrator"))
		cs, other = _any_course_schedule()
		self.course, self.other_course = cs.name, other.name
		frappe.db.set_value("Course Schedule", self.course, "published", 1)
		self.student_record = _student_for(self.student, "lti")
		self.roster = _roster(self.course, self.student_record, self.student)
		frappe.local.p007_cache = {}

		self.tool = frappe.get_doc(
			{
				"doctype": "LTI Tool",
				"tool_name": f"LTI test {frappe.generate_hash(length=6)}",
				"oidc_login_url": f"{TOOL_HOST}/login",
				"target_link_url": f"{TOOL_HOST}/launch",
				"deep_linking_url": f"{TOOL_HOST}/pick",
				"public_key": self.tool_public,
			}
		).insert(ignore_permissions=True)
		self.chapter = frappe.get_doc(
			{"doctype": "Course Schedule Chapter", "chapter_title": "LTI chapter", "coursesc": self.course}
		)
		self.chapter.flags.ignore_mandatory = True
		self.chapter.insert(ignore_permissions=True)
		self.lesson = self._lesson("Publisher reading")

	def _lesson(self, title, tool=None, chapter=None):
		doc = frappe.get_doc(
			{
				"doctype": "Course Lesson",
				"chapter": (chapter or self.chapter).name,
				"course_sc": self.course,
				"lesson_title": title,
				"lti_tool": (tool or self.tool).name,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_mandatory=True)
		return doc

	# --- the tool's side ---------------------------------------------------------
	def _sign_as_tool(self, claims: dict) -> str:
		now = int(time.time())
		base = {"iss": self.tool.client_id, "iat": now, "exp": now + 300}
		pem = self.tool_private.private_bytes(
			serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
		)
		return jwt.encode({**base, **claims}, pem, algorithm="RS256")

	def _launch_as(self, user, lesson=None, nonce="n-1", redirect=None):
		"""Leg 1 as `user`, then the tool's authorization request back to us."""
		frappe.set_user(user)
		started = launch.start((lesson or self.lesson).name)
		params = dict(re.findall(r"[?&]([^=&]+)=([^&]*)", started["url"]))
		from urllib.parse import unquote_plus

		params = {k: unquote_plus(v) for k, v in params.items()}
		frappe.set_user("Guest")  # a cross-site return carries no session
		return params, launch.authorize(
			{
				"scope": "openid",
				"response_type": "id_token",
				"response_mode": "form_post",
				"prompt": "none",
				"client_id": params["client_id"],
				"redirect_uri": redirect or self.tool.target_link_url,
				"login_hint": params["login_hint"],
				"lti_message_hint": params["lti_message_hint"],
				"state": "s-1",
				"nonce": nonce,
			}
		)

	def _token(self, scopes):
		assertion = self._sign_as_tool(
			{"sub": self.tool.client_id, "aud": url("token"), "jti": frappe.generate_hash(length=12)}
		)
		response = services.token(
			{
				"grant_type": "client_credentials",
				"client_assertion_type": services.ASSERTION_TYPE,
				"client_assertion": assertion,
				"scope": " ".join(scopes),
			}
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		frappe.local.lti_bearer = json.loads(response.get_data())["access_token"]
		self.addCleanup(lambda: setattr(frappe.local, "lti_bearer", None))


class TestLTIKeys(_LTICase):
	def test_rotation_keeps_the_old_key_published_for_a_day(self):
		old = keys.active_key().kid
		keys.rotate()
		kids = [k["kid"] for k in keys.published_jwks()["keys"]]
		self.assertIn(old, kids)
		self.assertNotEqual(keys.active_key().kid, old)
		frappe.db.set_value(
			"LTI Platform Key",
			{"kid": old},
			"retired_on",
			frappe.utils.add_days(frappe.utils.now_datetime(), -2),
		)
		keys.purge_retired()
		self.assertNotIn(old, [k["kid"] for k in keys.published_jwks()["keys"]])

	def test_the_private_key_is_never_published(self):
		for jwk in keys.published_jwks()["keys"]:
			self.assertNotIn("d", jwk)


class TestLTITool(_LTICase):
	def test_ids_are_ours_and_a_key_is_required(self):
		self.assertEqual(len(self.tool.client_id), 24)
		self.assertTrue(self.tool.deployment_id)
		doc = frappe.get_doc(
			{
				"doctype": "LTI Tool",
				"tool_name": "LTI test keyless",
				"oidc_login_url": f"{TOOL_HOST}/login",
				"target_link_url": f"{TOOL_HOST}/launch",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

	def test_http_urls_are_refused(self):
		self.tool.target_link_url = "http://tool.lti-test.example/launch"
		self.assertRaises(frappe.ValidationError, self.tool.save, ignore_permissions=True)

	def test_a_lesson_gets_a_resource_link_id_and_keeps_its_mapping_in_its_section(self):
		self.assertTrue(self.lesson.lti_resource_link_id)
		other_row = frappe.get_all(
			"Scheduled Course Assess Criteria", filters={"parent": self.other_course}, pluck="name", limit=1
		)
		if other_row:
			self.lesson.reload()
			self.lesson.lti_assessment_criteria = other_row[0]
			self.assertRaises(frappe.PermissionError, self.lesson.save, ignore_permissions=True)


class TestLTILaunch(_LTICase):
	def test_a_student_launch_posts_a_signed_id_token_to_the_tool(self):
		params, response = self._launch_as(self.student)
		self.assertEqual(response.status_code, 200)
		self.assertIn(f"form-action {TOOL_HOST}", response.headers["Content-Security-Policy"])
		fields = _form_fields(response)
		self.assertEqual(fields["state"], "s-1")
		claims = _our_claims(fields["id_token"], self.tool.client_id)
		self.assertEqual(claims["nonce"], "n-1")
		self.assertEqual(claims[CLAIM + "message_type"], "LtiResourceLinkRequest")
		self.assertEqual(claims[CLAIM + "roles"], [ROLE_LEARNER])
		self.assertEqual(claims[CLAIM + "deployment_id"], self.tool.deployment_id)
		self.assertEqual(claims[CLAIM + "resource_link"]["id"], self.lesson.lti_resource_link_id)
		self.assertEqual(claims[CLAIM + "context"]["id"], self.course)
		self.assertEqual(
			claims[AGS_CLAIM]["lineitem"], url("ags", self.course, "lineitems", self.lesson.name)
		)
		self.assertIn(NRPS_CLAIM, claims)
		self.assertEqual(claims["sub"], params["login_hint"])
		# Name and email are off unless the school turns them on.
		self.assertNotIn("email", claims)
		self.assertNotIn("name", claims)

	def test_the_subject_is_per_tool_and_says_nothing_about_the_person(self):
		sub = launch.subject(self.student, self.tool.name)
		self.assertNotIn(self.student.split("@")[0], sub)
		self.assertNotEqual(sub, launch.subject(self.student, "another tool"))

	def test_name_and_email_go_only_when_turned_on(self):
		self.tool.send_name = 1
		self.tool.send_email = 1
		self.tool.save(ignore_permissions=True)
		frappe.clear_document_cache("LTI Tool", self.tool.name)
		_params, response = self._launch_as(self.student)
		claims = _our_claims(_form_fields(response)["id_token"], self.tool.client_id)
		self.assertEqual(claims["email"], self.student)
		self.assertTrue(claims["name"])

	def test_a_hint_is_used_once(self):
		params, _response = self._launch_as(self.student)
		again = launch.authorize(
			{
				"scope": "openid",
				"response_type": "id_token",
				"response_mode": "form_post",
				"client_id": params["client_id"],
				"redirect_uri": self.tool.target_link_url,
				"login_hint": params["login_hint"],
				"lti_message_hint": params["lti_message_hint"],
				"nonce": "n-2",
			}
		)
		self.assertEqual(again.status_code, 400)
		self.assertNotIn("id_token", again.get_data(as_text=True))

	def test_an_unregistered_redirect_gets_nothing(self):
		_params, response = self._launch_as(self.student, redirect="https://evil.example/steal")
		self.assertEqual(response.status_code, 400)
		body = response.get_data(as_text=True)
		self.assertNotIn("id_token", body)
		self.assertNotIn("evil.example", body)

	def test_a_signed_in_stranger_cannot_use_someone_elses_hint(self):
		frappe.set_user(self.student)
		started = launch.start(self.lesson.name)
		hint = re.search(r"lti_message_hint=([^&]+)", started["url"]).group(1)
		login = re.search(r"login_hint=([^&]+)", started["url"]).group(1)
		frappe.set_user(self.outsider)
		response = launch.authorize(
			{
				"scope": "openid",
				"response_type": "id_token",
				"response_mode": "form_post",
				"client_id": self.tool.client_id,
				"redirect_uri": self.tool.target_link_url,
				"login_hint": login,
				"lti_message_hint": hint,
				"nonce": "n-3",
			}
		)
		self.assertNotIn("id_token", _form_fields(response))
		self.assertEqual(_form_fields(response).get("error"), "login_required")

	def test_someone_outside_the_section_cannot_start(self):
		frappe.set_user(self.outsider)
		self.assertRaises(frappe.PermissionError, launch.start, self.lesson.name)

	def test_a_disabled_tool_cannot_start(self):
		frappe.db.set_value("LTI Tool", self.tool.name, "enabled", 0)
		frappe.clear_document_cache("LTI Tool", self.tool.name)
		frappe.set_user(self.student)
		self.assertRaises(frappe.DoesNotExistError, launch.start, self.lesson.name)

	def test_staff_launch_as_instructor(self):
		self.assertEqual(launch.launch_roles(self.course, "Administrator"), [ROLE_INSTRUCTOR])
		self.assertIsNone(launch.launch_roles(self.course, self.outsider))


class TestLTIDeepLinking(_LTICase):
	def _pick(self, items, data=None, nonce=None):
		frappe.set_user("Administrator")
		started = launch.start_deep_link(self.chapter.name, self.tool.name)
		from urllib.parse import parse_qs, urlparse

		params = {k: v[0] for k, v in parse_qs(urlparse(started["url"]).query).items()}
		frappe.set_user("Guest")
		response = launch.authorize(
			{
				"scope": "openid",
				"response_type": "id_token",
				"response_mode": "form_post",
				"client_id": params["client_id"],
				"redirect_uri": self.tool.deep_linking_url,
				"login_hint": params["login_hint"],
				"lti_message_hint": params["lti_message_hint"],
				"nonce": "dl-1",
			}
		)
		claims = _our_claims(_form_fields(response)["id_token"], self.tool.client_id)
		self.assertEqual(claims[CLAIM + "message_type"], "LtiDeepLinkingRequest")
		settings = claims[DL_CLAIM + "deep_linking_settings"]
		self.assertEqual(settings["deep_link_return_url"], url("deep-link"))
		reply = self._sign_as_tool(
			{
				"aud": issuer(),
				"nonce": nonce or frappe.generate_hash(length=10),
				CLAIM + "message_type": "LtiDeepLinkingResponse",
				CLAIM + "version": "1.3.0",
				CLAIM + "deployment_id": self.tool.deployment_id,
				DL_CLAIM + "data": data if data is not None else settings["data"],
				DL_CLAIM + "content_items": items,
			}
		)
		return launch.deep_link_return({"JWT": reply})

	def _chapter_lessons(self):
		return frappe.get_all(
			"Course Lesson",
			filters={"chapter": self.chapter.name},
			fields=["name", "lesson_title", "lti_tool", "lti_url", "lti_custom", "lti_assessment_criteria"],
			order_by="creation asc",
		)

	def test_each_link_becomes_a_lesson_and_a_line_item_an_unweighted_row(self):
		response = self._pick(
			[
				{
					"type": "ltiResourceLink",
					"title": "Chapter 3 quiz",
					"url": f"{TOOL_HOST}/launch/ch3",
					"custom": {"chapter": "3"},
					"lineItem": {"scoreMaximum": 20, "label": "Ch 3 quiz"},
				},
				{"type": "html", "html": "<p>not a link</p>"},
			]
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		added = [r for r in self._chapter_lessons() if r.lesson_title == "Chapter 3 quiz"]
		self.assertEqual(len(added), 1)
		lesson = added[0]
		self.assertEqual(lesson.lti_tool, self.tool.name)
		self.assertEqual(lesson.lti_url, f"{TOOL_HOST}/launch/ch3")
		self.assertEqual(lesson.lti_custom, "chapter=3")
		self.assertTrue(
			frappe.db.exists(
				"Course Schedule Lesson Reference", {"parent": self.chapter.name, "lesson": lesson.name}
			)
		)
		from seminary.seminary import cbe

		if lesson.lti_assessment_criteria:
			row = frappe.db.get_value(
				"Scheduled Course Assess Criteria",
				lesson.lti_assessment_criteria,
				["parent", "weight_scac", "title"],
				as_dict=True,
			)
			self.assertEqual((row.parent, row.weight_scac, row.title), (self.course, 0, "Ch 3 quiz"))
		else:
			# Only a competency or narrative section, or a site with no criteria.
			self.assertTrue(
				cbe.framework_for(self.course)
				or not frappe.db.exists("Assessment Criteria", {"type": "Offline"})
			)

	def test_a_response_without_our_data_adds_nothing(self):
		before = len(self._chapter_lessons())
		response = self._pick([{"type": "ltiResourceLink", "title": "Sneaky"}], data="forged")
		self.assertEqual(response.status_code, 400)
		self.assertEqual(len(self._chapter_lessons()), before)

	def test_a_response_signed_by_another_key_adds_nothing(self):
		other_private, _pem = _tool_key()
		with patch.object(self, "tool_private", other_private):
			response = self._pick([{"type": "ltiResourceLink", "title": "Forged"}])
		self.assertEqual(response.status_code, 400)
		self.assertFalse([r for r in self._chapter_lessons() if r.lesson_title == "Forged"])

	def test_an_instructor_who_cannot_edit_cannot_start(self):
		frappe.set_user(self.student)
		self.assertRaises(frappe.PermissionError, launch.start_deep_link, self.chapter.name, self.tool.name)


class TestLTIServices(_LTICase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.criterion = self._criterion()
		self.card = self._card(self.criterion)
		self.sub = launch.subject(self.student, self.tool.name)

	def _criterion(self):
		criteria = frappe.db.get_value("Assessment Criteria", {"name": ["like", "%"]}, "name")
		row = frappe.get_doc(
			{
				"doctype": "Scheduled Course Assess Criteria",
				"assesscriteria_scac": criteria,
				"parent": self.course,
				"parenttype": "Course Schedule",
				"parentfield": "courseassescrit_sc",
				"title": "LTI unit",
				"type": "Assignment",
				"weight_scac": 10,
			}
		)
		row.flags.ignore_permissions = True
		row.insert()
		return row.name

	def _card(self, criterion):
		existing = frappe.db.get_value(
			"Course Assess Results Detail",
			{"assessment_criteria": criterion, "student_card": self.student_record},
			"name",
		)
		if existing:
			return existing
		card = frappe.get_doc(
			{
				"doctype": "Course Assess Results Detail",
				"parent": self.roster,
				"parenttype": "Scheduled Course Roster",
				"parentfield": "stdroster_grade",
				"assessment_criteria": criterion,
				"student_card": self.student_record,
				"maximum_score": 10,
			}
		)
		card.flags.ignore_permissions = True
		card.insert()
		return card.name

	def _post(self, given, grading="FullyGraded", stamp=None, lesson=None):
		body = {
			"userId": self.sub,
			"scoreGiven": given,
			"scoreMaximum": 20,
			"activityProgress": "Completed",
			"gradingProgress": grading,
			"timestamp": stamp or frappe.utils.now_datetime().isoformat() + "Z",
		}
		return services.score(
			self.course, (lesson or self.lesson).name, json.dumps(body).encode(), services.MT_SCORE
		)

	def _cell(self):
		return frappe.db.get_value(
			"Course Assess Results Detail",
			self.card,
			["rawscore_card", "graded_card", "lti_reported_card"],
			as_dict=True,
		)

	def _scores(self):
		return frappe.get_all(
			"LTI Score",
			filters={"lesson": self.lesson.name},
			fields=["score_given", "percentage", "reported", "report_reason"],
			order_by="creation asc",
		)

	def _competency(self):
		from seminary.seminary import cbe
		from seminary.seminary.api import narrative_section

		return cbe.framework_for(self.course) or narrative_section(self.course)

	def test_a_token_needs_a_signed_assertion_once(self):
		assertion = self._sign_as_tool({"sub": self.tool.client_id, "aud": url("token"), "jti": "once"})
		form = {
			"grant_type": "client_credentials",
			"client_assertion_type": services.ASSERTION_TYPE,
			"client_assertion": assertion,
			"scope": SCOPE_SCORE,
		}
		self.assertEqual(services.token(form).status_code, 200)
		self.assertEqual(services.token(form).status_code, 401)  # the jti again

	def test_scopes_follow_the_tools_services(self):
		frappe.db.set_value("LTI Tool", self.tool.name, "allow_names_roles", 0)
		frappe.clear_document_cache("LTI Tool", self.tool.name)
		assertion = self._sign_as_tool({"sub": self.tool.client_id, "aud": url("token"), "jti": "nrps"})
		response = services.token(
			{
				"grant_type": "client_credentials",
				"client_assertion_type": services.ASSERTION_TYPE,
				"client_assertion": assertion,
				"scope": SCOPE_NRPS,
			}
		)
		self.assertEqual(json.loads(response.get_data())["error"], "invalid_scope")

	def test_no_bearer_no_service(self):
		frappe.local.lti_bearer = None
		with self.assertRaises(Refused) as ctx:
			services.line_items(self.course, {})
		self.assertEqual(ctx.exception.response.status_code, 401)

	def test_a_tool_sees_only_sections_with_its_lessons(self):
		self._token([SCOPE_LINEITEM_READ])
		items = json.loads(services.line_items(self.course, {}).get_data())
		self.assertEqual([i["resourceLinkId"] for i in items], [self.lesson.lti_resource_link_id])
		with self.assertRaises(Refused) as ctx:
			services.line_items(self.other_course, {})
		self.assertEqual(ctx.exception.response.status_code, 404)

	def test_the_line_item_carries_the_criterion_and_its_due_date(self):
		frappe.db.set_value("Course Lesson", self.lesson.name, "lti_assessment_criteria", self.criterion)
		frappe.db.set_value(
			"Scheduled Course Assess Criteria", self.criterion, "due_date", "2026-12-01 23:59:00"
		)
		self._token([SCOPE_LINEITEM_READ])
		item = json.loads(services.line_item(self.course, self.lesson.name).get_data())
		self.assertEqual(item["label"], "LTI unit")
		self.assertTrue(item["endDateTime"].startswith("2026-12-01T23:59:00"))

	def test_an_unmapped_score_is_kept_and_reaches_no_grade(self):
		self._token([SCOPE_SCORE])
		self.assertEqual(self._post(15).status_code, 204)
		scores = self._scores()
		self.assertEqual((scores[-1].percentage, scores[-1].reported), (75.0, 0))
		self.assertEqual(scores[-1].report_reason, "not mapped")
		self.assertFalse(self._cell().graded_card)

	def test_a_mapped_final_score_is_written_and_a_graders_number_wins(self):
		if self._competency():
			self.skipTest("the fixture section stores levels")
		frappe.db.set_value("Course Lesson", self.lesson.name, "lti_assessment_criteria", self.criterion)
		self._token([SCOPE_SCORE])
		self._post(10, grading="Pending")
		self.assertFalse(self._cell().graded_card)
		self._post(15)
		self.assertEqual(self._cell(), {"rawscore_card": 75.0, "graded_card": 1, "lti_reported_card": 1})
		self._post(16)
		self.assertEqual(self._cell().rawscore_card, 80.0)
		# A grader changes it: later scores stand down, for good.
		frappe.db.set_value("Course Assess Results Detail", self.card, "rawscore_card", 55)
		self._post(20)
		self.assertEqual(self._cell().rawscore_card, 55)
		self.assertEqual(self._scores()[-1].report_reason, "a grader owns this cell")

	def test_an_older_score_changes_nothing(self):
		self._token([SCOPE_SCORE])
		self._post(15, stamp="2026-11-24T12:00:00Z")
		self._post(5, stamp="2026-11-24T11:00:00Z")
		self.assertEqual([s.score_given for s in self._scores()], [15])

	def test_a_score_for_someone_not_on_the_roster_is_refused(self):
		self._token([SCOPE_SCORE])
		self.sub = launch.subject(self.outsider, self.tool.name)
		with self.assertRaises(Refused) as ctx:
			self._post(10)
		self.assertEqual(ctx.exception.response.status_code, 422)

	def test_the_class_list_names_no_one_by_default(self):
		self._token([SCOPE_NRPS])
		data = json.loads(services.memberships(self.course, {}).get_data())
		student = next(m for m in data["members"] if m["user_id"] == self.sub)
		self.assertEqual(student["roles"], [ROLE_LEARNER])
		self.assertNotIn("email", student)
		self.assertNotIn("name", student)
		self.assertEqual(data["context"]["id"], self.course)


class TestLTIPlumbing(_LTICase):
	def test_take_bearer_moves_only_lti_bearer_headers(self):
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		saved = getattr(frappe.local, "request", None)
		self.addCleanup(lambda: setattr(frappe.local, "request", saved))
		frappe.local.request = Request(
			EnvironBuilder(
				path="/lti/nrps/x/memberships", headers={"Authorization": "Bearer abc"}
			).get_environ()
		)
		services.take_bearer()
		self.assertEqual(frappe.local.lti_bearer, "abc")
		self.assertNotIn("Authorization", frappe.local.request.headers)

		frappe.local.lti_bearer = None
		frappe.local.request = Request(
			EnvironBuilder(path="/api/method/x", headers={"Authorization": "Bearer abc"}).get_environ()
		)
		services.take_bearer()
		self.assertIsNone(frappe.local.lti_bearer)
		self.assertIn("Authorization", frappe.local.request.headers)

	def test_lti_responses_leave_the_browser_session_alone(self):
		# A tool's cross-site POST arrives without the Lax session cookie; a
		# Guest Set-Cookie on the answer would log the user out of Desk.
		from frappe.auth import CookieManager

		from seminary.lti.renderer import _keep_browser_session

		saved = getattr(frappe.local, "cookie_manager", None)
		self.addCleanup(lambda: setattr(frappe.local, "cookie_manager", saved))
		frappe.local.cookie_manager = cm = CookieManager()
		cm.set_cookie("sid", "Guest")
		cm.set_cookie("user_id", "Guest")
		cm.delete_cookie(["full_name"])
		_keep_browser_session()
		self.assertEqual(cm.cookies, {})
		self.assertEqual(cm.to_delete, [])

	def test_the_key_set_route(self):
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from seminary.lti.renderer import LTIRoutes

		saved = getattr(frappe.local, "request", None)
		self.addCleanup(lambda: setattr(frappe.local, "request", saved))
		frappe.local.request = Request(EnvironBuilder(path="/lti/jwks").get_environ())
		renderer = LTIRoutes("lti/jwks")
		self.assertTrue(renderer.can_render())
		self.assertIn("keys", json.loads(renderer.render().get_data()))
		frappe.local.request = Request(
			EnvironBuilder(path="/lti/ags/x/lineitems", method="POST").get_environ()
		)
		self.assertEqual(LTIRoutes("lti/ags/x/lineitems").render().status_code, 405)

	def test_dynamic_registration_creates_a_tool_with_privacy_off(self):
		from seminary.lti import registration

		started = registration.start_registration(f"{TOOL_HOST}/register")
		token = re.search(r"registration_token=([^&]+)", started["url"]).group(1)
		frappe.local.lti_bearer = token
		self.addCleanup(lambda: setattr(frappe.local, "lti_bearer", None))
		body = {
			"application_type": "web",
			"client_name": f"LTI test registered {frappe.generate_hash(length=4)}",
			"initiate_login_uri": f"{TOOL_HOST}/login",
			"redirect_uris": [f"{TOOL_HOST}/launch"],
			"jwks_uri": f"{TOOL_HOST}/jwks",
			"token_endpoint_auth_method": "private_key_jwt",  # nosec B105 - an OAuth method name
			"scope": f"{SCOPE_SCORE} {SCOPE_NRPS}",
			registration.TOOL_CONFIG: {
				"domain": "tool.lti-test.example",
				"target_link_uri": f"{TOOL_HOST}/launch",
				"claims": ["email", "name"],
				"messages": [{"type": "LtiDeepLinkingRequest", "target_link_uri": f"{TOOL_HOST}/pick"}],
			},
		}
		response = registration.register(json.dumps(body).encode())
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		answer = json.loads(response.get_data())
		tool = frappe.get_doc("LTI Tool", {"client_id": answer["client_id"]})
		self.assertEqual(answer[registration.TOOL_CONFIG]["deployment_id"], tool.deployment_id)
		self.assertEqual((tool.send_name, tool.send_email), (0, 0))
		self.assertEqual((tool.allow_grades, tool.allow_names_roles, tool.allow_deep_linking), (1, 1, 1))
		# The token is spent.
		self.assertEqual(registration.register(json.dumps(body).encode()).status_code, 401)
