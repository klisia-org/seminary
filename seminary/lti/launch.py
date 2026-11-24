"""The LTI 1.3 launch and Deep Linking 2.0 (decisions/110 §3-5).

A launch has three legs, and only the first runs in the SPA:

1. ``start`` (or ``start_deep_link``) authorises the person on the lesson, the
   way every course read is authorised, and mints a **single-use hint** naming
   who, which tool and which lesson. It returns the tool's login URL.
2. The browser goes to the tool, which sends it back to ``/lti/auth``.
3. ``authorize`` consumes the hint, re-checks the person's roles, and posts a
   signed id_token to one of the tool's registered redirect URLs.

**Why the user comes from the hint, not the session.** The tool may return the
browser to us with a cross-site POST, or inside a frame, and Frappe's session
cookie is SameSite=Lax: it is not sent on either. The hint is the capability
instead -- minted for one user, at most five minutes old, used once, and only
ever answered to a URL the tool registered. Where a session *is* present it
must be the same user.

Deep Linking returns to ``/lti/deep-link`` the same way: a cross-site POST with
no session, carrying a JWT the tool signed and the `data` token we gave it.
"""

from __future__ import annotations

import hashlib
import html
from urllib.parse import urlencode, urlparse

import frappe
from frappe import _
from frappe.utils import cint, flt
from werkzeug.wrappers import Response

from seminary.lti import (
	AGS_CLAIM,
	AGS_SCOPES,
	CLAIM,
	CONTEXT_SECTION,
	DL_CLAIM,
	LTI_VERSION,
	NRPS_CLAIM,
	ROLE_INSTRUCTOR,
	ROLE_LEARNER,
	ROLE_TA,
	issuer,
	keys,
	url,
)

HINT_TTL = 300
#: An instructor may browse a publisher's catalogue for a while before choosing.
DEEP_LINK_TTL = 3600
ID_TOKEN_TTL = 300
TITLE_MAX = 140


# ---------------------------------------------------------------- identity


def subject(user: str, tool: str) -> str:
	"""The `sub` a tool knows this person by: stable for (person, tool) and
	meaningless anywhere else, so two tools cannot match their records of a
	student by it (the SCORM learner id's rule)."""
	secret = frappe.local.conf.get("encryption_key") or frappe.local.site
	return hashlib.sha256(f"{secret}|lti|{tool}|{user}".encode()).hexdigest()[:32]


def launch_roles(course: str, user: str) -> list[str] | None:
	"""The LTI roles `user` launches with on `course` (§4), or None if they may not launch.

	Students launch as Learner. Staff whose category *Edits course content*
	launch as Instructor; other staff as Instructor and TeachingAssistant.
	Mentors, observers and record-tier readers see the lesson and do not launch.
	"""
	from seminary.seminary import guards

	if guards.is_course_staff(course, include_registrar=True, user=user):
		if guards.may_act(course, guards.CONTENT, include_registrar=True, user=user):
			return [ROLE_INSTRUCTOR]
		return [ROLE_INSTRUCTOR, ROLE_TA]
	if (
		guards.current_student(user)
		and guards.is_published(course)
		and frappe.db.exists(
			"Scheduled Course Roster",
			{"course_sc": course, "stuemail_rc": user, "active": 1},
		)
	):
		return [ROLE_LEARNER]
	return None


def person_claims(tool, user: str) -> dict:
	"""Name and email, each only if the tool is set to receive it (§1)."""
	out = {}
	if not (tool.send_name or tool.send_email):
		return out
	row = frappe.db.get_value("User", user, ["first_name", "last_name", "full_name", "email"], as_dict=True)
	if not row:
		return out
	if tool.send_name:
		out.update(
			{
				"name": row.full_name or "",
				"given_name": row.first_name or "",
				"family_name": row.last_name or "",
			}
		)
	if tool.send_email:
		out["email"] = row.email or ""
	return out


# ---------------------------------------------------------------- hints


def _mint(kind: str, payload: dict, ttl: int) -> str:
	token = frappe.generate_hash(length=40)
	frappe.cache.set_value(f"lti:{kind}:{token}", payload, expires_in_sec=ttl)
	return token


def _consume(kind: str, token: str) -> dict | None:
	if not token or len(token) > 100:
		return None
	key = f"lti:{kind}:{token}"
	payload = frappe.cache.get_value(key)
	if payload:
		frappe.cache.delete_value(key)
	return payload or None


def _enabled_tool(name: str):
	tool = frappe.get_cached_doc("LTI Tool", name) if name and frappe.db.exists("LTI Tool", name) else None
	if not tool or not tool.enabled:
		frappe.throw(_("This tool is not available."), frappe.DoesNotExistError)
	return tool


def _login_url(tool, user: str, target: str, hint: str) -> str:
	params = {
		"iss": issuer(),
		"login_hint": subject(user, tool.name),
		"target_link_uri": target,
		"lti_message_hint": hint,
		"client_id": tool.client_id,
		"lti_deployment_id": tool.deployment_id,
	}
	sep = "&" if "?" in tool.oidc_login_url else "?"
	return f"{tool.oidc_login_url}{sep}{urlencode(params)}"


def lesson_context(lesson: str):
	"""The lesson's LTI fields with its chapter and section, or a refusal that
	does not say whether the lesson exists."""
	row = frappe.db.get_value(
		"Course Lesson",
		lesson,
		[
			"name",
			"lesson_title",
			"chapter",
			"lti_tool",
			"lti_url",
			"lti_custom",
			"lti_resource_link_id",
			"lti_assessment_criteria",
			"lti_score_maximum",
		],
		as_dict=True,
	)
	course = frappe.db.get_value("Course Schedule Chapter", row.chapter, "coursesc") if row else None
	if not course:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	row.course = course
	return row


# ---------------------------------------------------------------- leg 1: the SPA


@frappe.whitelist(methods=["POST"])
def start(lesson: str) -> dict:
	"""Begin a launch of an LTI lesson. Returns the URL to open."""
	from seminary.scorm import limits
	from seminary.seminary import content_release, guards

	limits.enforce("lti_launch", 120, 3600)
	row = lesson_context(lesson)
	guards.require_content_reader(row.course)
	if not row.lti_tool:
		frappe.throw(_("This lesson does not open an external tool."), frappe.DoesNotExistError)
	user = frappe.session.user
	if not launch_roles(row.course, user):
		frappe.throw(
			_("Only the section's students and teaching staff can open this tool."),
			frappe.PermissionError,
		)
	content_release.require_chapter_open(row.course, row.chapter)
	tool = _enabled_tool(row.lti_tool)
	if not row.lti_resource_link_id:
		# A lesson saved before its tool was set through a path that skipped validate.
		row.lti_resource_link_id = frappe.generate_hash(length=20)
		frappe.db.set_value("Course Lesson", row.name, "lti_resource_link_id", row.lti_resource_link_id)
	hint = _mint(
		"hint",
		{"kind": "resource", "user": user, "tool": tool.name, "lesson": row.name, "course": row.course},
		HINT_TTL,
	)
	return {
		"url": _login_url(tool, user, row.lti_url or tool.target_link_url, hint),
		"presentation": "iframe" if tool.launch_presentation == "Embedded" else "window",
		"tool_name": tool.tool_name,
	}


@frappe.whitelist(methods=["POST"])
def start_deep_link(chapter: str, tool: str) -> dict:
	"""Begin choosing content from `tool` for `chapter` (§5)."""
	from seminary.scorm import limits
	from seminary.seminary import guards

	limits.enforce("lti_launch", 120, 3600)
	course = frappe.db.get_value("Course Schedule Chapter", chapter, "coursesc")
	if not course:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	guards.require_section_capability(course, guards.CONTENT, include_registrar=True)
	if frappe.db.get_value("Course Schedule Chapter", chapter, "is_scorm_package"):
		frappe.throw(_("A SCORM chapter's lessons come from its package."))
	doc = _enabled_tool(tool)
	if not (doc.allow_deep_linking and doc.deep_linking_url):
		frappe.throw(_("{0} does not offer content selection.").format(doc.tool_name))
	user = frappe.session.user
	hint = _mint(
		"hint",
		{"kind": "deep_link", "user": user, "tool": doc.name, "chapter": chapter, "course": course},
		HINT_TTL,
	)
	return {"url": _login_url(doc, user, doc.deep_linking_url, hint), "tool_name": doc.tool_name}


@frappe.whitelist()
def tools_for_lessons(course: str) -> list[dict]:
	"""The enabled tools an editor of `course` may put in a lesson or a chapter."""
	from seminary.seminary import guards

	guards.require_section_capability(course, guards.CONTENT, include_registrar=True)
	return frappe.get_all(
		"LTI Tool",
		filters={"enabled": 1},
		fields=["name", "tool_name", "description", "allow_deep_linking", "deep_linking_url"],
		order_by="tool_name asc",
	)


@frappe.whitelist()
def lesson_launch_info(lesson: str) -> dict:
	"""What the lesson page shows around the launch button."""
	from seminary.seminary import guards

	row = lesson_context(lesson)
	guards.require_content_reader(row.course)
	if not row.lti_tool:
		return {"lti": False}
	tool = frappe.db.get_value(
		"LTI Tool", row.lti_tool, ["tool_name", "enabled", "description", "launch_presentation"], as_dict=True
	)
	return {
		"lti": True,
		"tool_name": tool.tool_name if tool else row.lti_tool,
		"available": bool(tool and tool.enabled),
		"description": tool.description if tool else "",
		"presentation": "iframe" if tool and tool.launch_presentation == "Embedded" else "window",
		"may_launch": bool(launch_roles(row.course, frappe.session.user)),
	}


# ---------------------------------------------------------------- leg 3: /lti/auth


def authorize(params: dict) -> Response:
	"""The OIDC authorization endpoint. Answers only to a registered redirect URL."""
	from seminary.scorm import limits

	if limits.exceeded("lti_auth", 600, 3600, who=frappe.local.request_ip or "?"):
		return message_page(_("Too many requests"), _("Try again in a few minutes."), status=429)

	hint = _consume("hint", params.get("lti_message_hint") or "")
	if not hint:
		return message_page(
			_("This launch has expired"),
			_("Go back to the lesson and open the tool again."),
			status=400,
		)
	tool = (
		frappe.get_cached_doc("LTI Tool", hint["tool"])
		if frappe.db.exists("LTI Tool", hint["tool"])
		else None
	)
	redirect_uri = (params.get("redirect_uri") or "").strip()
	if not tool or not tool.enabled or params.get("client_id") != tool.client_id:
		return message_page(_("This tool is not available"), "", status=400)
	if redirect_uri not in tool.redirect_list():
		# Never redirect anywhere the tool did not register: that is the whole
		# protection on where an id_token can go.
		frappe.log_error(
			f"LTI tool {tool.name} asked for unregistered redirect {redirect_uri!r}", "lti: redirect"
		)
		return message_page(
			_("This tool is not set up correctly"),
			_("Ask your school to check its redirect URLs."),
			status=400,
		)

	state = params.get("state") or ""

	def fail(error, description):
		return form_post(redirect_uri, {"error": error, "error_description": description, "state": state})

	if params.get("response_type") != "id_token" or "openid" not in (params.get("scope") or "").split():
		return fail("unsupported_response_type", "response_type must be id_token and scope openid")
	if params.get("response_mode") != "form_post":
		return fail("invalid_request", "response_mode must be form_post")
	if not params.get("nonce"):
		return fail("invalid_request", "nonce is required")
	user = hint["user"]
	if params.get("login_hint") != subject(user, tool.name):
		return fail("login_required", "login_hint does not match this launch")
	session_user = frappe.session.user
	if session_user not in (None, "", "Guest") and session_user != user:
		return fail("login_required", "signed in as someone else")

	roles = launch_roles(hint["course"], user)
	if hint["kind"] == "deep_link":
		from seminary.seminary import guards

		if not guards.may_act(hint["course"], guards.CONTENT, include_registrar=True, user=user):
			return fail("access_denied", "not an editor of this section")
	elif not roles:
		return fail("access_denied", "not a member of this section")

	claims = id_token_claims(tool, hint, roles or [ROLE_INSTRUCTOR], params["nonce"])
	return form_post(redirect_uri, {"id_token": keys.sign(claims), "state": state})


def _context(course: str) -> dict:
	row = frappe.db.get_value(
		"Course Schedule", course, ["name", "title", "coursecode_cs", "course"], as_dict=True
	)
	return {
		"id": course,
		"label": (row.coursecode_cs or row.course or course) if row else course,
		"title": (row.title or row.course or course) if row else course,
		"type": [CONTEXT_SECTION],
	}


def id_token_claims(tool, hint: dict, roles: list[str], nonce: str) -> dict:
	import time

	from seminary.seminary.doctype.lti_tool.lti_tool import parse_custom

	now = int(time.time())
	user = hint["user"]
	course = hint["course"]
	claims = {
		"iss": issuer(),
		"aud": tool.client_id,
		"azp": tool.client_id,
		"sub": subject(user, tool.name),
		"iat": now,
		"exp": now + ID_TOKEN_TTL,
		"nonce": nonce,
		CLAIM + "version": LTI_VERSION,
		CLAIM + "deployment_id": tool.deployment_id,
		CLAIM + "roles": roles,
		CLAIM + "context": _context(course),
		CLAIM + "tool_platform": {
			"guid": hashlib.sha256(issuer().encode()).hexdigest()[:32],
			"name": frappe.db.get_single_value("Website Settings", "app_name") or frappe.local.site,
			"product_family_code": "seminary",
		},
		CLAIM + "launch_presentation": {
			"document_target": "iframe" if tool.launch_presentation == "Embedded" else "window",
			"locale": frappe.local.lang or "en",
		},
		**person_claims(tool, user),
	}
	custom = parse_custom(tool.custom_parameters)

	if hint["kind"] == "deep_link":
		claims[CLAIM + "message_type"] = "LtiDeepLinkingRequest"
		claims[CLAIM + "target_link_uri"] = tool.deep_linking_url
		data = _mint(
			"dl",
			{"user": user, "tool": tool.name, "chapter": hint["chapter"], "course": course},
			DEEP_LINK_TTL,
		)
		claims[DL_CLAIM + "deep_linking_settings"] = {
			"deep_link_return_url": url("deep-link"),
			"accept_types": ["ltiResourceLink"],
			"accept_presentation_document_targets": ["iframe", "window"],
			"accept_multiple": True,
			"auto_create": True,
			"title": frappe.db.get_value("Course Schedule Chapter", hint["chapter"], "chapter_title") or "",
			"data": data,
		}
	else:
		lesson = lesson_context(hint["lesson"])
		custom.update(parse_custom(lesson.lti_custom))
		claims[CLAIM + "message_type"] = "LtiResourceLinkRequest"
		claims[CLAIM + "target_link_uri"] = lesson.lti_url or tool.target_link_url
		claims[CLAIM + "resource_link"] = {
			"id": lesson.lti_resource_link_id,
			"title": lesson.lesson_title or "",
		}
		if tool.allow_grades:
			claims[AGS_CLAIM] = {
				"scope": list(AGS_SCOPES),
				"lineitems": url("ags", course, "lineitems"),
				"lineitem": url("ags", course, "lineitems", lesson.name),
			}

	if tool.allow_names_roles:
		claims[NRPS_CLAIM] = {
			"context_memberships_url": url("nrps", course, "memberships"),
			"service_versions": ["2.0"],
		}
	if custom:
		claims[CLAIM + "custom"] = custom
	return claims


# ---------------------------------------------------------------- deep-link return


def deep_link_return(form: dict) -> Response:
	"""The tool's LtiDeepLinkingResponse: each resource link becomes a lesson (§5)."""
	from seminary.scorm import limits
	from seminary.seminary import guards

	if limits.exceeded("lti_deep_link", 120, 3600, who=frappe.local.request_ip or "?"):
		return message_page(_("Too many requests"), _("Try again in a few minutes."), status=429)

	token = form.get("JWT") or ""
	client_id = keys.unverified_issuer(token)
	tool_name = frappe.db.get_value("LTI Tool", {"client_id": client_id or "-", "enabled": 1}, "name")
	if not tool_name:
		return message_page(
			_("Content was not added"), _("The tool is not registered on this site."), status=400
		)
	tool = frappe.get_cached_doc("LTI Tool", tool_name)
	try:
		claims = keys.verify_tool_jwt(tool, token, audience=issuer())
	except keys.InvalidToolMessage as e:
		frappe.log_error(f"LTI deep-link response from {tool.name} refused: {e}", "lti: deep link")
		return message_page(
			_("Content was not added"), _("The tool's response could not be verified."), status=400
		)

	if (
		claims.get(CLAIM + "message_type") != "LtiDeepLinkingResponse"
		or claims.get(CLAIM + "deployment_id") != tool.deployment_id
	):
		return message_page(
			_("Content was not added"), _("The tool sent the wrong kind of response."), status=400
		)
	if not keys.single_use("dl_nonce", claims.get("nonce") or "", DEEP_LINK_TTL):
		return message_page(_("Content was not added"), _("This response was already used."), status=400)
	data = _consume("dl", claims.get(DL_CLAIM + "data") or "")
	if not data or data.get("tool") != tool.name:
		return message_page(
			_("Content was not added"),
			_("This selection has expired. Choose the content again from the chapter."),
			status=400,
		)
	if not guards.may_act(data["course"], guards.CONTENT, include_registrar=True, user=data["user"]):
		return message_page(_("Content was not added"), _("You can no longer edit this section."), status=403)

	added, skipped = [], 0
	for item in claims.get(DL_CLAIM + "content_items") or []:
		if not isinstance(item, dict) or item.get("type") != "ltiResourceLink":
			skipped += 1
			continue
		added.append(add_lesson(data["chapter"], data["course"], tool, item, data["user"]))

	parts = []
	if added:
		parts.append(_("Added {0} lesson(s) to the chapter.").format(len(added)))
	if skipped:
		parts.append(_("{0} item(s) were not links to the tool and were left out.").format(skipped))
	if claims.get(DL_CLAIM + "msg"):
		parts.append(str(claims[DL_CLAIM + "msg"])[:500])
	if claims.get(DL_CLAIM + "errormsg"):
		parts.append(str(claims[DL_CLAIM + "errormsg"])[:500])
	if not parts:
		parts.append(_("Nothing was chosen."))
	# Opened by script, so the window may close itself; the outline reloads
	# when the editor returns to it.
	script = "setTimeout(function(){window.close()},2500);"
	return message_page(_("Done"), " ".join(parts), script=script)


def _short(text: str | None, fallback: str) -> str:
	text = " ".join(str(text or "").split())
	return (text[: TITLE_MAX - 1] + "…") if len(text) > TITLE_MAX else (text or fallback)


def add_lesson(chapter: str, course: str, tool, item: dict, owner: str) -> str:
	"""One returned resource link as a new lesson at the end of the chapter."""
	from seminary.seminary.lms_migration import html_blocks

	link = (item.get("url") or "").strip()
	if link and urlparse(link).scheme != "https" and not frappe.conf.developer_mode:
		link = ""
	custom = item.get("custom") if isinstance(item.get("custom"), dict) else {}
	line = item.get("lineItem") if isinstance(item.get("lineItem"), dict) else None
	title = _short(item.get("title") or (line or {}).get("label"), tool.tool_name)

	lesson = frappe.new_doc("Course Lesson")
	lesson.owner = owner
	lesson.chapter = chapter
	lesson.course_sc = course
	lesson.lesson_title = title
	lesson.lti_tool = tool.name
	lesson.lti_url = link or None
	lesson.lti_custom = "\n".join(f"{k}={v}" for k, v in custom.items() if "\n" not in f"{k}{v}")
	if item.get("text"):
		text = html.escape(str(item["text"])[:2000])
		lesson.content = html_blocks.content_json([{"type": "paragraph", "data": {"text": text}}])
	if line:
		lesson.lti_score_maximum = flt(line.get("scoreMaximum")) or 100
	lesson.flags.ignore_permissions = True
	lesson.insert(ignore_mandatory=True)

	idx = cint(
		frappe.db.sql(
			"SELECT MAX(idx) FROM `tabCourse Schedule Lesson Reference` WHERE parent = %s",
			chapter,
		)[0][0]
	)
	frappe.get_doc(
		{
			"doctype": "Course Schedule Lesson Reference",
			"parent": chapter,
			"parenttype": "Course Schedule Chapter",
			"parentfield": "lessons",
			"idx": idx + 1,
			"lesson": lesson.name,
		}
	).insert(ignore_permissions=True)

	if line and tool.allow_grades:
		from seminary.lti import grades

		criterion = grades.new_criterion(course, _short(line.get("label") or title, title))
		if criterion:
			frappe.db.set_value("Course Lesson", lesson.name, "lti_assessment_criteria", criterion)
	return lesson.name


# ---------------------------------------------------------------- pages


def _page(
	body: str, status: int = 200, script: str | None = None, form_origin: str | None = None
) -> Response:
	"""A small self-contained page with its own CSP.

	Its own, because the site's policy says `form-action 'self'`, and the one
	thing the authorization page must do is post a form to the tool. The policy
	here names exactly that origin, and nothing else may load."""
	form_action = form_origin or "'none'"
	doc = (
		"<!doctype html><html><head><meta charset='utf-8'>"
		"<meta name='viewport' content='width=device-width,initial-scale=1'>"
		"<meta name='referrer' content='no-referrer'>"
		"<style>body{font:16px/1.5 system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;"
		"color:#1f2937;background:#fff}@media(prefers-color-scheme:dark){body{color:#e5e7eb;background:#111827}}"
		"button{font:inherit;padding:.5rem 1rem}</style></head><body>"
		f"{body}{f'<script>{script}</script>' if script else ''}</body></html>"
	)
	return Response(
		doc,
		status=status,
		content_type="text/html; charset=utf-8",
		headers={
			"Cache-Control": "no-store",
			"X-Content-Type-Options": "nosniff",
			"Content-Security-Policy": (
				"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
				f"form-action {form_action}; frame-ancestors 'self'; base-uri 'none'"
			),
		},
	)


def message_page(title: str, text: str, status: int = 200, script: str | None = None) -> Response:
	return _page(f"<h1>{html.escape(title)}</h1><p>{html.escape(text)}</p>", status=status, script=script)


def form_post(action: str, fields: dict) -> Response:
	"""An auto-submitting form: how OIDC `form_post` delivers the id_token."""
	inputs = "".join(
		f"<input type='hidden' name='{html.escape(k)}' value='{html.escape(str(v), quote=True)}'>"
		for k, v in fields.items()
	)
	body = (
		f"<form method='post' action='{html.escape(action, quote=True)}'>{inputs}"
		f"<noscript><button type='submit'>{html.escape(_('Continue'))}</button></noscript></form>"
	)
	parsed = urlparse(action)
	return _page(body, script="document.forms[0].submit()", form_origin=f"{parsed.scheme}://{parsed.netloc}")
