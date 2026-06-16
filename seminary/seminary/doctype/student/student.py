# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.model.document import Document
from frappe.utils import getdate, today
from erpnext import get_default_currency
from frappe.utils.nestedset import get_root_of


class Student(Document):
    def validate(self):
        self.resolve_person()
        self.set_title()
        self.validate_dates()
        self.validate_user()

        if self.student_applicant:
            self.check_unique()
            self.update_applicant_status()

    def on_update(self):
        # for each student check whether a customer exists or not if it does not exist then create a customer with customer group student
        # This prevents from polluting users data
        self.set_customer_group()
        if self.customer:
            self.update_linked_customer()
        else:
            self.create_customer()
        self.update_person_links()

    def resolve_person(self):
        """Person spine seam (ADR 042). Admission path: reuse the applicant's
        Person; standalone creation: ensure one from the typed fields. After
        the link exists, the Person is authoritative and the local contact
        fields are read-only mirrors hydrated here (fetch_from can't source
        Person child rows, and validate_user below needs the email in-row)."""
        from seminary.seminary import person as person_spine

        if not self.person and self.student_applicant:
            self.person = frappe.db.get_value(
                "Student Applicant", self.student_applicant, "person"
            )
        if not self.person:
            if not self.student_email_id:
                return  # nothing to key on; validate_user will complain anyway
            self.person = person_spine.ensure_person(
                email=self.student_email_id,
                first_name=self.first_name,
                middle_name=self.middle_name,
                last_name=self.last_name,
                mobile=self.student_mobile_number,
                country=self.country,
                image=self.image,
                gender=self.gender,
            )
        self._hydrate_from_person()

    def _hydrate_from_person(self):
        spine = frappe.db.get_value(
            "Person",
            self.person,
            [
                "first_name",
                "middle_name",
                "last_name",
                "primary_email",
                "primary_mobile",
            ],
            as_dict=True,
        )
        if not spine:
            return
        if spine.first_name:
            self.first_name = spine.first_name
        self.middle_name = spine.middle_name
        self.last_name = spine.last_name
        if spine.primary_email:
            self.student_email_id = spine.primary_email
        if spine.primary_mobile:
            self.student_mobile_number = spine.primary_mobile

    def update_person_links(self):
        """Attach the system records this role created to the spine."""
        from seminary.seminary import person as person_spine

        if not self.person:
            return
        if self.user and not frappe.db.get_value("Person", self.person, "user"):
            frappe.db.set_value(
                "Person", self.person, "user", self.user, update_modified=False
            )
        # Gender is a shared human attribute: keep the spine current from the
        # student record (the usual entry point for a student's gender).
        if (
            self.gender
            and frappe.db.get_value("Person", self.person, "gender") != self.gender
        ):
            frappe.db.set_value(
                "Person", self.person, "gender", self.gender, update_modified=False
            )
        customer = self.customer or frappe.db.get_value(
            "Student", self.name, "customer"
        )
        person_spine.link_customer(self.person, customer)

    def set_customer_group(self):
        if frappe.flags.in_demo_install:
            return
        if not self.customer_group:
            self.customer_group = _("Student")
            frappe.db.set_value("Student", self.name, "customer_group", _("Student"))

    # Validate Functions
    def set_title(self):
        self.student_name = " ".join(
            filter(None, [self.first_name, self.middle_name, self.last_name])
        )

    def validate_dates(self):

        if self.date_of_birth and getdate(self.date_of_birth) >= getdate():
            frappe.throw(_("Date of Birth cannot be greater than today."))

        if self.date_of_birth and getdate(self.date_of_birth) >= getdate(
            self.joining_date
        ):
            frappe.throw(_("Date of Birth cannot be greater than Joining Date."))

        if self.joining_date:
            for record in self.leaving_records:
                if record.date_of_leaving and getdate(self.joining_date) > getdate(
                    record.date_of_leaving
                ):
                    frappe.throw(_("Joining Date can not be greater than Leaving Date"))

    def validate_user(self):
        """Create a website user for student creation if not already exists"""
        if not frappe.db.exists("User", self.student_email_id):
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
            self.user = student_user.name
        else:
            student_user = frappe.get_doc("User", self.student_email_id)
            student_user.add_roles("Student")
            student_user.save(ignore_permissions=True)
            self.user = student_user.name

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
        print("get_program_enrollments was called")
        program_enrollments = []
        program_enrollments = frappe.get_all(
            "Program Enrollment",
            filters={"student": self.name},
            fields=[
                "program",
                "pgmenrol_active",
                "enrollment_date",
                "date_of_comcusion",
            ],
        )
        if not program_enrollments:
            return "No Program Enrollments Found"
        else:
            print(program_enrollments)
            return program_enrollments

    # End of Validate Functions

    # On Update Functions
    def update_linked_customer(self):
        customer = frappe.get_doc("Customer", self.customer)
        if self.customer_group:
            customer.customer_group = self.customer_group
        customer.customer_name = self.student_name
        customer.image = self.image
        customer.save()

        frappe.msgprint(_("Customer {0} updated").format(customer.name), alert=True)

    def create_customer(self):
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": self.student_name,
                "customer_group": self.customer_group
                or frappe.db.get_single_value("Selling Settings", "customer_group"),
                "customer_type": "Individual",
                "image": self.image,
            }
        ).insert()

        frappe.db.set_value("Student", self.name, "customer", customer.name)
        frappe.msgprint(
            _("Customer {0} created and linked to Student").format(customer.name),
            alert=True,
        )

        self._create_contact(customer.name)

    def _create_contact(self, customer_name):
        contact = frappe.get_doc(
            {
                "doctype": "Contact",
                "first_name": self.first_name,
                "last_name": self.last_name,
                "is_primary_contact": 1,
                "email_ids": [{"email_id": self.student_email_id, "is_primary": 1}],
                "links": [
                    {
                        "link_doctype": "Customer",
                        "link_name": customer_name,
                    }
                ],
            }
        )
        contact.insert(ignore_permissions=True)

        frappe.msgprint(
            _("Contact {0} created and linked to Customer").format(contact.name),
            alert=True,
        )

    def enroll_in_program(self, program_name):
        try:
            enrollment = frappe.get_doc(
                {
                    "doctype": "Program Enrollment",
                    "student": self.name,
                    "academic_year": frappe.get_last_doc("Academic Year").name,
                    "program": program_name,
                    "enrollment_date": frappe.utils.datetime.datetime.now(),
                }
            )
            enrollment.save(ignore_permissions=True)
        except frappe.exceptions.ValidationError:
            enrollment_name = frappe.get_list(
                "Program Enrollment",
                filters={"student": self.name, "Program": program_name},
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
