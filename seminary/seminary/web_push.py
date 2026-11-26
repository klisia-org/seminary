"""Web Push: notifications on phones and browsers (decisions/121 §3, §4).

The Push channel sends to the person's Push Subscriptions, which the portal adds
from the preferences page once the browser grants permission. Each subscription
is one browser or installed portal. Notifications are signed with the VAPID key
pair on the Push Channel Provider Account and encrypted to the device with
``pywebpush``.

What a notification carries is deliberately thin: a title, who it is from and a
link. The message itself stays in the inbox, behind the person's session.

One service worker serves the whole site (``/sw.js``, scope ``/``), so a browser holds one
subscription however many portals it uses; each portal has its own web manifest for installing
(121 addendum §1). Other apps push through ``notify`` and say where a notice opens through the
``push_links`` hook.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import quote

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import now_datetime, strip_html
from werkzeug.wrappers import Response

from seminary.seminary.doctype.push_subscription.push_subscription import endpoint_hash

PUSH_CHANNEL = "Push"
PROVIDER = "web-push"
PORTAL_PREFIX = "/seminary"
INBOX_PATH = f"{PORTAL_PREFIX}/inbox"
# Push services keep an undelivered notification this long (seconds) while the
# device is off. A day is enough for "you have a message"; later than that the
# email notice (§1) has already told them.
TTL = 24 * 60 * 60
MAX_DEVICES_PER_USER = 10
BODY_CHARS = 140
# The push service has forgotten this subscription: the browser was reset, the
# permission was withdrawn, or the portal was uninstalled.
GONE = {404, 410}


# ---------------------------------------------------------------- keys


def _b64url(raw: bytes) -> str:
	return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate_vapid_keys() -> tuple[str, str]:
	"""(public, private) for a new Push account. The public key is the
	uncompressed P-256 point the browser's ``applicationServerKey`` takes; the
	private key is the raw 32-byte scalar, which ``pywebpush`` reads as is."""
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import ec

	key = ec.generate_private_key(ec.SECP256R1())
	public = key.public_key().public_bytes(
		serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
	)
	private = key.private_numbers().private_value.to_bytes(32, "big")
	return _b64url(public), _b64url(private)


def push_account():
	"""The enabled Push account, or None when the site has none."""
	from seminary.seminary.comms import pick_account

	if not frappe.db.exists("Communication Channel", {"name": PUSH_CHANNEL, "enabled": 1}):
		return None
	return pick_account(PUSH_CHANNEL)


# ---------------------------------------------------------------- who has devices


def _user_of(person) -> str | None:
	if person is None:
		return None
	if isinstance(person, str):
		return frappe.db.get_value("Person", person, "user")
	return person.get("user")


def has_subscription(person) -> bool:
	user = _user_of(person)
	return bool(user and frappe.db.exists("Push Subscription", {"user": user}))


# ---------------------------------------------------------------- In-App copies


def _sender_name(user):
	if not user or user in ("Administrator", "Guest"):
		return None
	return frappe.db.get_value("User", user, "full_name") or None


def notify(
	person,
	title,
	*,
	body="",
	reference_doctype=None,
	reference_name=None,
	category="Transactional",
	triggered_by=None,
	dedupe_key=None,
):
	"""Push a notice to a person's devices, for any app (121 addendum §3). Returns the Push log,
	or None when nothing was queued: the site has no Push account, the person has no user or no
	device, the person is the one who acted, or they opted out of Push for the category. So a
	caller never adds Cancelled rows for people who cannot be pushed to."""
	from seminary.seminary import comms

	if not person or not title or not push_account():
		return None
	person_doc = person if hasattr(person, "channel_addresses") else frappe.get_doc("Person", person)
	triggered_by = triggered_by or frappe.session.user
	if not person_doc.user or person_doc.user == triggered_by:
		return None
	if not has_subscription(person_doc):
		return None
	if comms.consent_blocks(person_doc, PUSH_CHANNEL, category):
		return None
	return comms.send_message(
		channel=PUSH_CHANNEL,
		person=person_doc,
		subject=strip_html(title).strip()[:140],
		message=body or "",
		category=category,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		triggered_by=triggered_by,
		dedupe_key=dedupe_key,
	)


def push_for_inapp(log):
	"""Queue a Push log for a delivered In-App log (§4)."""
	if not log.person or log.direction != "Outbound":
		return None
	sender = _sender_name(log.triggered_by)
	title = log.subject or (
		_("New message from {0}").format(sender) if sender else _("You have a new message")
	)
	body = _("From {0}").format(sender) if sender and log.subject else ""
	return notify(
		log.person,
		title,
		body=body,
		category=log.category,
		# The Push log points at the message it announces; the adapter links
		# there, and the announcement roll-up ignores it (§4).
		reference_doctype="Communication Log",
		reference_name=log.name,
		triggered_by=log.triggered_by,
		dedupe_key=f"push::{log.name}",
	)


# ---------------------------------------------------------------- adapter


LINK_HOOK = "push_links"


def _click_url(log) -> str:
	"""Where the notification opens: the inbox for a message, else the page an app names for the
	record through the ``push_links`` hook, else the Desk form for staff and the portal home for
	everyone else (121 addendum §4). Only a path on this site is ever used."""
	if log.reference_doctype == "Communication Log" and log.reference_name:
		return f"{INBOX_PATH}?message={log.reference_name}"
	user = _user_of(log.person)
	if log.reference_doctype and log.reference_name:
		for path in frappe.get_hooks(LINK_HOOK) or []:
			try:
				link = frappe.get_attr(path)(log.reference_doctype, log.reference_name, user)
			except Exception:
				frappe.log_error(frappe.get_traceback(), f"push_links {path} failed")
				continue
			if link and link.startswith("/") and not link.startswith("//"):
				return link
		if user and frappe.db.get_value("User", user, "user_type") == "System User":
			slug = log.reference_doctype.lower().replace(" ", "-")
			return f"/desk/{slug}/{quote(str(log.reference_name), safe='')}"
	return f"{PORTAL_PREFIX}/"


def _payload(log) -> str:
	body = strip_html(log.message or "").strip()
	if len(body) > BODY_CHARS:
		body = body[: BODY_CHARS - 1].rstrip() + "\u2026"
	return json.dumps(
		{
			"title": log.subject or _("New notification"),
			"body": body,
			"url": _click_url(log),
			# One notification per message: a resend replaces, never stacks.
			"tag": log.reference_name or log.name,
		}
	)


def _vapid_claims(settings) -> dict:
	subject = (settings.get("subject") or "").strip()
	if not subject.startswith(("mailto:", "https://")):
		subject = frappe.utils.get_url()
	return {"sub": subject}


class WebPushAdapter:
	"""Sends a Push log to every subscription of the person's user.

	A subscription the push service has forgotten is deleted. The log is Sent
	when at least one device took it; it fails at once, without retries, when
	the person has no device left, and retries when every push service errored."""

	final_status = "Sent"
	background = True

	def send(self, log, account):
		from pywebpush import WebPushException, webpush

		from seminary.seminary.comms import MAX_RETRIES, account_settings

		settings = account_settings(account)
		private_key = settings.get("private_key")
		if not private_key:
			raise ValueError(f"Channel Provider Account {account.name} has no push key pair")
		user = _user_of(log.person)
		subscriptions = (
			frappe.get_all(
				"Push Subscription",
				filters={"user": user},
				fields=["name", "endpoint", "p256dh", "auth"],
			)
			if user
			else []
		)
		if not subscriptions:
			# Nothing will ever take it: fail now rather than retry. _deliver
			# adds the attempt this one is, which reaches MAX_RETRIES.
			log.retry_count = MAX_RETRIES - 1
			raise ValueError("No device to push to")

		data = _payload(log)
		claims = _vapid_claims(settings)
		delivered, errors = 0, []
		for sub in subscriptions:
			try:
				webpush(
					subscription_info={
						"endpoint": sub.endpoint,
						"keys": {"p256dh": sub.p256dh, "auth": sub.auth},
					},
					data=data,
					vapid_private_key=private_key,
					# pywebpush adds `aud` from the endpoint; a shared dict would
					# carry the first service's audience to the next one.
					vapid_claims=dict(claims),
					ttl=TTL,
					timeout=10,
				)
				delivered += 1
				frappe.db.set_value(
					"Push Subscription", sub.name, "last_used", now_datetime(), update_modified=False
				)
			except WebPushException as e:
				status = getattr(e.response, "status_code", None)
				if status in GONE:
					frappe.delete_doc("Push Subscription", sub.name, ignore_permissions=True, force=True)
				else:
					errors.append(f"{status or ''} {e}".strip())
		if delivered:
			return None
		if not errors:
			log.retry_count = MAX_RETRIES - 1
			raise ValueError("Every device had unsubscribed")
		raise RuntimeError("; ".join(errors)[:400])


# ---------------------------------------------------------------- portal API


def _require_user():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in."), frappe.PermissionError)
	return frappe.session.user


def _device_row(row):
	return {
		"name": row.name,
		"device_label": row.device_label,
		"last_used": row.last_used,
		"creation": row.creation,
		"endpoint_hash": row.endpoint_hash,
	}


@frappe.whitelist()
def get_my_push_settings():
	"""Whether this site can push, the key a browser subscribes with, and the
	viewer's own devices. The endpoint itself never comes back to the page;
	the page matches its own device by the hash."""
	user = _require_user()
	account = push_account()
	public_key = None
	if account:
		public_key = frappe.db.get_value("Channel Provider Account", account, "vapid_public_key")
	devices = frappe.get_all(
		"Push Subscription",
		filters={"user": user},
		fields=["name", "device_label", "last_used", "creation", "endpoint_hash"],
		order_by="creation desc",
	)
	return {
		"available": bool(public_key),
		"public_key": public_key,
		"devices": [_device_row(d) for d in devices],
	}


def _clean_subscription(subscription):
	if isinstance(subscription, str):
		try:
			subscription = json.loads(subscription)
		except ValueError:
			subscription = None
	if not isinstance(subscription, dict):
		frappe.throw(_("This browser sent an unreadable subscription."))
	endpoint = (subscription.get("endpoint") or "").strip()
	keys = subscription.get("keys") or {}
	p256dh = (keys.get("p256dh") or "").strip()
	auth = (keys.get("auth") or "").strip()
	# Push services are HTTPS endpoints; anything else would have the server
	# POST to an address the page chose.
	if not endpoint.startswith("https://") or len(endpoint) > 2000:
		frappe.throw(_("This browser sent an unreadable subscription."))
	if not p256dh or not auth or len(p256dh) > 200 or len(auth) > 100:
		frappe.throw(_("This browser sent an unreadable subscription."))
	return endpoint, p256dh, auth


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def subscribe(subscription: str | dict, device_label: str | None = None):
	"""Add (or refresh) this browser as one of the viewer's devices. A device
	someone else subscribed before moves to the viewer: one browser has one
	subscription, and it belongs to whoever is signed in on it now."""
	user = _require_user()
	if not push_account():
		frappe.throw(_("Notifications on devices are not available on this site."))
	endpoint, p256dh, auth = _clean_subscription(subscription)
	label = (device_label or "").strip()[:140] or _("This device")
	request = getattr(frappe.local, "request", None)
	user_agent = ((request.headers.get("User-Agent") if request else None) or "")[:500]

	existing = frappe.db.get_value("Push Subscription", {"endpoint_hash": endpoint_hash(endpoint)}, "name")
	if existing:
		doc = frappe.get_doc("Push Subscription", existing)
		doc.update(
			{"user": user, "p256dh": p256dh, "auth": auth, "device_label": label, "user_agent": user_agent}
		)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Push Subscription",
				"user": user,
				"endpoint": endpoint,
				"p256dh": p256dh,
				"auth": auth,
				"device_label": label,
				"user_agent": user_agent,
			}
		).insert(ignore_permissions=True)

	# Old browsers the person never removed: keep the newest few.
	stale = frappe.get_all(
		"Push Subscription",
		filters={"user": user},
		pluck="name",
		order_by="creation desc",
		offset=MAX_DEVICES_PER_USER,
		limit=100,
	)
	for name in stale:
		frappe.delete_doc("Push Subscription", name, ignore_permissions=True, force=True)
	return {"name": doc.name, "endpoint_hash": doc.endpoint_hash}


@frappe.whitelist(methods=["POST"])
def remove_device(name: str | None = None, endpoint: str | None = None):
	"""Remove one of the viewer's devices, by row (the device list) or by
	endpoint (the browser turning itself off)."""
	user = _require_user()
	if not name and endpoint:
		name = frappe.db.get_value("Push Subscription", {"endpoint_hash": endpoint_hash(endpoint)}, "name")
	if not name:
		return False
	if frappe.db.get_value("Push Subscription", name, "user") != user:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	frappe.delete_doc("Push Subscription", name, ignore_permissions=True, force=True)
	return True


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def send_test_notification():
	"""Push a test notification to the viewer's own devices."""
	from seminary.seminary import comms
	from seminary.seminary.person import find_person

	user = _require_user()
	person = find_person(user=user)
	if not person or not has_subscription(person):
		frappe.throw(_("Turn on notifications on this device first."))
	if not push_account():
		frappe.throw(_("Notifications on devices are not available on this site."))
	log = comms.send_message(
		channel=PUSH_CHANNEL,
		person=person,
		subject=_("Notifications are on"),
		message=_("This is how messages from the school will reach you."),
		category="Transactional",
		triggered_by=user,
	)
	return {"log": log}


# ---------------------------------------------------------------- portal files

_SW_PATH = Path(__file__).resolve().parent.parent / "public" / "js" / "portal-sw.js"
MANIFEST_HOOK = "portal_manifests"
DEFAULT_ICONS = [
	{"src": "/assets/seminary/images/portal-icon-192.png", "sizes": "192x192", "type": "image/png"},
	{"src": "/assets/seminary/images/portal-icon-512.png", "sizes": "512x512", "type": "image/png"},
]


def site_name() -> str:
	return (
		frappe.db.get_single_value("Website Settings", "app_name")
		or frappe.db.get_single_value("System Settings", "app_name")
		or "Seminary"
	)


def build_manifest(prefix: str, name: str, icons=None) -> dict:
	"""A portal's web manifest: installs as its own app, opening at /<prefix>/."""
	return {
		"name": name,
		"short_name": name[:12],
		"start_url": f"/{prefix}/",
		"scope": f"/{prefix}/",
		"display": "standalone",
		"background_color": "#ffffff",
		"theme_color": "#ffffff",
		"icons": icons or DEFAULT_ICONS,
	}


def seminary_manifest() -> dict:
	"""This portal's manifest. Its name follows the site's branding."""
	return build_manifest(PORTAL_PREFIX.strip("/"), site_name())


def _manifests() -> dict:
	"""{portal prefix: dotted path returning its manifest}, from every app's
	``portal_manifests`` hook."""
	found = {}
	for prefix, path in (frappe.get_hooks(MANIFEST_HOOK) or {}).items():
		found[prefix] = path[-1] if isinstance(path, list) else path
	return found


class PortalPushRoutes:
	"""``/sw.js`` and ``/<portal>/manifest.webmanifest`` (121 addendum §1).

	A page renderer rather than a static file: a service worker's scope is limited to its own
	directory, so the site-wide worker has to be served from the root, and each portal's route
	rule would otherwise send its manifest to the SPA."""

	__slots__ = ("http_status_code", "path")

	def __init__(self, path, http_status_code=None):
		self.path = path
		self.http_status_code = http_status_code

	def _parts(self):
		request = getattr(frappe.local, "request", None)
		raw = (request.path if request else None) or self.path or ""
		return [p for p in raw.strip("/").split("/") if p]

	def _target(self):
		"""("sw", None), ("manifest", prefix), or None."""
		parts = self._parts()
		if parts == ["sw.js"]:
			return ("sw", None)
		if len(parts) == 2 and parts[1] == "manifest.webmanifest" and parts[0] in _manifests():
			return ("manifest", parts[0])
		return None

	def can_render(self) -> bool:
		from seminary.scorm.delivery import is_delivery_request

		return bool(self._target()) and not is_delivery_request()

	def render(self) -> Response:
		kind, prefix = self._target()
		if kind == "sw":
			response = Response(_SW_PATH.read_text(), mimetype="application/javascript")
		else:
			manifest = frappe.get_attr(_manifests()[prefix])()
			response = Response(json.dumps(manifest), mimetype="application/manifest+json")
		# Browsers check the worker for updates themselves; never pin a copy.
		response.headers["Cache-Control"] = "no-cache"
		return response
