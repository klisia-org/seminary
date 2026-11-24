"""The ``/lti/...`` routes, as a `page_renderer` (decisions/110).

A renderer rather than whitelisted methods because the protocol fixes the shape
of these URLs and their responses: an OAuth token response is a bare JSON
object, a line item has its own media type, and the authorization endpoint
answers with an HTML form. `/api/method/...` wraps everything in `message`.

Nothing here runs on the SCORM delivery host, where only `/scorm/...` exists.
"""

from __future__ import annotations

import frappe
from werkzeug.wrappers import Response

from seminary.lti import PREFIX


class LTIRoutes:
	__slots__ = ("http_status_code", "path")

	def __init__(self, path, http_status_code=None):
		self.path = path
		self.http_status_code = http_status_code

	def _parts(self) -> list[str]:
		request = getattr(frappe.local, "request", None)
		raw = (request.path if request else None) or self.path or ""
		return [p for p in raw.strip("/").split("/") if p]

	def can_render(self) -> bool:
		from seminary.scorm.delivery import is_delivery_request

		parts = self._parts()
		return bool(parts) and parts[0] == PREFIX and not is_delivery_request()

	def render(self) -> Response:
		from seminary.lti import services

		_keep_browser_session()
		try:
			return self._dispatch()
		except services.Refused as e:
			return e.response
		except Exception:
			frappe.log_error(title="lti: route failed")
			return services.oauth_error("server_error", status=500)

	def _dispatch(self) -> Response:
		from seminary.lti import keys, launch, registration, services

		request = frappe.local.request
		method = request.method
		parts = self._parts()[1:]
		args = {k: v for k, v in request.args.items()}
		form = dict(frappe.local.form_dict or {})

		match parts:
			case ["jwks"] if method in ("GET", "HEAD"):
				return services.json_response(keys.published_jwks())
			case ["openid-configuration"] if method in ("GET", "HEAD"):
				return services.json_response(registration.openid_configuration())
			case ["auth"] if method in ("GET", "POST"):
				return launch.authorize(form)
			case ["deep-link"] if method == "POST":
				return launch.deep_link_return(form)
			case ["token"] if method == "POST":
				return services.token(form)
			case ["register"] if method == "POST":
				return registration.register(request.get_data())
			case ["ags", course, "lineitems"] if method == "GET":
				return services.line_items(course, args)
			case ["ags", _course, "lineitems"]:
				# Line items are the section's lessons; a tool may not make them (§7).
				return services.oauth_error("unsupported_operation", "line items are read-only", status=405)
			case ["ags", course, "lineitems", lesson] if method == "GET":
				return services.line_item(course, lesson)
			case ["ags", course, "lineitems", lesson, "scores"] if method == "POST":
				return services.score(course, lesson, request.get_data(), request.content_type)
			case ["ags", course, "lineitems", lesson, "results"] if method == "GET":
				return services.results(course, lesson, args)
			case ["nrps", course, "memberships"] if method == "GET":
				return services.memberships(course, args)
		return services.oauth_error("not_found", status=404)


def _keep_browser_session() -> None:
	"""No /lti/ response sets or deletes a cookie (decisions/110 §3).

	A tool returns the browser here with a cross-site form POST (the Deep Linking
	return, or an OIDC request sent as POST), and the SameSite=Lax session cookie
	is not sent with it. Frappe then treats the request as Guest and answers with
	`sid=Guest`/`user_id=Guest`, overwriting the session the same browser still
	has open in Desk or the portal: the "session has expired" dialog. Nothing
	under /lti/ reads the session cookie for identity (the user comes from a
	signed hint), so none of these responses has a reason to touch cookies.
	"""
	cm = getattr(frappe.local, "cookie_manager", None)
	if cm is not None:
		cm.cookies.clear()
		cm.to_delete.clear()
