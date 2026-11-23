# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""WCAG 2.2 A and AA conformance of the portal and the public pages (decision 102).

`check()` signs in as a student, an instructor, a registrar and a partner, visits every
route in docs/accessibility/routes.yaml on the running site, and runs axe-core in the
Chromium Frappe keeps for PDFs. `conformance()` turns that run and the person-kept
docs/accessibility/manual.yaml into docs/accessibility/conformance.json, one row per
success criterion in the four terms of an Accessibility Conformance Report.

axe-core decides only part of WCAG. A criterion supports only when its axe rules pass on
every visited route and its manual row, when it has one, says so (§5).

Another app that draws its own pages runs the same check on them by passing a `Target`:
its own router, portal path, docs/accessibility folder, roles and scope. Every function
here takes `target=None`, which means Seminary's own pages.
"""

import dataclasses
import datetime
import json
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed tools run from argument lists, never a shell
import tempfile

import frappe
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
#: The browser side is shared by every app that runs the check.
RUNNER = os.path.join(ROOT, "scripts", "axe")

TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
STANDARD = "WCAG 2.2 Level AA"
#: Impacts that fail the test (§3). Lesser ones still count against the criterion.
BLOCKING = ("serious", "critical")
#: A manual check older than this counts as not checked (§4).
MANUAL_VALID_DAYS = 365

SUPPORTS = "Supports"
PARTIAL = "Partially Supports"
DOES_NOT = "Does Not Support"
NOT_APPLICABLE = "Not Applicable"
RESULTS = (SUPPORTS, PARTIAL, DOES_NOT, NOT_APPLICABLE)

SCOPE = (
	"The student, instructor, staff and partner portal, the public website pages Seminary renders, "
	"and the PDFs Seminary generates: announcement letters, signed agreements and mailing labels."
)
OUT_OF_SCOPE = (
	"Frappe Desk and its sign-in page; Desk print formats printed through Frappe's print view, "
	"such as the diploma; files and packages schools upload (SCORM, PDF, video) "
	"and the content instructors write; "
	"third-party pages such as payment gateways and meeting providers."
)

#: WCAG 2.2 Level A and AA success criteria: id, name, level, version that added it.
#: 4.1.1 Parsing is left out, as WCAG 2.2 removed it.
CRITERIA = [
	("1.1.1", "Non-text Content", "A", "2.0"),
	("1.2.1", "Audio-only and Video-only (Prerecorded)", "A", "2.0"),
	("1.2.2", "Captions (Prerecorded)", "A", "2.0"),
	("1.2.3", "Audio Description or Media Alternative (Prerecorded)", "A", "2.0"),
	("1.2.4", "Captions (Live)", "AA", "2.0"),
	("1.2.5", "Audio Description (Prerecorded)", "AA", "2.0"),
	("1.3.1", "Info and Relationships", "A", "2.0"),
	("1.3.2", "Meaningful Sequence", "A", "2.0"),
	("1.3.3", "Sensory Characteristics", "A", "2.0"),
	("1.3.4", "Orientation", "AA", "2.1"),
	("1.3.5", "Identify Input Purpose", "AA", "2.1"),
	("1.4.1", "Use of Color", "A", "2.0"),
	("1.4.2", "Audio Control", "A", "2.0"),
	("1.4.3", "Contrast (Minimum)", "AA", "2.0"),
	("1.4.4", "Resize Text", "AA", "2.0"),
	("1.4.5", "Images of Text", "AA", "2.0"),
	("1.4.10", "Reflow", "AA", "2.1"),
	("1.4.11", "Non-text Contrast", "AA", "2.1"),
	("1.4.12", "Text Spacing", "AA", "2.1"),
	("1.4.13", "Content on Hover or Focus", "AA", "2.1"),
	("2.1.1", "Keyboard", "A", "2.0"),
	("2.1.2", "No Keyboard Trap", "A", "2.0"),
	("2.1.4", "Character Key Shortcuts", "A", "2.1"),
	("2.2.1", "Timing Adjustable", "A", "2.0"),
	("2.2.2", "Pause, Stop, Hide", "A", "2.0"),
	("2.3.1", "Three Flashes or Below Threshold", "A", "2.0"),
	("2.4.1", "Bypass Blocks", "A", "2.0"),
	("2.4.2", "Page Titled", "A", "2.0"),
	("2.4.3", "Focus Order", "A", "2.0"),
	("2.4.4", "Link Purpose (In Context)", "A", "2.0"),
	("2.4.5", "Multiple Ways", "AA", "2.0"),
	("2.4.6", "Headings and Labels", "AA", "2.0"),
	("2.4.7", "Focus Visible", "AA", "2.0"),
	("2.4.11", "Focus Not Obscured (Minimum)", "AA", "2.2"),
	("2.5.1", "Pointer Gestures", "A", "2.1"),
	("2.5.2", "Pointer Cancellation", "A", "2.1"),
	("2.5.3", "Label in Name", "A", "2.1"),
	("2.5.4", "Motion Actuation", "A", "2.1"),
	("2.5.7", "Dragging Movements", "AA", "2.2"),
	("2.5.8", "Target Size (Minimum)", "AA", "2.2"),
	("3.1.1", "Language of Page", "A", "2.0"),
	("3.1.2", "Language of Parts", "AA", "2.0"),
	("3.2.1", "On Focus", "A", "2.0"),
	("3.2.2", "On Input", "A", "2.0"),
	("3.2.3", "Consistent Navigation", "AA", "2.0"),
	("3.2.4", "Consistent Identification", "AA", "2.0"),
	("3.2.6", "Consistent Help", "A", "2.2"),
	("3.3.1", "Error Identification", "A", "2.0"),
	("3.3.2", "Labels or Instructions", "A", "2.0"),
	("3.3.3", "Error Suggestion", "AA", "2.0"),
	("3.3.4", "Error Prevention (Legal, Financial, Data)", "AA", "2.0"),
	("3.3.7", "Redundant Entry", "A", "2.2"),
	("3.3.8", "Accessible Authentication (Minimum)", "AA", "2.2"),
	("4.1.2", "Name, Role, Value", "A", "2.0"),
	("4.1.3", "Status Messages", "AA", "2.1"),
]
#: Criteria axe-core decides on its own; every other one needs a manual row.
AUTOMATED = {"3.1.1"}


@dataclasses.dataclass
class Target:
	"""The pages one app draws, and how to visit them."""

	app: str
	product: str
	#: The portal's mount point; routes.yaml paths are relative to it.
	portal_base: str
	#: The router source, relative to the app's repository root.
	router: str
	scope: str
	out_of_scope: str
	#: role -> the sample key holding that role's user.
	role_users: dict
	#: role -> how the report names it ("an Institutional Quality Manager"); default "a <role>".
	role_labels: dict = dataclasses.field(default_factory=dict)
	#: () -> {sample key: value}, the samples the app finds before routes.yaml's own.
	builtin_samples: object = None
	#: (target) -> [path], for a router the default pattern can't read.
	router_paths: object = None
	#: Selectors removed before axe runs.
	remove: tuple = ("style#portal-theme",)
	#: How the report names the signed-out visits.
	guest_label: str = "signed out on the public pages"
	#: Signed-out visits need Seminary's public website on (it is switched on for the run).
	needs_public_website: bool = True
	#: () -> (visits, not visited), for an app that plans its visits itself; default `plan`.
	planner: object = None

	@property
	def root(self):
		return os.path.abspath(frappe.get_app_path(self.app, ".."))

	@property
	def docs(self):
		return os.path.join(self.root, "docs", "accessibility")


def _seminary():
	return Target(
		app="seminary",
		product="Seminary",
		portal_base="/seminary",
		router="frontend/src/router.js",
		scope=SCOPE,
		out_of_scope=OUT_OF_SCOPE,
		role_users=ROLE_USERS,
		builtin_samples=_builtin_samples,
	)


def _target(target):
	return target or _seminary()


def sc_tag(criterion):
	"""axe-core's tag for a success criterion: 1.4.10 -> wcag1410."""
	return "wcag" + criterion.replace(".", "")


def _load(name, target=None):
	# nosemgrep: frappe-security-file-traversal -- a fixed file of the app's docs
	with open(os.path.join(_target(target).docs, name)) as fh:
		return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------- routes


def router_paths(target=None):
	"""Every path the portal router declares, except the catch-all."""
	target = _target(target)
	if target.router_paths:
		return target.router_paths(target)
	# nosemgrep: frappe-security-file-traversal -- the app's own router source
	with open(os.path.join(target.root, target.router)) as fh:
		text = fh.read()
	return [
		p
		for p in re.findall(r"path\s*:\s*['\"]([^'\"]+)['\"]", text)
		if "catchAll" not in p and "pathMatch" not in p
	]


def unlisted_routes(spec=None, target=None):
	"""Router paths routes.yaml doesn't mention (§3)."""
	spec = spec or _load("routes.yaml", target)
	listed = {r["path"] for r in spec.get("portal") or []}
	return [p for p in router_paths(target) if p not in listed]


def _course():
	"""A published Course Schedule with enrolled students, chapters and an instructor."""
	rows = frappe.db.sql(
		"""
		select cs.name, cs.course
		from `tabCourse Schedule` cs
		where cs.published = 1
			and exists (select 1 from `tabCourse Schedule Chapter Reference` c where c.parent = cs.name)
			and exists (select 1 from `tabCourse Enrollment Individual` e
				where e.coursesc_ce = cs.name and e.docstatus = 1 and e.withdrawn = 0)
			and exists (select 1 from `tabCourse Schedule Instructors` i
				join `tabInstructor` ins on ins.name = i.instructor
				join `tabUser` u on u.name = ins.user and u.enabled = 1
				where i.parent = cs.name)
		order by (select count(*) from `tabCourse Schedule Chapter Reference` c where c.parent = cs.name) desc,
			cs.modified desc
		limit 1
		""",
		as_dict=True,
	)
	return rows[0] if rows else None


def _builtin_samples():
	s = {}
	course = _course()
	if course:
		s["course"], s["course_name"] = course.name, course.course
		student = frappe.db.sql(
			"""
			select st.name, st.user from `tabCourse Enrollment Individual` e
			join `tabStudent` st on st.name = e.student_ce
			join `tabUser` u on u.name = st.user and u.enabled = 1
			where e.coursesc_ce = %s and e.docstatus = 1 and e.withdrawn = 0
			order by e.modified desc limit 1
			""",
			course.name,
			as_dict=True,
		)
		if student:
			s["student"], s["student_user"] = student[0].name, student[0].user
		instructor = frappe.db.sql(
			"""
			select ins.name, ins.user from `tabCourse Schedule Instructors` i
			join `tabInstructor` ins on ins.name = i.instructor
			join `tabUser` u on u.name = ins.user and u.enabled = 1
			where i.parent = %s order by i.idx limit 1
			""",
			course.name,
			as_dict=True,
		)
		if instructor:
			s["instructor"], s["instructor_user"] = instructor[0].name, instructor[0].user
	registrar = frappe.db.sql(
		"""
		select u.name from `tabUser` u join `tabHas Role` r on r.parent = u.name and r.parenttype = 'User'
		where r.role = 'Seminary Manager' and u.enabled = 1 and u.user_type = 'System User'
			and u.name not in ('Administrator', 'Guest')
		order by u.name like '%%@example.%%' desc, u.last_active desc limit 1
		"""
	)
	if registrar:
		s["registrar"] = registrar[0][0]
	if frappe.db.table_exists("Partner Contact"):
		partner = frappe.db.sql(
			"""
			select pc.portal_user from `tabPartner Contact` pc
			join `tabUser` u on u.name = pc.portal_user and u.enabled = 1
			where pc.portal_access = 1 order by pc.modified desc limit 1
			"""
		)
		if partner:
			s["partner"] = partner[0][0]
	return s


def samples(spec=None, target=None):
	"""The records the routes open, picked from the site (see routes.yaml)."""
	target = _target(target)
	spec = spec or _load("routes.yaml", target)
	s = target.builtin_samples() if target.builtin_samples else {}
	for key, rule in (spec.get("samples") or {}).items():
		if "value" in rule:
			s[key] = str(rule["value"])
			continue
		if not frappe.db.table_exists(rule["doctype"]):
			continue
		filters, missing = {}, False
		for field, value in (rule.get("filters") or {}).items():
			if isinstance(value, str) and value.startswith("$"):
				if value[1:] not in s:
					missing = True
					break
				value = s[value[1:]]
			filters[field] = value
		if missing:
			continue
		value = frappe.db.get_value(
			rule["doctype"], filters, rule.get("field") or "name", order_by="modified desc"
		)
		if value:
			s[key] = value
	return s


ROLE_USERS = {
	"student": "student_user",
	"instructor": "instructor_user",
	"registrar": "registrar",
	"partner": "partner",
	"alumnus": "alumnus",
}


def plan(spec=None, found=None, target=None):
	"""(visits, not visited): what to open, as whom, and what had no sample."""
	from urllib.parse import quote, urlencode

	target = _target(target)
	spec = spec or _load("routes.yaml", target)
	found = found if found is not None else samples(spec, target)
	visits, missed = [], []
	for route in spec.get("portal") or []:
		if route.get("skip"):
			missed.append({"route": route["path"], "why": route["skip"]})
			continue
		for role in route.get("as") or []:
			# `guest`: a portal page a signed-out visitor opens, e.g. from a link with a token.
			user = None if role == "guest" else found.get(target.role_users[role])
			if role != "guest" and not user:
				missed.append({"route": route["path"], "as": role, "why": f"No {role} on this site."})
				continue
			path, gap = route["path"], None
			for name in re.findall(r":(\w+)\??", path):
				key = (route.get("params") or {}).get(name)
				if key and key in found:
					path = re.sub(rf":{name}\??", quote(str(found[key]), safe=""), path)
				elif f":{name}?" in path:
					path = path.replace(f"/:{name}?", "").replace(f":{name}?", "")
				else:
					gap = key or name
					break
			# A page opened from an emailed link reads its key from the query string.
			query = {name: found.get(key) for name, key in (route.get("query") or {}).items()}
			gap = gap or next((route["query"][n] for n, v in query.items() if v is None), None)
			if query and not gap:
				path += "?" + urlencode(query)
			if gap:
				missed.append({"route": route["path"], "as": role, "why": f"No {gap} on this site."})
				continue
			visits.append({"key": f"{role} {route['path']}", "path": target.portal_base + path, "user": user})
	for path in spec.get("website") or []:
		visits.append({"key": f"guest {path}", "path": path, "user": None})
	return visits, missed


# ---------------------------------------------------------------- running axe


def base_url():
	port = frappe.conf.webserver_port or 8000
	return f"http://{frappe.local.site}:{port}"


def _session(user):
	"""A Sessions row for `user`, without touching the user's login history."""
	from frappe.sessions import hash_sid

	sid = frappe.generate_hash()
	now = frappe.utils.now()
	data = {
		"user": user,
		"session_ip": "127.0.0.1",
		"last_updated": now,
		"creation": now,
		"session_expiry": "01:00:00",
		"full_name": frappe.db.get_value("User", user, "full_name"),
		"user_type": frappe.db.get_value("User", user, "user_type"),
	}
	frappe.db.sql(
		"insert into `tabSessions` (sessiondata, user, lastupdate, sid, status) values (%s, %s, %s, %s, 'Active')",
		(frappe.as_json(data, indent=None, separators=(",", ":")), user, now, hash_sid(sid)),
	)
	frappe.cache.hset("session", hash_sid(sid), frappe._dict(data))
	return sid


def _end_session(sid):
	from frappe.sessions import hash_sid

	frappe.db.sql("delete from `tabSessions` where sid = %s", hash_sid(sid))
	frappe.cache.hdel("session", hash_sid(sid))


def _runner():
	"""The node binary, installing the runner's packages the first time."""
	node = shutil.which("node")
	if not node:
		raise RuntimeError("The accessibility check needs Node.")
	packages = ("axe-core", os.path.join("@guidepup", "virtual-screen-reader"))
	if not all(os.path.isdir(os.path.join(RUNNER, "node_modules", p)) for p in packages):
		yarn = shutil.which("yarn")
		if not yarn:
			raise RuntimeError("The accessibility check needs yarn to install its packages.")
		subprocess.run(  # nosec B603 -- a fixed tool and an argument list, no shell
			[yarn, "install", "--frozen-lockfile", "--silent"], cwd=RUNNER, check=True, timeout=600
		)
	return node


def _cookies(user, sid, base):
	"""The cookies a signed-in browser carries."""
	user_type = frappe.db.get_value("User", user, "user_type")
	return [
		{"name": "sid", "value": sid, "url": base},
		{"name": "user_id", "value": user, "url": base},
		{"name": "system_user", "value": "yes" if user_type == "System User" else "no", "url": base},
	]


def check(visits, base=None, target=None):
	"""Run axe-core on `visits` ({key, path, user}) and return its report.

	A visit may carry `url` instead of `path` for a page outside the site, such as a
	plain host page for an embedded widget, and `steps` to run before axe (see
	scripts/axe/check.mjs), such as submitting an empty form to check its errors.
	"""
	from frappe.utils.print_utils import find_or_download_chromium_executable

	base = base or base_url()
	node = _runner()
	sids, job = {}, {"tags": TAGS, "remove": list(_target(target).remove), "visits": []}
	# The public pages answer 404 while the public website is off; switch it on for
	# the run only, without the side effects of saving Seminary Settings.
	website_off = (
		_target(target).needs_public_website
		and any(not v["user"] for v in visits)
		and not frappe.db.get_single_value("Seminary Settings", "public_website")
	)
	if website_off:
		frappe.db.set_single_value("Seminary Settings", "public_website", 1)
	try:
		for v in visits:
			cookies = []
			if v["user"]:
				if v["user"] not in sids:
					sids[v["user"]] = _session(v["user"])
				cookies = _cookies(v["user"], sids[v["user"]], base)
			url = v.get("url") or base + v["path"]
			row = {"key": v["key"], "url": url, "cookies": cookies, "steps": v.get("steps") or []}
			if v.get("journey"):
				row["journey"] = v["journey"]
			if v.get("keep_theme"):
				row["keep_theme"] = True
			job["visits"].append(row)
		frappe.db.commit()  # nosemgrep -- the browser reads the sessions from another connection
		tmp = tempfile.mkdtemp()
		job_path, out = os.path.join(tmp, "job.json"), os.path.join(tmp, "axe.json")
		# nosemgrep: frappe-security-file-traversal -- a temporary folder of its own
		with open(job_path, "w") as fh:
			json.dump(job, fh)
		env = {**os.environ, "PUPPETEER_EXECUTABLE_PATH": str(find_or_download_chromium_executable())}
		r = subprocess.run(  # nosec B603 -- a fixed tool and an argument list, no shell
			[node, os.path.join(RUNNER, "check.mjs"), job_path, out],
			capture_output=True,
			text=True,
			env=env,
			cwd=RUNNER,
			timeout=3600,
		)
		if not os.path.exists(out):
			raise RuntimeError((r.stderr or r.stdout or "The accessibility check did not run.")[:2000])
		# nosemgrep: frappe-security-file-traversal -- a temporary folder of its own
		with open(out) as fh:
			report = json.load(fh)
		shutil.rmtree(tmp, ignore_errors=True)
		return report
	finally:
		# A long run can outlast the database connection.
		try:
			frappe.db.sql("select 1")
		except Exception:
			frappe.db.connect()
		for sid in sids.values():
			_end_session(sid)
		if website_off:
			frappe.db.set_single_value("Seminary Settings", "public_website", 0)
		frappe.db.commit()  # nosemgrep -- remove the sessions the browser used


def themed(visits=None, target=None):
	"""The visits routes.yaml lists under `themed`, measured again with the school's theme (102b).

	The main run leaves the theme out, since a theme is checked when it is saved; this pass
	catches a colour the theme derives that the save check can't see. Empty when no installed
	app supplies a theme."""
	from seminary.seminary.portal_theme import get_portal_theme

	target = _target(target)
	if not get_portal_theme():
		return []
	if visits is None:
		visits, _missed = target.planner() if target.planner else plan(target=target)
	keys = _load("routes.yaml", target).get("themed") or []
	return [{**v, "key": f"{v['key']}, school theme", "keep_theme": True} for v in visits if v["key"] in keys]


# ---------------------------------------------------------------- screen-reader journeys


def journeys(visits=None, target=None):
	"""(journey visits, not run) from docs/accessibility/journeys.yaml (decision 102a).

	Each journey names a visit from `plan()` by its key ("instructor /courses/:courseName"),
	optional `steps` to run first, and the screen reader's `moves` (see scripts/axe/check.mjs).
	A journey whose visit has no sample on this site is listed as not run."""
	target = _target(target)
	if not os.path.exists(os.path.join(target.docs, "journeys.yaml")):
		return [], []
	if visits is None:
		visits, _missed = target.planner() if target.planner else plan(target=target)
	by_key = {v["key"]: v for v in visits}
	runs, missed = [], []
	for j in _load("journeys.yaml", target) or []:
		visit = by_key.get(j["visit"])
		if not visit:
			missed.append({"journey": j["key"], "why": f"{j['visit']} is not visited on this site."})
			continue
		runs.append(
			{
				**visit,
				"key": f"journey: {j['key']}",
				"steps": j.get("steps") or visit.get("steps") or [],
				"journey": j["moves"],
			}
		)
	return runs, missed


def journey_failures(report):
	"""What each journey didn't hear, or heard and mustn't have."""
	out = []
	for row in report["visits"]:
		if "journey" not in row["key"]:
			continue
		if row.get("error"):
			out.append(f"{row['key']}: {row['error']}")
		for failure in row.get("failures") or []:
			out.append(f"{row['key']}: {failure}")
	return out


def export_journeys(out, target=None, base=None):
	"""Write the journeys, with sessions to sign in with, for the NVDA script (102a §4).

	    bench --site <site> execute seminary.seminary.accessibility.export_journeys \
	        --kwargs "{'out': '/path/journeys.json'}"

	`target` may be a dotted path to another app's target function. The sessions last an hour;
	end them sooner with `end_exported_sessions`."""
	if isinstance(target, str):
		target = frappe.get_attr(target)()
	base = base or base_url()
	runs, missed = journeys(target=target)
	sids = {}
	rows = []
	for run in runs:
		cookies = []
		if run["user"]:
			if run["user"] not in sids:
				sids[run["user"]] = _session(run["user"])
			cookies = _cookies(run["user"], sids[run["user"]], base)
		rows.append(
			{
				"key": run["key"],
				"url": run.get("url") or base + run["path"],
				"cookies": cookies,
				"steps": run["steps"],
				"moves": run["journey"],
			}
		)
	frappe.db.commit()  # nosemgrep -- the Windows browser reads the sessions from another connection
	# nosemgrep: frappe-security-file-traversal -- a path the person running it chose
	with open(out, "w") as fh:
		json.dump(
			{"base": base, "sessions": list(sids.values()), "journeys": rows, "not_run": missed}, fh, indent=1
		)
	return out


def end_exported_sessions(path):
	"""End the sessions `export_journeys` wrote to `path`."""
	# nosemgrep: frappe-security-file-traversal -- a path the person running it chose
	with open(path) as fh:
		for sid in json.load(fh).get("sessions") or []:
			_end_session(sid)
	frappe.db.commit()  # nosemgrep -- the sessions are gone for every connection


def blocking(report):
	"""Lines naming each serious or critical violation, for a test message."""
	lines = []
	for v in report.get("visits", []):
		if v.get("error"):
			lines.append(f"{v['key']}: {v['error']}")
		for x in v.get("violations", []):
			if x["impact"] in BLOCKING:
				eg = "; ".join(n["target"] for n in x["nodes"][:2])
				lines.append(f"{v['key']}: {x['id']} ({x['impact']}, {x['count']}) {x['help']} e.g. {eg}")
	return lines


# ---------------------------------------------------------------- the conformance file


def _manual_rows(target=None):
	rows = _load("manual.yaml", target)
	return {str(r["id"]): r for r in rows or []}


def _fresh(row, today):
	when = row.get("checked_on")
	if not when or row.get("result") not in RESULTS:
		return False
	if isinstance(when, str):
		when = datetime.date.fromisoformat(when)
	return (today - when).days <= MANUAL_VALID_DAYS


def conformance(report, missed=(), today=None, version=None, commit=None, target=None):
	"""The conformance file (docs/accessibility/README.md) from a run and manual.yaml."""
	target = _target(target)
	today = today or datetime.date.today()
	manual = _manual_rows(target)
	visits = [v for v in report.get("visits", []) if not v.get("error")]
	rule_tags = {rid: set(r["tags"]) for rid, r in (report.get("rules") or {}).items()}
	rows = []
	for cid, name, level, since in CRITERIA:
		rules = sorted(rid for rid, tags in rule_tags.items() if sc_tag(cid) in tags)
		failed = {}
		passed_on = 0
		for v in visits:
			bad = [x for x in v.get("violations", []) if x["id"] in rules]
			for x in bad:
				failed.setdefault(x["id"], []).append(v["key"])
			if not bad and any(r in v.get("passes", []) for r in rules):
				passed_on += 1
		evidence, remarks = [], []
		if rules:
			evidence.append(
				f"axe: {', '.join(rules)} on {len(visits)} pages"
				+ (f", passing on {passed_on}" if passed_on else ", none applied")
			)
		for rid, keys in sorted(failed.items()):
			remarks.append(f"{rid} fails on {len(keys)} of {len(visits)} pages, e.g. {keys[0]}.")
		row = manual.get(cid)
		automated_only = cid in AUTOMATED and not row
		if row:
			if _fresh(row, today):
				evidence.append(
					f"manual: {row['result']}, checked {row['checked_on']} by {row.get('checked_by') or '?'}"
				)
			else:
				evidence.append("manual: not checked in the last 12 months")
			if row.get("remarks"):
				remarks.append(str(row["remarks"]).strip())
		if row and _fresh(row, today) and row["result"] in (DOES_NOT, NOT_APPLICABLE):
			result = row["result"]
		elif failed:
			result = PARTIAL
		elif automated_only and rules:
			result = SUPPORTS
		elif row and _fresh(row, today):
			result = row["result"]
		else:
			result = PARTIAL
		rows.append(
			{
				"id": cid,
				"name": name,
				"level": level,
				"since": since,
				"result": result,
				"remarks": " ".join(remarks),
				"evidence": "; ".join(evidence),
			}
		)
	axe_version = next((v.get("axe_version") for v in report.get("visits", []) if v.get("axe_version")), "")
	return {
		"format": 1,
		"product": target.product,
		"version": version or _version(target),
		"commit": commit or _commit(target),
		"date": today.isoformat(),
		"standard": STANDARD,
		"scope": target.scope,
		"out_of_scope": target.out_of_scope,
		"evaluation_methods": (
			f"axe-core {axe_version} in Chromium on {len(visits)} pages, {_roles(visits, target)}; "
			"manual review of the criteria axe-core can't decide."
		),
		"not_visited": list(missed),
		"criteria": rows,
	}


def _article(role):
	return f"an {role}" if role[0].lower() in "aeiou" else f"a {role}"


def _roles(visits, target=None):
	"""'signed in as a student and an instructor, and signed out' from the visit keys."""
	target = _target(target)
	seen = {v["key"].split(" ", 1)[0] for v in visits}
	signed_in = [target.role_labels.get(r) or _article(r) for r in target.role_users if r in seen]
	parts = []
	if signed_in:
		names = signed_in[0] if len(signed_in) == 1 else ", ".join(signed_in[:-1]) + " and " + signed_in[-1]
		parts.append("signed in as " + names)
	if "guest" in seen:
		parts.append(target.guest_label)
	return ", and ".join(parts) or "no pages visited"


def _version(target=None):
	return frappe.get_attr(_target(target).app + ".__version__")


def _commit(target=None):
	git = shutil.which("git")
	if not git:
		return ""
	r = subprocess.run(  # nosec B603 B607 -- a fixed tool and an argument list, no shell
		[git, "rev-parse", "HEAD"], cwd=_target(target).root, capture_output=True, text=True, timeout=30
	)
	return r.stdout.strip()


def write_conformance(report=None, missed=None, target=None):
	"""Run the check if needed and write docs/accessibility/conformance.json.

	bench --site <site> execute seminary.seminary.accessibility.write_conformance
	"""
	if report is None:
		visits, missed = plan(target=target)
		report = check(visits, target=target)
	data = conformance(report, missed or [], target=target)
	path = os.path.join(_target(target).docs, "conformance.json")
	# nosemgrep: frappe-security-file-traversal -- the app's docs/accessibility/conformance.json
	with open(path, "w") as fh:
		json.dump(data, fh, indent=1, ensure_ascii=False)
		fh.write("\n")
	return path
