# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""One outside tool registered for LTI 1.3 launches (decisions/110 §1)."""

from __future__ import annotations

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


class LTITool(Document):
	def before_insert(self):
		# Ours to issue, never the tool's or a user's to choose.
		self.client_id = frappe.generate_hash(length=24)
		self.deployment_id = frappe.generate_hash(length=12)

	def validate(self):
		from seminary.lti.keys import require_https

		for field in ("oidc_login_url", "target_link_url", "deep_linking_url", "jwks_url"):
			if self.get(field):
				self.set(field, self.get(field).strip())
				require_https(self.get(field), _(self.meta.get_label(field)))
		for uri in self.redirect_list(explicit_only=True):
			require_https(uri, _("Redirect URL"))
		if not (self.jwks_url or (self.public_key or "").strip()):
			frappe.throw(_("Give the tool's key-set URL, or paste its public key."))
		if self.public_key and "BEGIN PUBLIC KEY" not in self.public_key:
			frappe.throw(_("The public key must be in PEM format (-----BEGIN PUBLIC KEY-----)."))
		parse_custom(self.custom_parameters)

	def onload(self):
		from seminary.lti import issuer, url

		self.set_onload(
			"platform",
			{
				"issuer": issuer(),
				"auth_url": url("auth"),
				"token_url": url("token"),
				"jwks_url": url("jwks"),
				"deep_link_return_url": url("deep-link"),
				"openid_configuration": url("openid-configuration"),
			},
		)

	def redirect_list(self, explicit_only: bool = False) -> list[str]:
		"""Where an id_token may be sent: the listed URLs, else the tool's two."""
		listed = [line.strip() for line in (self.redirect_uris or "").splitlines() if line.strip()]
		if listed or explicit_only:
			return listed
		return [u for u in (self.target_link_url, self.deep_linking_url) if u]

	def host(self) -> str:
		return (urlparse(self.target_link_url or "").hostname or "").lower()


def parse_custom(text: str | None) -> dict:
	"""`key=value` lines as a dict. A line without `=` is refused, not guessed at."""
	out = {}
	for line in (text or "").splitlines():
		line = line.strip()
		if not line:
			continue
		if "=" not in line:
			frappe.throw(_("Custom parameters are one key=value per line: {0}").format(line))
		key, value = line.split("=", 1)
		out[key.strip()] = value.strip()
	return out


def tool_for_url(launch_url: str) -> str | None:
	"""The enabled tool whose launch URL is on the same host as `launch_url`.

	Used where a course arrives with LTI links (decisions/108 §4): the link names
	a URL, and the site's own registration of that tool supplies everything else.
	"""
	host = (urlparse(launch_url or "").hostname or "").lower()
	if not host:
		return None
	for row in frappe.get_all(
		"LTI Tool",
		filters={"enabled": 1},
		fields=["name", "target_link_url", "oidc_login_url"],
		order_by="creation asc",
	):
		hosts = {
			(urlparse(u or "").hostname or "").lower() for u in (row.target_link_url, row.oidc_login_url)
		}
		if host in hosts:
			return row.name
	return None
