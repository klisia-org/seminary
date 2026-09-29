# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Bulk Course Enrollment: one document is one run (ADR 083 §1-§2), for
Time-based programs where staff enroll students (decisions/084 §5).

The registrar picks a term and Time-based programs, gets the students and the
courses their term expects, picks a section per course, and enrolls. Each
enrollment goes through `api.enroll_in_section`, so prerequisites, duplicates,
capacity (the waitlist) and billing on submit behave exactly as for one
enrollment. The run is queued; each student×course lands in the results table,
and running it again retries only what failed or has not run.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, fmt_money, now_datetime

from seminary.seminary.financial.backend import get_financial_backend
from seminary.seminary.term_plan import (
    active_holds,
    expected_courses,
    time_based_enrollments,
)

RUN_ROLES = ["Registrar", "Seminary Manager", "System Manager"]
# Result states a re-run leaves alone: the student×course is settled.
SETTLED = {"Enrolled", "Awaiting Payment", "Waitlisted", "Draft", "Skipped"}
STATE_TO_STATUS = {
    "Submitted": "Enrolled",
    "Awaiting Payment": "Awaiting Payment",
    "Waitlisted": "Waitlisted",
    "Draft": "Draft",
}


class BulkCourseEnrollment(Document):
    def onload(self):
        self.set_onload("has_financials", get_financial_backend().has_financials())

    def before_insert(self):
        # A new run starts with its students and courses already listed.
        if not self.students and not self.flags.filled:
            self.fill_students()
            self.fill_courses()

    def validate(self):
        for row in self.programs:
            program = frappe.db.get_value(
                "Program",
                row.program,
                ["program_type", "staff_enroll_only"],
                as_dict=True,
            )
            if (
                not program
                or program.program_type != "Time-based"
                or not program.staff_enroll_only
            ):
                frappe.throw(
                    _(
                        "{0} can't be used here: only Time-based programs where staff "
                        "enroll students in courses can."
                    ).format(row.program)
                )
        for row in self.courses:
            if not row.course_schedule:
                continue
            cs = frappe.db.get_value(
                "Course Schedule",
                row.course_schedule,
                ["course", "academic_term"],
                as_dict=True,
            )
            if (
                not cs
                or cs.course != row.course
                or cs.academic_term != self.academic_term
            ):
                frappe.throw(
                    _("Row {0}: section {1} is not a {2} section in {3}.").format(
                        row.idx, row.course_schedule, row.course, self.academic_term
                    )
                )
        if not self.flags.figures_fresh and self.run_status not in (
            "Queued",
            "Running",
        ):
            # A section may have changed on the page: seats and charges follow it.
            self.refresh_course_figures()

    # -- the page's buttons (see the module functions below) ----------------

    def run_get_students(self):
        self.fill_students()
        self.fill_courses()
        self.save()

    def run_get_courses(self):
        self.fill_courses()
        self.save()

    def run_enroll(self):
        if self.run_status in ("Queued", "Running"):
            frappe.throw(_("This run is already in progress."))
        self.plan_results()
        pending = sum(1 for r in self.results if r.status == "Pending")
        if not pending:
            frappe.throw(_("There is nothing left to enroll in this run."))
        self.run_status = "Queued"
        self.run_by = frappe.session.user
        self.run_on = now_datetime()
        self.save()
        frappe.enqueue(
            "seminary.seminary.doctype.bulk_course_enrollment.bulk_course_enrollment.execute_run",
            queue="long",
            timeout=3600,
            enqueue_after_commit=True,
            run=self.name,
        )
        return pending

    # -- building the run --------------------------------------------------

    def fill_students(self, names=None):
        programs = [r.program for r in self.programs]
        if not programs:
            frappe.throw(_("Choose at least one program."))
        pes = time_based_enrollments(
            self.academic_term,
            programs=programs,
            student_term=cint(self.student_term) or None,
            intake_term=self.intake_term,
            names=names,
        )
        self.set("students", [])
        for pe in pes:
            self.append(
                "students",
                {
                    "include": 1,
                    "program_enrollment": pe.name,
                    "student": pe.student,
                    "student_name": pe.student_name,
                    "program": pe.program,
                    "current_std_term": pe.current_std_term,
                    "holds": ", ".join(active_holds(pe.student)),
                },
            )

    def included_students(self):
        return [
            frappe._dict(
                name=r.program_enrollment,
                program=r.program,
                current_std_term=r.current_std_term,
                student_name=r.student_name,
            )
            for r in self.students
            if r.include
        ]

    def fill_courses(self):
        """One row per (program, term, course, emphasis) the included students'
        plans expect. A row the registrar already set up keeps its section, cap
        and tick; so do extra rows added by hand."""
        groups = {}
        for pe in self.included_students():
            for c in expected_courses(pe):
                key = (pe.program, cint(pe.current_std_term), c.course, c.track or None)
                groups.setdefault(key, {"course_name": c.course_name, "pes": []})
                groups[key]["pes"].append(pe.name)

        kept = {}
        for row in self.courses:
            key = (row.program, cint(row.term), row.course, row.track or None)
            kept.setdefault(key, []).append(row)

        rows = []
        for key, g in groups.items():
            program, term, course, track = key
            previous = kept.pop(key, None)
            if previous:
                rows.extend(previous)
                continue
            rows.append(
                frappe._dict(
                    include=1,
                    program=program,
                    term=term,
                    course=course,
                    course_name=g["course_name"],
                    track=track,
                    course_schedule=_default_section(course, self.academic_term),
                )
            )
        for extra in kept.values():
            rows.extend(extra)

        self.set("courses", [])
        for row in rows:
            data = row.as_dict() if isinstance(row, Document) else dict(row)
            for f in ("name", "idx", "parent", "parentfield", "parenttype", "doctype"):
                data.pop(f, None)
            self.append("courses", data)
        self.refresh_course_figures(groups)
        self.flags.figures_fresh = True

    def refresh_course_figures(self, groups=None):
        """Students expected, seats left and the charge per student, per row."""
        if groups is None:
            groups = {}
            for pe in self.included_students():
                for c in expected_courses(pe):
                    key = (
                        pe.program,
                        cint(pe.current_std_term),
                        c.course,
                        c.track or None,
                    )
                    groups.setdefault(key, {"pes": []})["pes"].append(pe.name)
        backend = get_financial_backend()
        billing = backend.has_financials()
        for row in self.courses:
            key = (row.program, cint(row.term), row.course, row.track or None)
            if key in groups:
                pes = groups[key]["pes"]
            else:
                # A row added by hand; an emphasis row nobody here expects gets no one.
                pes = [] if row.track else self._row_students(row)
            row.students = len(pes)
            row.seats_left = _seats_left(row.course_schedule)
            row.charges = (
                _charge_text(backend, pes, row.course_schedule, row.program, row.course)
                if billing and row.course_schedule
                else None
            )

    def _row_students(self, row):
        """Included students a hand-added row applies to."""
        return [
            s.name
            for s in self.included_students()
            if s.program == row.program and cint(s.current_std_term) == cint(row.term)
        ]

    def plan(self):
        """[(student row, course row)] in table order. Rows for the same course
        are filled in order: each takes up to its Max Students, blank meaning
        everyone left."""
        students = self.included_students()
        tracks = {}
        by_course = {}
        for row in self.courses:
            if row.include:
                by_course.setdefault(
                    (row.program, cint(row.term), row.course), []
                ).append(row)
        taken = {}
        pairs = []
        for pe in students:
            for c in expected_courses(pe):
                tracks.setdefault(pe.name, set()).add((c.course, c.track or None))
            for (program, term, course), rows in by_course.items():
                if program != pe.program or term != cint(pe.current_std_term):
                    continue
                wanted = [
                    r
                    for r in rows
                    if not r.track or (course, r.track) in tracks.get(pe.name, set())
                ]
                if not wanted:
                    continue
                chosen = None
                for r in wanted:
                    if not r.max_students or taken.get(id(r), 0) < r.max_students:
                        chosen = r
                        break
                if chosen:
                    taken[id(chosen)] = taken.get(id(chosen), 0) + 1
                pairs.append((pe, course, chosen))
        return pairs

    def plan_results(self):
        """Merge the plan into the results: settled rows stay, failed and
        pending rows are planned again, and pending rows no longer planned go."""
        existing = {(r.program_enrollment, r.course): r for r in self.results}
        planned = set()
        for pe, course, row in self.plan():
            key = (pe.name, course)
            planned.add(key)
            section = row.course_schedule if row else None
            result = existing.get(key)
            if result and result.status in SETTLED:
                continue
            if not result:
                result = self.append(
                    "results",
                    {
                        "program_enrollment": pe.name,
                        "student_name": pe.student_name,
                        "course": course,
                    },
                )
            result.course_schedule = section
            result.status = "Pending"
            result.cei = None
            result.message = None
            if not row:
                result.status = "Skipped"
                result.message = _(
                    "Every section chosen for this course is full in this run."
                )
            elif not section:
                result.status = "Skipped"
                result.message = _("No section was chosen for this course.")
        self.results = [
            r
            for r in self.results
            if (r.program_enrollment, r.course) in planned
            or r.status not in ("Pending", "Failed")
        ]
        for i, r in enumerate(self.results, 1):
            r.idx = i


def _default_section(course, academic_term):
    """The section a new row starts with: the first open one, if any."""
    rows = frappe.get_all(
        "Course Schedule",
        filters={
            "course": course,
            "academic_term": academic_term,
            "workflow_state": "Open for Enrollment",
        },
        order_by="c_datestart asc, name asc",
        pluck="name",
        limit=1,
    )
    return rows[0] if rows else None


def _seats_left(course_schedule):
    if not course_schedule:
        return _("No open section")
    from seminary.seminary.waitlist import seats_used

    cap = frappe.db.get_value("Course Schedule", course_schedule, "max_enrollment")
    if not cap:
        return _("No limit")
    return str(max(cap - seats_used(course_schedule), 0))


def _charge_text(backend, pes, course_schedule, program, course):
    credits = (
        frappe.db.get_value(
            "Program Course", {"parent": program, "course": course}, "pgmcourse_credits"
        )
        or 0
    )
    totals, unpriced = [], 0
    for pe in pes:
        lines = backend.preview_enrollment_charges(pe, course_schedule, credits, False)
        if any(line.get("amount") is None for line in lines):
            unpriced += 1
        totals.append(sum(line.get("amount") or 0 for line in lines))
    if not totals:
        return None
    low, high = min(totals), max(totals)
    text = fmt_money(low) if low == high else f"{fmt_money(low)} – {fmt_money(high)}"
    if unpriced:
        text += " " + _("({0} with an unpriced fee)").format(unpriced)
    return text


# -- the page's buttons ------------------------------------------------------
# Module functions, not whitelisted document methods: a document method is
# admitted on read of the document alone, so each would have to gate itself
# anyway. These check the role and write access before touching the run.


def _run_for_writing(name):
    frappe.only_for(RUN_ROLES)
    doc = frappe.get_doc("Bulk Course Enrollment", name)
    doc.check_permission("write")
    return doc


@frappe.whitelist()
def get_students(name):
    _run_for_writing(name).run_get_students()


@frappe.whitelist()
def get_courses(name):
    _run_for_writing(name).run_get_courses()


@frappe.whitelist()
def enroll(name):
    return _run_for_writing(name).run_enroll()


# -- the queued job ----------------------------------------------------------


def execute_run(run):
    doc = frappe.get_doc("Bulk Course Enrollment", run)
    doc.db_set("run_status", "Running", update_modified=False)
    frappe.db.commit()  # nosemgrep -- background job: progress must survive a later failure

    for result in doc.results:
        if result.status != "Pending":
            continue
        try:
            status, cei, message = _enroll_one(result)
        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(frappe.get_traceback(), f"Bulk Course Enrollment {run}")
            status, cei, message = "Failed", None, str(e) or e.__class__.__name__
        frappe.db.set_value(
            "Bulk Course Enrollment Result",
            result.name,
            {"status": status, "cei": cei, "message": message},
            update_modified=False,
        )
        result.status = status
        frappe.db.commit()  # nosemgrep -- one student×course at a time

    counts = {}
    for r in doc.results:
        counts[r.status] = counts.get(r.status, 0) + 1
    summary = ", ".join(f"{_(k)}: {v}" for k, v in sorted(counts.items()))
    doc.db_set(
        {
            "run_status": (
                "Completed with Errors" if counts.get("Failed") else "Completed"
            ),
            "summary": summary,
        },
        update_modified=True,
    )
    frappe.db.commit()  # nosemgrep
    frappe.publish_realtime(
        "bulk_course_enrollment_done",
        {"name": doc.name, "summary": summary},
        user=doc.run_by,
        after_commit=False,
    )


def _enroll_one(result):
    """(status, cei, message) for one student×course."""
    from seminary.seminary.api import enroll_in_section
    from seminary.seminary.required_enrollment import (
        _already_covered,
        unmet_prerequisites,
    )

    pe, course = result.program_enrollment, result.course
    if not frappe.db.get_value("Program Enrollment", pe, "pgmenrol_active"):
        return "Skipped", None, _("The program enrollment is no longer active.")
    if _already_covered(pe, course):
        return "Skipped", None, _("Already enrolled in or passed this course.")
    missing = unmet_prerequisites(pe, course)
    if missing:
        return "Failed", None, _("Unmet prerequisite: {0}").format(", ".join(missing))

    frappe.db.savepoint("bulk_enroll_one")
    try:
        out = enroll_in_section(pe, result.course_schedule, submit_blocked=True)
    except Exception as e:
        frappe.db.rollback(save_point="bulk_enroll_one")
        frappe.clear_messages()
        return "Failed", None, str(e) or e.__class__.__name__
    status = STATE_TO_STATUS.get(out.get("workflow_state"), "Enrolled")
    return status, out["name"], None


# -- runs started from elsewhere ----------------------------------------------


@frappe.whitelist()
def new_run(academic_term, programs, enrollments=None, courses=None):
    """Create a run already filled in, for the enrollment check report's ticked
    gaps. Returns its name for the caller to open."""
    frappe.only_for(RUN_ROLES)
    programs = frappe.parse_json(programs) if isinstance(programs, str) else programs
    enrollments = (
        frappe.parse_json(enrollments) if isinstance(enrollments, str) else enrollments
    )
    courses = frappe.parse_json(courses) if isinstance(courses, str) else courses
    doc = frappe.new_doc("Bulk Course Enrollment")
    doc.academic_term = academic_term
    for p in dict.fromkeys(programs or []):
        doc.append("programs", {"program": p})
    doc.fill_students(names=enrollments)
    doc.fill_courses()
    doc.flags.filled = True
    if courses:
        wanted = set(courses)
        for row in doc.courses:
            row.include = 1 if row.course in wanted else 0
    doc.insert()
    return doc.name
