"""LTI Dynamic Registration (decisions/110 §1).

An administrator pastes the tool's registration URL. We open it with our
OpenID configuration URL and a single-use registration token; the tool reads the
configuration and posts its registration to ``/lti/register`` with that token;
we create the LTI Tool and answer with its client id and deployment id.

Name and email stay off on a tool registered this way, whatever claims it asks
for: sending them is the school's choice, made on the tool's form.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode

import frappe
from frappe import _
from werkzeug.wrappers import Response

from seminary.lti import AGS_SCOPES, SCOPE_NRPS, issuer, url
from seminary.lti.services import json_response, oauth_error

TOKEN_TTL = 3600
TOOL_CONFIG = "https://purl.imsglobal.org/spec/lti-tool-configuration"
PLATFORM_CONFIG = "https://purl.imsglobal.org/spec/lti-platform-configuration"
REGISTER_ROLES = ("System Manager", "Seminary Manager")


def openid_configuration() -> dict:
	from frappe.utils.change_log import get_versions

	version = (get_versions().get("seminary") or {}).get("version") or ""
	return {
		"issuer": issuer(),
		"authorization_endpoint": url("auth"),
		"registration_endpoint": url("register"),
		"jwks_uri": url("jwks"),
		"token_endpoint": url("token"),
		"token_endpoint_auth_methods_supported": ["private_key_jwt"],
		"token_endpoint_auth_signing_alg_values_supported": ["RS256"],
		"scopes_supported": ["openid", *AGS_SCOPES, SCOPE_NRPS],
		"response_types_supported": ["id_token"],
		"subject_types_supported": ["pairwise"],
		"id_token_signing_alg_values_supported": ["RS256"],
		"claims_supported": [
			"iss",
			"aud",
			"sub",
			"iat",
			"exp",
			"nonce",
			"name",
			"given_name",
			"family_name",
			"email",
		],
		PLATFORM_CONFIG: {
			"product_family_code": "seminary",
			"version": version,
			"messages_supported": [
				{"type": "LtiResourceLinkRequest"},
				{"type": "LtiDeepLinkingRequest", "placements": ["ContentArea"]},
			],
			"variables": [],
		},
	}


@frappe.whitelist(methods=["POST"])
def start_registration(registration_url: str) -> dict:
	"""The URL to open so the tool can register itself."""
	from seminary.lti.keys import require_https

	frappe.only_for(REGISTER_ROLES)
	registration_url = (registration_url or "").strip()
	require_https(registration_url, _("Registration URL"))
	token = frappe.generate_hash(length=40)
	frappe.cache.set_value(f"lti:register:{token}", frappe.session.user, expires_in_sec=TOKEN_TTL)
	sep = "&" if "?" in registration_url else "?"
	params = {"openid_configuration": url("openid-configuration"), "registration_token": token}
	return {"url": f"{registration_url}{sep}{urlencode(params)}"}


def _unique_name(name: str) -> str:
	base = (name or _("LTI tool")).strip()[:120]
	candidate, n = base, 2
	while frappe.db.exists("LTI Tool", candidate):
		candidate = f"{base} ({n})"
		n += 1
	return candidate


def register(body: bytes) -> Response:
	"""The tool's client registration, authorised by the registration token."""
	token = getattr(frappe.local, "lti_bearer", None) or ""
	key = f"lti:register:{token}"
	registered_by = frappe.cache.get_value(key) if token else None
	if not registered_by:
		return oauth_error("invalid_token", "the registration token is missing or expired", status=401)
	try:
		data = json.loads(body or b"{}")
	except ValueError:
		return oauth_error("invalid_client_metadata", "the body is not JSON")
	config = data.get(TOOL_CONFIG) if isinstance(data, dict) else None
	if not isinstance(config, dict):
		return oauth_error("invalid_client_metadata", f"{TOOL_CONFIG} is required")
	if data.get("token_endpoint_auth_method", "private_key_jwt") != "private_key_jwt":
		return oauth_error("invalid_client_metadata", "token_endpoint_auth_method must be private_key_jwt")

	scopes = set((data.get("scope") or "").split())
	deep_link = next(
		(
			m
			for m in config.get("messages") or []
			if isinstance(m, dict) and m.get("type") == "LtiDeepLinkingRequest"
		),
		None,
	)
	target = config.get("target_link_uri") or ""
	custom = config.get("custom_parameters") if isinstance(config.get("custom_parameters"), dict) else {}
	redirects = [u for u in data.get("redirect_uris") or [] if isinstance(u, str)]
	tool = frappe.get_doc(
		{
			"doctype": "LTI Tool",
			"tool_name": _unique_name(data.get("client_name")),
			"enabled": 1,
			"description": str(config.get("description") or "")[:500],
			"oidc_login_url": data.get("initiate_login_uri") or "",
			"target_link_url": target,
			"deep_linking_url": (deep_link or {}).get("target_link_uri") or (target if deep_link else ""),
			"redirect_uris": "\n".join(redirects),
			"jwks_url": data.get("jwks_uri") or "",
			"allow_deep_linking": 1 if deep_link else 0,
			"allow_grades": 1 if scopes & set(AGS_SCOPES) else 0,
			"allow_names_roles": 1 if SCOPE_NRPS in scopes else 0,
			"send_name": 0,
			"send_email": 0,
			"custom_parameters": "\n".join(f"{k}={v}" for k, v in custom.items() if "\n" not in f"{k}{v}"),
			"registered_dynamically": 1,
			"registration_json": json.dumps(data, indent=1)[:60000],
		}
	)
	tool.owner = registered_by
	try:
		tool.insert(ignore_permissions=True)
	except frappe.ValidationError as e:
		return oauth_error("invalid_client_metadata", str(e))
	frappe.cache.delete_value(key)

	granted = []
	if tool.allow_grades:
		granted.extend(sorted(scopes & set(AGS_SCOPES)))
	if tool.allow_names_roles:
		granted.append(SCOPE_NRPS)
	answer = dict(data)
	answer.update(
		{
			"client_id": tool.client_id,
			"scope": " ".join(granted),
			TOOL_CONFIG: {**config, "deployment_id": tool.deployment_id},
		}
	)
	return json_response(answer, status=200)
