# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Sample records for the accessibility check on a test site (decision 102b §3).

`plan()` lists a route as not visited when the site has no record for it to open.
`seed()` adds those records: a partner organization with a portal contact, its job
and internship postings, the sample student's application to each, a discussion with
the student's post, a quiz submission and a recommendation request. They hang off the
course and the student `accessibility.samples()` already picks, so the pages show
real-looking content.

    bench --site <site> execute seminary.seminary.accessibility_seed.seed
    bench --site <site> execute seminary.seminary.accessibility_seed.purge

Everything it makes is marked (see "the marking" below), and it only ever reads the records
it didn't make. A second run finds what the first one made and creates nothing. It
sends no email and queues none: it refuses to commit if a run would add a row to the
email queue or to a communication table. Meant for test sites only.
"""

import contextlib

import frappe
from frappe import _

# ---------------------------------------------------------------- the marking
#
# Every row the seed makes carries the tag below, matched whole through Tag Link, so a run
# (or the tag filter on any Desk list) finds them all. Users and emails are at
# DOMAIN, and every title or name the seed chooses starts with PREFIX.
DOMAIN = "a11y-seed.example.test"
PREFIX = "Sample"
TAG = "a11y-seed"

#: The doctypes the seed writes to, in the order `purge()` deletes them.
SEEDED = (
	"Quiz Submission",
	"Discussion Submission",
	"Discussion Activity",
	"Recommendation Letter",
	"Internship Placement",
	"Internship Application",
	"Internship Position",
	"Internship Type",
	"Partner Job Application",
	"Partner Job Opening",
	"Partner Organization",
	"Alumni Profile",
	"Person",
	"Contact",
	"User",
)

#: Tables a seed run must leave as it found them (§3: it sends no email and queues none).
QUIET = ("Email Queue", "Communication", "Communication Log", "Notification Log")

#: Document hooks that stand down while the seed inserts: the school's communication
#: triggers, which would write to the sample student (an accepted internship, say), and
#: the gradebook bridge, so a sample submission never changes a real student's grade.
#: Validation still runs in full.
SILENCED = (
	"seminary.seminary.communication_triggers.process",
	"seminary.seminary.api.quizresult_to_card",
)

PARTNER_EMAIL = f"sample.partner@{DOMAIN}"
RECOMMENDER_EMAIL = f"sample.recommender@{DOMAIN}"
ALUMNUS_EMAIL = f"sample.alumnus@{DOMAIN}"


def _tagged(doctype):
	"""Names of `doctype` rows carrying exactly this seed's tag. Another app's seed may tag with
	a longer name that starts with this one, so the tag is matched whole, not as a substring."""
	return frappe.get_all("Tag Link", filters={"tag": TAG, "document_type": doctype}, pluck="document_name")


def _marked(doctype, filters=None):
	"""The name of the seed's row of `doctype` matching `filters`, or None."""
	names = set(_tagged(doctype))
	filters = dict(filters or {})
	if "name" in filters:
		# A lookup by name: keep it, and only within the seed's own rows.
		wanted = filters.pop("name")
		names &= {wanted} if isinstance(wanted, str) else set(names)
	if not names:
		return None
	rows = frappe.get_all(
		doctype,
		filters={**filters, "name": ["in", sorted(names)]},
		pluck="name",
		order_by="creation asc",
		limit=1,
	)
	return rows[0] if rows else None


def _mark(doc):
	from frappe.desk.doctype.tag.tag import add_tag

	add_tag(TAG, doc.doctype, doc.name)
	return doc.name


def _insert(values):
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc


def _adopt(created, doctype, filters):
	"""Mark the rows the app made on the seed's behalf, such as a placement."""
	for name in frappe.get_all(doctype, filters=filters, pluck="name"):
		if not _marked(doctype, {"name": name}):
			created.append((doctype, name))
			_mark(frappe.get_doc(doctype, name))


def _ensure(created, doctype, find, make):
	"""The seed's `doctype` row found by `find`, else a new one from `make()`."""
	name = _marked(doctype, find)
	if name:
		return name
	doc = make()
	created.append((doctype, doc.name))
	return _mark(doc)


@contextlib.contextmanager
def _quiet():
	"""No email, no notification, and no gradebook write while the seed inserts."""
	saved_hooks = frappe.get_doc_hooks()
	trimmed = {
		dt: {ev: [fn for fn in fns if fn not in SILENCED] for ev, fns in events.items()}
		for dt, events in saved_hooks.items()
	}
	muted = frappe.flags.mute_emails
	frappe.flags.mute_emails = True
	frappe.local.doc_events_hooks = trimmed
	try:
		yield
	finally:
		frappe.local.doc_events_hooks = saved_hooks
		frappe.flags.mute_emails = muted


def _counts():
	return {t: frappe.db.count(t) for t in QUIET if frappe.db.table_exists(t)}


# ---------------------------------------------------------------- seed


def seed():
	"""Add the sample records the accessibility check needs; return what it created."""
	from seminary.seminary import accessibility

	found = accessibility.samples()
	for key in ("course", "course_name", "student", "student_user", "instructor_user"):
		if key not in found:
			frappe.throw(
				_("This site has no sample {0} for the accessibility check to build on.").format(key)
			)

	before = _counts()
	created = []
	with _quiet():
		partner_person = _partner(created)
		org = _organization(created, partner_person)
		_jobs(created, org, found)
		_internships(created, org, partner_person, found)
		_discussion(created, found)
		_quiz_submission(created, found)
		_recommendation(created, found)
		_alumnus(created)

	after = _counts()
	noisy = {t: after[t] - before.get(t, 0) for t in after if after[t] != before.get(t, 0)}
	if noisy:
		frappe.db.rollback()
		frappe.throw(
			_("The sample records would have sent or queued messages ({0}), so none were kept.").format(
				", ".join(f"{t}: {n:+d}" for t, n in noisy.items())
			)
		)
	frappe.db.commit()  # nosemgrep -- a bench command; the check's browser reads these rows
	return {"created": [f"{dt} {name}" for dt, name in created]}


def _partner(created):
	"""A partner portal user and their Person."""

	def make_user():
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": PARTNER_EMAIL,
				"first_name": PREFIX,
				"last_name": "Partner Contact",
				"user_type": "Website User",
				"send_welcome_email": 0,
				"roles": [{"role": "Partner"}],
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		# Frappe gives a new user a Contact from a job queued for after the commit; make
		# it now, the same way, so this run marks it and a later run finds it.
		from frappe.core.doctype.user.user import create_contact

		create_contact(user, ignore_mandatory=True)
		return user

	user = _ensure(created, "User", {"name": PARTNER_EMAIL}, make_user)
	_adopt(created, "Contact", {"user": user})

	def make_person():
		from seminary.seminary.person import ensure_person

		return frappe.get_doc(
			"Person",
			ensure_person(email=PARTNER_EMAIL, user=user, first_name=PREFIX, last_name="Partner Contact"),
		)

	return _ensure(created, "Person", {"user": user}, make_person)


def _alumnus(created):
	"""A graduate with an Alumni Profile, which is what grants the Alumni role, so the alumni
	pages show what an alumnus sees rather than a student's access message."""

	def make_user():
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": ALUMNUS_EMAIL,
				"first_name": PREFIX,
				"last_name": "Alumnus",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		from frappe.core.doctype.user.user import create_contact

		create_contact(user, ignore_mandatory=True)
		return user

	user = _ensure(created, "User", {"name": ALUMNUS_EMAIL}, make_user)
	_adopt(created, "Contact", {"user": user})

	def make_person():
		from seminary.seminary.person import ensure_person

		return frappe.get_doc(
			"Person", ensure_person(email=ALUMNUS_EMAIL, user=user, first_name=PREFIX, last_name="Alumnus")
		)

	person = _ensure(created, "Person", {"user": user}, make_person)

	def make_profile():
		from seminary.seminary import intake

		return intake.make_alumni_profile(person)

	return _ensure(created, "Alumni Profile", {"user": user}, make_profile)


def _organization(created, person):
	return _ensure(
		created,
		"Partner Organization",
		{"organization_name": f"{PREFIX} Hope Community Church"},
		lambda: _insert(
			{
				"doctype": "Partner Organization",
				"organization_name": f"{PREFIX} Hope Community Church",
				"partner_type": "Church" if frappe.db.exists("Partner Type", "Church") else None,
				"status": "Active",
				"listing_status": "Listed",
				"accepts_job_postings": 1,
				"offers_internships": 1,
				"website": "https://example.test",
				"primary_email": f"office@{DOMAIN}",
				"about_us": "<p>A congregation of about two hundred people that has hosted "
				"seminary interns for ten years.</p>",
				"contacts": [
					{
						"person": person,
						"role_at_org": "Senior Pastor",
						"is_primary": 1,
						"can_supervise": 1,
						"portal_user": PARTNER_EMAIL,
						"portal_access": 1,
					}
				],
			}
		),
	)


def _jobs(created, org, found):
	"""Two postings: one the student applied to, and one still open to them.

	The one they haven't applied to is made last, so it is the newest open posting
	and the student's job sample opens its apply form.
	"""
	student_person = frappe.db.get_value("Student", found["student"], "person")

	def opening(title, description):
		return {
			"doctype": "Partner Job Opening",
			"partner_org": org,
			"job_title": title,
			"status": "Open",
			"publish": 1,
			"open_students": 1,
			"posted_on": frappe.utils.now_datetime(),
			"planned_vacancies": 2,
			"employment_type": "Full-time",
			"description": description,
			"qualifications": "<p>A completed or nearly completed Master of Divinity.</p>",
		}

	applied = _ensure(
		created,
		"Partner Job Opening",
		{"job_title": f"{PREFIX} Associate Pastor", "partner_org": org},
		lambda: _insert(
			opening(
				f"{PREFIX} Associate Pastor",
				"<p>Preach once a month, lead the adult education hour and visit members.</p>",
			)
		),
	)
	if student_person:
		_ensure(
			created,
			"Partner Job Application",
			{"job_opening": applied, "applicant": student_person},
			lambda: _insert(
				{
					"doctype": "Partner Job Application",
					"job_opening": applied,
					"applicant": student_person,
					"status": "Open",
					"cover_letter": "<p>I would be glad to serve the congregation while I finish "
					"my degree.</p>",
				}
			),
		)
	_ensure(
		created,
		"Partner Job Opening",
		{"job_title": f"{PREFIX} Youth Ministry Coordinator", "partner_org": org},
		lambda: _insert(
			opening(
				f"{PREFIX} Youth Ministry Coordinator",
				"<p>Plan the Wednesday youth gathering and the summer camp.</p>",
			)
		),
	)


def _internships(created, org, supervisor, found):
	"""An internship type and two positions, one of them with the student's accepted
	application and, through it, a placement."""
	itype = _ensure(
		created,
		"Internship Type",
		{"name": f"{PREFIX} Pastoral Internship"},
		lambda: _insert(
			{
				"doctype": "Internship Type",
				"type_name": f"{PREFIX} Pastoral Internship",
				"hours_tracking": "Portal Daily Log",
				"evaluation_model": "Pass/Fail",
				"total_hours_required": 120,
			}
		),
	)

	def position(title, description):
		return {
			"doctype": "Internship Position",
			"partner_org": org,
			"internship_type": itype,
			"title": title,
			"status": "Open",
			"publish": 1,
			"open_students": 1,
			"planned_placements": 3,
			"min_hours_per_week": 10,
			"flexible_dates": 1,
			"default_site_supervisor": supervisor,
			"description": description,
		}

	placed = _ensure(
		created,
		"Internship Position",
		{"title": f"{PREFIX} Summer Chaplaincy Internship", "partner_org": org},
		lambda: _insert(
			position(
				f"{PREFIX} Summer Chaplaincy Internship",
				"<p>Visit patients with the hospital chaplain and keep a reflection journal.</p>",
			)
		),
	)
	application = _ensure(
		created,
		"Internship Application",
		{"internship_position": placed, "student": found["student"]},
		lambda: _insert(
			{
				"doctype": "Internship Application",
				"internship_position": placed,
				"student": found["student"],
				"status": "Accepted",
			}
		),
	)
	# Accepting the application made its placement; it is the seed's too.
	_adopt(created, "Internship Placement", {"internship_application": application})
	_ensure(
		created,
		"Internship Position",
		{"title": f"{PREFIX} Worship Ministry Internship", "partner_org": org},
		lambda: _insert(
			position(
				f"{PREFIX} Worship Ministry Internship",
				"<p>Plan Sunday services with the worship team for one semester.</p>",
			)
		),
	)


def _discussion(created, found):
	activity = _ensure(
		created,
		"Discussion Activity",
		{"discussion_name": f"{PREFIX} discussion: Scripture and tradition", "course": found["course_name"]},
		lambda: _insert(
			{
				"doctype": "Discussion Activity",
				"discussion_name": f"{PREFIX} discussion: Scripture and tradition",
				"course": found["course_name"],
				"prompt": "<p>How should tradition inform the way we read Scripture? "
				"Reply to at least one classmate.</p>",
				"min_replies_required": 1,
			}
		),
	)
	_ensure(
		created,
		"Discussion Submission",
		{"disc_activity": activity, "member": found["student_user"]},
		lambda: _insert(
			{
				"doctype": "Discussion Submission",
				"disc_activity": activity,
				"member": found["student_user"],
				"student": found["student"],
				"coursesc": found["course"],
				"course": found["course_name"],
				"original_post": "<p>Tradition is a guide that keeps our reading accountable to "
				"the church that came before us, while Scripture remains the final authority.</p>",
				"replies": [
					{
						"member": found["instructor_user"],
						"reply": "<p>Good start. Which tradition do you have in mind?</p>",
						"reply_dt": frappe.utils.now_datetime(),
					}
				],
			}
		),
	)


def _quiz_submission(created, found):
	"""One ungraded attempt at the sample quiz. No points are awarded, so no score
	notice goes to the student."""
	quiz = found.get("quiz")
	if not quiz:
		return
	questions = frappe.get_all(
		"Quiz Question",
		filters={"parent": quiz, "parenttype": "Quiz"},
		fields=["question", "question_detail", "points"],
		order_by="idx asc",
	)
	_ensure(
		created,
		"Quiz Submission",
		{"quiz": quiz, "member": found["student_user"], "course": found["course"]},
		lambda: _insert(
			{
				"doctype": "Quiz Submission",
				"quiz": quiz,
				"course": found["course"],
				"member": found["student_user"],
				"score_out_of": frappe.db.get_value("Quiz", quiz, "total_points") or 0,
				"result": [
					{
						"question_name": q.question,
						"question": q.question_detail,
						"answer": f"{PREFIX} answer",
						"points": 0,
						"points_out_of": q.points,
					}
					for q in questions
				],
			}
		),
	)


def _recommendation(created, found):
	"""A recommendation request the recommender hasn't answered yet. It stays a draft:
	submitting it is what emails the recommender."""
	enrollment = frappe.db.get_value(
		"Program Enrollment",
		{"student": found["student"], "docstatus": 1},
		"name",
		order_by="modified desc",
	)
	if not enrollment:
		return
	_ensure(
		created,
		"Recommendation Letter",
		{"program_enrollment": enrollment, "recommender_email": RECOMMENDER_EMAIL},
		lambda: _insert(
			{
				"doctype": "Recommendation Letter",
				"program_enrollment": enrollment,
				"recommender_name": f"{PREFIX} Recommender",
				"recommender_email": RECOMMENDER_EMAIL,
				"recommender_role": "Pastor",
				"delivery_method": "Portal Form",
			}
		),
	)


# ---------------------------------------------------------------- purge


def purge():
	"""Delete every row the seed made, dependants first; return what it deleted."""
	deleted, since = [], frappe.utils.now_datetime()
	with _quiet():
		for doctype in SEEDED:
			names = _tagged(doctype)
			if not names:
				continue
			for name in frappe.get_all(
				doctype, filters={"name": ["in", names]}, pluck="name", order_by="creation desc"
			):
				frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True)
				deleted.append((doctype, name))
		if frappe.db.exists("Tag", TAG) and not frappe.db.exists("Tag Link", {"tag": TAG}):
			frappe.delete_doc("Tag", TAG, ignore_permissions=True, delete_permanently=True)
			deleted.append(("Tag", TAG))
		_forget(deleted, since)
	frappe.db.commit()  # nosemgrep -- a bench command
	return {"deleted": [f"{dt} {name}" for dt, name in deleted]}


def _forget(deleted, since):
	"""Drop the traces this purge left: the "Deleted" timeline entries, and the copies
	Frappe keeps of rows removed along with them (a user's notification settings)."""
	recent = {"creation": [">=", since]}
	cascaded = [("Notification Settings", name) for doctype, name in deleted if doctype == "User"]
	for doctype, name in deleted + cascaded:
		frappe.db.delete(
			"Comment",
			{
				**recent,
				"comment_type": "Deleted",
				"reference_doctype": doctype,
				"subject": f"{_(doctype)} {name}",
			},
		)
	for doctype, name in cascaded:
		frappe.db.delete("Deleted Document", {**recent, "deleted_doctype": doctype, "deleted_name": name})
