# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import time

import frappe
from frappe import _
from frappe.model.document import Document

from seminary.seminary.overrides.salary_slip import _hrms_enabled

EDU_MIRROR_FIELDS = (
    "school_univ",
    "qualification",
    "level",
    "year_of_passing",
    "class_per",
    "maj_opt_subj",
)
EDU_SEMINARY_ONLY_FIELDS = (
    "institution_country",
    "discipline",
    "accrediting_body",
    "is_accredited",
    "is_terminal_degree",
    "evidence_attachment",
    "notes",
)


class Instructor(Document):
    def validate(self):
        self.validate_payroll_link()
        self._maybe_auto_pull_education()

    def validate_payroll_link(self):
        if not self.instructor_type:
            return
        if self.instructor_type == "Volunteer":
            return
        if not self.employee:
            frappe.throw(
                _("Instructor Type {0} requires an Employee link for payroll.").format(
                    self.instructor_type
                )
            )

    def _maybe_auto_pull_education(self):
        """Auto-pull education once, on the save where `employee` first gets set."""
        if not _hrms_enabled() or not self.employee:
            return
        if self.education or self.education_last_pulled_on:
            return
        previous = self.get_doc_before_save()
        prev_emp = previous.employee if previous else None
        if prev_emp == self.employee:
            return
        emp = frappe.get_doc("Employee", self.employee)
        for src in emp.get("education") or []:
            row = self.append("education", {})
            for f in EDU_MIRROR_FIELDS:
                row.set(f, src.get(f))
        self.education_last_pulled_on = frappe.utils.now_datetime()

    @frappe.whitelist()
    def pull_education_from_employee(self):
        """Replace Instructor education with a copy of Employee.education."""
        if not _hrms_enabled():
            frappe.throw(_("HRMS is not enabled in Seminary Settings."))
        if not self.employee:
            frappe.throw(_("No Employee linked to this Instructor."))

        emp = frappe.get_doc("Employee", self.employee)
        self.set("education", [])
        for src in emp.get("education") or []:
            row = self.append("education", {})
            for f in EDU_MIRROR_FIELDS:
                row.set(f, src.get(f))
        self.education_last_pulled_on = frappe.utils.now_datetime()
        self.save()
        return len(self.education)

    @frappe.whitelist()
    def push_education_to_employee(self):
        """Replace Employee.education with the mirror fields from Instructor.education."""
        if not _hrms_enabled():
            frappe.throw(_("HRMS is not enabled in Seminary Settings."))
        if not self.employee:
            frappe.throw(_("No Employee linked to this Instructor."))
        if not frappe.has_permission("Employee", "write", doc=self.employee):
            frappe.throw(
                _("You do not have permission to write to Employee {0}.").format(
                    self.employee
                )
            )

        emp = frappe.get_doc("Employee", self.employee)
        emp.set("education", [])
        dropped = False
        for src in self.education or []:
            row = emp.append("education", {})
            for f in EDU_MIRROR_FIELDS:
                row.set(f, src.get(f))
            if any(src.get(x) for x in EDU_SEMINARY_ONLY_FIELDS):
                dropped = True
        emp.save()
        self.db_set("education_last_pushed_on", frappe.utils.now_datetime())
        if dropped:
            frappe.msgprint(
                _(
                    "Pushed to Employee. Seminary-only fields (accreditation, evidence, notes) "
                    "are not stored on Employee and were dropped."
                ),
                indicator="orange",
            )
        return len(emp.education)

    @frappe.whitelist()
    def create_supplier(self, supplier_group=None):
        """Create a Supplier from this Instructor and link it back.

        Used for Volunteer / honorarium billing via Purchase Invoice.
        """
        if self.supplier:
            frappe.msgprint(
                _("Supplier {0} is already linked to this Instructor.").format(
                    self.supplier
                )
            )
            return self.supplier

        group = supplier_group or (
            "Instructor"
            if frappe.db.exists("Supplier Group", "Instructor")
            else frappe.db.get_single_value("Buying Settings", "supplier_group")
        )

        supplier = frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": self.instructor_name,
                "supplier_group": group,
                "supplier_type": "Individual",
                "email_id": self.prof_email,
                "mobile_no": self.phone_message,
            }
        ).insert(ignore_permissions=True)

        self.db_set("supplier", supplier.name)
        frappe.msgprint(
            _("Supplier {0} created and linked.").format(supplier.name), alert=True
        )
        return supplier.name


def get_roles_with_write_permission():
    """Get all roles that have write permission on Instructors DocType."""
    writable_roles = frappe.get_all(
        "DocPerm",
        filters={
            "parent": "Instructor",
            "write": 1,
            "permlevel": 0,
        },
        pluck="role",
    )
    return writable_roles


def user_has_only_instructor_role(user):
    """
    Check if 'Instructor' is the ONLY role granting write access
    to this DocType for this user. If they have other write-capable
    roles, don't restrict them.
    """
    user_roles = frappe.get_roles(user)
    write_roles = get_roles_with_write_permission()

    user_write_roles = set(user_roles) & set(write_roles)

    instructor_role = frappe._("Instructor")
    return user_write_roles == {instructor_role}


def has_permission(doc, ptype, user):
    if not user:
        user = frappe.session.user

    if not user_has_only_instructor_role(user):
        return True

    return doc.user == user


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user

    if not user_has_only_instructor_role(user):
        return ""

    return f"(`tabInstructor`.user = {frappe.db.escape(user)})"


def get_timeline_data(doctype, name):
    """Return timeline for course schedule meeting dates"""
    timeline_data = dict(
        frappe.db.sql(
            """
			SELECT unix_timestamp(mt.cs_meetdate), count(mt.name)
			FROM `tabCourse Schedule Meeting Dates` mt
			JOIN `tabCourse Schedule` cs ON cs.name = mt.parent
			JOIN `tabCourse Schedule Instructors` csi ON cs.name = csi.parent
			WHERE csi.instructor = %s
			GROUP BY mt.cs_meetdate
			""",
            name,
        )
    )
    if not timeline_data:
        timeline_data = {int(time.time()): 0}
    return timeline_data


@frappe.whitelist()
def update_instructorlog(doc):
    """Update Instructor Log from Course Schedule Instructors + Scheduled Course Roster."""

    inst = frappe.get_doc("Instructor", doc)
    instructor = inst.name

    current_instructor_log = frappe.db.sql(
        """
		select course, academic_term, instructor_category, n_students
		from `tabInstructor Log`
		where parent = %s
		""",
        instructor,
        as_list=1,
    )
    full_instructor_log = frappe.db.sql(
        """
		select cs.name, cs.academic_term, csi.instructor_category, count(r.name) as students
		from `tabCourse Schedule Instructors` csi, `tabCourse Schedule` cs, `tabScheduled Course Roster` r
		where csi.parent = cs.name and cs.name = r.course_sc and csi.instructor = %s
		group by cs.name, cs.academic_term, csi.instructor_category
		""",
        instructor,
        as_list=1,
    )
    instructor_log = []
    for log in full_instructor_log:
        if current_instructor_log:
            if log not in current_instructor_log:
                instructor_log.append(log)
        else:
            instructor_log.append(log)

    if not instructor_log:
        return

    for log in instructor_log:
        row = frappe.new_doc("Instructor Log")
        row.course = log[0]
        row.academic_term = log[1]
        row.instructor_category = log[2]
        row.n_students = log[3]
        row.parent = instructor
        row.parentfield = "instructor_log"
        row.parenttype = "Instructor"
        row.save()
        frappe.db.commit()
