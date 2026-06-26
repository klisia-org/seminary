# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.csvutils import getlink

# Roles allowed to bypass the prerequisite gate via the no_prereq flag.
_PREREQ_OVERRIDE_ROLES = {
    "Registrar",
    "Program Chair",
    "Seminary Manager",
    "System Manager",
}


def _user_can_override_prereqs():
    return bool(_PREREQ_OVERRIDE_ROLES & set(frappe.get_roles(frappe.session.user)))


class CourseEnrollmentIndividual(Document):
    def validate(self):
        self.validate_duplicate()
        self.validate_duplicate_course()
        self._hydrate_program_flags()
        self._compute_seat_availability()
        self._validate_prerequisites()
        self._warn_schedule_conflict()

    def _warn_schedule_conflict(self):
        """Warn (never block) when this enrollment overlaps another of the
        student's active sections (ADR 050).

        Double-booking is allowed on purpose — a waitlisted student often holds
        a less-desired section at the same time until the waitlist clears — so
        this only surfaces a notice. The CEI form script (before_save) shows an
        interactive "Proceed Anyway / Cancel" confirm; this server-side check is
        the non-interactive safety net for API/registrar-script paths that
        bypass the form.
        """
        if (
            frappe.flags.in_install
            or frappe.flags.in_migrate
            or frappe.flags.in_demo_install
        ):
            return
        if self.audit or not (self.student_ce and self.coursesc_ce):
            return

        from seminary.seminary.utils import student_schedule_conflicts

        clashes = student_schedule_conflicts(
            self.student_ce, self.coursesc_ce, exclude_cei=self.name
        )
        if not clashes:
            return

        lines = "<br>".join(
            _("{0} on {1} ({2}–{3})").format(
                c.title or c.course_schedule, c.meetdate, c.from_time, c.to_time
            )
            for c in clashes
        )
        frappe.msgprint(
            _("Schedule conflict: this section overlaps the student's:<br>{0}").format(
                lines
            ),
            title=_("Schedule conflict"),
            indicator="orange",
        )

    def _validate_prerequisites(self):
        """Block enrollment when the course has an unmet mandatory prerequisite.

        Authoritative server-side gate (the courses_for_student picker is the
        student-facing UX, but this is the real boundary). A registrar can
        override by ticking ``no_prereq`` ("Don't check pre-requisites"); the
        override is honored only for staff, so a student-driven enrollment can't
        set the flag to skip the check.
        """
        if (
            frappe.flags.in_install
            or frappe.flags.in_migrate
            or frappe.flags.in_demo_install
        ):
            return
        if self.no_prereq and _user_can_override_prereqs():
            return
        if not (self.program_ce and self.course_data):
            return

        from seminary.seminary.required_enrollment import unmet_prerequisites

        missing = unmet_prerequisites(self.program_ce, self.course_data)
        if missing:
            frappe.throw(
                _(
                    "Cannot enroll in {0}: missing mandatory prerequisite(s): {1}. "
                    "A registrar can override by ticking "
                    "“Don't check pre-requisites” on this enrollment."
                ).format(self.course_data, ", ".join(missing))
            )

    def _compute_seat_availability(self):
        """Set ``seat_available`` so the workflow can route a submission to a
        seat vs. the waitlist. Read live from the section's seat count (the
        same pattern as the payment-gating flags above). Excludes self so a
        re-save of an existing seat-holder doesn't count against itself.
        """
        from seminary.seminary.waitlist import is_seat_available

        self.seat_available = (
            1 if is_seat_available(self.coursesc_ce, exclude_cei=self.name) else 0
        )

    def _hydrate_program_flags(self):
        """Mirror payment-gating flags from the linked Program.

        We can't rely on JSON `fetch_from: program_data.<field>` because
        `program_data` is itself a fetch_from of `program_ce.program`, and
        Frappe's two-level chain doesn't always resolve in a single validate
        pass. Reading the source live keeps the workflow conditions honest.
        """
        program = self.program_data
        if not program and self.program_ce:
            program = frappe.db.get_value(
                "Program Enrollment", self.program_ce, "program"
            )
            self.program_data = program
        if not program:
            return
        flags = frappe.db.get_value(
            "Program",
            program,
            ["is_free", "require_pay_submit", "percent_to_pay", "registrar_block_cei"],
            as_dict=True,
        )
        if not flags:
            return
        self.is_free = flags.is_free or 0
        self.require_pay_submit = flags.require_pay_submit or 0
        self.percent_to_pay = flags.percent_to_pay or 0
        self.registrar_block_cei = flags.registrar_block_cei or 0

    def on_submit(self):
        # Waitlisted students hold a queue position, not a seat — no invoice is
        # raised until they are promoted (see waitlist._promote_cei, which calls
        # generate_enrollment_invoice at that point).
        if self.workflow_state == "Waitlisted":
            return
        self.generate_enrollment_invoice()

    def generate_enrollment_invoice(self):
        """Raise the enrollment Sales Invoice once. Free programs just flag
        ``cei_si``; everyone else gets an invoice via ``get_inv_data_ce``.

        Idempotent on ``cei_si``. Shared by on_submit (Draft → Awaiting Payment
        / Submitted) and by waitlist promotion (Waitlisted → Awaiting Payment /
        Submitted), so a promoted student is billed exactly like a directly
        enrolled one.
        """
        if self.cei_si:
            return
        if frappe.db.get_value("Program", self.program_data, "is_free"):
            self.db_set("cei_si", 1)
            return
        # Billing is delegated to the financial backend; with none installed the
        # null backend is a no-op and the enrollment proceeds as free.
        from seminary.seminary.financial.backend import get_financial_backend

        get_financial_backend().generate_enrollment_invoice(self)
        self.db_set("cei_si", 1)

    def before_cancel(self):
        """Block cancellation if the course has already started.

        Exception: a pre-seat unpaid release (api.cancel_unpaid_enrollment) sets
        ``allow_unpaid_release`` and is gated instead on the section still being
        Open for Enrollment — an unpaid, unrostered student dropping out before
        being seated isn't a post-start withdrawal.
        """
        from frappe.utils import getdate

        if self.flags.get("allow_unpaid_release"):
            return

        if self.coursesc_ce:
            start_date = frappe.db.get_value(
                "Course Schedule", self.coursesc_ce, "c_datestart"
            )
            if start_date and getdate(start_date) <= getdate(frappe.utils.today()):
                frappe.throw(
                    _(
                        "Cannot cancel enrollment after course has started ({0}). "
                        "Please use a Withdrawal Request instead."
                    ).format(start_date)
                )

    # Cancelling the linked Sales Invoices on CEI cancel is owned by the oikonomos
    # bridge (oikonomos.financial.backend.on_cei_cancel, via doc_events). A
    # Frappe-only seminary cancels a CEI without touching billing.

    def validate_duplicate(self):
        CEI = frappe.get_list(
            "Course Enrollment Individual",
            filters={
                "program_ce": (self.program_ce),
                "coursesc_ce": self.coursesc_ce,
                "docstatus": ("=", 1),
                "audit": ("=", 0),
                "course_cancelled": ("=", 0),
            },
        )
        if CEI:
            frappe.throw(
                _("This Course Enrollment {0} already exists.").format(
                    getlink("Course Enrollment Individual", CEI[0].name)
                )
            )

    def validate_duplicate_course(self):
        CEI = frappe.db.sql(
            """select c.coursesc_ce
                from `tabProgram Course` a, `tabCourse Enrollment Individual` c, `tabProgram Enrollment Course` p
                where c.course_data = a.course AND
                a.repeatable = '0' AND
                c.docstatus = '1' AND
                c.audit = '0' AND
                c.course_data = %s AND
                c.program_ce = p.parent AND
                p.course_name = c.course_data AND
                p.status = "Pass" AND
                c.program_ce = %s""",
            (self.course_data, self.program_ce),
        )
        if CEI:
            frappe.throw(
                _(
                    "Student already enrolled in {0} for credit. If students should be able to enroll more than once, please adjust the program course settings to make this course repeatable."
                ).format(getlink("Course Enrollment Individual", CEI[0][0]))
            )

    @frappe.whitelist()
    def get_credits(self):
        pe = self.program_data
        ce = self.course_data
        audit = self.audit
        if audit == 1:
            credits = 0
        else:
            print("Audit is not 1")
            credits = frappe.db.sql(
                """select pgmcourse_credits from `tabProgram Course` where parent = %s and course = %s""",
                (pe, ce),
            )
            if credits:
                credits = credits[0][0]
                print(credits)
            else:
                credits = 0

        return credits

    @frappe.whitelist()
    def get_credits2(self):
        pe = self.program_data
        ce = self.course_data
        audit = self.audit
        if audit == 1:
            credits = 0
        else:
            print("Audit is not 1")
            credits = frappe.db.sql(
                """select pgmcourse_credits from `tabProgram Course` where parent = %s and course = %s""",
                (pe, ce),
            )
            credits = credits[0][0] if credits else 0
            print(credits)
            doc = frappe.get_doc("Course Enrollment Individual", self.name)
            doc.credits = credits
        return credits

    @frappe.whitelist()
    def get_inv_data_ce(self):
        """Raise this enrollment's Sales Invoices via the financial backend.

        The billing engine (payer resolution, scholarship math, invoice
        construction) lives in the oikonomos bridge; seminary keeps only this
        whitelisted entry point so the desk form button and the lifecycle still
        call it by name. With no backend installed this is a no-op and the
        enrollment proceeds as free.
        """
        from seminary.seminary.financial.backend import get_financial_backend

        return get_financial_backend().generate_enrollment_invoice(self)
