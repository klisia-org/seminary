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

def before_install():
    check_erpnext()

def after_install():
    check_erpnext()
    setup_fixtures()
    create_studentappl_role()
    create_student_role()
    create_registrar_role()
    create_instructor_role()
    get_custom_fields()
    delete_genders()
    update_company_in_item_details()

def check_erpnext():
    check_erpnext_installed()
    status = check_erpnext_setup_complete()
    if status["errors"]:
        frappe.throw(
            _("ERPNext setup is incomplete. Please complete the setup before installing {0}").format("SeminaryERP"),
            title=_("Setup Incomplete"),
        )


def check_erpnext_installed():
    """Check if ERPNext app is installed on the site."""
    installed_apps = frappe.get_installed_apps()
    if "erpnext" not in installed_apps:
        frappe.throw(
            _("ERPNext must be installed before installing {0}").format("SeminaryERP"),
            title=_("Missing Dependency"),
        )


def check_erpnext_setup_complete():
    """
    Check if ERPNext has been set up (i.e., the Setup Wizard was completed
    and at least one Company exists).
    Returns a dict with detailed status.
    """
    status = {
        "company_exists": False,
        "fiscal_year_exists": False,
        "selling_price_list_exists": False,
        "buying_price_list_exists": False,
        "default_company": None,
        "errors": [],
    }

    # Check for Company
    companies = frappe.get_all("Company", limit=1, pluck="name")
    if companies:
        status["company_exists"] = True
        status["default_company"] = companies[0]
    else:
        status["errors"].append(
            _("No Company found. Please complete the ERPNext Setup Wizard first.")
        )

    # Check for Fiscal Year
    if frappe.db.count("Fiscal Year") > 0:
        status["fiscal_year_exists"] = True
    else:
        status["errors"].append(_("No Fiscal Year found."))

    # Check for Selling Price List
    selling_pl = frappe.db.get_value(
        "Price List", {"selling": 1, "enabled": 1}, "name"
    )
    if selling_pl:
        status["selling_price_list_exists"] = True
    else:
        status["errors"].append(_("No active Selling Price List found."))

    # Check for Buying Price List
    buying_pl = frappe.db.get_value(
        "Price List", {"buying": 1, "enabled": 1}, "name"
    )
    if buying_pl:
        status["buying_price_list_exists"] = True
    else:
        status["errors"].append(_("No active Buying Price List found."))

    return status


def setup_fixtures():
    default_price_list = frappe.db.get_value(
        "Price List", {"selling": 1, "enabled": 1}, "name", order_by="creation asc"
    )
    records = [
        # Item Group Records
        {"doctype": "Item Group", "item_group_name": "Tuition"},
        # Customer Group Records
        {
            "doctype": "Customer Group",
            "customer_group_name": "Student",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Donor",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Church",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Denomination",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Seminary",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Para-church Organization",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Alumni",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Board Member",
            "default_price_list": default_price_list,
        },
        {
            "doctype": "Customer Group",
            "customer_group_name": "Volunteer",
            "default_price_list": default_price_list,
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
                "label": _("Student Info"),
                "collapsible": 1,
                "insert_after": "ignore_pricing_rule",
            },
            {
                "fieldname": "student",
                "fieldtype": "Link",
                "label":_("Student"),
                "options": _("Student"),
                "insert_after": "student_info_section",
            },
        ],
    }


def delete_genders():
    # Functionally delete Frappe's auto inserted genders
    frappe.db.sql(
        "UPDATE `tabGender` SET enabled` = 1 WHERE name IN (%s, %s)",
        (_("Male"), _("Female")),
    )

def update_company_in_item_details():
    """
    Update the company in the "Item Details" table to use the default company
    instead of the hardcoded value 'ToBeReplaced' in fixtures.
    """
    # Get the default company
    default_company = frappe.db.get_single_value("Global Defaults", "default_company")
    default_price_list = frappe.db.get_value(
        "Price List", {"selling": 1, "enabled": 1}, "name", order_by="creation asc"
    )
    default_income_account = frappe.db.get_value("Company", {"company_name": default_company}, "default_income_account")
    # Update the company in the "Item Details" table
    frappe.db.sql(
        """
        UPDATE `tabItem Details`
        SET company = %s, default_price_list = %s, income_account = %s
        WHERE company = 'ToBeReplaced'
        """,
        (default_company, default_price_list, default_income_account)
    )

    frappe.db.commit()
