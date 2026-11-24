# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""A lesson's saved versions, for the History panel in the lesson editor (decision 109 §3).

Course Lesson has `track_changes`, so every save that changes a field writes a Version
row holding each changed field's old and new value. The editor autosaves every few
seconds, so the panel lists editing sessions rather than single saves: consecutive saves
by one person, no more than `SESSION_GAP` apart and within `SESSION_SPAN` of the first,
are one entry, and it opens the last of them. (The editor saves no timestamp in the
content, so an autosave without an edit writes no version at all.)

A version's content is read from the Version rows alone: a field's value at a version is
the new value of the latest change at or before it, or else the old value of the first
change after it, or else the lesson's current value.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, get_fullname

#: The fields the lesson editor writes: the lesson's blocks and the instructor notes.
FIELDS = ("content", "instructor_content")

#: Saves closer together than this, by one person, are one editing session...
SESSION_GAP = 15 * 60
#: ...up to this long, so a long sitting still has points to go back to.
SESSION_SPAN = 30 * 60

#: How many Version rows the list reads. Older sessions drop off the end.
MAX_ROWS = 2000


def _require_edit(lesson):
	# Who may edit lessons at all comes first, so a caller who can't is refused
	# before the answer says whether the lesson exists.
	if not frappe.has_permission("Course Lesson", "write"):
		frappe.throw(_("Only someone who can edit this lesson can see its history."), frappe.PermissionError)
	if not frappe.db.exists("Course Lesson", lesson):
		frappe.throw(_("Lesson not found."), frappe.DoesNotExistError)
	if not frappe.has_permission("Course Lesson", "write", doc=lesson):
		frappe.throw(_("Only someone who can edit this lesson can see its history."), frappe.PermissionError)


def _changes(data):
	"""{field: (old, new)} for the editor's fields changed in one Version row."""
	try:
		parsed = frappe.parse_json(data) or {}
	except Exception:
		return {}
	out = {}
	for row in parsed.get("changed") or []:
		if isinstance(row, list | tuple) and len(row) == 3 and row[0] in FIELDS:
			out[row[0]] = (row[1], row[2])
	return out


def _versions(lesson, fields=("name", "owner", "creation")):
	"""The lesson's Version rows that changed an editor field, oldest first."""
	# A cheap first cut on the stored JSON, confirmed by parsing in `_changes`.
	return frappe.get_all(
		"Version",
		filters={"ref_doctype": "Course Lesson", "docname": lesson},
		or_filters=[["data", "like", f'%["{f}",%'] for f in FIELDS],
		fields=list(fields),
		order_by="creation desc, name desc",
		limit=MAX_ROWS,
	)[::-1]


@frappe.whitelist()
def get_lesson_history(lesson: str):
	"""The lesson's editing sessions, newest first: who, when, and the version to open."""
	_require_edit(lesson)
	sessions = []
	for row in _versions(lesson):
		last = sessions[-1] if sessions else None
		if (
			last
			and last["owner"] == row.owner
			and (get_datetime(row.creation) - get_datetime(last["saved_at"])).total_seconds() <= SESSION_GAP
			and (get_datetime(row.creation) - get_datetime(last["started_at"])).total_seconds()
			<= SESSION_SPAN
		):
			last.update(version=row.name, saved_at=row.creation, saves=last["saves"] + 1)
		else:
			sessions.append(
				{
					"version": row.name,
					"owner": row.owner,
					"started_at": row.creation,
					"saved_at": row.creation,
					"saves": 1,
				}
			)
	names = {}
	for s in sessions:
		if s["owner"] not in names:
			names[s["owner"]] = get_fullname(s["owner"])
		s["owner_name"] = names[s["owner"]]
	# The newest session is the lesson as it is now; it is listed but has nothing to restore.
	for s in sessions:
		s["current"] = False
	if sessions:
		sessions[-1]["current"] = True
	return sessions[::-1]


@frappe.whitelist()
def get_lesson_version(lesson: str, version: str):
	"""The editor's fields as they were after `version` was saved."""
	_require_edit(lesson)
	rows = _versions(lesson, fields=("name", "creation", "data"))
	at = next((i for i, r in enumerate(rows) if r.name == version), None)
	if at is None:
		frappe.throw(_("That version isn't in this lesson's history."), frappe.DoesNotExistError)
	changes = [_changes(r.data) for r in rows]
	current = frappe.db.get_value("Course Lesson", lesson, list(FIELDS), as_dict=True) or {}
	values = {}
	for field in FIELDS:
		before = next((c[field][1] for c in reversed(changes[: at + 1]) if field in c), None)
		after = next((c[field][0] for c in changes[at + 1 :] if field in c), None)
		if before is not None:
			values[field] = before
		elif any(field in c for c in changes[at + 1 :]):
			values[field] = after
		else:
			values[field] = current.get(field)
	return {"version": version, "saved_at": rows[at].creation, **values}
