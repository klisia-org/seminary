import frappe
from frappe.model.document import Document


class CourseWithdrawalRequest(Document):
    def validate(self):
        self.validate_documentation_required()
        self.set_resulting_grade()
        self.auto_assign_withdrawal_rule()
        if (
            self.withdrawal_scope
            in ("All Courses This Term", "Full Program Withdrawal")
            and not self.has_parent
        ):
            self.is_parent = 1

    def on_submit(self):
        if self.is_parent:
            self.create_child_withdrawal_requests()

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
        if not self.withdrawal_rule:
            self.resulting_grade = ""
            return
        rule = frappe.get_doc("Withdrawal Rules", self.withdrawal_rule)
        if rule.exclude_from_grade_calculation and rule.grading_symbol:
            self.resulting_grade = rule.grading_symbol
        elif not rule.exclude_from_grade_calculation and rule.consider_grade_as:
            self.resulting_grade = frappe.db.get_value(
                "Grading Scale Interval", rule.consider_grade_as, "grade_code"
            )
        else:
            self.resulting_grade = ""

    def auto_assign_withdrawal_rule(self):
        if self.withdrawal_rule:
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
        academic_term = frappe.db.get_value(
            "Course Enrollment Individual",
            self.course_enrollment_individual,
            "academic_term",
        )

        filters = {
            "program_ce": self.program_enrollment,
            "docstatus": 1,
        }

        if self.withdrawal_scope == "All Courses This Term":
            filters["academic_term"] = academic_term

        enrollments = frappe.get_all(
            "Course Enrollment Individual",
            filters=filters,
            fields=["name", "student_ce", "coursesc_ce", "course_data"],
        )

        for enroll in enrollments:
            if enroll.name == self.course_enrollment_individual:
                continue

            existing = frappe.db.exists(
                "Course Withdrawal Request",
                {
                    "course_enrollment_individual": enroll.name,
                    "docstatus": ("!=", 2),
                },
            )
            if existing:
                continue

            child_req = frappe.get_doc(
                {
                    "doctype": "Course Withdrawal Request",
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
                    "withdrawal_effective_date": self.withdrawal_effective_date,
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
                    "parenttype": "Course Withdrawal Request",
                    "parentfield": "withdrawal_courses",
                    "course_enrollment_individual": enroll.name,
                    "course_withdrawal_request": child_req.name,
                }
            )
            child_row.db_insert()
