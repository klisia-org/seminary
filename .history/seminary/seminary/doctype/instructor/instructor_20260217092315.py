# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series
import time


class Instructor(Document):
    pass
    # def autoname(self):
    # 	naming_method = frappe.db.get_value(
    # 		"Seminary Settings", None, "instructor_created_by"
    # 	)
    # 	if not naming_method:
    # 		frappe.throw(
    # 			_("Please setup Instructor Naming System in Seminary > Seminary Settings")
    # 		)
    # 	else:
    # 		if naming_method == "Naming Series":
    # 			set_name_by_naming_series(self)
    # 		elif naming_method == "Employee Number":
    # 			if not self.employee:
    # 				frappe.throw(_("Please select Employee"))
    # 			self.name = self.employee
    # 		elif naming_method == "Full Name":
    # 			self.name = self.instructor_name

    # def validate(self):
    # 	self.validate_duplicate_employee()

    # def validate_duplicate_employee(self):
    # 	if self.employee and frappe.db.get_value(
    # 		"Instructor", {"employee": self.employee, "name": ["!=", self.name]}, "name"
    # 	):
    # 		frappe.throw(_("Employee ID is linked with another instructor"))

def get_roles_with_write_permission():
    """Get all roles that have write permission on Instructors DocType."""
    writable_roles = frappe.get_all(
        "DocPerm",
        filters={
            "parent": "Instructors",
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
    print(f"User Roles for {user}: {user_roles}")
    write_roles = get_roles_with_write_permission()
    print(f"Write Roles for {user}: {write_roles}")

    # Roles this user has that grant write access to Instructors
    user_write_roles = set(user_roles) & set(write_roles)
    print(f"User Write Roles for {user}: {user_write_roles}")

    # Only restrict if "Instructor" is the sole write role they have
    instructor_role = frappe._("Instructor")  # translatable
    return user_write_roles == {instructor_role}


def has_permission(doc, ptype, user):
    if not user:
        user = frappe.session.user

    # Only apply filtering for users whose sole write role is "Instructor"
    if not user_has_only_instructor_role(user):
        return True

    # Instructor can only access their own record
    return doc.user == user


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user

    if not user_has_only_instructor_role(user):
        return ""

    return f"(`tabInstructors`.user = {frappe.db.escape(user)})" 

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
    print(timeline_data)
    if not timeline_data:
        timeline_data = {
            int(time.time()): 0
        }  # Set current date as cs_meetdate if timeline_data is empty
    return timeline_data


@frappe.whitelist()
def update_instructorlog(doc):
    """Update Instructor Log"""

    inst = frappe.get_doc("Instructor", doc)
    instructor = inst.name
    print("Instructor: " + instructor)
    """Update Instructor log"""
    current_instructor_log = frappe.db.sql(
        """
		select course, academic_term, inst_record, n_students
		from `tabInstructor Log`
		where parent = %s
		""",
        instructor,
        as_list=1,
    )
    full_instructor_log = frappe.db.sql(
        """
		select cs.name, cs.academic_term, csi.inst_record, count(r.name) as students
		from `tabCourse Schedule Instructors` csi, `tabCourse Schedule` cs, `tabScheduled Course Roster` r
		where csi.parent = cs.name and cs.name = r.course_sc and csi.instructor = %s
		group by cs.name, cs.academic_term, csi.inst_record
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

    if instructor_log:
        for log in instructor_log:
            doc = frappe.new_doc("Instructor Log")
            doc.course = log[0]
            doc.academic_term = log[1]
            doc.inst_record = log[2]
            doc.n_students = log[3]
            doc.parent = instructor
            doc.parentfield = "instructor_log"
            doc.parenttype = "Instructor"
            doc.save()
            frappe.db.commit()

    else:
        return
