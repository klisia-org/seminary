"""This site's signing keys, and checking what a tool signed (decisions/110 §2).

One RS256 key signs every message this platform sends. It is created on first
use, stored encrypted with the site's encryption key, and published at
``/lti/jwks``. Rotating adds a new key and keeps the old one published for a
day, so an id_token signed a moment before the rotation still verifies.

A tool's messages (deep-link responses, client assertions) are checked against
the tool's own key set, fetched from its key-set URL and cached for an hour, or
against the PEM key pasted on the tool when it has no key-set URL.
"""

from __future__ import annotations

import json
import time

import frappe
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.password import decrypt, encrypt

ALGORITHM = "RS256"
#: How long a retired key stays in the published key set.
RETIRED_KEEP_HOURS = 24
#: How long a tool's fetched key set is trusted before it is fetched again.
TOOL_JWKS_TTL = 3600
#: Clock skew allowed on a tool's `iat`/`exp`.
LEEWAY = 60


class InvalidToolMessage(Exception):
	"""A JWT from a tool that does not verify. The message says why, for the log."""


# ---------------------------------------------------------------- our keys


def _new_key() -> str:
	private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	pem = private.private_bytes(
		serialization.Encoding.PEM,
		serialization.PrivateFormat.PKCS8,
		serialization.NoEncryption(),
	).decode()
	kid = frappe.generate_hash(length=16)
	jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
	jwk.update({"kid": kid, "alg": ALGORITHM, "use": "sig"})
	doc = frappe.get_doc(
		{
			"doctype": "LTI Platform Key",
			"kid": kid,
			"active": 1,
			"public_jwk": json.dumps(jwk),
			"private_key": encrypt(pem),
		}
	)
	doc.insert(ignore_permissions=True)
	# The first key is usually made on a GET (the key set, or a launch), which
	# Frappe does not commit: without this every request would sign with a key
	# of its own that no later request publishes.
	frappe.local.flags.commit = True
	return doc.name


def active_key():
	"""The key messages are signed with now, created if the site has none."""
	name = frappe.db.get_value("LTI Platform Key", {"active": 1}, "name", order_by="creation desc")
	if not name:
		name = _new_key()
	return frappe.get_doc("LTI Platform Key", name)


def sign(claims: dict) -> str:
	key = active_key()
	return jwt.encode(
		claims,
		decrypt(key.private_key),
		algorithm=ALGORITHM,
		headers={"kid": key.kid, "typ": "JWT"},
	)


def published_jwks() -> dict:
	"""The active key and any retired within the last day."""
	cutoff = add_to_date(now_datetime(), hours=-RETIRED_KEEP_HOURS)
	keys = []
	for row in frappe.get_all(
		"LTI Platform Key",
		fields=["public_jwk", "active", "retired_on"],
		order_by="creation desc",
	):
		if row.active or (row.retired_on and get_datetime(row.retired_on) > cutoff):
			keys.append(json.loads(row.public_jwk))
	if not keys:
		keys.append(json.loads(active_key().public_jwk))
	return {"keys": keys}


@frappe.whitelist(methods=["POST"])
def rotate() -> dict:
	"""Start signing with a new key. The old one stays published for a day."""
	frappe.only_for("System Manager")
	for name in frappe.get_all("LTI Platform Key", filters={"active": 1}, pluck="name"):
		frappe.db.set_value("LTI Platform Key", name, {"active": 0, "retired_on": now_datetime()})
	name = _new_key()
	return {"kid": frappe.db.get_value("LTI Platform Key", name, "kid")}


def purge_retired() -> None:
	"""Daily: drop keys retired long enough ago that nothing signed with them is live."""
	cutoff = add_to_date(now_datetime(), hours=-RETIRED_KEEP_HOURS)
	for name in frappe.get_all(
		"LTI Platform Key",
		filters={"active": 0, "retired_on": ["<", cutoff]},
		pluck="name",
	):
		frappe.delete_doc("LTI Platform Key", name, ignore_permissions=True, force=True)


# ---------------------------------------------------------------- tool keys


def _fetch_jwks(url: str) -> dict:
	cache_key = f"lti:tool_jwks:{url}"
	cached = frappe.cache.get_value(cache_key)
	if cached:
		return cached
	import requests

	try:
		response = requests.get(url, timeout=5, headers={"Accept": "application/json"})
		response.raise_for_status()
		data = response.json()
	except Exception as e:
		raise InvalidToolMessage(f"could not fetch the tool's key set: {e}") from e
	if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
		raise InvalidToolMessage("the tool's key set is not a JWKS")
	frappe.cache.set_value(cache_key, data, expires_in_sec=TOOL_JWKS_TTL)
	return data


def _tool_key(tool, kid: str | None):
	if tool.jwks_url:
		data = _fetch_jwks(tool.jwks_url)
		keys = data["keys"]
		match = [k for k in keys if not kid or k.get("kid") == kid]
		if not match and kid:
			# The tool may have rotated since we cached its set.
			frappe.cache.delete_value(f"lti:tool_jwks:{tool.jwks_url}")
			match = [k for k in _fetch_jwks(tool.jwks_url)["keys"] if k.get("kid") == kid]
		if not match:
			raise InvalidToolMessage(f"no key {kid!r} in the tool's key set")
		return jwt.PyJWK(match[0], algorithm=ALGORITHM).key
	if tool.public_key:
		return tool.public_key.strip()
	raise InvalidToolMessage("the tool has neither a key-set URL nor a public key")


def unverified_issuer(token: str) -> str | None:
	"""The `iss` a tool claims, to find which tool should have signed it."""
	try:
		return jwt.decode(token, options={"verify_signature": False}).get("iss")
	except jwt.PyJWTError:
		return None


def verify_tool_jwt(tool, token: str, audience: str | list[str]) -> dict:
	"""The claims of `token`, if `tool` signed it for `audience` and it is current."""
	try:
		header = jwt.get_unverified_header(token)
	except jwt.PyJWTError as e:
		raise InvalidToolMessage(f"not a JWT: {e}") from e
	if header.get("alg") != ALGORITHM:
		raise InvalidToolMessage(f"algorithm {header.get('alg')!r} is not RS256")
	key = _tool_key(tool, header.get("kid"))
	try:
		return jwt.decode(
			token,
			key,
			algorithms=[ALGORITHM],
			audience=audience,
			issuer=tool.client_id,
			leeway=LEEWAY,
			options={"require": ["exp", "iat", "iss", "aud"]},
		)
	except jwt.PyJWTError as e:
		raise InvalidToolMessage(str(e)) from e


def single_use(kind: str, value: str, ttl: int) -> bool:
	"""True the first time `value` is seen for `kind` within `ttl` seconds."""
	if not value:
		return False
	key = f"lti:seen:{kind}:{value}"
	if frappe.cache.get_value(key):
		return False
	frappe.cache.set_value(key, int(time.time()), expires_in_sec=max(ttl, 60))
	return True


def require_https(url: str, label: str) -> None:
	"""Tool URLs are https, except to a loopback host in developer mode."""
	from urllib.parse import urlparse

	parsed = urlparse(url or "")
	if parsed.scheme == "https" and parsed.netloc:
		return
	host = parsed.hostname or ""
	loopback = host in ("localhost", "127.0.0.1") or host.endswith(".localhost")
	if parsed.scheme == "http" and loopback and frappe.conf.developer_mode:
		return
	frappe.throw(_("{0} must be an https URL.").format(label))
