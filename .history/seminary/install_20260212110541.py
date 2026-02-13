import frappe

# from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.page.setup_wizard.setup_wizard import make_records
import os
import re
from frappe.desk.doctype.global_search_settings.global_search_settings import (
    update_global_search_doctypes,
)
from frappe.utils.dashboard import sync_dashboards
from frappe import _


# TODO: create uninstall file and remove all the custom fields, roles, assessment groups, fixtures, etc
# TODO: Remove all Items created when Fee Category is created
# TODO: Remove all Customers (with group = Student) & Users created (with role = Student) when Student is created.


def after_install():
    setup_fixtures()
    create_studentappl_role()
    create_student_role()
    create_registrar_role()
    create_instructor_role()
    get_custom_fields()
    delete_genders()


def setup_fixtures():
    records = [
        # Item Group Records
        {"doctype": "Item Group", "item_group_name": "Tuition"},
        # Customer Group Records
        {
            "doctype": "Customer Group",
            "customer_group_name": "Student",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Donor",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Church",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Denomination",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Seminary",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Para-church Organization",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Alumni",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Board Member",
            "default_price_list": _("Standard Selling"),
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Volunteer",
            "default_price_list": _("Standard Selling"),
        },
        # UOM
        {"doctype": "UOM", "uom_name": _("Academic Event"), "must_be_whole_number": 0},
        {"doctype": "UOM", "uom_name": _("Credit hour"), "must_be_whole_number": 0},
    ]
    make_records(records)


def create_studentappl_role():
    if not frappe.db.exists("Role", _("Student Applicant")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Student Applicant"), "desk_access": 0}
        ).save()


def create_student_role():
    if not frappe.db.exists("Role", _("Student")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Student"), "desk_access": 0}
        ).save()


def create_registrar_role():
    if not frappe.db.exists("Role", _("Registrar")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Registrar"), "desk_access": 1}
        ).save()


def create_instructor_role():
    if not frappe.db.exists("Role", _("Instructor")):
        frappe.get_doc(
            {"doctype": "Role", "role_name": _("Instructor"), "desk_access": 1}
        ).save()


def get_custom_fields():
    """Seminary specific custom fields that needs to be added to the Sales Invoice DocType."""
    return {
        "Sales Invoice": [
            {
                "fieldname": "student_info_section",
                "fieldtype": "Section Break",
                "label": __("Student Info"),
                "collapsible": 1,
                "insert_after": "ignore_pricing_rule",
            },
            {
                "fieldname": "student",
                "fieldtype": "Link",
                "label": __("Student"),
                "options": __("Student"),
                "insert_after": "student_info_section",
            },
        ],
    }


def delete_genders():
    # Delete auto inserted genders
    frappe.db.sql(
        "DELETE FROM `tabGender` WHERE name NOT IN (%s, %s)",
        (__("Male"), __("Female")),
    )
