# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""School meeting accounts (decisions/051a).

A section, or one meeting row, sets ``school_meeting``; Seminary then picks a
Web Meeting Account free for the meeting's window (an account is a room, 051a
§4), and after the save commits a background job asks the provider to create,
update or delete the meeting. Seminary holds no credentials: an installed app
provides each provider through the ``meeting_providers`` hook,
``{provider: "dotted.path.to.Class"}``, whose instances have

- ``create(account, meeting) -> {"join_url", "meeting_id", "host_key", "alternative_hosts"}``
- ``update(account, meeting_id, meeting) -> dict | None`` (same keys, all optional)
- ``delete(account, meeting_id)``

``account`` is ``{"name", "provider", "host_id"}``; ``meeting`` is ``{"topic",
"date", "from_time", "to_time", "start", "duration", "timezone",
"alternative_hosts"}``. A provider raises on failure; the row then shows the
error and keeps its previous link (051a §5).
"""

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, get_system_timezone, get_time, getdate

ROW = "Course Schedule Meeting Dates"
HOOK = "meeting_providers"
ACCOUNT = "Web Meeting Account"
_CLEAR = {
	"cs_meeting_account": None,
	"cs_meeting_id": None,
	"cs_meeting_status": None,
	"cs_meeting_error": None,
	"cs_meeting_hosts": None,
	"cs_host_key": None,
}


def providers() -> dict[str, str]:
	"""{provider: dotted path} from the ``meeting_providers`` hook; the last app wins."""
	provided = {}
	for name, paths in dict(frappe.get_hooks(HOOK) or {}).items():
		path = paths[-1] if isinstance(paths, list) else paths
		if path:
			provided[name] = path
	return provided


@frappe.whitelist()
def provider_names() -> list[str]:
	"""For the Web Meeting Account form's Provider choices."""
	frappe.has_permission(ACCOUNT, "read", throw=True)
	return sorted(providers())


def connector(provider):
	path = providers().get(provider)
	if not path:
		frappe.throw(_("No installed app offers meetings on {0}.").format(provider))
	return frappe.get_attr(path)()


def is_managed(cs, row) -> bool:
	"""A school meeting: the row asks for one, or the section does and the row is online."""
	if cint(row.get("school_meeting")):
		return True
	if not cint(cs.get("school_meeting")):
		return False
	return bool(cint(row.get("cs_online")) or cs.get("modality") == "Virtual")


# --- On save: pick accounts ----------------------------------------------------


def validate(cs):
	"""Course Schedule validate: give each school meeting a free account, or refuse."""
	rows = [r for r in cs.cs_meetinfo or [] if r.cs_meetdate]
	managed = [r for r in rows if is_managed(cs, r)]
	for row in rows:
		if row not in managed and row.cs_meeting_account:
			# No longer a school meeting: the provider's meeting goes (on_update).
			row.update(_CLEAR)
			row.cs_web_meeting = None
	if not managed:
		return
	for row in managed:
		row.cs_online = 1
		if not (row.cs_fromtime and row.cs_totime):
			frappe.throw(
				_("The school meeting on {0} needs a From and To time.").format(
					frappe.format(row.cs_meetdate, "Date")
				)
			)
	accounts = frappe.get_all(
		ACCOUNT,
		filters={"enabled": 1, "provider": ["in", list(providers()) or [""]]},
		fields=["name", "max_concurrent"],
		order_by="name asc",
	)
	if not accounts:
		frappe.throw(
			_(
				"There is no enabled school meeting account. Add one under Web Meeting "
				"Account, or turn School Meetings off and paste a link."
			)
		)
	limit = {a.name: max(1, cint(a.max_concurrent)) for a in accounts}
	others = _others_booked(cs, managed, list(limit))
	taken = []  # (account, row) assigned in this save
	for row in managed:
		busy = {}
		clashes = []
		for o in others:
			if str(o.cs_meetdate) == str(row.cs_meetdate) and _overlap(row, o):
				busy[o.cs_meeting_account] = busy.get(o.cs_meeting_account, 0) + 1
				clashes.append(o)
		for account, other in taken:
			if str(other.cs_meetdate) == str(row.cs_meetdate) and _overlap(row, other):
				busy[account] = busy.get(account, 0) + 1
		order = sorted(limit, key=lambda a: (a != row.cs_meeting_account, a))
		free = next((a for a in order if busy.get(a, 0) < limit[a]), None)
		if not free:
			names = sorted({o.title or o.parent for o in clashes})
			frappe.throw(
				_(
					"No school meeting account is free on {0} from {1} to {2}: they are "
					"in use by {3}. Add an account, or move this meeting."
				).format(
					frappe.format(row.cs_meetdate, "Date"),
					_hm(row.cs_fromtime),
					_hm(row.cs_totime),
					", ".join(names) or _("this section"),
				),
				title=_("School meeting clash"),
			)
		if row.cs_meeting_account and free != row.cs_meeting_account:
			# A new account means a new meeting there; the old one is deleted.
			row.update(_CLEAR)
		row.cs_meeting_account = free
		taken.append((free, row))


def _others_booked(cs, rows, accounts):
	booked = _class_booked(cs, rows, accounts)
	# Group meetings of oral activities hold accounts too (100d-a §4).
	for m in frappe.get_all(
		"Oral Activity Meeting",
		filters={
			"kind": "Group",
			"status": ["not in", ["Cancelled", "Failed"]],
			"meeting_account": ["in", list(accounts)],
			"meeting_date": ["in", list({str(r.cs_meetdate) for r in rows})],
		},
		fields=[
			"course_schedule",
			"group_label",
			"meeting_date",
			"from_time",
			"to_time",
			"meeting_account",
		],
	):
		booked.append(
			frappe._dict(
				parent=m.course_schedule,
				title=_("{0}, group meeting {1}").format(m.course_schedule, m.group_label or ""),
				cs_meetdate=m.meeting_date,
				cs_fromtime=m.from_time,
				cs_totime=m.to_time,
				cs_meeting_account=m.meeting_account,
			)
		)
	# So do cohort meetings on a school account (decisions/101 section 4.4).
	from seminary.seminary.discipleship.meetings import class_rows

	booked.extend(class_rows(accounts, {str(r.cs_meetdate) for r in rows}))
	return booked


def _class_booked(cs, rows, accounts):
	return frappe.db.sql(
		"""
        SELECT m.parent, cs.title, m.cs_meetdate, m.cs_fromtime, m.cs_totime,
               m.cs_meeting_account
        FROM `tabCourse Schedule Meeting Dates` m
        JOIN `tabCourse Schedule` cs ON m.parent = cs.name
        WHERE m.parenttype = 'Course Schedule'
          AND m.parent != %(cs)s
          AND COALESCE(cs.workflow_state, '') != 'Cancelled'
          AND m.cs_meeting_account IN %(accounts)s
          AND m.cs_meetdate IN %(dates)s
        """,
		{
			"cs": cs.name or "",
			"accounts": tuple(accounts),
			"dates": tuple({str(r.cs_meetdate) for r in rows}),
		},
		as_dict=True,
	)


def _overlap(a, b):
	from seminary.seminary.utils import times_overlap

	return times_overlap(a.cs_fromtime, a.cs_totime, b.cs_fromtime, b.cs_totime)


def _hm(value):
	return get_time(value).strftime("%H:%M") if value else ""


# --- After save: ask the provider ---------------------------------------------


def on_update(cs):
	"""Course Schedule on_update: queue the provider calls this save needs."""
	before = cs.get_doc_before_save()
	old = {}
	for r in (before.cs_meetinfo if before else []) or []:
		if r.cs_meeting_account and r.cs_meeting_id:
			old[r.name] = r
	now_ids = {(r.cs_meeting_account, r.cs_meeting_id) for r in cs.cs_meetinfo or [] if r.cs_meeting_id}
	deletes = [
		(r.cs_meeting_account, r.cs_meeting_id)
		for r in old.values()
		if (r.cs_meeting_account, r.cs_meeting_id) not in now_ids
	]
	sync = []
	for row in cs.cs_meetinfo or []:
		if not row.cs_meeting_account:
			continue
		prev = old.get(row.name)
		if (
			not row.cs_meeting_id
			or row.cs_meeting_status in ("Pending", "Failed")
			or not prev
			or _changed(prev, row)
			or (before and before.title != cs.title)
		):
			sync.append(row.name)
	if not (deletes or sync):
		return
	if sync:
		frappe.db.set_value(
			ROW,
			{"name": ["in", sync]},
			"cs_meeting_status",
			"Pending",
			update_modified=False,
		)
	_enqueue(cs.name, deletes, sync)


def _changed(prev, row):
	return (
		getdate(prev.cs_meetdate) != getdate(row.cs_meetdate)
		or _hm(prev.cs_fromtime) != _hm(row.cs_fromtime)
		or _hm(prev.cs_totime) != _hm(row.cs_totime)
	)


def on_section_gone(cs):
	"""A cancelled or deleted section: every meeting it holds is deleted."""
	rows = [r for r in cs.cs_meetinfo or [] if r.cs_meeting_account and r.cs_meeting_id]
	if not rows:
		return
	deletes = [(r.cs_meeting_account, r.cs_meeting_id) for r in rows]
	for r in rows:
		frappe.db.set_value(ROW, r.name, _CLEAR, update_modified=False)
	_enqueue(cs.name, deletes, [])


def _enqueue(cs_name, deletes, sync):
	frappe.enqueue(
		"seminary.seminary.school_meetings.run_sync",
		queue="short",
		enqueue_after_commit=True,
		now=bool(frappe.flags.in_test),
		cs_name=cs_name,
		deletes=deletes,
		sync=sync,
	)


def run_sync(cs_name, deletes=None, sync=None):
	"""The background job: delete what went, create or update what stays."""
	for account, meeting_id in deletes or []:
		try:
			acc = _account(account)
			if acc:
				connector(acc["provider"]).delete(acc, meeting_id)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"School meeting delete failed: {account} {meeting_id}",
			)
	if not sync:
		return
	cs = frappe.get_doc("Course Schedule", cs_name)
	rows = {r.name: r for r in cs.cs_meetinfo or []}
	hosts = _instructor_emails(cs_name)
	for name in sync:
		row = rows.get(name)
		if not row or not row.cs_meeting_account or not is_managed(cs, row):
			continue
		_sync_row(cs, row, hosts)


def _sync_row(cs, row, hosts):
	acc = _account(row.cs_meeting_account)
	try:
		if not acc:
			frappe.throw(_("The meeting account is gone or disabled."))
		meeting = _meeting(cs, row, hosts)
		provider = connector(acc["provider"])
		if row.cs_meeting_id:
			out = provider.update(acc, row.cs_meeting_id, meeting) or {}
		else:
			out = provider.create(acc, meeting) or {}
			if not (out.get("join_url") and out.get("meeting_id")):
				frappe.throw(_("The provider returned no meeting."))
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"School meeting failed: {cs.name} {row.name}")
		frappe.db.set_value(
			ROW,
			row.name,
			{"cs_meeting_status": "Failed", "cs_meeting_error": _message(e)},
			update_modified=False,
		)
		return
	values = {"cs_meeting_status": "Created", "cs_meeting_error": None}
	if out.get("join_url"):
		values["cs_web_meeting"] = out["join_url"]
	if out.get("meeting_id"):
		values["cs_meeting_id"] = str(out["meeting_id"])
	if "host_key" in out:
		values["cs_host_key"] = out.get("host_key") or None
	if "alternative_hosts" in out:
		values["cs_meeting_hosts"] = ", ".join(out.get("alternative_hosts") or []) or None
	frappe.db.set_value(ROW, row.name, values, update_modified=False)
	if values.get("cs_web_meeting") and values["cs_web_meeting"] != row.cs_web_meeting:
		# A capture waiting for this link can now arm (decisions/100d).
		from seminary.seminary.oral_meetings import on_meeting_link

		on_meeting_link(row.name)


def _message(e):
	text = getattr(e, "message", None) or str(e) or e.__class__.__name__
	return frappe.utils.strip_html(text)[:500]


def _account(name):
	acc = frappe.db.get_value(ACCOUNT, name, ["name", "provider", "host_id", "enabled"], as_dict=True)
	if not acc or not acc.enabled:
		return None
	return {"name": acc.name, "provider": acc.provider, "host_id": acc.host_id}


def _meeting(cs, row, hosts):
	start = datetime.combine(getdate(row.cs_meetdate), get_time(row.cs_fromtime))
	end = datetime.combine(getdate(row.cs_meetdate), get_time(row.cs_totime))
	return {
		"topic": f"{cs.title or cs.name} ({frappe.format(row.cs_meetdate, 'Date')})",
		"date": str(getdate(row.cs_meetdate)),
		"from_time": _hm(row.cs_fromtime),
		"to_time": _hm(row.cs_totime),
		"start": start.strftime("%Y-%m-%dT%H:%M:%S"),
		"duration": max(1, int((end - start).total_seconds() // 60)),
		"timezone": get_system_timezone(),
		"alternative_hosts": hosts,
	}


def _instructor_emails(cs_name):
	"""The instructors of record's emails, the candidates for alternative host (051a §6)."""
	from seminary.seminary.guards import _of_record_categories

	rows = frappe.get_all(
		"Course Schedule Instructors",
		filters={"parent": cs_name, "parenttype": "Course Schedule"},
		fields=["instructor", "instructor_category"],
	)
	of_record = _of_record_categories()
	names = [r.instructor for r in rows if r.instructor_category in of_record]
	if not names:
		return []
	users = frappe.get_all(
		"Instructor",
		filters={"name": ["in", names], "user": ["is", "set"]},
		pluck="user",
	)
	return sorted({e for e in frappe.get_all("User", filters={"name": ["in", users]}, pluck="email") if e})


@frappe.whitelist()
def retry(course_schedule):
	"""Try the failed school meetings of a section again."""
	from seminary.seminary.guards import require_course_staff

	require_course_staff(course_schedule, include_registrar=True)
	rows = frappe.get_all(
		ROW,
		filters={
			"parent": course_schedule,
			"parenttype": "Course Schedule",
			"cs_meeting_status": "Failed",
		},
		pluck="name",
	)
	if rows:
		_enqueue(course_schedule, [], rows)
	return len(rows)
