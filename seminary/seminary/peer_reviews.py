# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Peer review and teammate ratings (decisions/120 §5-§7).

A **round** belongs to one assessment row (an activity on a section). It
opens at the due date, the cut-off or by hand; reviews and ratings are due a
set number of days later, and the round is then **released**: authors see the
reviews of their work and members the ratings they received.

* **Peer Review**: one student reviewing one piece of work, which for group
  work is the group's. Assigned so each submission gets about the same number
  of reviews, never to its own authors.
* **Teammate Rating**: one member rating one teammate's contribution.
* **Review credit** (§7): the share of a student's assigned reviews and
  ratings done by the due date. With a ``review_share`` it is that part of the
  grade; the rest is the instructor's grade on the work.
"""

import json
import random

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime

from seminary.seminary import group_work
from seminary.seminary.group_work import ACTIVITY_OF, GROUP, SCAC, SUBMISSION

REVIEW = "Peer Review"
RATING = "Teammate Rating"
RATING_SCALE = (1, 2, 3, 4, 5)
DEFAULT_CRITERIA = (
	"Contributed their share",
	"Met commitments",
	"Worked well with others",
)
_ROW_FIELDS = [
	"name",
	"parent",
	"title",
	"due_date",
	"cutoff_date",
	"review_opened_on",
	"review_due_on",
	"reviews_released_on",
]


# ------------------------------------------------------------------ helpers


def _parse(value, default=None):
	if value in (None, ""):
		return default
	if isinstance(value, str):
		try:
			return json.loads(value)
		except ValueError:
			return default
	return value


def _row(course_assess):
	return frappe.db.get_value(SCAC, course_assess, _ROW_FIELDS, as_dict=True) if course_assess else None


def _row_for(course_schedule, activity_doctype, activity):
	row = group_work.require_row(course_schedule, activity_doctype, activity)
	return _row(row.name)


def _activity_of_row(row):
	for adt, (_sub, _f, field) in SUBMISSION.items():
		act = frappe.db.get_value(SCAC, row.name, field)
		if act:
			return adt, act
	return None, None


def is_open(row, at=None):
	return bool(row and row.review_opened_on and not row.reviews_released_on)


def criteria():
	"""What teammates rate each other on (§6), from Seminary Settings."""
	rows = frappe.get_all(
		"Teammate Rating Criterion",
		filters={"parent": "Seminary Settings", "parenttype": "Seminary Settings"},
		fields=["criterion"],
		order_by="idx asc",
	)
	return [r.criterion for r in rows if r.criterion] or [_(c) for c in DEFAULT_CRITERIA]


def _handed_in(doctype, sub):
	if doctype == "Assignment Submission":
		return bool(sub.get("answer") or sub.get("assignment_attachment"))
	return bool(sub.get("recording"))


def _person(student):
	return frappe.db.get_value("Student", student, "person")


def _name(student):
	return frappe.db.get_value("Student", student, "student_name") or student


def _notify(student, subject, message, course_schedule, key):
	from seminary.seminary import comms

	person = _person(student)
	if not person:
		return
	try:
		comms.send_message(
			channel="In-App",
			subject=subject,
			message=message,
			person=person,
			category="Academic",
			reference_doctype="Course Schedule",
			reference_name=course_schedule,
			dedupe_key=key,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Peer review notice failed")


# ------------------------------------------------------------------ work items


def work_items(row, activity_doctype):
	"""The pieces of work to review on this row: one per group for group
	work, else one per student. {key: {key, submission, group, author, authors}}"""
	sub_dt = SUBMISSION[activity_doctype][0]
	fields = ["name", "student", "activity_group", "modified"]
	fields += ["answer", "assignment_attachment"] if sub_dt == "Assignment Submission" else ["recording"]
	items = {}
	for sub in frappe.get_all(
		sub_dt, filters={"course_assess": row.name}, fields=fields, order_by="modified desc"
	):
		if not sub.student or not _handed_in(sub_dt, sub):
			continue
		key = sub.activity_group or sub.student
		item = items.get(key)
		if item is None:
			item = items[key] = frappe._dict(
				key=key,
				submission=sub.name,
				submission_doctype=sub_dt,
				group=sub.activity_group,
				author=sub.student,
				authors=set(),
			)
		item.authors.add(sub.student)
	return items


def _reviews(row, **filters):
	return frappe.get_all(
		REVIEW,
		filters={"course_assess": row.name, **filters},
		fields=[
			"name",
			"submission",
			"submission_doctype",
			"activity_group",
			"author",
			"reviewer",
			"status",
			"extra",
			"hidden",
			"credit_withdrawn",
			"submitted_on",
			"assigned_by",
		],
		order_by="creation asc",
	)


def _item_key(review):
	return review.activity_group or review.author


def _insert_review(row, activity_doctype, activity, item, reviewer, assigned_by="Automatic", extra=0):
	doc = frappe.get_doc(
		{
			"doctype": REVIEW,
			"course_schedule": row.parent,
			"activity_doctype": activity_doctype,
			"activity": activity,
			"course_assess": row.name,
			"submission_doctype": item.submission_doctype,
			"submission": item.submission,
			"activity_group": item.group,
			"author": item.author,
			"reviewer": reviewer,
			"status": "Assigned",
			"assigned_by": assigned_by,
			"extra": cint(extra),
			"assigned_on": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def allocate(row, s):
	"""Give every reviewer up to ``reviews_per_student`` reviews, round by
	round so the load stays even: each pick is the eligible work with the
	fewest reviews so far. Returns the reviews created."""
	n = max(1, cint(s.reviews_per_student) or 2)
	items = work_items(row, s.activity_doctype)
	if len(items) < 2:
		return []
	on_roster = {p["student"] for p in group_work.roster(row.parent)}
	reviewers = sorted({a for it in items.values() for a in it.authors if a in on_roster})
	existing = _reviews(row)
	load = {k: 0 for k in items}
	have = {r: set() for r in reviewers}
	counted = {r: 0 for r in reviewers}
	for rv in existing:
		key = _item_key(rv)
		if key in load:
			load[key] += 1
		have.setdefault(rv.reviewer, set()).add(key)
		if not cint(rv.extra):
			counted[rv.reviewer] = counted.get(rv.reviewer, 0) + 1
	# A fair, repeatable order, not a secret.
	rng = random.Random(f"{row.name}|reviews")  # nosec B311
	order = list(reviewers)
	rng.shuffle(order)
	tiebreak = {k: rng.random() for k in sorted(items)}
	created = []
	solo = all(len(it.authors) == 1 for it in items.values())
	if solo and not existing and n < len(items):
		# Individual work at opening: each student reviews the next n in a
		# shuffled ring, so every piece gets exactly n reviews.
		ring = [it for it in items.values() if next(iter(it.authors)) in set(reviewers)]
		ring.sort(key=lambda it: order.index(next(iter(it.authors))))
		for i, it in enumerate(ring if len(ring) > n else []):
			reviewer = next(iter(it.authors))
			for step in range(1, n + 1):
				pick = ring[(i + step) % len(ring)]
				created.append(_insert_review(row, s.activity_doctype, s.activity, pick, reviewer))
				load[pick.key] += 1
				have.setdefault(reviewer, set()).add(pick.key)
				counted[reviewer] = counted.get(reviewer, 0) + 1
	for _round in range(n):
		for reviewer in order:
			if counted.get(reviewer, 0) >= n:
				continue
			candidates = [
				it
				for k, it in items.items()
				if reviewer not in it.authors and k not in have.get(reviewer, set())
			]
			if not candidates:
				continue
			pick = min(candidates, key=lambda it: (load[it.key], tiebreak[it.key]))
			created.append(_insert_review(row, s.activity_doctype, s.activity, pick, reviewer))
			load[pick.key] += 1
			have.setdefault(reviewer, set()).add(pick.key)
			counted[reviewer] = counted.get(reviewer, 0) + 1
	return created


# ------------------------------------------------------------------ the round


def _lock_row(name):
	frappe.db.sql(
		"select name from `tabScheduled Course Assess Criteria` where name = %s for update", (name,)
	)


def open_round(row, s, at=None):
	"""Open reviews and ratings on this row (§5, §6)."""
	_lock_row(row.name)
	row = _row(row.name)
	if row.review_opened_on:
		return row
	at = get_datetime(at) if at else now_datetime()
	due = add_to_date(at, days=max(1, cint(s.review_due_days) or 7))
	frappe.db.set_value(SCAC, row.name, {"review_opened_on": at, "review_due_on": due}, update_modified=False)
	row.review_opened_on, row.review_due_on = at, due
	created = allocate(row, s) if cint(s.peer_review) else []
	title = s.title or row.title or ""
	for student in sorted({r.reviewer for r in created}):
		_notify(
			student,
			_("Peer reviews to do: {0}").format(title),
			_("You have classmates' work to review for {0}, due {1}.").format(
				title, frappe.utils.format_datetime(due)
			),
			row.parent,
			f"peer-review-open-{row.name}-{student}",
		)
	if cint(s.teammate_ratings) and s.is_group_work:
		for g in group_work.group_rows(row.parent, s.activity_doctype, s.activity):
			members = group_work.active_members(g.name)
			if len(members) < 2:
				continue
			for student in members:
				_notify(
					student,
					_("Rate your teammates: {0}").format(title),
					_("Rate your teammates' contribution to {0} by {1}.").format(
						title, frappe.utils.format_datetime(due)
					),
					row.parent,
					f"teammate-ratings-open-{row.name}-{student}",
				)
	refresh_credit(row, s)
	return row


def release(row, s, at=None):
	"""Authors see their reviews, members their ratings (§5, §6)."""
	_lock_row(row.name)
	row = _row(row.name)
	if row.reviews_released_on or not row.review_opened_on:
		return row
	at = get_datetime(at) if at else now_datetime()
	frappe.db.set_value(SCAC, row.name, "reviews_released_on", at, update_modified=False)
	row.reviews_released_on = at
	title = s.title or row.title or ""
	authors = set()
	for rv in _reviews(row, status="Submitted", hidden=0):
		key = _item_key(rv)
		authors.update(group_work.active_members(key) if rv.activity_group else [key])
	if cint(s.teammate_ratings) and s.ratings_shown != "Instructor only":
		authors.update(frappe.get_all(RATING, filters={"course_assess": row.name}, pluck="ratee"))
	for student in sorted(authors):
		_notify(
			student,
			_("Feedback from classmates: {0}").format(title),
			_("Your classmates' feedback on {0} is ready.").format(title),
			row.parent,
			f"peer-review-released-{row.name}-{student}",
		)
	refresh_credit(row, s)
	return row


# Rows of activities with reviews or ratings whose round is not yet released.
_ROUND_QUERIES = {
	group_work.ASSIGNMENT: """select r.name, r.assignment as activity, r.review_opened_on
		from `tabScheduled Course Assess Criteria` r
		join `tabAssignment Activity` a on a.name = r.assignment
		join `tabCourse Schedule` cs on cs.name = r.parent
		where r.parenttype = 'Course Schedule'
		  and (a.peer_review = 1 or a.teammate_ratings = 1)
		  and r.reviews_released_on is null
		  and cs.workflow_state not in %(closed)s""",
	group_work.ORAL: """select r.name, r.oral as activity, r.review_opened_on
		from `tabScheduled Course Assess Criteria` r
		join `tabOral Activity` a on a.name = r.oral
		join `tabCourse Schedule` cs on cs.name = r.parent
		where r.parenttype = 'Course Schedule'
		  and (a.peer_review = 1 or a.teammate_ratings = 1)
		  and r.reviews_released_on is null
		  and cs.workflow_state not in %(closed)s""",
}


def hourly(at=None):
	"""Open rounds whose due date or cut-off has passed; release rounds whose
	reviews are due. A failure on one row is logged and the rest go on."""
	from seminary.seminary.content_release import CLOSED_STATES

	at = get_datetime(at) if at else now_datetime()
	for adt, query in _ROUND_QUERIES.items():
		rows = frappe.db.sql(query, {"closed": list(CLOSED_STATES) or [""]}, as_dict=True)
		for r in rows:
			try:
				s = group_work.settings(adt, r.activity)
				row = _row(r.name)
				if not row.review_opened_on:
					opens = {
						"At the due date": row.due_date,
						"At the cut-off": row.cutoff_date,
					}.get(s.review_opens or "At the due date")
					if opens and get_datetime(opens) <= at:
						open_round(row, s, at=at)
				elif row.review_due_on and get_datetime(row.review_due_on) <= at:
					release(row, s, at=at)
				frappe.db.commit()  # nosemgrep -- one row's round per commit in a scheduled job
			except Exception:
				frappe.db.rollback()
				frappe.log_error(frappe.get_traceback(), f"Peer review round {r.name} failed")


def on_submission_update(doc, method=None):
	"""Work handed in after the round opened joins it: its authors get their
	reviews to do, and classmates who have finished may take it as an extra."""
	if doc.flags.group_copy or frappe.flags.seminary_group_copy:
		return
	if doc.doctype not in ACTIVITY_OF:
		return
	row = _row(doc.get("course_assess"))
	if not is_open(row):
		return
	adt, field = ACTIVITY_OF[doc.doctype]
	s = group_work.settings(adt, doc.get(field))
	if not cint(s.peer_review):
		return
	before = doc.get_doc_before_save()
	if before is not None and not any(
		doc.get(f) != before.get(f) for f in group_work.CONTENT_FIELDS[doc.doctype]
	):
		return
	created = allocate(row, s)
	if created:
		refresh_credit(row, s, {r.reviewer for r in created})


# ------------------------------------------------------------------ credit


def credit(row, s, student):
	"""Percent of this student's assigned reviews and ratings done by the
	due date, or None when nothing was asked of them (§7)."""
	if not (row and row.review_opened_on):
		return None
	due = get_datetime(row.review_due_on) if row.review_due_on else None
	asked = done = 0
	if cint(s.peer_review):
		for rv in _reviews(row, reviewer=student, extra=0):
			asked += 1
			on_time = rv.submitted_on and (not due or get_datetime(rv.submitted_on) <= due)
			if rv.status == "Submitted" and on_time and not cint(rv.credit_withdrawn):
				done += 1
	if cint(s.teammate_ratings) and s.is_group_work:
		group = group_work.group_of(row.parent, s.activity_doctype, s.activity, student)
		if group:
			mates = [m for m in group_work.active_members(group) if m != student]
			asked += len(mates)
			rated = frappe.get_all(
				RATING,
				filters={"activity_group": group, "rater": student, "ratee": ["in", mates or [""]]},
				fields=["submitted_on"],
			)
			done += sum(
				1 for r in rated if r.submitted_on and (not due or get_datetime(r.submitted_on) <= due)
			)
	if not asked:
		return None
	return round(100.0 * done / asked, 2)


def blend(doc):
	"""Submission validate (§7): the grade that counts is the work's grade
	less ``review_share``, plus that share earned by review credit."""
	if doc.doctype not in ACTIVITY_OF:
		return
	adt, field = ACTIVITY_OF[doc.doctype]
	activity = doc.get(field)
	if not activity:
		return
	share = flt(frappe.db.get_value(adt, activity, "review_share"))
	if share <= 0:
		return
	row = _row(doc.get("course_assess"))
	if not (row and row.review_opened_on):
		return
	if cint(doc.get("review_credit_override")):
		value = flt(doc.get("review_credit"))
	else:
		value = credit(row, group_work.settings(adt, activity), doc.student)
		if value is None:
			return
		doc.review_credit = value
	if doc.get("grade") in (None, ""):
		return
	from seminary.seminary.rubrics import max_grade

	top = max_grade(doc.course)
	share = min(share, 100.0) / 100.0
	doc.percentage = round(flt(doc.grade) * (1 - share) + share * value / 100.0 * top, 2)


def refresh_credit(row, s, students=None):
	"""Re-save the submissions whose review credit moved, so the gradebook
	follows. Only when the activity has a review share."""
	if flt(frappe.db.get_value(s.activity_doctype, s.activity, "review_share")) <= 0:
		return
	sub_dt = SUBMISSION[s.activity_doctype][0]
	filters = {"course_assess": row.name}
	if students:
		filters["student"] = ["in", list(students)]
	for sub in frappe.get_all(
		sub_dt,
		filters=filters,
		fields=["name", "student", "review_credit", "review_credit_override"],
	):
		if cint(sub.review_credit_override):
			continue
		value = credit(row, s, sub.student)
		if value is None or abs(flt(sub.review_credit) - value) < 0.005:
			continue
		doc = frappe.get_doc(sub_dt, sub.name)
		doc.flags.group_copy = True
		doc.save(ignore_permissions=True)


# ------------------------------------------------------------------ views


def _anonymous(s):
	return bool(cint(s.review_anonymous))


def _work_label(item_group, author, s, n=None):
	if _anonymous(s):
		return _("Work {0}").format(n) if n else _("A classmate's work")
	if item_group:
		return frappe.db.get_value(GROUP, item_group, "group_name") or _("A group")
	return _name(author)


def _rubric_for_review(s):
	"""The activity's rubric for a reviewer: criteria and level names, no
	points (§5)."""
	if s.review_form == "Comments only" or not s.get("rubric"):
		return None
	from seminary.seminary import rubrics

	payload = rubrics.rubric_payload(s.rubric)
	if not payload:
		return None
	# Copies: the levels may come from a cache shared with the grading page.
	payload["levels"] = [
		{k: v for k, v in dict(lv).items() if k not in ("percent", "meets_expectations")}
		for lv in payload.get("levels") or []
	]
	payload["criteria"] = [
		{k: v for k, v in c.items() if k not in ("weight", "share")} for c in payload.get("criteria") or []
	]
	return payload


def _review_out(rv, s, viewer, staff=False, own=False):
	"""A review for display. ``own``: the reviewer's own view, which carries
	the file's address so a save can keep it."""
	doc = frappe.get_doc(REVIEW, rv) if isinstance(rv, str) else rv
	show_reviewer = staff or own or not _anonymous(s)
	return {
		"name": doc.name,
		"status": doc.status,
		"reviewer": doc.reviewer if show_reviewer else None,
		"reviewer_name": (doc.reviewer_name or _name(doc.reviewer)) if show_reviewer else _("A classmate"),
		"rubric_levels": _parse(doc.rubric_levels, {}),
		"comments": doc.comments,
		"attachment": bool(doc.attachment),
		"moments": _parse(doc.moments, []),
		"submitted_on": doc.submitted_on,
		"hidden": cint(doc.hidden),
		"credit_withdrawn": cint(doc.credit_withdrawn),
		"attachment_url": doc.attachment if (own or staff) else None,
	}


def _received_reviews(row, s, student, group):
	if not row.reviews_released_on:
		return []
	filters = {"status": "Submitted", "hidden": 0}
	if group:
		filters["activity_group"] = group
	else:
		filters["author"] = student
		filters["activity_group"] = ["is", "not set"]
	return [_review_out(frappe.get_doc(REVIEW, r.name), s, student) for r in _reviews(row, **filters)]


def ratings_summary(group, crit=None, with_names=True):
	"""For each member: the average per criterion and overall, the spread of
	raters' overall marks, and the comments (§6)."""
	crit = crit or criteria()
	out = {}
	for r in frappe.get_all(
		RATING,
		filters={"activity_group": group, "submitted_on": ["is", "set"]},
		fields=["rater", "rater_name", "ratee", "scores", "comment"],
	):
		scores = _parse(r.scores, {}) or {}
		vals = [flt(scores.get(c)) for c in crit if scores.get(c) not in (None, "")]
		m = out.setdefault(r.ratee, {"by_criterion": {c: [] for c in crit}, "overall": [], "comments": []})
		for c in crit:
			if scores.get(c) not in (None, ""):
				m["by_criterion"][c].append(flt(scores.get(c)))
		if vals:
			m["overall"].append(sum(vals) / len(vals))
		if r.comment:
			m["comments"].append(
				{"rater": (r.rater_name or _name(r.rater)) if with_names else None, "comment": r.comment}
			)
	for m in out.values():
		m["average"] = round(sum(m["overall"]) / len(m["overall"]), 2) if m["overall"] else None
		m["spread"] = round(max(m["overall"]) - min(m["overall"]), 2) if len(m["overall"]) > 1 else 0
		m["count"] = len(m["overall"])
		m["by_criterion"] = {
			c: (round(sum(v) / len(v), 2) if v else None) for c, v in m["by_criterion"].items()
		}
		del m["overall"]
	return out


# ------------------------------------------------------------------ files


def _file_doc(url):
	name = frappe.db.get_value("File", {"file_url": url}, "name") if url else None
	return frappe.get_doc("File", name) if name else None


def _send_file(url):
	f = _file_doc(url)
	if not f:
		frappe.throw(_("File not found."), frappe.DoesNotExistError)
	frappe.local.response.filename = f.file_name
	frappe.local.response.filecontent = f.get_content()
	frappe.local.response.type = "download"


def may_review_recording(recording, user):
	"""Oral Recording read for a reviewer of the work it belongs to (§5)."""
	student = frappe.db.get_value("Student", {"user": user}, "name")
	if not student:
		return False
	subs = frappe.get_all("Oral Activity Submission", filters={"recording": recording}, pluck="name")
	return bool(
		subs
		and frappe.db.exists(
			REVIEW,
			{
				"submission_doctype": "Oral Activity Submission",
				"submission": ["in", subs],
				"reviewer": student,
			},
		)
	)


# ================================================================== students


def _me():
	from seminary.seminary.guards import current_student

	student = current_student(frappe.session.user)
	if not student:
		frappe.throw(_("Only students can do this."), frappe.PermissionError)
	return student


def _student_context(course, activity_doctype, activity):
	from seminary.seminary.guards import require_enrolled

	require_enrolled(course)
	student = _me()
	s = group_work.settings(activity_doctype, activity)
	row = _row_for(course, activity_doctype, activity)
	return student, s, row


@frappe.whitelist()
def get_panel(course: str, activity_doctype: str, activity: str):
	"""Everything a student sees about group work, topics, reviews and
	ratings on one activity."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if s.is_group_work:
		group_work.ensure_groups(course, activity_doctype, activity)
	group = group_work.group_of(course, activity_doctype, activity, student) if s.is_group_work else None
	topic = group_work.topic_of(course, activity_doctype, activity, student, group=group)
	out = {
		"is_group_work": s.is_group_work,
		"group_source": group_work.default_source(course, s) if s.is_group_work else None,
		"topic_mode": s.topic_mode,
		"peer_review": cint(s.peer_review),
		"teammate_ratings": cint(s.teammate_ratings) and s.is_group_work,
		"review_anonymous": cint(s.review_anonymous),
		"ratings_shown": s.ratings_shown or "Named",
		"review_share": flt(s.review_share),
		"reviews_per_student": cint(s.reviews_per_student),
		"dates": {k: row.get(k) for k in ("review_opened_on", "review_due_on", "reviews_released_on")},
		"signup_closes_on": frappe.db.get_value(SCAC, row.name, "signup_closes_on"),
		"topics_close_on": frappe.db.get_value(SCAC, row.name, "topics_close_on"),
		"group": None,
		"groups": [],
		"topic": None,
		"topics": [],
		"reviews": [],
		"may_take_extra": False,
		"received": [],
		"ratings": None,
		"ratings_received": None,
		"credit": None,
	}
	if group:
		out["group"] = {
			"name": group,
			"group_name": frappe.db.get_value(GROUP, group, "group_name"),
			"members": [{"student": m, "name": _name(m)} for m in group_work.active_members(group)],
		}
	signup_open = group_work.window_open(out["signup_closes_on"])
	out["may_sign_up"] = bool(s.is_group_work and out["group_source"] == "Self sign-up" and signup_open)
	if out["may_sign_up"]:
		size = cint(s.group_size)
		for g in group_work.group_rows(course, activity_doctype, activity):
			members = group_work.active_members(g.name)
			out["groups"].append(
				{
					"name": g.name,
					"group_name": g.group_name,
					"members": [_name(m) for m in members],
					"full": bool(size and len(members) >= size),
				}
			)
	if topic:
		t = frappe.db.get_value(group_work.TOPIC, topic, ["name", "title", "description"], as_dict=True)
		out["topic"] = t
	may_choose = (
		s.topic_mode == "Students choose"
		and group_work.window_open(out["topics_close_on"])
		and (group or not s.is_group_work)
	)
	if may_choose:
		out["topics"] = [
			{
				"name": t.name,
				"title": t.title,
				"description": t.description,
				"free": max(0, t.capacity - t.taken),
				"mine": t.name == topic,
			}
			for t in group_work.topics(course, activity_doctype, activity)
		]
	if cint(s.peer_review) and row.review_opened_on:
		mine = _reviews(row, reviewer=student)
		for n, rv in enumerate(mine, start=1):
			out["reviews"].append(
				{
					"name": rv.name,
					"status": rv.status,
					"extra": cint(rv.extra),
					"label": _work_label(rv.activity_group, rv.author, s, n),
				}
			)
		out["may_take_extra"] = bool(
			is_open(row)
			and mine
			and all(r.status == "Submitted" for r in mine)
			and _extra_candidates(row, s, student)
		)
	out["received"] = _received_reviews(row, s, student, group)
	if out["teammate_ratings"] and group and row.review_opened_on:
		mates = [m for m in group_work.active_members(group) if m != student]
		given = {
			r.ratee: r
			for r in frappe.get_all(
				RATING,
				filters={"activity_group": group, "rater": student},
				fields=["ratee", "scores", "comment", "submitted_on"],
			)
		}
		out["ratings"] = {
			"criteria": criteria(),
			"scale": list(RATING_SCALE),
			"open": is_open(row),
			"teammates": [
				{
					"student": m,
					"name": _name(m),
					"scores": _parse(given[m].scores, {}) if m in given else {},
					"comment": given[m].comment if m in given else "",
					"done": bool(m in given and given[m].submitted_on),
				}
				for m in mates
			],
		}
	if out["teammate_ratings"] and group and row.reviews_released_on and s.ratings_shown != "Instructor only":
		mine = ratings_summary(group, with_names=s.ratings_shown == "Named").get(student)
		out["ratings_received"] = mine
	if flt(s.review_share) > 0:
		out["credit"] = credit(row, s, student)
	return out


@frappe.whitelist(methods=["POST"])
def join_group(course: str, activity_doctype: str, activity: str, group: str):
	"""Self sign-up (§2): join a group with room, before sign-up closes."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if not s.is_group_work or group_work.default_source(course, s) != "Self sign-up":
		frappe.throw(_("Groups on this activity are not chosen by students."))
	if not group_work.window_open(frappe.db.get_value(SCAC, row.name, "signup_closes_on")):
		frappe.throw(_("Group sign-up has closed. Ask your instructor to move you."))
	g = frappe.db.sql(
		"select name, course_schedule, activity from `tabActivity Group` where name = %s for update",
		(group,),
		as_dict=True,
	)
	if not g or (g[0].course_schedule, g[0].activity) != (course, activity):
		frappe.throw(_("This group is not on this activity."))
	current = group_work.group_of(course, activity_doctype, activity, student)
	if current == group:
		return {"group": group}
	if current and group_work.has_work(current):
		frappe.throw(_("Your group has handed in work, so you cannot change groups. Ask your instructor."))
	size = cint(s.group_size)
	if size and len(group_work.active_members(group)) >= size:
		frappe.throw(_("This group is full."))
	group_work.add_member(group, student)
	return {"group": group}


@frappe.whitelist(methods=["POST"])
def start_group(course: str, activity_doctype: str, activity: str):
	"""Self sign-up (§2): a student with no group starts one, which others
	may then join."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if not s.is_group_work or group_work.default_source(course, s) != "Self sign-up":
		frappe.throw(_("Groups on this activity are not chosen by students."))
	if not group_work.window_open(frappe.db.get_value(SCAC, row.name, "signup_closes_on")):
		frappe.throw(_("Group sign-up has closed. Ask your instructor to place you."))
	current = group_work.group_of(course, activity_doctype, activity, student)
	if current and group_work.has_work(current):
		frappe.throw(_("Your group has handed in work, so you cannot change groups. Ask your instructor."))
	group_work._lock_section(course)
	taken = {g.group_name for g in group_work.group_rows(course, activity_doctype, activity)}
	n = len(taken) + 1
	while _("Group {0}").format(n) in taken:
		n += 1
	doc = group_work.make_group(
		course, activity_doctype, activity, _("Group {0}").format(n), [student], "Self sign-up"
	)
	return {"group": doc.name}


@frappe.whitelist(methods=["POST"])
def leave_group(course: str, activity_doctype: str, activity: str):
	student, s, row = _student_context(course, activity_doctype, activity)
	if group_work.default_source(course, s) != "Self sign-up":
		frappe.throw(_("Groups on this activity are not chosen by students."))
	if not group_work.window_open(frappe.db.get_value(SCAC, row.name, "signup_closes_on")):
		frappe.throw(_("Group sign-up has closed. Ask your instructor to move you."))
	current = group_work.group_of(course, activity_doctype, activity, student)
	if not current:
		return {"group": None}
	if group_work.has_work(current):
		frappe.throw(_("Your group has handed in work, so you cannot leave it. Ask your instructor."))
	group_work.remove_member(current, student)
	return {"group": None}


@frappe.whitelist(methods=["POST"])
def choose_topic(course: str, activity_doctype: str, activity: str, topic: str | None = None):
	"""*Students choose* (§3): take a free topic, or let go of yours with no
	topic given, until topic choice closes."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if s.topic_mode != "Students choose":
		frappe.throw(_("Topics on this activity are not chosen by students."))
	if not group_work.window_open(frappe.db.get_value(SCAC, row.name, "topics_close_on")):
		frappe.throw(_("Topic choice has closed. Ask your instructor."))
	holder = student
	if s.is_group_work:
		holder = group_work.group_of(course, activity_doctype, activity, student)
		if not holder:
			frappe.throw(_("Join a group before choosing a topic."))
	if not topic:
		group_work.clear_topic(course, activity_doctype, activity, holder)
		return {"topic": None}
	if frappe.db.get_value(group_work.TOPIC, topic, ["course_schedule", "activity"]) != (course, activity):
		frappe.throw(_("This topic is not on this activity."))
	group_work.give_topic(topic, holder, chosen_by="Student")
	return {"topic": topic}


def _my_review(review):
	doc = frappe.get_doc(REVIEW, review) if frappe.db.exists(REVIEW, review) else None
	if not doc:
		frappe.throw(_("Review not found."), frappe.PermissionError)
	from seminary.seminary.guards import current_student, is_course_staff

	if is_course_staff(doc.course_schedule, include_registrar=True):
		return doc, True
	if doc.reviewer != current_student(frappe.session.user):
		frappe.throw(_("Review not found."), frappe.PermissionError)
	return doc, False


def _work_payload(doc):
	"""What a reviewer reads or listens to (§5). Files come through
	``download`` so the reviewer never reads the submission record itself."""
	sub = frappe.get_doc(doc.submission_doctype, doc.submission)
	base = f"/api/method/seminary.seminary.peer_reviews.download?review={doc.name}"
	if doc.submission_doctype == "Assignment Submission":
		return {
			"kind": "assignment",
			"type": sub.type,
			"answer": sub.answer if sub.type in ("Text", "URL", "YouTube") else None,
			"file": (base + "&kind=work") if sub.assignment_attachment else None,
			"file_name": frappe.db.get_value("File", {"file_url": sub.assignment_attachment}, "file_name")
			if sub.assignment_attachment
			else None,
		}
	return {"kind": "oral", "recording": sub.recording}


@frappe.whitelist()
def get_review(review: str):
	doc, staff = _my_review(review)
	s = group_work.settings(doc.activity_doctype, doc.activity)
	row = _row(doc.course_assess)
	prompt_field = "question" if doc.activity_doctype == group_work.ASSIGNMENT else "prompt"
	return {
		"review": _review_out(doc, s, None, staff=staff, own=not staff),
		"work_label": _work_label(doc.activity_group, doc.author, s)
		if not staff
		else _work_label(doc.activity_group, doc.author, frappe._dict(review_anonymous=0)),
		"activity_title": s.title,
		"prompt": frappe.db.get_value(doc.activity_doctype, doc.activity, prompt_field),
		"course_schedule": doc.course_schedule,
		"work": _work_payload(doc),
		"rubric": _rubric_for_review(s),
		"due": row.review_due_on if row else None,
		"editable": (not staff) and not (row and row.reviews_released_on),
		"is_staff": staff,
	}


@frappe.whitelist(methods=["POST"])
def save_review(
	review: str,
	rubric_levels: str | list | dict | None = None,
	comments: str | None = None,
	attachment: str | None = None,
	moments: str | list | dict | None = None,
	submit: int | str = 0,
):
	"""Save the reviewer's work, and hand it in with ``submit``. Editable
	until the reviews are released."""
	doc, staff = _my_review(review)
	if staff:
		frappe.throw(_("Only the reviewer can write this review."), frappe.PermissionError)
	row = _row(doc.course_assess)
	if row and row.reviews_released_on:
		frappe.throw(_("Reviews have been released, so this review can no longer change."))
	s = group_work.settings(doc.activity_doctype, doc.activity)
	levels = _parse(rubric_levels, {}) or {}
	rubric = _rubric_for_review(s)
	if rubric:
		codes = {c["criterion_code"] for c in rubric.get("criteria") or []}
		names = {lv["label"] for lv in rubric.get("levels") or []}
		levels = {k: v for k, v in levels.items() if k in codes and v in names}
	else:
		levels = {}
	marks = []
	for m in _parse(moments, []) or []:
		try:
			marks.append(
				{"t": max(0.0, flt(m.get("t"))), "note": frappe.utils.strip_html(m.get("note") or "")[:2000]}
			)
		except AttributeError:
			continue
	doc.rubric_levels = json.dumps(levels)
	doc.comments = frappe.utils.sanitize_html(comments or "", always_sanitize=True) if comments else None
	doc.moments = json.dumps(sorted(marks, key=lambda m: m["t"]))
	if attachment != doc.attachment:
		doc.attachment = _adopt_attachment(attachment, doc) if attachment else None
	if cint(submit):
		if not (
			levels
			or (doc.comments and frappe.utils.strip_html(doc.comments).strip())
			or doc.attachment
			or marks
		):
			frappe.throw(_("Write some feedback before handing in the review."))
		if rubric and len(levels) < len(rubric.get("criteria") or []):
			frappe.throw(_("Choose a level for every criterion."))
		if doc.status != "Submitted":
			doc.status = "Submitted"
			doc.submitted_on = now_datetime()
	doc.save(ignore_permissions=True)
	if row:
		refresh_credit(row, s, {doc.reviewer})
	return _review_out(doc, s, None, own=True)


def _adopt_attachment(url, doc):
	"""The reviewer's marked-up file: their own upload, attached to the review."""
	f = _file_doc(url)
	if not f or f.owner != frappe.session.user:
		frappe.throw(_("Upload the file again."))
	frappe.db.set_value(
		"File",
		f.name,
		{"attached_to_doctype": REVIEW, "attached_to_name": doc.name, "is_private": 1},
	)
	return f.file_url


@frappe.whitelist()
def download(review: str, kind: str = "work"):
	"""The reviewed work's file for its reviewer, or the reviewer's marked-up
	file for the work's authors once released (and for the staff)."""
	doc = frappe.get_doc(REVIEW, review) if frappe.db.exists(REVIEW, review) else None
	if not doc:
		frappe.throw(_("File not found."), frappe.PermissionError)
	from seminary.seminary.guards import current_student, is_course_staff

	staff = is_course_staff(doc.course_schedule, include_registrar=True)
	me = current_student(frappe.session.user)
	if kind == "work":
		if not (staff or doc.reviewer == me):
			frappe.throw(_("File not found."), frappe.PermissionError)
		url = frappe.db.get_value(doc.submission_doctype, doc.submission, "assignment_attachment")
		return _send_file(url)
	if not staff:
		row = _row(doc.course_assess)
		authors = set(group_work.active_members(doc.activity_group)) if doc.activity_group else {doc.author}
		released = row and row.reviews_released_on and not cint(doc.hidden) and doc.status == "Submitted"
		if not ((me in authors and released) or doc.reviewer == me):
			frappe.throw(_("File not found."), frappe.PermissionError)
	return _send_file(doc.attachment)


def _extra_candidates(row, s, student):
	n = max(1, cint(s.reviews_per_student) or 2)
	items = work_items(row, s.activity_doctype)
	load = {}
	mine = set()
	for rv in _reviews(row):
		load[_item_key(rv)] = load.get(_item_key(rv), 0) + 1
		if rv.reviewer == student:
			mine.add(_item_key(rv))
	return sorted(
		(it for k, it in items.items() if student not in it.authors and k not in mine and load.get(k, 0) < n),
		key=lambda it: load.get(it.key, 0),
	)


@frappe.whitelist(methods=["POST"])
def take_extra_review(course: str, activity_doctype: str, activity: str):
	"""A reviewer who has finished takes work still short of reviews (§5)."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if not (cint(s.peer_review) and is_open(row)):
		frappe.throw(_("Peer review is not open on this activity."))
	_lock_row(row.name)
	candidates = _extra_candidates(row, s, student)
	if not candidates:
		frappe.throw(_("Every piece of work has its reviews. Thank you!"))
	doc = _insert_review(
		row, activity_doctype, activity, candidates[0], student, assigned_by="Reviewer", extra=1
	)
	return {"review": doc.name}


@frappe.whitelist(methods=["POST"])
def save_ratings(course: str, activity_doctype: str, activity: str, ratings: str | list | dict):
	"""Rate each teammate (§6): ``[{student, scores: {criterion: 1-5}, comment}]``."""
	student, s, row = _student_context(course, activity_doctype, activity)
	if not (cint(s.teammate_ratings) and s.is_group_work and row.review_opened_on):
		frappe.throw(_("Teammate ratings are not open on this activity."))
	if row.reviews_released_on:
		frappe.throw(_("Ratings have been released, so they can no longer change."))
	group = group_work.group_of(course, activity_doctype, activity, student)
	if not group:
		frappe.throw(_("You are not in a group on this activity."))
	mates = set(group_work.active_members(group)) - {student}
	crit = criteria()
	at = now_datetime()
	for r in _parse(ratings, []) or []:
		ratee = r.get("student")
		if ratee not in mates:
			continue
		scores = {}
		for c in crit:
			v = cint((r.get("scores") or {}).get(c))
			if v:
				if v not in RATING_SCALE:
					frappe.throw(_("Ratings go from 1 to 5."))
				scores[c] = v
		name = frappe.db.get_value(RATING, {"activity_group": group, "rater": student, "ratee": ratee})
		doc = frappe.get_doc(RATING, name) if name else frappe.new_doc(RATING)
		doc.update(
			{
				"course_schedule": course,
				"activity_doctype": activity_doctype,
				"activity": activity,
				"course_assess": row.name,
				"activity_group": group,
				"rater": student,
				"ratee": ratee,
				"scores": json.dumps(scores),
				"comment": frappe.utils.strip_html(r.get("comment") or "")[:2000] or None,
			}
		)
		complete = len(scores) == len(crit)
		if complete and not doc.submitted_on:
			doc.submitted_on = at
		if not complete:
			doc.submitted_on = None
		doc.save(ignore_permissions=True)
	refresh_credit(row, s, {student})
	return get_panel(course, activity_doctype, activity)["ratings"]


@frappe.whitelist()
def my_todos(course: str):
	"""Reviews and ratings still to do on a section, for the course card."""
	from seminary.seminary.guards import current_student, require_enrolled

	require_enrolled(course)
	student = current_student(frappe.session.user)
	if not student:
		return []
	out = []
	reviews = frappe.get_all(
		REVIEW,
		filters={"course_schedule": course, "reviewer": student, "status": "Assigned"},
		fields=["name", "course_assess", "activity_doctype", "activity"],
		order_by="creation asc",
	)
	by_row = {}
	first = {}
	for r in reviews:
		key = (r.course_assess, r.activity_doctype, r.activity)
		by_row.setdefault(key, [0, 0])[0] += 1
		first.setdefault(key, r.name)
	for g in frappe.db.sql(
		"""select g.name, g.activity_doctype, g.activity from `tabActivity Group` g
		join `tabActivity Group Member` m on m.parent = g.name and m.parenttype = 'Activity Group'
		where g.course_schedule = %s and m.student = %s and m.left_on is null""",
		(course, student),
		as_dict=True,
	):
		s = group_work.settings(g.activity_doctype, g.activity)
		row = group_work.scac_row(course, g.activity_doctype, g.activity)
		if not (cint(s.teammate_ratings) and row and is_open(_row(row.name))):
			continue
		mates = [m for m in group_work.active_members(g.name) if m != student]
		done = frappe.db.count(
			RATING, {"activity_group": g.name, "rater": student, "submitted_on": ["is", "set"]}
		)
		if len(mates) > done:
			by_row.setdefault((row.name, g.activity_doctype, g.activity), [0, 0])[1] += len(mates) - done
	for (scac, adt, act), (n_reviews, n_ratings) in by_row.items():
		row = _row(scac)
		if not is_open(row):
			continue
		out.append(
			{
				"activity_doctype": adt,
				"activity": act,
				"title": row.title or frappe.db.get_value(adt, act, "title"),
				"reviews": n_reviews,
				"ratings": n_ratings,
				"due": row.review_due_on,
				"review": first.get((scac, adt, act)),
			}
		)
	return out


# ================================================================== staff


def _require_grader():
	from seminary.seminary.guards import require_grader

	require_grader(include_registrar=True)


def _staff(course, write=True):
	from seminary.seminary.guards import (
		GRADE,
		require_course_staff,
		require_grader,
		require_section_capability,
	)

	require_grader(include_registrar=not write)
	if write:
		require_section_capability(course, GRADE)
	else:
		require_course_staff(course, include_registrar=True)


@frappe.whitelist()
def get_manage(course: str, activity_doctype: str, activity: str):
	"""The instructor's page for one activity on one section: groups, topics,
	review progress and ratings."""
	_staff(course, write=False)
	s = group_work.settings(activity_doctype, activity)
	row = _row_for(course, activity_doctype, activity)
	scac = frappe.db.get_value(SCAC, row.name, ["signup_closes_on", "topics_close_on"], as_dict=True)
	if s.is_group_work:
		group_work.ensure_groups(course, activity_doctype, activity)
	people = group_work.roster(course)
	names = {p["student"]: p["name"] for p in people}
	groups = []
	grouped = set()
	crit = criteria()
	for g in group_work.group_rows(course, activity_doctype, activity):
		members = group_work.active_members(g.name)
		grouped.update(members)
		groups.append(
			{
				"name": g.name,
				"group_name": g.group_name,
				"topic": g.topic,
				"source": g.source,
				"has_work": group_work.has_work(g.name),
				"members": [{"student": m, "name": names.get(m) or _name(m)} for m in members],
				"ratings": ratings_summary(g.name, crit) if cint(s.teammate_ratings) else {},
			}
		)
	reviews = []
	progress = {}
	if cint(s.peer_review):
		for rv in _reviews(row):
			reviews.append(
				{
					"name": rv.name,
					"reviewer": rv.reviewer,
					"reviewer_name": names.get(rv.reviewer) or _name(rv.reviewer),
					"work": _work_label(rv.activity_group, rv.author, frappe._dict(review_anonymous=0)),
					"work_key": _item_key(rv),
					"status": rv.status,
					"extra": cint(rv.extra),
					"hidden": cint(rv.hidden),
					"credit_withdrawn": cint(rv.credit_withdrawn),
					"submitted_on": rv.submitted_on,
				}
			)
			p = progress.setdefault(rv.reviewer, {"assigned": 0, "done": 0})
			if not cint(rv.extra):
				p["assigned"] += 1
			if rv.status == "Submitted":
				p["done"] += 1
	items = []
	if cint(s.peer_review):
		load = {}
		for r in reviews:
			load[r["work_key"]] = load.get(r["work_key"], 0) + 1
		for it in work_items(row, activity_doctype).values():
			items.append(
				{
					"key": it.key,
					"submission": it.submission,
					"label": _work_label(it.group, it.author, frappe._dict(review_anonymous=0)),
					"reviews": load.get(it.key, 0),
					"authors": sorted(it.authors),
				}
			)
	return {
		"settings": {
			k: s.get(k)
			for k in (
				"title",
				"is_group_work",
				"topic_mode",
				"peer_review",
				"reviews_per_student",
				"review_opens",
				"review_due_days",
				"review_anonymous",
				"review_form",
				"teammate_ratings",
				"ratings_shown",
				"review_share",
				"group_size",
			)
		}
		| {"group_source": group_work.default_source(course, s) if s.is_group_work else None},
		"row": {
			"name": row.name,
			"due_date": row.due_date,
			"cutoff_date": row.cutoff_date,
			"review_opened_on": row.review_opened_on,
			"review_due_on": row.review_due_on,
			"reviews_released_on": row.reviews_released_on,
			"signup_closes_on": scac.signup_closes_on,
			"topics_close_on": scac.topics_close_on,
		},
		"students": people,
		"groups": groups,
		"ungrouped": [p for p in people if p["student"] not in grouped] if s.is_group_work else [],
		"topics": group_work.topics(course, activity_doctype, activity),
		"reviews": reviews,
		"review_progress": progress,
		"work": items,
		"criteria": crit,
		"may_edit": _may_edit(course),
	}


def _may_edit(course):
	from seminary.seminary.guards import GRADE, may_act

	return may_act(course, GRADE)


@frappe.whitelist(methods=["POST"])
def save_group(
	course: str,
	activity_doctype: str,
	activity: str,
	group_name: str,
	students: str | list | dict | None = None,
	group: str | None = None,
):
	"""Create a group, or rename one and set its members."""
	_staff(course)
	group_work.require_row(course, activity_doctype, activity)
	students = [s for s in (_parse(students, []) or [])]
	known = {p["student"] for p in group_work.roster(course)}
	students = [s for s in students if s in known]
	if not group:
		doc = group_work.make_group(course, activity_doctype, activity, group_name, students)
		return {"group": doc.name}
	g = frappe.get_doc(GROUP, group)
	if (g.course_schedule, g.activity) != (course, activity):
		frappe.throw(_("This group is not on this activity."))
	if group_name and group_name != g.group_name:
		g.group_name = group_name[:140]
		g.save(ignore_permissions=True)
		group_work.on_rename(group, g.group_name)
	current = set(group_work.active_members(group))
	for s_ in current - set(students):
		group_work.remove_member(group, s_)
	for s_ in students:
		if s_ not in current:
			group_work.add_member(group, s_)
	return {"group": group}


@frappe.whitelist(methods=["POST"])
def move_member(course: str, activity_doctype: str, activity: str, student: str, group: str | None = None):
	"""Move a student to ``group``, or out of every group with none."""
	_staff(course)
	if group:
		g = frappe.db.get_value(GROUP, group, ["course_schedule", "activity"])
		if g != (course, activity):
			frappe.throw(_("This group is not on this activity."))
		group_work.add_member(group, student)
	else:
		current = group_work.group_of(course, activity_doctype, activity, student)
		if current:
			group_work.remove_member(current, student)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def delete_group(group: str):
	_require_grader()
	course = frappe.db.get_value(GROUP, group, "course_schedule")
	_staff(course)
	group_work.delete_group(group)
	return {"deleted": group}


@frappe.whitelist(methods=["POST"])
def make_groups(
	course: str,
	activity_doctype: str,
	activity: str,
	source: str,
	size: int | str | None = None,
	count: int | str | None = None,
):
	"""Make the groups in one step: from the section's groups, at random by
	size, or ``count`` empty groups for students to sign up to. Groups that
	have handed in work are kept; the others are replaced."""
	_staff(course)
	group_work.require_row(course, activity_doctype, activity)
	if not group_work.is_group_work(activity_doctype, activity):
		frappe.throw(_("This activity is not group work."))
	existing = group_work.group_rows(course, activity_doctype, activity)
	if any(group_work.has_work(g.name) for g in existing):
		frappe.throw(_("Some groups have handed in work. Move students one by one instead."))
	for g in existing:
		group_work.delete_group(g.name)
	if source in ("Section groups", "Random"):
		group_work.make_auto_groups(course, activity_doctype, activity, source, size)
	elif source == "Empty":
		for n in range(1, max(1, cint(count)) + 1):
			group_work.make_group(
				course, activity_doctype, activity, _("Group {0}").format(n), [], "Self sign-up"
			)
	else:
		frappe.throw(_("Choose how to make the groups."))
	return {"groups": len(group_work.group_rows(course, activity_doctype, activity))}


@frappe.whitelist(methods=["POST"])
def save_topics(course: str, activity_doctype: str, activity: str, topics: str | list | dict):
	"""Upsert the section's topics; a topic left out is deleted unless held."""
	_staff(course)
	group_work.require_row(course, activity_doctype, activity)
	keep = set()
	for n, t in enumerate(_parse(topics, []) or [], start=1):
		title = (t.get("title") or "").strip()
		if not title:
			continue
		name = t.get("name")
		doc = frappe.get_doc(group_work.TOPIC, name) if name else frappe.new_doc(group_work.TOPIC)
		if name and (doc.course_schedule, doc.activity) != (course, activity):
			frappe.throw(_("This topic belongs to another activity."))
		doc.update(
			{
				"course_schedule": course,
				"activity_doctype": activity_doctype,
				"activity": activity,
				"title": title[:140],
				"description": (t.get("description") or "")[:2000] or None,
				"capacity": max(1, cint(t.get("capacity")) or 1),
				"sort_order": n,
			}
		)
		doc.save(ignore_permissions=True)
		keep.add(doc.name)
	held = group_work.holders(course, activity_doctype, activity)
	for t in group_work.topics(course, activity_doctype, activity):
		if t.name in keep:
			continue
		if held.get(t.name):
			frappe.throw(
				_("{0} is held, so it cannot be removed. Give its holders another topic first.").format(
					t.title
				)
			)
		frappe.delete_doc(group_work.TOPIC, t.name, ignore_permissions=True)
	return group_work.topics(course, activity_doctype, activity)


@frappe.whitelist(methods=["POST"])
def assign_topic(course: str, activity_doctype: str, activity: str, holder: str, topic: str | None = None):
	"""Give a topic to a group or student by hand, or take it away."""
	_staff(course)
	if topic:
		if frappe.db.get_value(group_work.TOPIC, topic, ["course_schedule", "activity"]) != (
			course,
			activity,
		):
			frappe.throw(_("This topic is not on this activity."))
		group_work.give_topic(topic, holder, chosen_by="Instructor")
	else:
		group_work.clear_topic(course, activity_doctype, activity, holder)
	return group_work.topics(course, activity_doctype, activity)


@frappe.whitelist(methods=["POST"])
def draw_topics(course: str, activity_doctype: str, activity: str):
	_staff(course)
	group_work.require_row(course, activity_doctype, activity)
	return {"given": group_work.random_topics(course, activity_doctype, activity)}


@frappe.whitelist(methods=["POST"])
def set_windows(
	course: str,
	activity_doctype: str,
	activity: str,
	signup_closes_on: str | None = None,
	topics_close_on: str | None = None,
):
	"""When group sign-up and topic choice close on this section."""
	_staff(course)
	row = group_work.require_row(course, activity_doctype, activity)
	frappe.db.set_value(
		SCAC,
		row.name,
		{
			"signup_closes_on": get_datetime(signup_closes_on) if signup_closes_on else None,
			"topics_close_on": get_datetime(topics_close_on) if topics_close_on else None,
		},
		update_modified=False,
	)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def open_now(course: str, activity_doctype: str, activity: str):
	_staff(course)
	s = group_work.settings(activity_doctype, activity)
	if not (cint(s.peer_review) or cint(s.teammate_ratings)):
		frappe.throw(_("This activity has neither peer review nor teammate ratings."))
	row = open_round(_row_for(course, activity_doctype, activity), s)
	return {"review_opened_on": row.review_opened_on, "review_due_on": row.review_due_on}


@frappe.whitelist(methods=["POST"])
def release_now(course: str, activity_doctype: str, activity: str):
	_staff(course)
	s = group_work.settings(activity_doctype, activity)
	row = _row_for(course, activity_doctype, activity)
	if not row.review_opened_on:
		frappe.throw(_("Reviews have not opened yet."))
	row = release(row, s)
	return {"reviews_released_on": row.reviews_released_on}


@frappe.whitelist(methods=["POST"])
def assign_review(course: str, activity_doctype: str, activity: str, work: str, reviewer: str):
	"""The instructor gives a piece of work (a group or a student, by its
	key) to a reviewer."""
	_staff(course)
	s = group_work.settings(activity_doctype, activity)
	row = _row_for(course, activity_doctype, activity)
	if not row.review_opened_on:
		frappe.throw(_("Reviews have not opened yet."))
	items = work_items(row, activity_doctype)
	item = items.get(work)
	if not item:
		frappe.throw(_("This work has not been handed in."))
	if reviewer in item.authors:
		frappe.throw(_("Students do not review their own work."))
	if reviewer not in {p["student"] for p in group_work.roster(course)}:
		frappe.throw(_("The reviewer is not on this section."))
	if any(_item_key(r) == work for r in _reviews(row, reviewer=reviewer)):
		frappe.throw(_("This student already reviews this work."))
	doc = _insert_review(row, activity_doctype, activity, item, reviewer, assigned_by="Instructor")
	refresh_credit(row, s, {reviewer})
	_notify(
		reviewer,
		_("Peer review to do: {0}").format(s.title or row.title or ""),
		_("You have a classmate's work to review for {0}.").format(s.title or row.title or ""),
		course,
		f"peer-review-assigned-{doc.name}",
	)
	return {"review": doc.name}


@frappe.whitelist(methods=["POST"])
def remove_review(review: str):
	_require_grader()
	doc = frappe.get_doc(REVIEW, review)
	_staff(doc.course_schedule)
	if doc.status == "Submitted":
		frappe.throw(_("This review was handed in. Hide it instead."))
	frappe.delete_doc(REVIEW, review, ignore_permissions=True)
	row = _row(doc.course_assess)
	if row:
		refresh_credit(row, group_work.settings(doc.activity_doctype, doc.activity), {doc.reviewer})
	return {"deleted": review}


@frappe.whitelist(methods=["POST"])
def moderate_review(review: str, hidden: int | str | None = None, credit_withdrawn: int | str | None = None):
	"""Hide a review from its authors, or withdraw its credit (§5)."""
	_require_grader()
	doc = frappe.get_doc(REVIEW, review)
	_staff(doc.course_schedule)
	if hidden is not None:
		doc.hidden = cint(hidden)
	if credit_withdrawn is not None:
		doc.credit_withdrawn = cint(credit_withdrawn)
	doc.save(ignore_permissions=True)
	row = _row(doc.course_assess)
	if row:
		refresh_credit(row, group_work.settings(doc.activity_doctype, doc.activity), {doc.reviewer})
	return {"hidden": doc.hidden, "credit_withdrawn": doc.credit_withdrawn}


@frappe.whitelist(methods=["POST"])
def extend_for_group(group: str, due_date: str, cutoff_date: str | None = None, reason: str | None = None):
	_require_grader()
	course = frappe.db.get_value(GROUP, group, "course_schedule")
	_staff(course)
	group_work.extend_group(group, due_date, cutoff_date, reason)
	return {"ok": True}


def _submission(submission_doctype, submission):
	if submission_doctype not in ACTIVITY_OF:
		frappe.throw(_("Group work is only for assignments and oral activities."))
	return frappe.get_doc(submission_doctype, submission)


@frappe.whitelist()
def get_grading(submission_doctype: str, submission: str):
	"""For the grading panel: the group, its members' records, the ratings
	about them, and this student's review credit."""
	_require_grader()
	doc = _submission(submission_doctype, submission)
	_staff(doc.course, write=False)
	adt, field = ACTIVITY_OF[submission_doctype]
	s = group_work.settings(adt, doc.get(field))
	row = _row(doc.course_assess)
	out = {
		"group": None,
		"topic": doc.get("topic_title"),
		"review_share": flt(s.review_share),
		"review_credit": credit(row, s, doc.student) if row else None,
		"review_credit_override": cint(doc.get("review_credit_override")),
		"stored_credit": flt(doc.get("review_credit")),
		"grade_override": cint(doc.get("grade_override")),
		"reviews_received": [],
	}
	if doc.get("activity_group"):
		g = doc.activity_group
		members = []
		for m in group_work.active_members(g):
			name = group_work.find_submission(submission_doctype, field, doc.get(field), doc.course, m)
			sub = (
				frappe.db.get_value(
					submission_doctype,
					name,
					["name", "grade", "status"]
					+ (["grade_override"] if submission_doctype == "Assignment Submission" else []),
					as_dict=True,
				)
				if name
				else None
			)
			members.append({"student": m, "name": _name(m), "submission": sub})
		out["group"] = {
			"name": g,
			"group_name": frappe.db.get_value(GROUP, g, "group_name"),
			"members": members,
			"ratings": ratings_summary(g) if cint(s.teammate_ratings) else {},
			"criteria": criteria(),
		}
	if row and cint(s.peer_review):
		filters = {"status": "Submitted"}
		if doc.get("activity_group"):
			filters["activity_group"] = doc.activity_group
		else:
			filters["author"] = doc.student
		out["reviews_received"] = [
			_review_out(frappe.get_doc(REVIEW, r.name), s, None, staff=True) for r in _reviews(row, **filters)
		]
	return out


@frappe.whitelist(methods=["POST"])
def set_separate_grade(submission: str, separate: int | str):
	"""Grade one member on their own (§4), or put them back on the group's
	grade, which is copied back from a member still on it."""
	_require_grader()
	doc = _submission("Assignment Submission", submission)
	_staff(doc.course)
	doc.grade_override = cint(separate)
	if not cint(separate) and doc.activity_group:
		for name in group_work.siblings(doc):
			other = frappe.get_doc(doc.doctype, name)
			if not cint(other.grade_override):
				for f in group_work.GRADER_FIELDS[doc.doctype]:
					doc.set(f, other.get(f))
				group_work._copy_rubric_scores(other, doc)
				break
	doc.flags.group_copy = True
	doc.save(ignore_permissions=True)
	return {"grade_override": doc.grade_override, "grade": doc.grade}


@frappe.whitelist(methods=["POST"])
def set_review_credit(
	submission_doctype: str, submission: str, credit_value: int | float | str | None = None
):
	"""The instructor sets one student's review part (§7); none puts it back
	on the computed credit."""
	_require_grader()
	doc = _submission(submission_doctype, submission)
	_staff(doc.course)
	if credit_value in (None, ""):
		doc.review_credit_override = 0
	else:
		value = flt(credit_value)
		if not 0 <= value <= 100:
			frappe.throw(_("Review credit is a percent from 0 to 100."))
		doc.review_credit_override = 1
		doc.review_credit = value
	doc.flags.group_copy = True
	doc.save(ignore_permissions=True)
	return {"review_credit": doc.review_credit, "percentage": doc.percentage}
