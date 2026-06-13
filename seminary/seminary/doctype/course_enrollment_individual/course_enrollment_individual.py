# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.csvutils import getlink

from seminary.seminary.billing import build_and_create_invoice as create_payer_invoice

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
        self.get_inv_data_ce()
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

    def on_cancel(self):
        """Cancel linked Sales Invoices when CEI is cancelled."""
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "custom_cei": self.name,
                "docstatus": 1,
                "is_return": 0,
            },
            pluck="name",
        )

        for inv_name in invoices:
            si = frappe.get_doc("Sales Invoice", inv_name)
            si.flags.ignore_permissions = True
            si.cancel()

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
        audithours = frappe.db.get_single_value("Seminary Settings", "auditcredit")
        is_audit = self.audit
        stulink = self.student_ce
        # Only the student's own payer line carries a scholarship; resolve it at
        # invoice time and book the forgiveness to a separate invoice.
        student_customer = (
            frappe.db.get_value("Student", stulink, "customer") or stulink
        )
        academic_term = self.academic_term or frappe.db.get_value(
            "Course Schedule", self.coursesc_ce, "academic_term"
        )
        inv_data = []
        inv_data = frappe.db.sql(
            """select cei.student_ce, cei.audit, cei.credits, cei.program_data,  pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate
		from `tabCourse Enrollment Individual` cei,  `tabFee Category` fc, `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabCustomer Group` cg, `tabItem Price` ip
		where cei.name = %s and
		cei.program_ce = pfc.pf_pe and
		pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		cei.cei_si =0 and
		fc.is_audit = %s and
		pep.pep_event = 'Course Enrollment'""",
            (self.name, is_audit),
            as_list=1,
        )
        rows = frappe.db.sql(
            """select count(pep.payer)
		from `tabCourse Enrollment Individual` cei,  `tabFee Category` fc, `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabCustomer Group` cg, `tabItem Price` ip
		where cei.name = %s and
		cei.program_ce = pfc.pf_pe and
		pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		cei.cei_si =0 and
		fc.is_audit = %s and
		pep.pep_event = 'Course Enrollment'""",
            (self.name, is_audit),
        )[0][0]

        audit_suffix = _(" (Audit)") if is_audit == 1 else ""
        summary = _("Course: {0}{1}").format(self.course_data, audit_suffix)

        from seminary.seminary.billing import (
            create_scholarship_invoice,
            resolve_scholarship,
        )

        i = 0
        while i < rows:
            row = inv_data[i]
            if row[11] == 1:
                qty = row[2] * row[7] / 100
            elif is_audit == 1 and audithours == 1:
                qty = row[2] * row[7] / 100
            else:
                qty = row[7] / 100

            fee_category = row[4]
            price_list_rate = row[14]
            forgiven, award = 0, None
            if row[5] == student_customer:
                student_gross = round(qty * (price_list_rate or 0), 2)
                forgiven, award = resolve_scholarship(
                    program_enrollment=self.program_ce,
                    fee_category=fee_category,
                    student_gross=student_gross,
                    academic_term=academic_term,
                )

            create_payer_invoice(
                customer=row[5],
                item_code=row[12],
                qty=qty,
                price_list_rate=price_list_rate,
                selling_price_list=row[13],
                payment_terms_template=row[8],
                summary=summary,
                student=stulink,
                link_field="custom_cei",
                link_value=self.name,
                discount_amount=(forgiven if (forgiven and award) else 0),
            )

            if forgiven and award:
                create_scholarship_invoice(
                    award=award,
                    fee_category=fee_category,
                    academic_term=academic_term,
                    scope=self.name,
                    forgiven=forgiven,
                    item_code=row[12],
                    selling_price_list=row[13],
                    payment_terms_template=row[8],
                    summary=summary,
                    student=stulink,
                    link_field="custom_cei",
                    link_value=self.name,
                )
            i += 1
