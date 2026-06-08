import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class WithdrawalRequest(Document):
    def validate(self):
        self.validate_enrollment_active()
        self.validate_documentation_required()
        self.set_resulting_grade()
        self.auto_assign_withdrawal_rule()
        if (
            self.withdrawal_scope
            in ("All Courses This Term", "Full Program Withdrawal")
            and not self.has_parent
        ):
            self.is_parent = 1
        self.validate_separation_timing()

    def validate_enrollment_active(self):
        """Block new top-level requests against a Program Enrollment that has
        already reached a terminal status. Child requests (created during the
        cascade) and the initiate_program_separation path are built while the PE
        is still active, so this only catches manual top-level creations."""
        if not self.is_new() or self.has_parent or not self.program_enrollment:
            return
        status = frappe.db.get_value(
            "Program Enrollment", self.program_enrollment, "status"
        )
        if status in TERMINAL_STATUSES:
            frappe.throw(
                _(
                    "Program Enrollment {0} is already {1}; no further withdrawal "
                    "requests can be created for it."
                ).format(self.program_enrollment, status)
            )

    def validate_separation_timing(self):
        if self.withdrawal_scope != "Full Program Withdrawal":
            return
        if (
            self.separation_timing == "Specific Date"
            and not self.separation_effective_date
        ):
            frappe.throw(
                _(
                    "Please set a Separation Effective Date for a specific-date separation."
                )
            )

    def on_submit(self):
        if not self.is_parent:
            return
        if self._is_deferred_separation():
            # Defer the course-withdrawal cascade to the effective date; the
            # daily scheduler (process_due_separations) spawns the children then.
            self._resolve_separation_effective_date()
            return
        self.create_child_withdrawal_requests()
        self.db_set("cascade_done", 1, update_modified=False)

    def _is_deferred_separation(self):
        return (
            self.withdrawal_scope == "Full Program Withdrawal"
            and self.separation_timing
            and self.separation_timing != "Immediate"
        )

    def _resolve_separation_effective_date(self):
        if self.separation_effective_date:
            return
        if self.separation_timing == "End of Current Term":
            term = frappe.db.get_value(
                "Academic Term",
                {"iscurrent_acterm": 1},
                ["name", "term_end_date"],
                as_dict=True,
            )
            if term and term.term_end_date:
                self.db_set(
                    "separation_effective_date",
                    term.term_end_date,
                    update_modified=False,
                )

    def validate_documentation_required(self):
        if not self.withdrawal_reason:
            return
        requires_doc = frappe.db.get_value(
            "Withdrawal Reasons", self.withdrawal_reason, "requires_documentation"
        )
        if requires_doc and not self.student_documentation:
            doc_label = (
                frappe.db.get_value(
                    "Withdrawal Reasons", self.withdrawal_reason, "documentation_label"
                )
                or "documentation"
            )
            frappe.throw(f"This withdrawal reason requires {doc_label}.")

    def set_resulting_grade(self):
        # Flat Symbol resolves at validate. Calculated * resolve at academic approval
        # (when grade calc runs). Clean Drop never has a resulting grade.
        if not self.withdrawal_rule:
            self.resulting_grade = ""
            return
        rule = frappe.get_doc("Withdrawal Rules", self.withdrawal_rule)
        if rule.grade_treatment == "Flat Symbol":
            self.resulting_grade = rule.transcript_symbol or ""
        else:
            self.resulting_grade = ""

    def auto_assign_withdrawal_rule(self):
        if self.withdrawal_rule:
            return

        # Program-level separations (Full Program Withdrawal parents) carry no
        # single CEI/term to anchor a rule; children inherit/auto-assign their own.
        if not self.course_enrollment_individual:
            return

        settings = frappe.get_cached_doc("Seminary Settings")
        if not settings.term_based_withdrawal_dates:
            return

        academic_term = frappe.db.get_value(
            "Course Enrollment Individual",
            self.course_enrollment_individual,
            "academic_term",
        )
        if not academic_term:
            return

        term_rule = frappe.db.get_value(
            "Term Withdrawal Rules",
            filters={
                "academic_term": academic_term,
                "applies_until": (">=", self.withdrawal_effective_date),
            },
            fieldname=["name", "withdrawal_rule"],
            order_by="applies_until asc",
            as_dict=True,
        )
        if term_rule:
            self.withdrawal_rule = term_rule.withdrawal_rule
            self.set_resulting_grade()

    def create_child_withdrawal_requests(self):
        academic_term = (
            frappe.db.get_value(
                "Course Enrollment Individual",
                self.course_enrollment_individual,
                "academic_term",
            )
            if self.course_enrollment_individual
            else None
        )

        filters = {
            "program_ce": self.program_enrollment,
            "docstatus": 1,
            "withdrawn": 0,
        }

        if self.withdrawal_scope == "All Courses This Term":
            filters["academic_term"] = academic_term

        enrollments = frappe.get_all(
            "Course Enrollment Individual",
            filters=filters,
            fields=["name", "student_ce", "coursesc_ce", "course_data"],
        )

        effective_date = (
            self.separation_effective_date or self.withdrawal_effective_date
        )

        for enroll in enrollments:
            # A program-origin parent has no own CEI to skip.
            if (
                self.course_enrollment_individual
                and enroll.name == self.course_enrollment_individual
            ):
                continue

            existing = frappe.db.exists(
                "Withdrawal Request",
                {
                    "course_enrollment_individual": enroll.name,
                    "docstatus": ("!=", 2),
                },
            )
            if existing:
                continue

            child_req = frappe.get_doc(
                {
                    "doctype": "Withdrawal Request",
                    "student": self.student,
                    "program_enrollment": self.program_enrollment,
                    "course_enrollment_individual": enroll.name,
                    "withdrawal_scope": self.withdrawal_scope,
                    "is_parent": 0,
                    "has_parent": 1,
                    "parent_withdrawal": self.name,
                    "withdrawal_reason": self.withdrawal_reason,
                    "student_comment": self.student_comment,
                    "student_documentation": self.student_documentation,
                    "withdrawal_effective_date": effective_date,
                    "withdrawal_rule": self.withdrawal_rule,
                }
            )
            child_req.insert(ignore_permissions=True)
            child_req.submit()

            # Add to child table via direct DB insert to avoid modifying submitted parent
            child_row = frappe.get_doc(
                {
                    "doctype": "Withdrawal Courses",
                    "parent": self.name,
                    "parenttype": "Withdrawal Request",
                    "parentfield": "withdrawal_courses",
                    "course_enrollment_individual": enroll.name,
                    "withdrawal_request": child_req.name,
                }
            )
            child_row.db_insert()


TERMINAL_STATUSES = ("Withdrawn", "Dismissed", "Graduated", "Transferred")


@frappe.whitelist()
def initiate_program_separation(
    program_enrollment,
    withdrawal_reason,
    effective_date=None,
    timing="Immediate",
    separation_status="Withdrawn",
    separation_category="Voluntary",
    comment=None,
):
    """Create a program-level Full Program Withdrawal request (no pre-selected
    CEI). Shared entry point for the Program Enrollment form button and the
    disciplinary dismissal path. Returns the new request's name.

    The request is created in Draft and flows through the Course Withdrawal
    workflow like any registrar-initiated separation; completion drives the
    Program Enrollment terminal transition via process_completion -> the spine.
    """
    status = frappe.db.get_value("Program Enrollment", program_enrollment, "status")
    if status in TERMINAL_STATUSES:
        frappe.throw(
            _("Program Enrollment {0} is already {1}.").format(
                program_enrollment, status
            )
        )

    existing = frappe.db.exists(
        "Withdrawal Request",
        {
            "program_enrollment": program_enrollment,
            "withdrawal_scope": "Full Program Withdrawal",
            "is_parent": 1,
            "docstatus": ("<", 2),
        },
    )
    if existing:
        frappe.throw(
            _("A program separation request ({0}) is already in progress.").format(
                existing
            )
        )

    student = frappe.db.get_value("Program Enrollment", program_enrollment, "student")
    doc = frappe.get_doc(
        {
            "doctype": "Withdrawal Request",
            "program_enrollment": program_enrollment,
            "student": student,
            "withdrawal_scope": "Full Program Withdrawal",
            "is_parent": 1,
            "withdrawal_reason": withdrawal_reason,
            "withdrawal_effective_date": effective_date or today(),
            "separation_timing": timing or "Immediate",
            "separation_effective_date": (
                effective_date if (timing and timing == "Specific Date") else None
            ),
            "separation_status": separation_status,
            "separation_category": separation_category,
            "student_comment": comment,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name
