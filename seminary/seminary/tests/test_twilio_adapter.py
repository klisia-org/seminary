# Copyright (c) 2026, Klisia / SeminaryERP and Contributors
# See license.txt
"""The Twilio adapter (ADR 043, tests added with decisions/121): SMS, WhatsApp
and Voice sends, the signature check on Twilio's callbacks, and how callbacks
become status and inbound events. Twilio's API is called with `requests`, which
these tests replace; nothing leaves the machine."""

import base64
import hashlib
import hmac
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase as FrappeTestCase

from seminary.seminary.twilio_adapter import TwilioAdapter, _to_text

SID = "AC" + "0" * 32
TOKEN = "test-auth-token"  # nosec B105


def _account(channel="SMS", **fields):
	doc = frappe.get_doc(
		{
			"doctype": "Channel Provider Account",
			"account_name": "Twilio Test",
			"channel": channel,
			"provider": "twilio",
			"twilio_account_sid": SID,
			"twilio_auth_token": TOKEN,
			"twilio_from_number": "+15550001111",
			**fields,
		}
	)
	doc.name = "Twilio Test"
	return doc


def _log(**fields):
	return SimpleNamespace(
		**{
			"name": "LOG-1",
			"to_address": "+15552223333",
			"subject": None,
			"message": "<p>Class moved</p><p>Room 4</p>",
			"media_url": None,
			**fields,
		}
	)


def _response(status=201, body=None):
	return SimpleNamespace(status_code=status, json=lambda: body or {"sid": "SM123"})


class TestTwilioSend(FrappeTestCase):
	def test_sms(self):
		with patch("requests.post", return_value=_response()) as post:
			sid = TwilioAdapter().send(_log(), _account())
		self.assertEqual(sid, "SM123")
		url = post.call_args.args[0]
		data = post.call_args.kwargs["data"]
		self.assertEqual(url, f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json")
		self.assertEqual(post.call_args.kwargs["auth"], (SID, TOKEN))
		self.assertEqual(data["To"], "+15552223333")
		self.assertEqual(data["From"], "+15550001111")
		self.assertEqual(data["Body"], "Class moved\n\nRoom 4")
		self.assertIn("seminary.seminary.comms.webhook?account=Twilio%20Test", data["StatusCallback"])

	def test_whatsapp_prefixes_both_numbers(self):
		with patch("requests.post", return_value=_response()) as post:
			TwilioAdapter().send(_log(), _account("WhatsApp"))
		data = post.call_args.kwargs["data"]
		self.assertEqual(data["To"], "whatsapp:+15552223333")
		self.assertEqual(data["From"], "whatsapp:+15550001111")

	def test_messaging_service_replaces_the_from_number(self):
		account = _account(twilio_messaging_service_sid="MG1")
		with patch("requests.post", return_value=_response()) as post:
			TwilioAdapter().send(_log(), account)
		data = post.call_args.kwargs["data"]
		self.assertEqual(data["MessagingServiceSid"], "MG1")
		self.assertNotIn("From", data)

	def test_voice_reads_the_message_escaped(self):
		log = _log(subject="Alert", message="<p>Tom & Jerry <b>now</b></p>")
		with patch("requests.post", return_value=_response(body={"sid": "CA1"})) as post:
			sid = TwilioAdapter().send(log, _account("Voice"))
		self.assertEqual(sid, "CA1")
		self.assertTrue(post.call_args.args[0].endswith("/Calls.json"))
		twiml = post.call_args.kwargs["data"]["Twiml"]
		self.assertEqual(twiml, "<Response><Say>Alert\n\nTom &amp; Jerry now</Say></Response>")

	def test_voice_plays_a_recording(self):
		log = _log(media_url="https://example.test/a.mp3?x=1&y=2")
		with patch("requests.post", return_value=_response(body={"sid": "CA2"})) as post:
			TwilioAdapter().send(log, _account("Voice"))
		self.assertEqual(
			post.call_args.kwargs["data"]["Twiml"],
			"<Response><Play>https://example.test/a.mp3?x=1&amp;y=2</Play></Response>",
		)

	def test_refusals(self):
		with self.assertRaises(ValueError):
			TwilioAdapter().send(_log(to_address=None), _account())
		with self.assertRaises(ValueError):
			TwilioAdapter().send(_log(), _account(twilio_auth_token=None))
		with self.assertRaises(ValueError):
			TwilioAdapter().send(_log(), _account(twilio_from_number=None))
		with patch("requests.post", return_value=_response(400, {"message": "Invalid To"})):
			with self.assertRaisesRegex(RuntimeError, "Invalid To"):
				TwilioAdapter().send(_log(), _account())

	def test_text_flattening(self):
		self.assertEqual(_to_text("Hi", "<p>a<br>b</p><p>c &amp; d</p>"), "Hi\n\na\nb\n\nc & d")
		self.assertEqual(_to_text("Only subject", ""), "Only subject")


class TestTwilioCallbacks(FrappeTestCase):
	URL = "https://school.example.test/api/method/seminary.seminary.comms.webhook?account=Twilio%20Test"
	FORM: ClassVar[dict] = {"MessageSid": "SM9", "MessageStatus": "delivered", "To": "+1555"}

	def _signature(self, url, params, token=TOKEN):
		payload = url + "".join(k + params[k] for k in sorted(params))
		return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()

	def _verify(self, signature, form=None, settings=None):
		form = form or self.FORM
		request = SimpleNamespace(
			headers={"X-Twilio-Signature": signature} if signature else {},
			url=self.URL,
			form=SimpleNamespace(to_dict=lambda: dict(form)),
		)
		with patch.object(frappe.local, "request", request, create=True):
			return TwilioAdapter().verify_webhook(
				None, settings or {"auth_token": TOKEN, "public_url": self.URL}, None
			)

	def test_signature(self):
		good = self._signature(self.URL, self.FORM)
		self.assertTrue(self._verify(good))
		self.assertFalse(self._verify(None))
		self.assertFalse(self._verify(self._signature(self.URL, self.FORM, "other-token")))
		self.assertFalse(self._verify(good, form={**self.FORM, "MessageStatus": "read"}))
		self.assertFalse(self._verify(good, settings={"public_url": self.URL}))

	def test_message_status(self):
		adapter = TwilioAdapter()
		self.assertEqual(
			adapter.handle_webhook({"MessageSid": "SM9", "MessageStatus": "delivered"}, None),
			{"kind": "status", "provider_message_id": "SM9", "status": "Delivered"},
		)
		self.assertEqual(
			adapter.handle_webhook({"SmsSid": "SM9", "SmsStatus": "undelivered"}, None)["status"],
			"Bounced",
		)
		# Not terminal yet: nothing to record.
		self.assertIsNone(adapter.handle_webhook({"MessageSid": "SM9", "MessageStatus": "queued"}, None))

	def test_call_status(self):
		adapter = TwilioAdapter()
		self.assertEqual(
			adapter.handle_webhook({"CallSid": "CA1", "CallStatus": "completed"}, None)["status"],
			"Delivered",
		)
		self.assertEqual(
			adapter.handle_webhook({"CallSid": "CA1", "CallStatus": "no-answer"}, None)["status"],
			"Failed",
		)
		self.assertIsNone(adapter.handle_webhook({"CallSid": "CA1", "CallStatus": "ringing"}, None))

	def test_inbound_reply(self):
		event = TwilioAdapter().handle_webhook(
			{"From": "whatsapp:+15552223333", "Body": "Thanks", "MessageSid": "SM5"}, None
		)
		self.assertEqual(
			event,
			{
				"kind": "inbound",
				"from_address": "+15552223333",
				"body": "Thanks",
				"provider_message_id": "SM5",
			},
		)
