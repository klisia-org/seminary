# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.model.document import Document
from frappe.utils import getdate, today
from frappe.utils.nestedset import get_root_of


def _current_academic_term():
    """The term a self-service enrollment belongs to.

    One app-wide definition, read from one place: `api.current_academic_term`.
    Not `Seminary Settings` — `seminary_keydict` there maps a
    `current_academic_term` key the doctype has no field for, so asking for it
    raises rather than returning a default.
    """
    from seminary.seminary.api import current_academic_term

    return current_academic_term()


class Student(Document):
    def validate(self):
        self.validate_dates()

        if self.student_applicant:
            self.check_unique()
            self.update_applicant_status()

    def after_insert(self):
        # Not in `validate`: this creates a User and grants it the Student
        # role, and doing that mid-validation committed both even when the
        # Student itself went on to fail (ADR 068 phase 5).
        self.provision_user()

    def on_update(self):
        # Customer (billing identity) creation + Person<->Customer linking is owned
        # by the oikonomos bridge (it subscribes to Student.on_update). With no
        # bridge installed the Student is purely academic.
        self.update_person_links()

    # `resolve_person` is gone. A Student is created against a Person that
    # already exists — `seminary.seminary.intake.make_student` — and `person`
    # is reqd, so there is nothing left to resolve. Resolving it here was also
    # too late to be useful: `_validate_links` runs *before* `validate`, so a
    # `person` set in this method missed Frappe's `fetch_from` pass and the
    # mirrors stayed empty until the record was saved a second time.

    def update_person_links(self):
        """Attach the User this role created to the spine.

        Gender used to be pushed back from here, and it was the only path in
        the app that could record one. It cannot be any more: `Student.gender`
        is a `fetch_from person.gender` mirror since ADR 068 phase 4, so
        pushing it back would just write the spine's own value to itself.
        Gender is now captured at the applicant form, the importer, or by a
        Registrar on the Person — which ADR 067's readiness check must account
        for. The Customer link is owned by the oikonomos bridge."""
        if not self.person:
            return
        if self.user and not frappe.db.get_value("Person", self.person, "user"):
            frappe.db.set_value(
                "Person", self.person, "user", self.user, update_modified=False
            )

    # Validate Functions
    # `set_title` is gone: `student_name` is `fetch_from person.full_name` now,
    # so recomputing it here would fight the mirror (ADR 068).

    def validate_dates(self):
        # Date of birth lives on the Person (ADR 068). The "not in the future"
        # rule belongs there with it; what stays here is the one comparison
        # that is genuinely about *this* record — you cannot join before you
        # were born.
        dob = (
            frappe.db.get_value("Person", self.person, "date_of_birth")
            if self.person
            else None
        )
        if dob and self.joining_date and getdate(dob) >= getdate(self.joining_date):
            frappe.throw(_("Date of Birth cannot be greater than Joining Date."))

        if self.joining_date:
            for record in self.leaving_records:
                if record.date_of_leaving and getdate(self.joining_date) > getdate(
                    record.date_of_leaving
                ):
                    frappe.throw(_("Joining Date can not be greater than Leaving Date"))

    def provision_user(self):
        """Give the student a portal login, or grant the role to their existing
        one. Runs from `after_insert`, so `db_set` — a plain assignment there
        is never written.

        `student_email_id` mirrors `person.primary_email`, which the Person's
        own `assert_reachable` keeps populated for anyone holding a role. The
        guard below is for the order-of-operations case where a Student is
        created against a Person whose email has not landed yet: better to
        leave the student without a login than to hand `User.autoname` a null
        and meet an opaque `'NoneType' has no attribute 'strip'`.
        """
        if not self.student_email_id:
            frappe.msgprint(
                _(
                    "No email on {0}, so no portal login was created. Add a "
                    "primary email to the person record and re-save."
                ).format(self.person),
                indicator="orange",
                alert=True,
            )
            return

        if frappe.db.exists("User", self.student_email_id):
            student_user = frappe.get_doc("User", self.student_email_id)
        else:
            student_user = frappe.get_doc(
                {
                    "doctype": "User",
                    "first_name": self.first_name,
                    "last_name": self.last_name,
                    "email": self.student_email_id,
                    "gender": self.gender,
                    "send_welcome_email": 1,
                    "user_type": "Website User",
                }
            )
        student_user.add_roles("Student")
        student_user.save(ignore_permissions=True)
        self.db_set("user", student_user.name, update_modified=False)

    def check_unique(self):
        """Validates if the Student Applicant is Unique"""
        student = frappe.get_all(
            "Student",
            {"student_applicant": self.student_applicant, "name": ["!=", self.name]},
            pluck="name",
        )
        if len(student):
            frappe.throw(
                _("Student {0} exist against student applicant {1}").format(
                    student[0], self.student_applicant
                )
            )

    def update_applicant_status(self):
        """Updates Student Applicant status to Admitted"""
        if self.student_applicant:
            frappe.db.set_value(
                "Student Applicant",
                self.student_applicant,
                "application_status",
                "Admitted",
            )

    @frappe.whitelist()
    def get_pgmenrollments(self):
        # `date_of_comcusion` was a typo for `date_of_conclusion`, so every call
        # to this whitelisted method raised OperationalError on an unknown
        # column. Nothing in the app called it, which is how it survived.
        return frappe.get_all(
            "Program Enrollment",
            filters={"student": self.name},
            fields=[
                "program",
                "pgmenrol_active",
                "enrollment_date",
                "date_of_conclusion",
            ],
        )

    # End of Validate Functions

    def enroll_in_program(self, program_name):
        try:
            enrollment = frappe.get_doc(
                {
                    "doctype": "Program Enrollment",
                    "student": self.name,
                    "academic_year": frappe.get_last_doc("Academic Year").name,
                    # Required since the term became mandatory on Program
                    # Enrollment; without it self-enrollment (utils.
                    # enroll_in_program, a whitelisted portal endpoint) could
                    # not create a record at all.
                    "academic_term": _current_academic_term(),
                    "program": program_name,
                    # `today()`, not `datetime.now()`: validation compares this
                    # against the system timezone's today, and the process's
                    # local clock can land on the other side of midnight from
                    # it — the enrollment then fails as "before today".
                    "enrollment_date": today(),
                }
            )
            enrollment.save(ignore_permissions=True)
        except frappe.exceptions.ValidationError:
            enrollment_name = frappe.get_list(
                "Program Enrollment",
                filters={"student": self.name, "program": program_name},
            )[0].name
            return frappe.get_doc("Program Enrollment", enrollment_name)
        else:
            enrollment.submit()
            return enrollment

    def enroll_in_course(self, course_name, program_enrollment, enrollment_date=None):
        if enrollment_date is None:
            enrollment_date = frappe.utils.datetime.datetime.now()
        try:
            enrollment = frappe.get_doc(
                {
                    "doctype": "Course Enrollment",
                    "student": self.name,
                    "course": course_name,
                    "program_enrollment": program_enrollment,
                    "enrollment_date": enrollment_date,
                }
            )
            enrollment.save(ignore_permissions=True)
        except frappe.exceptions.ValidationError:
            enrollment_name = frappe.get_list(
                "Course Enrollment",
                filters={
                    "student": self.name,
                    "course": course_name,
                    "program_enrollment": program_enrollment,
                },
            )[0].name
            return frappe.get_doc("Course Enrollment", enrollment_name)
        else:
            return enrollment

    # def get_timeline_data(doctype, name):
    """Return timeline for attendance"""


# 	return dict(
# 		frappe.db.sql(
# 			"""select unix_timestamp(`date`), count(*)
# 		from `tabStudent Attendance` where
# 			student=%s
# 			and `date` > date_sub(curdate(), interval 1 year)
# 			and docstatus = 1 and status = 'Present'
# 			group by date""",
# 			name,
# 		)
# 	)
