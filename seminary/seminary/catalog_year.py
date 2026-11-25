# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Catalog years (decisions/115).

A Program Graduation Requirement is a program's catalog year: the courses, credits and other
requirements that bind the students who enter under it. The Program stays the live offering and
the place where curriculum is edited day to day. A catalog is a frozen copy. It is drafted with
New Catalog Year, becomes Scheduled on submit, and becomes Active when its first term starts, at
which point it writes its academic section back onto the Program and supersedes the previous one.

Requirement readers (the audit, the graduation check, GPA minimum and honors, the transfer cap,
time limits, required auto-enrollment, billing credits, substitutions and waivers) read
`for_enrollment(pe)`: a Program-shaped view with the student's catalog laid over it. Offering
readers (the public program page, course schedules, the term plan, the course picker) keep
reading the Program.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, today

CATALOG = "Program Graduation Requirement"
SUBMITTED_STATES = ("Scheduled", "Active", "Superseded")
PENDING_STATES = ("Draft", "Scheduled")
PE_FIELDS = ("name", "program", "graduation_policy", "academic_term", "enrollment_date")

# The Program fields a catalog freezes, in display order.
SCALARS = (
	"credits_complete",
	"terms_complete",
	"min_graduation_gpa",
	"max_transfer_credits",
	"max_time_enrolled",
	"emphasis_overlap_policy",
)

ROW_META = (
	"name",
	"parent",
	"parentfield",
	"parenttype",
	"idx",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"doctype",
)


# --------------------------------------------------------------------------- #
# Which catalog a student is under
# --------------------------------------------------------------------------- #
def entry_date(pe):
	"""The date a student entered: their entry term's start, else the enrollment date."""
	term = pe.get("academic_term")
	if term:
		start = frappe.db.get_value("Academic Term", term, "term_start_date")
		if start:
			return getdate(start)
	when = pe.get("enrollment_date")
	return getdate(when) if when else None


def resolve(program, on_date):
	"""The submitted catalog of `program` whose window contains `on_date`: the latest one that
	started on or before it, whether Scheduled, Active or Superseded."""
	if not program or not on_date:
		return None
	rows = frappe.get_all(
		CATALOG,
		filters={
			"program_name": program,
			"docstatus": 1,
			"workflow_state": ("in", SUBMITTED_STATES),
			"starts_on": ("<=", getdate(on_date)),
		},
		pluck="name",
		order_by="starts_on desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def _pe(pe):
	if isinstance(pe, Document):
		return pe
	if isinstance(pe, str):
		return frappe.db.get_value("Program Enrollment", pe, PE_FIELDS, as_dict=True)
	if pe is not None and all(f in pe for f in PE_FIELDS):
		return pe
	name = pe.get("name") if pe else None
	return frappe.db.get_value("Program Enrollment", name, PE_FIELDS, as_dict=True) if name else None


def catalog_of(pe):
	"""The catalog a Program Enrollment is under: the one it is bound to, else the one its entry
	term resolves to (an enrollment not yet submitted). None for ongoing programs."""
	pe = _pe(pe)
	if not pe or not pe.get("program"):
		return None
	if pe.get("graduation_policy"):
		return pe.graduation_policy
	if frappe.db.get_value("Program", pe.program, "is_ongoing"):
		return None
	return resolve(pe.program, entry_date(pe))


# --------------------------------------------------------------------------- #
# The Program-shaped view requirement readers use
# --------------------------------------------------------------------------- #
def for_enrollment(pe):
	"""The Program as it binds this student: every Program field, with the academic section of
	the student's catalog laid over it. Without a catalog it is the Program itself."""
	pe = _pe(pe)
	if not pe:
		return None
	return view(pe.program, catalog_of(pe))


def view(program, catalog=None):
	"""`program` (a name) with `catalog`'s academic section laid over it. The catalog's section
	is immutable once submitted, so the cached copy is safe to read."""
	out = frappe.get_cached_doc("Program", program).as_dict()
	out.catalog = None
	out.catalog_year = None
	if not catalog:
		return out
	cat = frappe.get_cached_doc(CATALOG, catalog)
	for field in SCALARS:
		out[field] = cat.get(field)
	out.courses = [
		frappe._dict(
			course=r.course,
			course_name=r.course_name,
			required=cint(r.required),
			course_term=cint(r.course_term),
			pgmcourse_credits=cint(r.credits),
			pgm_course_reqonenroll=cint(r.required_on_enroll),
			disabled=0,
		)
		for r in cat.catalog_courses or []
	]
	out.pgm_courses_track = [
		frappe._dict(
			program_track=r.program_track,
			program_track_course=r.course,
			pgm_track_course_mandatory=cint(r.mandatory),
			term=cint(r.term),
		)
		for r in cat.catalog_track_courses or []
	]
	credits = {r.program_track: r for r in cat.catalog_tracks or []}
	for track in out.pgm_pgmtracks or []:
		row = credits.get(track.name)
		if row:
			track.addcredits = cint(row.addcredits)
			track.max_credits = cint(row.max_credits)
	out.honors_levels = [
		frappe._dict(honor_name=r.honor_name, min_gpa=flt(r.min_gpa)) for r in cat.honors_levels or []
	]
	out.catalog = cat.name
	out.catalog_year = cat.catalog_year
	return out


def track(program_view, name):
	"""A Program Track row of the view, with the catalog's credits."""
	for row in program_view.get("pgm_pgmtracks") or []:
		if row.name == name:
			return row
	return None


def track_courses(program_view, track_name=None, mandatory=None):
	rows = program_view.get("pgm_courses_track") or []
	return [
		r
		for r in rows
		if (track_name is None or r.program_track == track_name)
		and (mandatory is None or cint(r.pgm_track_course_mandatory) == cint(mandatory))
	]


def track_credits_passed(pe_name, program_view, track_name):
	"""Credits the student has passed in a track's courses, under their catalog."""
	courses = {r.program_track_course for r in track_courses(program_view, track_name)}
	if not courses:
		return 0
	return flt(
		frappe.db.sql(
			"""SELECT COALESCE(SUM(credits), 0) FROM `tabProgram Enrollment Course`
			WHERE parent = %s AND status = 'Pass' AND course_name IN %s""",
			(pe_name, tuple(courses)),
		)[0][0]
	)


def course_credits(pe, course):
	"""The credits a course carries for this student: their catalog's, else the Program's for a
	course their catalog doesn't list."""
	program_view = for_enrollment(pe)
	if not program_view or not course:
		return 0
	for row in program_view.courses or []:
		if row.course == course:
			return cint(row.pgmcourse_credits)
	return cint(
		frappe.db.get_value(
			"Program Course",
			{"parent": program_view.name, "parenttype": "Program", "course": course},
			"pgmcourse_credits",
		)
	)


# --------------------------------------------------------------------------- #
# Drafting a catalog year
# --------------------------------------------------------------------------- #
def latest(program, states=SUBMITTED_STATES):
	rows = frappe.get_all(
		CATALOG,
		filters={"program_name": program, "docstatus": 1, "workflow_state": ("in", states)},
		pluck="name",
		order_by="starts_on desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def next_term(program):
	"""The first term the next catalog of `program` could start in: after the latest catalog's
	first term, preferring the current or coming term over a past one."""
	after = None
	last = latest(program)
	if last:
		after = frappe.db.get_value(CATALOG, last, "starts_on")
	filters = {"term_start_date": ("is", "set")}
	if after:
		filters["term_start_date"] = (">", after)
	terms = frappe.get_all(
		"Academic Term",
		filters=filters,
		fields=["name", "term_start_date", "term_end_date"],
		order_by="term_start_date asc",
	)
	now = getdate(today())
	for term in terms:
		if term.term_end_date and getdate(term.term_end_date) >= now:
			return term.name
	return terms[-1].name if terms else None


def copy_from_program(catalog, program):
	"""Fill a draft catalog's academic section from the Program as it is now. Disabled program
	courses are left out."""
	for field in SCALARS:
		catalog.set(field, program.get(field))
	catalog.set("catalog_courses", [])
	for row in program.courses or []:
		if row.disabled or not row.course:
			continue
		catalog.append(
			"catalog_courses",
			{
				"course": row.course,
				"course_name": row.course_name,
				"required": row.required,
				"course_term": row.course_term,
				"credits": row.pgmcourse_credits,
				"required_on_enroll": row.pgm_course_reqonenroll,
			},
		)
	catalog.set("catalog_tracks", [])
	for row in program.pgm_pgmtracks or []:
		catalog.append(
			"catalog_tracks",
			{
				"program_track": row.name,
				"track_name": row.track_name,
				"addcredits": row.addcredits,
				"max_credits": row.max_credits,
			},
		)
	catalog.set("catalog_track_courses", [])
	for row in program.pgm_courses_track or []:
		if not (row.program_track and row.program_track_course):
			continue
		catalog.append(
			"catalog_track_courses",
			{
				"program_track": row.program_track,
				"course": row.program_track_course,
				"mandatory": row.pgm_track_course_mandatory,
				"term": row.term,
			},
		)
	catalog.set("honors_levels", [])
	for row in program.honors_levels or []:
		catalog.append("honors_levels", {"honor_name": row.honor_name, "min_gpa": row.min_gpa})


def _copy_rows(source, target, fieldname):
	for row in source.get(fieldname) or []:
		values = {k: v for k, v in row.as_dict().items() if k not in ROW_META}
		target.append(fieldname, values)


@frappe.whitelist()
def new_catalog_year(program: str, academic_term: str | None = None):
	"""Draft the next catalog year of `program` (decisions/115 §3). Returns the open draft if
	there is one. The academic section is copied from the Program, the other requirement rows
	from the latest catalog."""
	frappe.has_permission(CATALOG, "create", throw=True)
	frappe.has_permission("Program", "read", doc=program, throw=True)
	draft = frappe.db.get_value(CATALOG, {"program_name": program, "docstatus": 0}, "name")
	if draft:
		return draft
	prog = frappe.get_doc("Program", program)
	if prog.is_ongoing:
		frappe.throw(_("An ongoing program has no graduation, so it has no catalog year."))
	term = academic_term or next_term(program)
	if not term:
		frappe.throw(_("Create the academic term the catalog year starts in first."))
	doc = frappe.new_doc(CATALOG)
	doc.program_name = program
	doc.academic_term_from = term
	copy_from_program(doc, prog)
	last = latest(program)
	if last:
		_copy_rows(frappe.get_doc(CATALOG, last), doc, "pgr_items")
		doc.supersedes = last
	doc.insert()
	return doc.name


def publish_first_catalog(program, academic_term=None):
	"""Draft and submit a program's catalog from the Program as it is. Used by the patch, the
	demo and tests; a school does the same through New Catalog Year."""
	from frappe.model.workflow import apply_workflow

	name = new_catalog_year(program, academic_term)
	doc = frappe.get_doc(CATALOG, name)
	if doc.docstatus == 0:
		apply_workflow(doc, "Submit")
	return name


# --------------------------------------------------------------------------- #
# Lifecycle: submit, take effect, write back onto the Program
# --------------------------------------------------------------------------- #
def term_before(starts_on):
	rows = frappe.get_all(
		"Academic Term",
		filters={"term_start_date": ("<", starts_on)},
		pluck="name",
		order_by="term_start_date desc",
		limit=1,
	)
	return rows[0] if rows else None


def on_submit(doc):
	"""A submitted catalog follows the latest earlier one, which now ends the term before it
	starts. It takes effect now if its first term has already started."""
	previous = frappe.get_all(
		CATALOG,
		filters={
			"program_name": doc.program_name,
			"docstatus": 1,
			"name": ("!=", doc.name),
			"workflow_state": ("in", SUBMITTED_STATES),
			"starts_on": ("<", doc.starts_on),
		},
		pluck="name",
		order_by="starts_on desc",
		limit=1,
	)
	if previous:
		doc.db_set("supersedes", previous[0], update_modified=False)
		frappe.db.set_value(
			CATALOG,
			previous[0],
			{"superseded_by": doc.name, "academic_term_to": term_before(doc.starts_on)},
			update_modified=False,
		)
	activate_due(doc.program_name)
	doc.reload()


def activate_due(program=None):
	"""Daily (and on submit): every Scheduled catalog whose first term has started takes effect,
	in order. One program's failure doesn't stop the others in the daily run."""
	filters = {"docstatus": 1, "workflow_state": "Scheduled", "starts_on": ("<=", today())}
	if program:
		filters["program_name"] = program
	for name in frappe.get_all(CATALOG, filters=filters, pluck="name", order_by="starts_on asc"):
		if program:
			activate(name)
			continue
		try:
			activate(name)
			frappe.db.commit()  # nosemgrep -- each catalog takes effect on its own in the daily run
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=_("Catalog year could not take effect"), reference_doctype=CATALOG)


def activate(name):
	doc = frappe.get_doc(CATALOG, name)
	if doc.workflow_state != "Scheduled":
		return
	apply_to_program(doc)
	for previous in frappe.get_all(
		CATALOG,
		filters={
			"program_name": doc.program_name,
			"docstatus": 1,
			"workflow_state": "Active",
			"name": ("!=", doc.name),
		},
		pluck="name",
	):
		frappe.db.set_value(
			CATALOG, previous, {"workflow_state": "Superseded", "active": 0}, update_modified=False
		)
	frappe.db.set_value(CATALOG, doc.name, {"workflow_state": "Active", "active": 1}, update_modified=False)
	frappe.clear_document_cache(CATALOG, doc.name)


def apply_to_program(catalog):
	"""Write a catalog's academic section onto its Program (decisions/115 §4). Program courses the
	catalog leaves out are disabled with the reason; courses it lists are enabled. This is the
	catalog taking effect, which its submitter was entitled to, so the Program write is the
	system's."""
	program = frappe.get_doc("Program", catalog.program_name)
	if not changes(curriculum(program), curriculum(catalog)):
		return  # already the Program's curriculum, as a first catalog is
	reason = _("Not in the {0} catalog").format(catalog.catalog_year or catalog.name)
	by_course = {r.course: r for r in program.courses or []}
	listed = set()
	for row in catalog.catalog_courses or []:
		listed.add(row.course)
		target = by_course.get(row.course)
		if not target:
			target = program.append("courses", {"course": row.course})
			by_course[row.course] = target
		target.course_name = row.course_name or target.course_name
		target.required = row.required
		target.course_term = row.course_term
		target.pgmcourse_credits = row.credits
		target.pgm_course_reqonenroll = row.required_on_enroll
		if target.disabled:
			target.disabled = 0
			target.disabled_on = None
			target.disable_reason = None
	for row in program.courses or []:
		if row.course not in listed and not row.disabled:
			row.disabled = 1
			row.disabled_on = today()
			row.disable_reason = reason
	program.set("pgm_courses_track", [])
	for row in catalog.catalog_track_courses or []:
		program.append(
			"pgm_courses_track",
			{
				"program_track": row.program_track,
				"program_track_course": row.course,
				"pgm_track_course_mandatory": row.mandatory,
				"term": row.term,
			},
		)
	credits = {r.program_track: r for r in catalog.catalog_tracks or []}
	for row in program.pgm_pgmtracks or []:
		if row.name in credits:
			row.addcredits = credits[row.name].addcredits
			row.max_credits = credits[row.name].max_credits
	for field in SCALARS:
		program.set(field, catalog.get(field))
	program.set("honors_levels", [])
	for row in catalog.honors_levels or []:
		program.append("honors_levels", {"honor_name": row.honor_name, "min_gpa": row.min_gpa})
	program.flags.ignore_permissions = True
	program.flags.from_catalog_year = catalog.name
	program.save()


# --------------------------------------------------------------------------- #
# Comparing (decisions/115 §6, and the program's specification in another app)
# --------------------------------------------------------------------------- #
def curriculum(source):
	"""A catalog's (or the Program's) academic section as plain, JSON-safe data. `source` is a
	catalog name, a catalog document or a Program document."""
	if isinstance(source, str):
		source = frappe.get_doc(CATALOG, source)
	is_program = source.doctype == "Program"
	out = {field: source.get(field) for field in SCALARS}
	for field in ("credits_complete", "terms_complete", "max_transfer_credits"):
		out[field] = cint(out[field])
	for field in ("min_graduation_gpa", "max_time_enrolled"):
		out[field] = flt(out[field])
	courses = {}
	rows = [r for r in source.courses or [] if not r.disabled] if is_program else source.catalog_courses
	for r in rows or []:
		if not r.course:
			continue
		courses[r.course] = {
			"name": r.course_name or r.course,
			"required": cint(r.required),
			"credits": cint(r.pgmcourse_credits if is_program else r.credits),
			"term": cint(r.course_term),
			"on_enroll": cint(r.pgm_course_reqonenroll if is_program else r.required_on_enroll),
		}
	out["courses"] = courses
	tracks = {}
	if is_program:
		for r in source.pgm_pgmtracks or []:
			tracks[r.name] = {
				"name": r.track_name or r.name,
				"required": cint(r.addcredits),
				"ceiling": cint(r.max_credits),
			}
	else:
		for r in source.catalog_tracks or []:
			tracks[r.program_track] = {
				"name": r.track_name or r.program_track,
				"required": cint(r.addcredits),
				"ceiling": cint(r.max_credits),
			}
	out["tracks"] = tracks
	track_rows = {}
	for r in source.pgm_courses_track or [] if is_program else source.catalog_track_courses or []:
		track_name = r.program_track
		course = r.program_track_course if is_program else r.course
		if not (track_name and course):
			continue
		track_rows[f"{track_name}|{course}"] = {
			"track": track_name,
			"course": course,
			"mandatory": cint(r.pgm_track_course_mandatory if is_program else r.mandatory),
			"term": cint(r.term),
		}
	out["track_courses"] = track_rows
	out["honors"] = {r.honor_name: flt(r.min_gpa) for r in source.honors_levels or [] if r.honor_name}
	return out


def _scalar_labels():
	return {
		"credits_complete": _("Credits for completion"),
		"terms_complete": _("Terms for completion"),
		"min_graduation_gpa": _("Minimum graduation GPA"),
		"max_transfer_credits": _("Max transfer credits"),
		"max_time_enrolled": _("Max years to graduate"),
		"emphasis_overlap_policy": _("Emphasis overlap policy"),
	}


def _yes(value):
	return _("Yes") if value else _("No")


def _course_label(course, rows):
	return (
		(rows.get(course) or {}).get("name") or frappe.db.get_value("Course", course, "course_name") or course
	)


def changes(old, new):
	"""What changed from curriculum `old` to curriculum `new`, as sentences."""
	out = []
	arrow = "→"
	for field, label in _scalar_labels().items():
		if (old.get(field) or 0) != (new.get(field) or 0):
			out.append(f"{label}: {old.get(field) or 0} {arrow} {new.get(field) or 0}")

	before, after = old.get("courses") or {}, new.get("courses") or {}
	for course in sorted(after.keys() - before.keys(), key=lambda c: after[c]["name"]):
		out.append(_("Course added: {0}").format(after[course]["name"]))
	for course in sorted(before.keys() - after.keys(), key=lambda c: before[c]["name"]):
		out.append(_("Course removed: {0}").format(before[course]["name"]))
	for course in sorted(before.keys() & after.keys(), key=lambda c: after[c]["name"]):
		a, b = before[course], after[course]
		for key, label, fmt in (
			("required", _("mandatory"), _yes),
			("credits", _("credits"), str),
			("term", _("term"), str),
			("on_enroll", _("mandatory on enrollment"), _yes),
		):
			if a.get(key) != b.get(key):
				out.append(f"{b['name']}: {label} {fmt(a.get(key))} {arrow} {fmt(b.get(key))}")

	before, after = old.get("tracks") or {}, new.get("tracks") or {}
	for key in sorted(after.keys() - before.keys()):
		out.append(_("Track added: {0}").format(after[key]["name"]))
	for key in sorted(before.keys() - after.keys()):
		out.append(_("Track removed: {0}").format(before[key]["name"]))
	for key in sorted(before.keys() & after.keys()):
		a, b = before[key], after[key]
		for field, label in (("required", _("credits required")), ("ceiling", _("credits ceiling"))):
			if a.get(field) != b.get(field):
				out.append(f"{b['name']}: {label} {a.get(field)} {arrow} {b.get(field)}")

	before, after = old.get("track_courses") or {}, new.get("track_courses") or {}
	courses = {**(old.get("courses") or {}), **(new.get("courses") or {})}
	tracks = {**(old.get("tracks") or {}), **(new.get("tracks") or {})}

	def _tc(row):
		track_label = (tracks.get(row["track"]) or {}).get("name") or row["track"]
		return f"{track_label}, {_course_label(row['course'], courses)}"

	for key in sorted(after.keys() - before.keys()):
		out.append(_("Track course added: {0}").format(_tc(after[key])))
	for key in sorted(before.keys() - after.keys()):
		out.append(_("Track course removed: {0}").format(_tc(before[key])))
	for key in sorted(before.keys() & after.keys()):
		a, b = before[key], after[key]
		if a.get("mandatory") != b.get("mandatory"):
			out.append(f"{_tc(b)}: {_('mandatory')} {_yes(a['mandatory'])} {arrow} {_yes(b['mandatory'])}")
		if a.get("term") != b.get("term"):
			out.append(f"{_tc(b)}: {_('term')} {a.get('term')} {arrow} {b.get('term')}")

	before, after = old.get("honors") or {}, new.get("honors") or {}
	for key in sorted(after.keys() - before.keys()):
		out.append(_("Honor added: {0} ({1})").format(key, after[key]))
	for key in sorted(before.keys() - after.keys()):
		out.append(_("Honor removed: {0}").format(key))
	for key in sorted(before.keys() & after.keys()):
		if before[key] != after[key]:
			out.append(f"{key}: {_('minimum GPA')} {before[key]} {arrow} {after[key]}")
	return out


def _requirements(doc):
	out = {}
	for r in doc.pgr_items or []:
		key = f"{r.grad_requirement_item}|{r.applies_to_emphasis or ''}"
		out[key] = r
	return out


def requirement_changes(old, new):
	"""The other requirement rows added, removed or changed between two catalogs."""
	before, after = _requirements(old), _requirements(new)
	out = []

	def _label(row):
		return row.grad_req_name or row.grad_requirement_item

	for key in sorted(after.keys() - before.keys()):
		out.append(_("Requirement added: {0}").format(_label(after[key])))
	for key in sorted(before.keys() - after.keys()):
		out.append(_("Requirement removed: {0}").format(_label(before[key])))
	fields = (
		"mandatory",
		"blocks_graduation_request",
		"quantity_required",
		"activation_mode",
		"activation_credits",
		"prerequisite_course",
		"prerequisite_requirement",
		"internship_hours_required",
		"offset_anchor",
		"offset_value",
		"offset_unit",
	)
	for key in sorted(before.keys() & after.keys()):
		a, b = before[key], after[key]
		if any((a.get(f) or 0) != (b.get(f) or 0) for f in fields):
			out.append(_("Requirement changed: {0}").format(_label(b)))
	return out


@frappe.whitelist()
def compare(catalog: str, other: str | None = None):
	"""A catalog beside another version of the same program, by default the one it follows."""
	frappe.has_permission(CATALOG, "read", throw=True)
	doc = frappe.get_doc(CATALOG, catalog)
	doc.check_permission("read")
	other = other or doc.supersedes
	if not other:
		return {"catalog": _summary(doc), "other": None, "changes": []}
	previous = frappe.get_doc(CATALOG, other)
	previous.check_permission("read")
	if previous.program_name != doc.program_name:
		frappe.throw(_("Both catalog years must belong to the same program."))
	if previous.starts_on and doc.starts_on and getdate(previous.starts_on) > getdate(doc.starts_on):
		doc, previous = previous, doc
	return {
		"catalog": _summary(doc),
		"other": _summary(previous),
		"changes": changes(curriculum(previous), curriculum(doc)) + requirement_changes(previous, doc),
	}


def _summary(doc):
	return {
		"name": doc.name,
		"catalog_year": doc.catalog_year,
		"state": doc.workflow_state,
		"first_term": doc.academic_term_from,
	}


@frappe.whitelist()
def program_status(program: str):
	"""What the Program form says about its catalogs (decisions/115 §4): a pending draft or
	scheduled catalog, or how the Program differs from the Active one."""
	frappe.has_permission(CATALOG, "read", throw=True)
	frappe.has_permission("Program", "read", doc=program, throw=True)
	pending = frappe.get_all(
		CATALOG,
		filters={"program_name": program, "docstatus": ("<", 2), "workflow_state": ("in", PENDING_STATES)},
		fields=["name", "workflow_state", "catalog_year", "academic_term_from"],
		order_by="starts_on asc",
	)
	active = latest(program, ("Active",))
	out = {"pending": pending, "active": None, "differences": []}
	if active:
		cat = frappe.get_doc(CATALOG, active)
		out["active"] = _summary(cat)
		if not pending:
			out["differences"] = changes(curriculum(cat), curriculum(frappe.get_doc("Program", program)))
	return out


# --------------------------------------------------------------------------- #
# Guards (decisions/115 §7)
# --------------------------------------------------------------------------- #
def has_catalog(program):
	return bool(latest(program))


def validate_program(program):
	"""A program that isn't ongoing can't be published before it has a catalog year."""
	if not program.published or program.is_ongoing:
		return
	if program.is_new() or not has_catalog(program.name):
		frappe.throw(
			_(
				"Publish a catalog year before publishing the program: save it unpublished, then use "
				"New Catalog Year."
			)
		)


def bind_enrollment(pe):
	"""On submit, an enrollment in a graduating program is bound to the catalog its entry term
	falls in, and can't be submitted without one."""
	if frappe.db.get_value("Program", pe.program, "is_ongoing"):
		return
	if not pe.graduation_policy:
		pe.graduation_policy = resolve(pe.program, entry_date(pe))
	if not pe.graduation_policy:
		frappe.throw(
			_(
				"No catalog year of {0} covers this enrollment's term. Publish one with New Catalog "
				"Year on the program."
			).format(frappe.bold(pe.program))
		)


# --------------------------------------------------------------------------- #
# Setup Progress
# --------------------------------------------------------------------------- #
def programs_with_catalog():
	programs = frappe.get_all("Program", filters={"is_ongoing": 0}, pluck="name")
	with_catalog = set(
		frappe.get_all(
			CATALOG,
			filters={"docstatus": 1, "program_name": ("in", programs or ["\x00"])},
			pluck="program_name",
			distinct=True,
		)
	)
	return len(with_catalog), len(programs)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def program_course_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | None = None
):
	"""The Program's courses, disabled ones included, for a catalog's course picker."""
	frappe.has_permission(CATALOG, "read", throw=True)
	program = (filters or {}).get("program")
	if not program:
		return []
	return frappe.db.sql(
		"""SELECT course, course_name FROM `tabProgram Course`
		WHERE parent = %(program)s AND parenttype = 'Program'
			AND (course LIKE %(txt)s OR course_name LIKE %(txt)s)
		ORDER BY idx LIMIT %(start)s, %(page_len)s""",
		{"program": program, "txt": f"%{txt}%", "start": cint(start), "page_len": cint(page_len)},
	)
