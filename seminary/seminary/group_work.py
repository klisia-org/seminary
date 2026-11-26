# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Group work and topics on assignments and oral activities (decisions/120).

* An **Activity Group** is a set of students doing one activity together on
  one section (§2). Section student groups keep splitting grading; these sit
  beside them.
* An **Activity Topic** is a section's topic on one activity, held by a group
  or, on individual work, by a student through a **Topic Choice** (§3).
* A group hands in **one submission, saved on every member's record** (§4):
  the submitting member's content, and the grader's grade, rubric and
  comments, are copied to the other active members. A member graded
  separately (``grade_override``) keeps their own grade.

Peer review and teammate ratings are in ``peer_reviews``.
"""

import random

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

ASSIGNMENT = "Assignment Activity"
ORAL = "Oral Activity"
ACTIVITY_DOCTYPES = (ASSIGNMENT, ORAL)
GROUP = "Activity Group"
TOPIC = "Activity Topic"
CHOICE = "Topic Choice"
SCAC = "Scheduled Course Assess Criteria"

# activity doctype -> (submission doctype, submission's activity field, SCAC field)
SUBMISSION = {
	ASSIGNMENT: ("Assignment Submission", "assignment", "assignment"),
	ORAL: ("Oral Activity Submission", "oral_activity", "oral"),
}
ACTIVITY_OF = {sub: (adt, field) for adt, (sub, field, _s) in SUBMISSION.items()}

SETTINGS_FIELDS = (
	"group_source",
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
	"rubric",
	"title",
)

# What a member hands in, and what a grader writes, per submission doctype.
CONTENT_FIELDS = {
	"Assignment Submission": ("type", "answer", "assignment_attachment", "submitted_on", "late"),
	"Oral Activity Submission": ("recording", "activity_meeting", "submitted_on", "late"),
}
GRADER_FIELDS = {
	"Assignment Submission": ("grade", "status", "comments", "comment_attach", "evaluator", "graded_on"),
	"Oral Activity Submission": ("grade", "status", "comments", "evaluator", "graded_on"),
}


# ------------------------------------------------------------------ settings


def _check_doctype(activity_doctype):
	if activity_doctype not in ACTIVITY_DOCTYPES:
		frappe.throw(_("Group work is only for assignments and oral activities."))


def settings(activity_doctype, activity):
	"""The activity's group, topic and review settings (§1)."""
	_check_doctype(activity_doctype)
	fields = [f for f in SETTINGS_FIELDS if frappe.get_meta(activity_doctype).has_field(f)]
	extra = ["group_work"] if activity_doctype == ASSIGNMENT else ["mode"]
	row = frappe.db.get_value(activity_doctype, activity, fields + extra, as_dict=True)
	if not row:
		frappe.throw(_("{0} {1} does not exist.").format(_(activity_doctype), activity))
	row.activity_doctype = activity_doctype
	row.activity = activity
	row.is_group_work = bool(
		cint(row.get("group_work")) if activity_doctype == ASSIGNMENT else row.get("mode") == "Conversation"
	)
	return row


def is_group_work(activity_doctype, activity):
	return settings(activity_doctype, activity).is_group_work


def scac_row(course_schedule, activity_doctype, activity):
	"""The assessment row that puts the activity on this section, or None."""
	field = SUBMISSION[activity_doctype][2]
	return frappe.db.get_value(
		SCAC,
		{"parent": course_schedule, "parenttype": "Course Schedule", field: activity},
		[
			"name",
			"parent",
			"title",
			"due_date",
			"cutoff_date",
			"signup_closes_on",
			"topics_close_on",
			"review_opened_on",
			"review_due_on",
			"reviews_released_on",
		],
		as_dict=True,
	)


def require_row(course_schedule, activity_doctype, activity):
	row = scac_row(course_schedule, activity_doctype, activity)
	if not row:
		frappe.throw(_("This activity is not part of this section's assessments."))
	return row


# ------------------------------------------------------------------ people


def roster(course_schedule):
	"""The section's active, non-audit students: [{student, name, user}]."""
	out = []
	for r in frappe.get_all(
		"Scheduled Course Roster",
		filters={"course_sc": course_schedule, "active": 1, "audit_bool": 0},
		fields=["student", "stuname_roster", "stuemail_rc"],
		order_by="stuname_roster asc",
	):
		if r.student:
			out.append({"student": r.student, "name": r.stuname_roster or r.student, "user": r.stuemail_rc})
	return out


def student_user(student):
	return frappe.db.get_value("Student", student, "user")


def _members(group_name, active_only=True):
	filters = {"parent": group_name, "parenttype": GROUP}
	if active_only:
		filters["left_on"] = ["is", "not set"]
	return frappe.get_all(
		"Activity Group Member",
		filters=filters,
		fields=["name", "student", "student_name", "joined_on", "left_on"],
		order_by="idx asc",
	)


def active_members(group_name):
	"""The members who have not left and are still on the section's roster."""
	cs = frappe.db.get_value(GROUP, group_name, "course_schedule")
	on_roster = {r["student"] for r in roster(cs)} if cs else set()
	return [m.student for m in _members(group_name) if m.student in on_roster]


def group_rows(course_schedule, activity_doctype, activity):
	return frappe.get_all(
		GROUP,
		filters={
			"course_schedule": course_schedule,
			"activity_doctype": activity_doctype,
			"activity": activity,
		},
		fields=["name", "group_name", "topic", "source"],
		order_by="creation asc, name asc",
	)


def group_of(course_schedule, activity_doctype, activity, student):
	"""The group this student is in now on this activity, or None."""
	if not student:
		return None
	rows = frappe.db.sql(
		"""select g.name from `tabActivity Group` g
		join `tabActivity Group Member` m on m.parent = g.name and m.parenttype = 'Activity Group'
		where g.course_schedule = %s and g.activity_doctype = %s and g.activity = %s
		  and m.student = %s and m.left_on is null
		order by g.creation asc limit 1""",
		(course_schedule, activity_doctype, activity, student),
	)
	return rows[0][0] if rows else None


def fire(group, event):
	"""``activity_group_changed`` (§9): another app may give the group a
	workspace. A failing listener is logged and never blocks the change."""
	doc = frappe.get_doc(GROUP, group) if isinstance(group, str) else group
	for path in frappe.get_hooks("activity_group_changed") or []:
		try:
			frappe.get_attr(path)(doc, event)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"activity_group_changed listener {path} failed")


# ------------------------------------------------------------------ making groups


def _lock_section(course_schedule):
	frappe.db.sql("select name from `tabCourse Schedule` where name = %s for update", (course_schedule,))


def make_group(
	course_schedule, activity_doctype, activity, group_name, students, source="By hand", topic=None
):
	"""Insert one group; a student already in another group of this activity
	is moved out of it first."""
	at = now_datetime()
	for s in students:
		_leave(course_schedule, activity_doctype, activity, s, at)
	doc = frappe.get_doc(
		{
			"doctype": GROUP,
			"course_schedule": course_schedule,
			"activity_doctype": activity_doctype,
			"activity": activity,
			"group_name": (group_name or "")[:140] or _("Group"),
			"source": source,
			"topic": topic,
			"members": [{"student": s, "joined_on": at} for s in students],
		}
	)
	doc.insert(ignore_permissions=True)
	fire(doc, "created")
	return doc


def _leave(course_schedule, activity_doctype, activity, student, at=None):
	"""Close the student's membership in their current group, if any."""
	current = group_of(course_schedule, activity_doctype, activity, student)
	if not current:
		return None
	frappe.db.set_value(
		"Activity Group Member",
		{"parent": current, "parenttype": GROUP, "student": student, "left_on": ["is", "not set"]},
		"left_on",
		at or now_datetime(),
	)
	fire(current, "members")
	return current


def add_member(group, student):
	"""Put the student in ``group`` (out of any other group of the activity)
	and give them the group's current work (§4)."""
	g = frappe.get_doc(GROUP, group)
	if group_of(g.course_schedule, g.activity_doctype, g.activity, student) == group:
		return g
	at = now_datetime()
	_leave(g.course_schedule, g.activity_doctype, g.activity, student, at)
	g.reload()
	g.append("members", {"student": student, "joined_on": at})
	g.save(ignore_permissions=True)
	fire(g, "members")
	give_current_work(g.name, student)
	return g


def remove_member(group, student):
	g = frappe.get_doc(GROUP, group)
	_leave(g.course_schedule, g.activity_doctype, g.activity, student)


def _chunks(people, size):
	size = max(1, cint(size))
	chunks = [people[i : i + size] for i in range(0, len(people), size)]
	if len(chunks) > 1 and len(chunks[-1]) == 1 and size > 1:
		chunks[-2].extend(chunks.pop())
	return chunks


def section_groups(course_schedule):
	"""{Student Group: [student]} from the section's student groups (097)."""
	from seminary.seminary.oral_activities import _section_groups

	return _section_groups(course_schedule)


def default_source(course_schedule, s):
	"""What makes the groups when the activity does not say: an oral
	conversation keeps 100b's rule (the section's groups, else random groups
	of its size); an assignment is grouped by hand."""
	if s.get("group_source"):
		return s.group_source
	if s.activity_doctype == ORAL:
		return "Section groups" if section_groups(course_schedule) else "Random"
	return "By hand"


def ensure_groups(course_schedule, activity_doctype, activity):
	"""Make the groups the activity's source makes on its own (*Section
	groups*, *Random*) the first time they are needed. Groups made by hand or
	by sign-up are left to people. Returns the section's groups."""
	s = settings(activity_doctype, activity)
	if not s.is_group_work:
		return []
	existing = group_rows(course_schedule, activity_doctype, activity)
	if existing:
		return existing
	source = default_source(course_schedule, s)
	if source not in ("Section groups", "Random"):
		return existing
	_lock_section(course_schedule)
	existing = group_rows(course_schedule, activity_doctype, activity)
	if existing:
		return existing
	make_auto_groups(course_schedule, activity_doctype, activity, source, s.get("group_size"))
	return group_rows(course_schedule, activity_doctype, activity)


def make_auto_groups(course_schedule, activity_doctype, activity, source, size=None):
	people = roster(course_schedule)
	known = {p["student"] for p in people}
	if source == "Section groups":
		for sg, members in section_groups(course_schedule).items():
			students = [m for m in members if m in known]
			if students:
				name = frappe.db.get_value("Student Group", sg, "group_name") or sg
				make_group(course_schedule, activity_doctype, activity, name, students, source)
		return
	if source == "Random":
		if cint(size) < 2 or len(people) < 2:
			return
		# A fair, repeatable shuffle for grouping, not a secret.
		random.Random(f"{course_schedule}|{activity}").shuffle(people)  # nosec B311
		for n, chunk in enumerate(_chunks(people, size), start=1):
			make_group(
				course_schedule,
				activity_doctype,
				activity,
				_("Group {0}").format(n),
				[p["student"] for p in chunk],
				source,
			)


def has_work(group):
	"""Has anyone in the group handed anything in?"""
	g = frappe.db.get_value(GROUP, group, ["activity_doctype", "activity"], as_dict=True)
	sub_dt = SUBMISSION[g.activity_doctype][0]
	return bool(frappe.db.exists(sub_dt, {"activity_group": group}))


def delete_group(group):
	if has_work(group):
		frappe.throw(_("This group has handed in work, so it cannot be deleted. Move its members instead."))
	doc = frappe.get_doc(GROUP, group)
	fire(doc, "deleted")
	frappe.delete_doc(GROUP, group, ignore_permissions=True)


# ------------------------------------------------------------------ topics


def topics(course_schedule, activity_doctype, activity):
	rows = frappe.get_all(
		TOPIC,
		filters={
			"course_schedule": course_schedule,
			"activity_doctype": activity_doctype,
			"activity": activity,
		},
		fields=["name", "title", "description", "capacity", "sort_order"],
		order_by="sort_order asc, creation asc",
	)
	held = holders(course_schedule, activity_doctype, activity)
	for r in rows:
		r["holders"] = held.get(r.name, [])
		r["taken"] = len(r["holders"])
		r["capacity"] = max(1, cint(r.capacity))
	return rows


def holders(course_schedule, activity_doctype, activity):
	"""{topic: [{kind, name, label}]}: groups holding it, or students on
	individual work."""
	out = {}
	if is_group_work(activity_doctype, activity):
		for g in group_rows(course_schedule, activity_doctype, activity):
			if g.topic:
				out.setdefault(g.topic, []).append({"kind": "group", "name": g.name, "label": g.group_name})
	else:
		for c in frappe.get_all(
			CHOICE,
			filters={
				"course_schedule": course_schedule,
				"activity_doctype": activity_doctype,
				"activity": activity,
			},
			fields=["student", "student_name", "topic"],
		):
			out.setdefault(c.topic, []).append(
				{"kind": "student", "name": c.student, "label": c.student_name or c.student}
			)
	return out


def topic_of(course_schedule, activity_doctype, activity, student, group=None):
	"""The topic this student (or their group) holds, or None."""
	if group:
		return frappe.db.get_value(GROUP, group, "topic")
	return frappe.db.get_value(
		CHOICE,
		{
			"course_schedule": course_schedule,
			"activity_doctype": activity_doctype,
			"activity": activity,
			"student": student,
		},
		"topic",
	)


def give_topic(topic, holder, chosen_by="Instructor"):
	"""Give ``topic`` to ``holder`` (an Activity Group, or a Student on
	individual work), within its capacity. The topic row is locked so two
	students choosing at once cannot both take its last place."""
	t = frappe.db.sql(
		"""select name, course_schedule, activity_doctype, activity, capacity
		from `tabActivity Topic` where name = %s for update""",
		(topic,),
		as_dict=True,
	)
	if not t:
		frappe.throw(_("This topic no longer exists."))
	t = t[0]
	group_work = is_group_work(t.activity_doctype, t.activity)
	taken = [
		h
		for h in holders(t.course_schedule, t.activity_doctype, t.activity).get(topic, [])
		if h["name"] != holder
	]
	if len(taken) >= max(1, cint(t.capacity)):
		frappe.throw(_("This topic is already taken."))
	if group_work:
		g = frappe.get_doc(GROUP, holder)
		if (g.course_schedule, g.activity) != (t.course_schedule, t.activity):
			frappe.throw(_("This topic belongs to another activity."))
		g.topic = topic
		g.save(ignore_permissions=True)
		fire(g, "topic")
		_restamp_topic(t, group=holder)
		return
	name = frappe.db.get_value(
		CHOICE,
		{
			"course_schedule": t.course_schedule,
			"activity_doctype": t.activity_doctype,
			"activity": t.activity,
			"student": holder,
		},
	)
	doc = frappe.get_doc(CHOICE, name) if name else frappe.new_doc(CHOICE)
	doc.update(
		{
			"course_schedule": t.course_schedule,
			"activity_doctype": t.activity_doctype,
			"activity": t.activity,
			"student": holder,
			"topic": topic,
			"chosen_by": chosen_by,
		}
	)
	doc.save(ignore_permissions=True)
	_restamp_topic(t, student=holder)


def clear_topic(course_schedule, activity_doctype, activity, holder):
	if is_group_work(activity_doctype, activity):
		frappe.db.set_value(GROUP, holder, "topic", None)
		_restamp_topic(
			frappe._dict(
				course_schedule=course_schedule, activity_doctype=activity_doctype, activity=activity
			),
			group=holder,
		)
		return
	frappe.db.delete(
		CHOICE,
		{
			"course_schedule": course_schedule,
			"activity_doctype": activity_doctype,
			"activity": activity,
			"student": holder,
		},
	)
	_restamp_topic(
		frappe._dict(course_schedule=course_schedule, activity_doctype=activity_doctype, activity=activity),
		student=holder,
	)


def _restamp_topic(t, group=None, student=None):
	"""Keep the topic shown on submissions already handed in."""
	sub_dt, field, _s = SUBMISSION[t.activity_doctype]
	filters = {"course": t.course_schedule, field: t.activity}
	if group:
		filters["activity_group"] = group
		topic = frappe.db.get_value(GROUP, group, "topic")
	else:
		filters["student"] = student
		topic = topic_of(t.course_schedule, t.activity_doctype, t.activity, student)
	title = frappe.db.get_value(TOPIC, topic, "title") if topic else None
	for name in frappe.get_all(sub_dt, filters=filters, pluck="name"):
		frappe.db.set_value(sub_dt, name, {"topic": topic, "topic_title": title}, update_modified=False)


def random_topics(course_schedule, activity_doctype, activity):
	"""Give every holder without a topic a free one, at random."""
	rows = topics(course_schedule, activity_doctype, activity)
	free = []
	for r in rows:
		free.extend([r.name] * max(0, r.capacity - r.taken))
	if is_group_work(activity_doctype, activity):
		waiting = [g.name for g in group_rows(course_schedule, activity_doctype, activity) if not g.topic]
	else:
		have = {h["name"] for r in rows for h in r["holders"]}
		waiting = [p["student"] for p in roster(course_schedule) if p["student"] not in have]
	# A fair, repeatable draw, not a secret.
	rng = random.Random(f"{course_schedule}|{activity}|topics")  # nosec B311
	rng.shuffle(free)
	given = 0
	for holder, topic in zip(waiting, free, strict=False):
		give_topic(topic, holder, chosen_by="Random")
		given += 1
	return given


def copy_topics(source_cs, target_cs, scac_name_map=None):
	"""Template import (§3): the target section gets the source's topics for
	the activities they share. Held topics are copied unheld."""
	for t in frappe.get_all(
		TOPIC,
		filters={"course_schedule": source_cs},
		fields=["activity_doctype", "activity", "title", "description", "capacity", "sort_order"],
		order_by="sort_order asc, creation asc",
	):
		if not scac_row(target_cs, t.activity_doctype, t.activity):
			continue
		frappe.get_doc({"doctype": TOPIC, "course_schedule": target_cs, **t}).insert(ignore_permissions=True)


def window_open(closes_on, at=None):
	if not closes_on:
		return True
	return (get_datetime(at) if at else now_datetime()) <= get_datetime(closes_on)


# ------------------------------------------------------------------ submissions


def stamp(doc):
	"""Submission validate (§3, §4): which group the work is for, and its
	topic. A member who left keeps the group they handed in with."""
	adt, field = ACTIVITY_OF[doc.doctype]
	activity = doc.get(field)
	cs = doc.get("course")
	if not (activity and cs and doc.get("student")):
		return
	if not doc.get("activity_group") and is_group_work(adt, activity):
		doc.activity_group = group_of(cs, adt, activity, doc.student)
	if doc.get("activity_group"):
		doc.group_name = frappe.db.get_value(GROUP, doc.activity_group, "group_name")
	topic = topic_of(cs, adt, activity, doc.student, group=doc.get("activity_group"))
	if topic != doc.get("topic"):
		doc.topic = topic
		doc.topic_title = frappe.db.get_value(TOPIC, topic, "title") if topic else None


def _changed(doc, before, fields):
	if before is None:
		return True
	return any(doc.get(f) != before.get(f) for f in fields)


def find_submission(sub_dt, field, activity, course_schedule, student):
	return frappe.db.get_value(
		sub_dt,
		{field: activity, "course": course_schedule, "student": student},
		"name",
		order_by="creation desc",
	)


def _copy_rubric_scores(source, target):
	"""The grader's rubric levels, so the target's grade derives the same way."""
	frappe.db.delete("Rubric Score", {"submission_doctype": target.doctype, "submission": target.name})
	for s in frappe.get_all(
		"Rubric Score",
		filters={"submission_doctype": source.doctype, "submission": source.name},
		fields=["rubric", "criterion_code", "level", "comment"],
	):
		frappe.get_doc(
			{
				"doctype": "Rubric Score",
				"submission_doctype": target.doctype,
				"submission": target.name,
				**s,
			}
		).insert(ignore_permissions=True)


def _own(twin):
	"""The member owns their record of the group's work, so they can edit it
	as their own until it is graded. Insert sets the session user."""
	if twin.owner != twin.member:
		frappe.db.set_value(twin.doctype, twin.name, "owner", twin.member, update_modified=False)
		twin.owner = twin.member


def _new_twin(doc, student):
	_adt, field = ACTIVITY_OF[doc.doctype]
	user = student_user(student)
	if not user:
		return None
	twin = frappe.new_doc(doc.doctype)
	twin.update(
		{
			field: doc.get(field),
			"member": user,
			"student": student,
			"course": doc.course,
			"activity_group": doc.activity_group,
		}
	)
	if doc.doctype == "Assignment Submission":
		twin.lesson = doc.get("lesson")
		twin.status = "Not Graded"
	return twin


def propagate(doc, method=None):
	"""Submission on_update (§4): one piece of work, a record per member.

	The member's content goes to every other active member; the grader's
	grade, rubric levels and comments go to every member not graded
	separately. Copies are saved with ``group_copy`` set so they do not copy
	back."""
	# Oral conversations already give every participant their own record and
	# grade from one recording (100b); only assignments are copied.
	if doc.doctype != "Assignment Submission":
		return
	if doc.flags.group_copy or frappe.flags.seminary_group_copy or not doc.get("activity_group"):
		return
	members = active_members(doc.activity_group)
	if doc.student not in members:
		return
	before = doc.get_doc_before_save()
	content = _changed(doc, before, CONTENT_FIELDS[doc.doctype])
	grading = not cint(doc.get("grade_override")) and _changed(doc, before, GRADER_FIELDS[doc.doctype])
	if not (content or grading):
		return
	_adt, field = ACTIVITY_OF[doc.doctype]
	frappe.flags.seminary_group_copy = True
	try:
		for student in members:
			if student == doc.student:
				continue
			name = find_submission(doc.doctype, field, doc.get(field), doc.course, student)
			twin = frappe.get_doc(doc.doctype, name) if name else _new_twin(doc, student)
			if twin is None:
				continue
			if content or twin.is_new():
				for f in CONTENT_FIELDS[doc.doctype]:
					twin.set(f, doc.get(f))
			separate = cint(twin.get("grade_override"))
			if grading and not separate and not twin.is_new():
				_copy_rubric_scores(doc, twin)
			if grading and not separate:
				for f in GRADER_FIELDS[doc.doctype]:
					twin.set(f, doc.get(f))
			twin.activity_group = doc.activity_group
			twin.flags.group_copy = True
			twin.flags.ignore_permissions = True
			twin.save(ignore_permissions=True)
			_own(twin)
			if grading and not separate and name is None:
				# A new twin had no name when the scores were due; give them now.
				_copy_rubric_scores(doc, twin)
	finally:
		frappe.flags.seminary_group_copy = False


def give_current_work(group, student):
	"""A member who joins gets the group's current work (§4)."""
	g = frappe.db.get_value(GROUP, group, ["course_schedule", "activity_doctype", "activity"], as_dict=True)
	sub_dt, field, _s = SUBMISSION[g.activity_doctype]
	latest = frappe.db.get_value(
		sub_dt,
		{"activity_group": group, "student": ["!=", student]},
		"name",
		order_by="modified desc",
	)
	if not latest:
		return
	source = frappe.get_doc(sub_dt, latest)
	name = find_submission(sub_dt, field, g.activity, g.course_schedule, student)
	twin = frappe.get_doc(sub_dt, name) if name else _new_twin(source, student)
	if twin is None:
		return
	for f in CONTENT_FIELDS[sub_dt]:
		twin.set(f, source.get(f))
	twin.activity_group = group
	if not cint(twin.get("grade_override")):
		for f in GRADER_FIELDS[sub_dt]:
			twin.set(f, source.get(f))
	twin.flags.group_copy = True
	frappe.flags.seminary_group_copy = True
	try:
		twin.save(ignore_permissions=True)
		_own(twin)
		if not cint(twin.get("grade_override")):
			_copy_rubric_scores(source, twin)
			twin.reload()
			twin.flags.group_copy = True
			twin.save(ignore_permissions=True)
	finally:
		frappe.flags.seminary_group_copy = False


def siblings(doc):
	"""The other active members' submissions for the same group work."""
	if not doc.get("activity_group"):
		return []
	_adt, field = ACTIVITY_OF[doc.doctype]
	out = []
	for student in active_members(doc.activity_group):
		if student == doc.student:
			continue
		name = find_submission(doc.doctype, field, doc.get(field), doc.course, student)
		if name:
			out.append(name)
	return out


# ------------------------------------------------------------------ due dates


def group_dates(row, group):
	"""The dates a group works to (§4): the activity's, unless every active
	member has an extension, then the earliest of theirs. One member's own
	override does not move the group."""
	from seminary.seminary import deadlines

	dates = deadlines.effective(row.name, None, row=row)
	if not dates:
		return None
	members = active_members(group)
	ovs = [deadlines.get_override(row.name, m) for m in members]
	if members and all(ov and ov.due_date for ov in ovs):
		dates.due_date = min(get_datetime(ov.due_date) for ov in ovs)
		cutoffs = [get_datetime(ov.cutoff_date) for ov in ovs if ov.cutoff_date]
		dates.cutoff_date = min(cutoffs) if len(cutoffs) == len(ovs) else row.cutoff_date
	return dates


def dates_for(doc, row=None):
	"""Group dates for a group submission, else None (the caller falls back
	to the student's own dates)."""
	group = doc.get("activity_group")
	if not group or doc.doctype not in ACTIVITY_OF:
		return None
	from seminary.seminary import deadlines

	row = row or deadlines._row(doc.get("course_assess"))
	return group_dates(row, group) if row else None


def extend_group(group, due_date, cutoff_date=None, reason=None):
	"""*Extend for the group*: an override for each active member at once."""
	from seminary.seminary import deadlines

	g = frappe.db.get_value(GROUP, group, ["course_schedule", "activity_doctype", "activity"], as_dict=True)
	row = require_row(g.course_schedule, g.activity_doctype, g.activity)
	due = get_datetime(due_date)
	if cutoff_date and get_datetime(cutoff_date) < due:
		frappe.throw(_("The cut-off cannot be before the due date."))
	for student in active_members(group):
		name = frappe.db.get_value(
			"Student Due Date Override", {"course_assess": row.name, "student": student}
		)
		ov = (
			frappe.get_doc("Student Due Date Override", name)
			if name
			else frappe.new_doc("Student Due Date Override")
		)
		if not name:
			ov.source = "Instructor"
		ov.update(
			{
				"course_schedule": g.course_schedule,
				"course_assess": row.name,
				"student": student,
				"due_date": due,
				"cutoff_date": get_datetime(cutoff_date) if cutoff_date else None,
				"reason": reason or ov.get("reason") or _("Extension for the group"),
			}
		)
		ov.save(ignore_permissions=True)
	deadlines.refresh(row.name)
	return row.name


def on_rename(group, group_name):
	"""A renamed group's name on the work already handed in."""
	adt = frappe.db.get_value(GROUP, group, "activity_doctype")
	sub_dt = SUBMISSION[adt][0]
	frappe.db.set_value(sub_dt, {"activity_group": group}, "group_name", group_name, update_modified=False)
