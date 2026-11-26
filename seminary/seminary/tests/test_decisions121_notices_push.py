# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""decisions/121: email notices for unread portal messages, and the Push
channel (device subscriptions, In-App copies, the adapter, the portal files)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from seminary.seminary import comms, message_notices, web_push
from seminary.seminary.tests import cohort_fixtures as fx

ENDPOINT = "https://push.example.test/send/"


def _subscription(user, tag="a"):
	return frappe.get_doc(
		{
			"doctype": "Push Subscription",
			"user": user,
			"endpoint": ENDPOINT + tag + frappe.generate_hash(length=8),
			"p256dh": "BKey" + tag,
			"auth": "auth" + tag,
			"device_label": "Test " + tag,
		}
	).insert(ignore_permissions=True)


def _push_error(status):
	from pywebpush import WebPushException

	return WebPushException("refused", response=SimpleNamespace(status_code=status, text=""))


class Decisions121Base(FrappeTestCase):
	def setUp(self):
		self.account = web_push.push_account()
		self.assertTrue(self.account, "migrate seeds the Push account")
		self.sender = fx.make_user()
		self.sender_person = fx.make_person("Sender", user=self.sender.name)
		self.user = fx.make_user()
		self.person = fx.make_person("Reader", user=self.user.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _inapp(self, **kwargs):
		values = {
			"channel": comms.IN_APP_CHANNEL,
			"person": self.person.name,
			"subject": "Hello",
			"message": "<p>Private words</p>",
			"category": "Community",
			"triggered_by": self.sender.name,
			"notify_if_unread": 1,
		}
		values.update(kwargs)
		with patch("frappe.enqueue"):
			return comms.send_message(**values)


class TestKeysAndAccount(Decisions121Base):
	def test_generated_key_pair_signs(self):
		import base64

		from cryptography.hazmat.primitives import serialization
		from py_vapid import Vapid02, b64urlencode

		public, private = web_push.generate_vapid_keys()
		vapid = Vapid02.from_string(private_key=private)
		raw = vapid.public_key.public_bytes(
			serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
		)
		self.assertEqual(b64urlencode(raw), public)
		self.assertEqual(len(base64.urlsafe_b64decode(public + "==")), 65)

	def test_seeded_account_has_keys_and_provider_option(self):
		account = frappe.get_doc("Channel Provider Account", self.account)
		self.assertEqual(account.provider, "web-push")
		config = account.get_config()
		self.assertTrue(config.get("public_key"))
		self.assertTrue(config.get("private_key"))
		options = frappe.get_meta("Channel Provider Account").get_field("provider").options.split("\n")
		for key in comms.get_adapter_registry():
			self.assertIn(key, options)


class TestSubscriptions(Decisions121Base):
	def test_subscribe_refresh_and_remove(self):
		frappe.set_user(self.user.name)
		endpoint = ENDPOINT + frappe.generate_hash(length=10)
		sub = {"endpoint": endpoint, "keys": {"p256dh": "BKey", "auth": "secret"}}
		first = web_push.subscribe(json.dumps(sub), "Phone")
		again = web_push.subscribe(json.dumps(sub), "Phone again")
		self.assertEqual(first["name"], again["name"])
		settings = web_push.get_my_push_settings()
		self.assertTrue(settings["available"])
		self.assertEqual([d["name"] for d in settings["devices"]], [first["name"]])
		self.assertNotIn("endpoint", settings["devices"][0])
		self.assertTrue(web_push.remove_device(endpoint=endpoint))
		self.assertFalse(frappe.db.exists("Push Subscription", first["name"]))

	def test_only_https_endpoints(self):
		frappe.set_user(self.user.name)
		for endpoint in ("http://push.example.test/x", "file:///etc/passwd", ""):
			with self.assertRaises(frappe.ValidationError):
				web_push.subscribe(json.dumps({"endpoint": endpoint, "keys": {"p256dh": "a", "auth": "b"}}))

	def test_cannot_remove_someone_elses_device(self):
		sub = _subscription(self.sender.name)
		frappe.set_user(self.user.name)
		with self.assertRaises(frappe.PermissionError):
			web_push.remove_device(name=sub.name)

	def test_a_browser_moves_to_whoever_signs_in(self):
		sub = _subscription(self.sender.name)
		frappe.set_user(self.user.name)
		web_push.subscribe(
			json.dumps({"endpoint": sub.endpoint, "keys": {"p256dh": "BNew", "auth": "new"}}),
			"Shared laptop",
		)
		self.assertEqual(frappe.db.get_value("Push Subscription", sub.name, "user"), self.user.name)


class TestInAppCopies(Decisions121Base):
	def _push_logs(self, inapp):
		return frappe.get_all(
			"Communication Log",
			filters={"reference_doctype": "Communication Log", "reference_name": inapp},
			fields=["name", "channel", "status", "subject", "message", "category"],
		)

	def test_no_device_no_push_log(self):
		inapp = self._inapp()
		self.assertEqual(self._push_logs(inapp), [])

	def test_inapp_message_is_copied_to_push(self):
		_subscription(self.user.name)
		inapp = self._inapp()
		logs = self._push_logs(inapp)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].channel, "Push")
		self.assertEqual(logs[0].status, "Queued")
		self.assertEqual(logs[0].category, "Community")
		# A title, the sender and a link -- never the message itself.
		self.assertEqual(logs[0].subject, "Hello")
		self.assertNotIn("Private words", logs[0].message or "")

	def test_push_opt_out_for_the_category(self):
		_subscription(self.user.name)
		self.person.append("consents", {"channel": "Push", "category": "Community", "status": "Opted Out"})
		self.person.save(ignore_permissions=True)
		inapp = self._inapp()
		self.assertEqual(self._push_logs(inapp), [])

	def test_direct_push_without_a_device_is_cancelled(self):
		log = comms.send_message(
			channel="Push", person=self.person.name, subject="Hi", message="", category="Academic"
		)
		row = frappe.db.get_value("Communication Log", log, ["status", "error"], as_dict=True)
		self.assertEqual(row.status, "Cancelled")
		self.assertEqual(comms.reachability(self.person, "Push", "Academic"), "no_address")


class TestAdapter(Decisions121Base):
	def _queued_push(self):
		_subscription(self.user.name, "a")
		_subscription(self.user.name, "b")
		inapp = self._inapp()
		name = frappe.db.get_value(
			"Communication Log", {"reference_doctype": "Communication Log", "reference_name": inapp}
		)
		return inapp, name

	def test_sent_to_every_device_with_a_link(self):
		inapp, name = self._queued_push()
		with patch("pywebpush.webpush") as push:
			comms.deliver_now(name)
		self.assertEqual(push.call_count, 2)
		payload = json.loads(push.call_args.kwargs["data"])
		self.assertEqual(payload["url"], f"/seminary/inbox?message={inapp}")
		self.assertEqual(payload["tag"], inapp)
		self.assertEqual(frappe.db.get_value("Communication Log", name, "status"), "Sent")
		self.assertTrue(all(frappe.get_all("Push Subscription", {"user": self.user.name}, pluck="last_used")))

	def test_a_gone_device_is_deleted(self):
		_inapp, name = self._queued_push()
		with patch("pywebpush.webpush", side_effect=[_push_error(410), None]):
			comms.deliver_now(name)
		self.assertEqual(frappe.db.count("Push Subscription", {"user": self.user.name}), 1)
		self.assertEqual(frappe.db.get_value("Communication Log", name, "status"), "Sent")

	def test_every_device_gone_fails_without_retry(self):
		_inapp, name = self._queued_push()
		with patch("pywebpush.webpush", side_effect=[_push_error(404), _push_error(410)]):
			comms.deliver_now(name)
		self.assertEqual(frappe.db.count("Push Subscription", {"user": self.user.name}), 0)
		self.assertEqual(frappe.db.get_value("Communication Log", name, "status"), "Failed")

	def test_service_errors_retry(self):
		_inapp, name = self._queued_push()
		with patch("pywebpush.webpush", side_effect=_push_error(500)):
			comms.deliver_now(name)
		row = frappe.db.get_value("Communication Log", name, ["status", "retry_count"], as_dict=True)
		self.assertEqual((row.status, row.retry_count), ("Queued", 1))
		self.assertEqual(frappe.db.count("Push Subscription", {"user": self.user.name}), 2)


class TestUnreadNotices(Decisions121Base):
	def _age(self, log, minutes):
		frappe.db.set_value(
			"Communication Log",
			log,
			"creation",
			add_to_date(now_datetime(), minutes=-minutes),
			update_modified=False,
		)

	def _notices(self):
		return frappe.get_all(
			"Communication Log",
			filters={"person": self.person.name, "template": message_notices.TEMPLATE},
			fields=["name", "channel", "subject", "message", "status"],
		)

	def test_only_person_to_person_inapp_is_marked(self):
		marked = self._inapp()
		plain = self._inapp(notify_if_unread=0)
		email = comms.send_message(
			channel="Email",
			person=self.person.name,
			subject="x",
			message="<p>x</p>",
			category="Community",
			notify_if_unread=1,
		)
		self.assertEqual(frappe.db.get_value("Communication Log", marked, "notify_if_unread"), 1)
		self.assertEqual(frappe.db.get_value("Communication Log", plain, "notify_if_unread"), 0)
		self.assertEqual(frappe.db.get_value("Communication Log", email, "notify_if_unread"), 0)

	def test_one_notice_after_the_window(self):
		first = self._inapp()
		second = self._inapp(subject="Again")
		read = self._inapp(subject="Seen")
		frappe.db.set_value("Communication Log", read, "read_at", now_datetime())
		for log in (first, read):
			self._age(log, 20)
		self._age(second, 5)

		message_notices.send_unread_notices()
		notices = self._notices()
		self.assertEqual(len(notices), 1)
		self.assertEqual(notices[0].channel, "Email")
		self.assertIn("2 new messages", notices[0].subject)
		self.assertNotIn("Private words", notices[0].message)
		self.assertIn("/seminary/inbox", notices[0].message)
		for log in (first, second):
			self.assertEqual(frappe.db.get_value("Communication Log", log, "unread_notice"), notices[0].name)
		self.assertFalse(frappe.db.get_value("Communication Log", read, "unread_notice"))

		# Announced messages are not announced again.
		message_notices.send_unread_notices()
		self.assertEqual(len(self._notices()), 1)

	def test_nothing_before_the_window_closes(self):
		log = self._inapp()
		self._age(log, 10)
		message_notices.send_unread_notices()
		self.assertEqual(self._notices(), [])
		self.assertFalse(frappe.db.get_value("Communication Log", log, "unread_notice"))

	def test_community_email_opt_out_still_closes_the_batch(self):
		self.person.append("consents", {"channel": "Email", "category": "Community", "status": "Opted Out"})
		self.person.save(ignore_permissions=True)
		log = self._inapp()
		self._age(log, 20)
		message_notices.send_unread_notices()
		notices = self._notices()
		self.assertEqual([n.status for n in notices], ["Cancelled"])
		self.assertEqual(frappe.db.get_value("Communication Log", log, "unread_notice"), notices[0].name)


def fake_link(doctype, name, user):
	if doctype == "Person":
		return f"/elsewhere/{name}"
	return None


def _link_hooks(hook, *args, **kwargs):
	if hook == web_push.LINK_HOOK:
		return ["seminary.seminary.tests.test_decisions121_notices_push.fake_link"]
	return _real_get_hooks(hook, *args, **kwargs)


_real_get_hooks = frappe.get_hooks


class TestNotify(Decisions121Base):
	"""The helper other apps push through (121 addendum §3, §4)."""

	def test_nothing_without_a_device_or_for_the_actor(self):
		self.assertIsNone(web_push.notify(self.person.name, "Hi", triggered_by=self.sender.name))
		_subscription(self.user.name)
		self.assertIsNone(web_push.notify(self.person.name, "Hi", triggered_by=self.user.name))
		self.assertTrue(web_push.notify(self.person.name, "Hi", triggered_by=self.sender.name))

	def test_opt_out_for_the_category(self):
		_subscription(self.user.name)
		self.person.append(
			"consents", {"channel": "Push", "category": "Transactional", "status": "Opted Out"}
		)
		self.person.save(ignore_permissions=True)
		self.assertIsNone(web_push.notify(self.person.name, "Hi", triggered_by=self.sender.name))

	def _url(self, reference_doctype, reference_name, person=None):
		with patch("frappe.enqueue"):
			log = web_push.notify(
				person or self.person.name,
				"<b>New</b> submission",
				reference_doctype=reference_doctype,
				reference_name=reference_name,
				triggered_by=self.sender.name,
			)
		doc = frappe.get_doc("Communication Log", log)
		self.assertEqual(doc.subject, "New submission")
		return web_push._click_url(doc)

	def test_an_app_names_the_page(self):
		_subscription(self.user.name)
		with patch("frappe.get_hooks", side_effect=_link_hooks):
			self.assertEqual(
				self._url("Person", self.sender_person.name), f"/elsewhere/{self.sender_person.name}"
			)

	def test_staff_get_desk_and_others_the_portal(self):
		_subscription(self.user.name)
		ref = self.sender_person.name
		self.assertEqual(self._url("Person", ref), "/seminary/")
		staff = fx.make_user()
		staff.db_set("user_type", "System User")
		staff_person = fx.make_person("Staff", user=staff.name)
		_subscription(staff.name)
		self.assertEqual(self._url("Person", ref, staff_person.name), f"/desk/person/{ref}")


class TestPortalFiles(FrappeTestCase):
	def test_site_wide_worker(self):
		sw = web_push.PortalPushRoutes("sw.js")
		self.assertTrue(sw.can_render())
		response = sw.render()
		self.assertEqual(response.mimetype, "application/javascript")
		self.assertIn("notificationclick", response.get_data(as_text=True))

	def test_portal_manifest(self):
		manifest = web_push.PortalPushRoutes("seminary/manifest.webmanifest")
		self.assertTrue(manifest.can_render())
		data = json.loads(manifest.render().get_data(as_text=True))
		self.assertEqual((data["start_url"], data["scope"]), ("/seminary/", "/seminary/"))
		self.assertEqual({i["sizes"] for i in data["icons"]}, {"192x192", "512x512"})

	def test_other_paths_are_left_alone(self):
		for path in ("seminary/inbox", "seminary/sw.js", "nowhere/manifest.webmanifest", "x/sw.js"):
			self.assertFalse(web_push.PortalPushRoutes(path).can_render(), path)
