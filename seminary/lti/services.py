"""The token endpoint and the LTI Advantage services (decisions/110 §6-8).

    POST /lti/token
    GET  /lti/ags/<section>/lineitems
    GET  /lti/ags/<section>/lineitems/<lesson>
    POST /lti/ags/<section>/lineitems/<lesson>/scores
    GET  /lti/ags/<section>/lineitems/<lesson>/results
    GET  /lti/nrps/<section>/memberships

Every service call carries a bearer token from ``/lti/token``. A token is for
one tool and the scopes it was granted, and it reaches **only the sections that
have a lesson opening that tool** -- a tool registered for one course cannot read
another's class list.

**The bearer header is taken before Frappe sees it.** Frappe reads every
`Authorization: Bearer` header as one of its own OAuth tokens, and a request
whose token it does not know is refused as a failed login before any route
runs. ``take_bearer`` is a `before_request` hook that moves our header aside for
``/lti/`` paths only. No user is signed in for these requests; every check here
is on the token.
"""

from __future__ import annotations

import json
import time
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import flt, get_datetime, get_system_timezone
from werkzeug.wrappers import Response

from seminary.lti import (
	AGS_SCOPES,
	ROLE_LEARNER,
	SCOPE_LINEITEM_READ,
	SCOPE_NRPS,
	SCOPE_RESULT_READ,
	SCOPE_SCORE,
	issuer,
	keys,
	url,
)

TOKEN_TTL = 3600
TOKEN_TYPE = "Bearer"  # nosec B105 -- the OAuth token type, not a secret
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
MT_LINEITEM = "application/vnd.ims.lis.v2.lineitem+json"
MT_LINEITEMS = "application/vnd.ims.lis.v2.lineitemcontainer+json"
MT_RESULTS = "application/vnd.ims.lis.v2.resultcontainer+json"
MT_SCORE = "application/vnd.ims.lis.v1.score+json"
MT_MEMBERS = "application/vnd.ims.lti-nrps.v2.membershipcontainer+json"
ACTIVITY = {"Initialized", "Started", "InProgress", "Submitted", "Completed"}
GRADING = {"FullyGraded", "Pending", "PendingManual", "Failed", "NotReady"}


def take_bearer():
	"""`before_request`: lift an `/lti/` request's bearer token out of Frappe's way."""
	request = getattr(frappe.local, "request", None)
	if not request or not request.path.startswith("/lti/"):
		return
	header = request.environ.get("HTTP_AUTHORIZATION") or ""
	if header[:7].lower() == "bearer ":
		frappe.local.lti_bearer = header[7:].strip()
		request.environ.pop("HTTP_AUTHORIZATION", None)


def json_response(data, status: int = 200, content_type: str = "application/json") -> Response:
	return Response(
		json.dumps(data),
		status=status,
		content_type=content_type,
		headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
	)


def oauth_error(error: str, description: str = "", status: int = 400) -> Response:
	return json_response({"error": error, "error_description": description}, status=status)


# ---------------------------------------------------------------- /lti/token


def token(form: dict) -> Response:
	"""Client credentials, authenticated by a JWT the tool signed (`private_key_jwt`)."""
	from seminary.scorm import limits

	if limits.exceeded("lti_token", 600, 3600, who=frappe.local.request_ip or "?"):
		return oauth_error("slow_down", "too many token requests", status=429)
	if form.get("grant_type") != "client_credentials":
		return oauth_error("unsupported_grant_type")
	if form.get("client_assertion_type") != ASSERTION_TYPE:
		return oauth_error("invalid_client", "client_assertion_type must be jwt-bearer", status=401)
	assertion = form.get("client_assertion") or ""
	client_id = keys.unverified_issuer(assertion)
	name = frappe.db.get_value("LTI Tool", {"client_id": client_id or "-", "enabled": 1}, "name")
	if not name:
		return oauth_error("invalid_client", "unknown client", status=401)
	tool = frappe.get_cached_doc("LTI Tool", name)
	try:
		claims = keys.verify_tool_jwt(tool, assertion, audience=[url("token"), issuer()])
	except keys.InvalidToolMessage as e:
		frappe.log_error(f"LTI client assertion from {tool.name} refused: {e}", "lti: token")
		return oauth_error("invalid_client", "the client assertion does not verify", status=401)
	if claims.get("sub") != tool.client_id:
		return oauth_error("invalid_client", "sub must be the client id", status=401)
	ttl = max(60, int(claims.get("exp", 0)) - int(time.time()) + keys.LEEWAY)
	if not keys.single_use("jti", f"{tool.name}:{claims.get('jti') or ''}", ttl):
		return oauth_error("invalid_client", "jti is missing or was already used", status=401)

	allowed = set()
	if tool.allow_grades:
		allowed.update(AGS_SCOPES)
	if tool.allow_names_roles:
		allowed.add(SCOPE_NRPS)
	requested = set((form.get("scope") or "").split())
	granted = sorted(requested & allowed)
	if not granted:
		return oauth_error("invalid_scope", "none of the requested scopes is granted to this tool")

	access = frappe.generate_hash(length=48)
	frappe.cache.set_value(
		f"lti:access:{access}", {"tool": tool.name, "scopes": granted}, expires_in_sec=TOKEN_TTL
	)
	return json_response(
		{
			"access_token": access,
			"token_type": TOKEN_TYPE,
			"expires_in": TOKEN_TTL,
			"scope": " ".join(granted),
		}
	)


# ---------------------------------------------------------------- bearer checks


class Refused(Exception):
	def __init__(self, status: int, error: str, description: str = ""):
		super().__init__(description or error)
		self.response = oauth_error(error, description, status=status)


def _grant(scope: str) -> dict:
	access = getattr(frappe.local, "lti_bearer", None)
	grant = frappe.cache.get_value(f"lti:access:{access}") if access else None
	if not grant:
		raise Refused(401, "invalid_token", "a valid bearer token is required")
	if scope not in grant["scopes"]:
		raise Refused(403, "insufficient_scope", scope)
	return grant


def _tool_lessons(course: str, tool: str) -> list[str]:
	return frappe.db.sql_list(
		"""
		SELECT l.name FROM `tabCourse Lesson` l
		JOIN `tabCourse Schedule Chapter` c ON c.name = l.chapter
		WHERE c.coursesc = %s AND l.lti_tool = %s
		ORDER BY c.creation, l.creation
		""",
		(course, tool),
	)


def _section(course: str, tool: str) -> list[str]:
	"""The tool's lessons on `course`, refusing a section the tool is not in.

	A section the tool is not in and one that does not exist answer alike."""
	lessons = _tool_lessons(course, tool) if course else []
	if not lessons:
		raise Refused(404, "not_found", "no such context for this tool")
	return lessons


def _iso(value) -> str | None:
	if not value:
		return None
	return get_datetime(value).replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


# ---------------------------------------------------------------- Assignment and Grade Services


def _line_item(course: str, lesson: str) -> dict:
	row = frappe.db.get_value(
		"Course Lesson",
		lesson,
		["lesson_title", "lti_resource_link_id", "lti_assessment_criteria", "lti_score_maximum"],
		as_dict=True,
	)
	item = {
		"id": url("ags", course, "lineitems", lesson),
		"label": row.lesson_title or lesson,
		"scoreMaximum": flt(row.lti_score_maximum) or 100,
		"resourceLinkId": row.lti_resource_link_id or "",
	}
	if row.lti_assessment_criteria:
		crit = frappe.db.get_value(
			"Scheduled Course Assess Criteria",
			row.lti_assessment_criteria,
			["title", "due_date"],
			as_dict=True,
		)
		if crit:
			item["label"] = crit.title or item["label"]
			if crit.due_date:
				item["endDateTime"] = _iso(crit.due_date)
	return item


def line_items(course: str, args: dict) -> Response:
	grant = _grant(SCOPE_LINEITEM_READ)
	items = [_line_item(course, lesson) for lesson in _section(course, grant["tool"])]
	if args.get("resource_link_id"):
		items = [i for i in items if i["resourceLinkId"] == args["resource_link_id"]]
	if args.get("resource_id") or args.get("tag"):
		# We keep no resourceId or tag: a filter on either matches nothing.
		items = []
	return json_response(items, content_type=MT_LINEITEMS)


def _lesson_in(course: str, lesson: str, tool: str) -> str:
	if lesson not in _section(course, tool):
		raise Refused(404, "not_found", "no such line item")
	return lesson


def line_item(course: str, lesson: str) -> Response:
	grant = _grant(SCOPE_LINEITEM_READ)
	return json_response(
		_line_item(course, _lesson_in(course, lesson, grant["tool"])), content_type=MT_LINEITEM
	)


def _members_by_subject(course: str, tool: str) -> dict:
	from seminary.lti.launch import subject

	out = {}
	for row in frappe.get_all(
		"Scheduled Course Roster",
		filters={"course_sc": course, "active": 1},
		fields=["name", "stuemail_rc"],
	):
		if row.stuemail_rc:
			out[subject(row.stuemail_rc, tool)] = row
	return out


def score(course: str, lesson: str, body: bytes, content_type: str) -> Response:
	"""Keep the score; write it to the gradebook if the rules allow (`grades.push`)."""
	from seminary.lti import grades

	grant = _grant(SCOPE_SCORE)
	lesson = _lesson_in(course, lesson, grant["tool"])
	if "json" not in (content_type or ""):
		raise Refused(415, "unsupported_media_type", MT_SCORE)
	try:
		data = json.loads(body or b"{}")
	except ValueError:
		raise Refused(400, "invalid_request", "the body is not JSON") from None
	if not isinstance(data, dict):
		raise Refused(400, "invalid_request", "the body is not a score")

	member = _members_by_subject(course, grant["tool"]).get(str(data.get("userId") or ""))
	if not member:
		raise Refused(422, "invalid_request", "userId is not an active student of this section")
	activity, grading = data.get("activityProgress"), data.get("gradingProgress")
	if activity not in ACTIVITY or grading not in GRADING:
		raise Refused(400, "invalid_request", "activityProgress and gradingProgress are required")
	if not data.get("timestamp"):
		raise Refused(400, "invalid_request", "timestamp is required")
	given = data.get("scoreGiven")
	if given is not None:
		try:
			given = float(given)
			top = float(data.get("scoreMaximum"))
		except (TypeError, ValueError):
			raise Refused(400, "invalid_request", "scoreGiven needs a numeric scoreMaximum") from None
		if given < 0 or top <= 0:
			raise Refused(400, "invalid_request", "scores must be non-negative and scoreMaximum positive")
	else:
		top = data.get("scoreMaximum")

	latest = frappe.get_all(
		"LTI Score",
		filters={"lesson": lesson, "member": member.stuemail_rc},
		fields=["tool_timestamp"],
		order_by="creation desc",
		limit=1,
	)
	stamp = str(data["timestamp"])[:64]
	if latest and _older(stamp, latest[0].tool_timestamp):
		# The spec: a score older than the one already held changes nothing.
		return Response(status=204)

	doc = frappe.get_doc(
		{
			"doctype": "LTI Score",
			"lesson": lesson,
			"course": course,
			"tool": grant["tool"],
			"member": member.stuemail_rc,
			"roster": member.name,
			"score_given": given,
			"score_maximum": flt(top) if top is not None else None,
			"has_score": 1 if given is not None else 0,
			"percentage": grades.percentage(given, top) if given is not None else None,
			"activity_progress": activity,
			"grading_progress": grading,
			"tool_timestamp": stamp,
			"comment": str(data.get("comment") or "")[:2000],
		}
	)
	doc.insert(ignore_permissions=True)
	result = grades.push(doc)
	doc.db_set(
		{
			"reported": 1 if result.get("reported") else 0,
			"report_reason": result.get("reason") or "",
			# Float columns are NOT NULL; `reported` says whether this is real.
			"pushed_score": result.get("percentage") or 0,
		},
		update_modified=False,
	)
	return Response(status=204)


def _older(stamp: str, held: str | None) -> bool:
	if not held:
		return False
	try:
		return get_datetime(stamp.replace("Z", "+00:00")) < get_datetime(held.replace("Z", "+00:00"))
	except Exception:
		return False


def results(course: str, lesson: str, args: dict) -> Response:
	from seminary.lti.launch import subject

	grant = _grant(SCOPE_RESULT_READ)
	lesson = _lesson_in(course, lesson, grant["tool"])
	latest = {}
	for row in frappe.get_all(
		"LTI Score",
		filters={"lesson": lesson},
		fields=["name", "member", "score_given", "score_maximum", "has_score", "comment"],
		order_by="creation asc",
	):
		latest[row.member] = row
	out = []
	for member, row in latest.items():
		user_id = subject(member, grant["tool"])
		if args.get("user_id") and args["user_id"] != user_id:
			continue
		entry = {
			"id": url("ags", course, "lineitems", lesson, "results", row.name),
			"scoreOf": url("ags", course, "lineitems", lesson),
			"userId": user_id,
		}
		if row.has_score:
			entry.update({"resultScore": row.score_given, "resultMaximum": row.score_maximum})
		if row.comment:
			entry["comment"] = row.comment
		out.append(entry)
	return json_response(out, content_type=MT_RESULTS)


# ---------------------------------------------------------------- Names and Roles


def memberships(course: str, args: dict) -> Response:
	from seminary.lti.launch import _context, launch_roles, subject

	grant = _grant(SCOPE_NRPS)
	_section(course, grant["tool"])
	tool = frappe.get_cached_doc("LTI Tool", grant["tool"])

	users = {}
	for row in frappe.get_all(
		"Scheduled Course Roster", filters={"course_sc": course, "active": 1}, pluck="stuemail_rc"
	):
		if row:
			users[row] = [ROLE_LEARNER]
	for row in frappe.get_all(
		"Course Schedule Instructors",
		filters={"parent": course, "parenttype": "Course Schedule"},
		fields=["instructor", "user"],
	):
		user = row.user or frappe.db.get_value("Instructor", row.instructor, "user")
		if user and user not in users:
			roles = launch_roles(course, user)
			if roles:
				users[user] = roles

	people = {}
	if tool.send_name or tool.send_email:
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", list(users) or ["-"]]},
			fields=["name", "first_name", "last_name", "full_name", "email"],
		):
			people[row.name] = row

	members = []
	for user, roles in users.items():
		member = {"status": "Active", "user_id": subject(user, tool.name), "roles": roles}
		person = people.get(user)
		if person and tool.send_name:
			member.update(
				{
					"name": person.full_name or "",
					"given_name": person.first_name or "",
					"family_name": person.last_name or "",
				}
			)
		if person and tool.send_email:
			member["email"] = person.email or ""
		members.append(member)
	if args.get("role"):
		members = [m for m in members if args["role"] in m["roles"]]
	return json_response(
		{"id": url("nrps", course, "memberships"), "context": _context(course), "members": members},
		content_type=MT_MEMBERS,
	)
