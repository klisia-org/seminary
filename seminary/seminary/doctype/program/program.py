# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.utils import format_date, getdate, today
from frappe.website.website_generator import WebsiteGenerator
from seminary.seminary.utils import assert_url_safe_code, slugify


class Program(WebsiteGenerator):
    def autoname(self):
        self.name = self.program_name
        self.slug = slugify(self.program_name)

    def validate(self):
        # WebsiteGenerator.validate sets/scrubs the web `route` from the title for
        # published programs. We override validate, so call super first or the
        # route field is never populated and the program's web page has no URL.
        super().validate()
        assert_url_safe_code(self.program_abbreviation, _("Program Abbreviation"))
        self._hydrate_graduation_gpa_default()

        # Free programs cannot gate enrollment on payment — there are no invoices.
        # Force the gating fields off so the CEI workflow conditions evaluate
        # cleanly regardless of fetch_from chain timing.
        if self.is_free:
            self.require_pay_submit = 0
            self.percent_to_pay = 0

        self._hydrate_pacing_mode_default()
        self._stamp_course_disabled_on()
        self._validate_course_term_and_credits()
        self._validate_competency_courses()

    def on_update(self):
        # WebsiteGenerator.on_update drives the search-index refresh; same
        # reason validate() calls super — skipping it silently breaks the
        # program's web page indexing.
        super().on_update()
        self._recompute_candidacy_on_graduation_config_change()

    def _recompute_candidacy_on_graduation_config_change(self):
        """Re-evaluate every active enrollment when the graduation-request
        config changes. `grad_candidate` is otherwise only refreshed by
        enrollment-side hooks, so turning the feature on for an existing program
        would leave students who already finished their courses stuck at 0.

        Enqueued: the fan-out is one evaluation per active enrollment and must
        not make saving the Program slow. Nothing user-facing waits on it — the
        audit page and the request endpoint recompute candidacy on read — so
        this only settles the stored flag that reports read.
        """
        before = self.get_doc_before_save()
        if not before:
            return
        watched = ("students_can_request_graduation", "graduation_request_trigger")
        if all(before.get(f) == self.get(f) for f in watched):
            return
        frappe.enqueue(
            "seminary.seminary.graduation_candidate.recompute_for_program",
            queue="long",
            program=self.name,
            enqueue_after_commit=True,
        )

    def _hydrate_graduation_gpa_default(self):
        """Default min_graduation_gpa from the Program Level, but keep it
        overridable: pull the level's value only on create or when the level
        changes, so an explicit per-program value (including 0 = no minimum) is
        preserved. fetch_from is not used here because it would overwrite the
        override on every save (ADR 057)."""
        if not self.program_level:
            return
        before = self.get_doc_before_save()
        if before and before.program_level == self.program_level:
            return  # level unchanged — respect any per-program override
        self.min_graduation_gpa = (
            frappe.db.get_value(
                "Program Level", self.program_level, "min_graduation_gpa"
            )
            or 0
        )

    def _hydrate_pacing_mode_default(self):
        """Default pacing_mode from the Competency Framework, but keep it
        overridable: pull the framework's value only on create or when the
        framework changes. Same reasoning as _hydrate_graduation_gpa_default —
        fetch_from would overwrite a per-program override on every save
        (ADR 057)."""
        if not self.competency_framework:
            return
        before = self.get_doc_before_save()
        if (
            before
            and before.competency_framework == self.competency_framework
            and self.pacing_mode
        ):
            return  # framework unchanged — respect any per-program override
        self.pacing_mode = frappe.db.get_value(
            "Competency Framework", self.competency_framework, "default_pacing_mode"
        )

    def _validate_competency_courses(self):
        """A competency-based program's curriculum has to be able to carry
        competencies (ADR 065).

        Without this, any course could sit in a CBE program and would simply
        produce no competency results at grading time — a failure that surfaces
        at the end of a term rather than when the curriculum is built. Both
        conditions are checked together so the registrar fixes the whole list in
        one pass rather than one course per save.
        """
        if not self.competency_framework:
            return

        framework_scale = frappe.db.get_value(
            "Competency Framework", self.competency_framework, "grading_scale"
        )
        if not framework_scale:
            return

        wrong_scale, no_competency = [], []
        for pc in self.courses or []:
            if pc.disabled or not pc.course:
                continue
            course_scale = frappe.db.get_value(
                "Course", pc.course, "default_grading_scale"
            )
            if course_scale != framework_scale:
                wrong_scale.append(f"{pc.course} ({course_scale or _('no scale')})")
                continue
            if not frappe.db.exists(
                "Course Competency", {"course": pc.course, "is_active": 1}
            ):
                no_competency.append(pc.course)

        problems = []
        if wrong_scale:
            problems.append(
                _(
                    "These courses do not use the framework's grading scale {0}: {1}."
                ).format(framework_scale, ", ".join(wrong_scale))
            )
        if no_competency:
            problems.append(
                _("These courses define no active competency: {0}.").format(
                    ", ".join(no_competency)
                )
            )
        if problems:
            frappe.throw(
                _("Program {0} uses competency framework {1}.").format(
                    self.name, self.competency_framework
                )
                + "<br><br>"
                + "<br><br>".join(problems)
            )

    def _stamp_course_disabled_on(self):
        for pc in self.courses or []:
            if pc.disabled and not pc.disabled_on:
                pc.disabled_on = today()

    def _validate_course_term_and_credits(self):
        # Per-type curriculum requirements. mandatory_depends_on on the child
        # fields gives client-side hinting, but it can't read the parent's
        # program_type server-side — enforce authoritatively here. Time-based
        # progression keys off course_term (see petb_enroll); Credits-based
        # completion keys off pgmcourse_credits.
        if self.is_ongoing:
            return
        for pc in self.courses or []:
            if pc.disabled:
                continue
            if self.program_type == "Time-based" and not pc.course_term:
                frappe.throw(
                    _(
                        "Course {0}: Term number is required for Time-based programs."
                    ).format(pc.course)
                )
            if self.program_type == "Credits-based" and not pc.pgmcourse_credits:
                frappe.throw(
                    _(
                        "Course {0}: Credits are required for Credits-based programs."
                    ).format(pc.course)
                )

    def get_context(self, context):
        from seminary.seminary.api import get_application_web_form_route
        from seminary.seminary.seo import page_metatags

        context.open_windows = []
        context.continuous_term = None
        context.apply_route = get_application_web_form_route(self.name)
        context.metatags = page_metatags(
            self.program_name,
            self.blurb or self.program_description,
            image=self.hero_image or self.image_blurb,
        )

        if self.enrollment_mode == "Timed":
            context.open_windows = self._resolve_open_windows()
        elif self.enrollment_mode == "Continuous" and self.display_cta:
            context.continuous_term = self._resolve_continuous_term()
            if not context.continuous_term:
                frappe.log_error(
                    f"Program {self.name} is Continuous with display_cta=1 "
                    "but no current/upcoming Academic Term is configured.",
                    "program.get_context",
                )

    def _resolve_open_windows(self):
        windows = frappe.db.sql(
            """
            SELECT ta.name, ta.academic_term, ta.admission_start_date,
                   ta.admission_end_date, ta.introduction,
                   at.term_name, at.term_for_web,
                   at.term_start_date, at.term_end_date
            FROM `tabTerm Admission` ta
            INNER JOIN `tabTerm Admission Program` tap
                    ON tap.parent = ta.name
                   AND tap.parenttype = 'Term Admission'
            INNER JOIN `tabAcademic Term` at
                    ON at.name = ta.academic_term
            WHERE ta.docstatus = 1
              AND ta.published = 1
              AND ta.admission_end_date >= %(today)s
              AND tap.program = %(program)s
            ORDER BY ta.admission_start_date ASC
            """,
            {"today": today(), "program": self.name},
            as_dict=True,
        )
        today_d = getdate()
        for w in windows:
            w["term_label"] = w.term_for_web or w.term_name or w.academic_term
            w["apply_window_display"] = "{} – {}".format(
                format_date(w.admission_start_date), format_date(w.admission_end_date)
            )
            w["term_window_display"] = (
                "{} – {}".format(
                    format_date(w.term_start_date), format_date(w.term_end_date)
                )
                if w.term_start_date and w.term_end_date
                else None
            )
            start = getdate(w.admission_start_date)
            end = getdate(w.admission_end_date)
            if start > today_d:
                w["status_label"] = _("Opens soon")
                w["indicator"] = "blue"
            elif end == today_d:
                w["status_label"] = _("Last day to apply")
                w["indicator"] = "red"
            else:
                w["status_label"] = _("Now accepting applications")
                w["indicator"] = "green"
        return windows

    def _resolve_continuous_term(self):
        fields = [
            "name",
            "term_name",
            "term_for_web",
            "term_start_date",
            "term_end_date",
        ]
        current = frappe.db.get_value(
            "Academic Term",
            {"iscurrent_acterm": 1},
            fields,
            as_dict=True,
        )
        if not current:
            upcoming = frappe.get_all(
                "Academic Term",
                filters={"term_start_date": [">", today()]},
                fields=fields,
                order_by="term_start_date asc",
                limit=1,
            )
            current = upcoming[0] if upcoming else None
        if not current:
            return None
        current["term_label"] = (
            current.get("term_for_web") or current.get("term_name") or current["name"]
        )
        if current.get("term_start_date") and current.get("term_end_date"):
            current["term_window_display"] = "{} – {}".format(
                format_date(current["term_start_date"]),
                format_date(current["term_end_date"]),
            )
        else:
            current["term_window_display"] = None
        return current

    def get_course_list(self):
        course_list = [
            frappe.get_doc("Course", program_course.course)
            for program_course in self.courses
            if not program_course.disabled
        ]
        return course_list


@frappe.whitelist()
def apply_required_on_enroll(program):
    """Explicit, append-only backfill: push the program's currently-flagged
    mandatory-on-enrollment courses onto active enrollments' snapshots and
    auto-enroll where an offering is open. Triggered from the Program form
    button (see program.js) or bench. See ADR 035."""
    frappe.only_for(("Registrar", "System Manager"))
    from seminary.seminary.required_enrollment import reconcile_required_enrollments

    return reconcile_required_enrollments(program)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_program_tracks(doctype, txt, searchfield, start, page_len, filters):
    if not filters.get("program"):
        return []

    return frappe.db.sql(
        """SELECT name, track_name
        FROM `tabProgram Track`
        WHERE parent = %(program)s
            AND name LIKE %(txt)s
        ORDER BY track_name
        LIMIT %(start)s, %(page_len)s""",
        {
            "program": filters["program"],
            "txt": "%{0}%".format(txt),
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_competency_courses(doctype, txt, searchfield, start, page_len, filters):
    """Courses eligible for a competency-based program's curriculum (ADR 065).

    A course qualifies when it uses the framework's grading scale and defines at
    least one active competency. Program.validate enforces the same rule; this
    only keeps the registrar from picking a course that would be rejected.
    """
    framework = (filters or {}).get("competency_framework")
    if not framework:
        return []
    scale = frappe.db.get_value("Competency Framework", framework, "grading_scale")
    if not scale:
        return []

    return frappe.db.sql(
        """SELECT c.name, c.coursecode
        FROM `tabCourse` c
        WHERE c.disabled = 0
            AND c.default_grading_scale = %(scale)s
            AND EXISTS (
                SELECT 1 FROM `tabCourse Competency` cc
                WHERE cc.course = c.name AND cc.is_active = 1
            )
            AND (c.name LIKE %(txt)s OR c.coursecode LIKE %(txt)s)
        ORDER BY c.name
        LIMIT %(start)s, %(page_len)s""",
        {
            "scale": scale,
            "txt": "%{0}%".format(txt),
            "start": start,
            "page_len": page_len,
        },
    )
