# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
import frappe.defaults
from frappe.model.document import Document

seminary_keydict = {
    # "key in defaults": "key in Global Defaults"
    "academic_year": "current_academic_year",
    "academic_term": "current_academic_term",
    "validate_course": "validate_course",
}


class SeminarySettings(Document):
    def on_update(self):
        """update defaults"""
        for key in seminary_keydict:
            frappe.db.set_default(key, self.get(seminary_keydict[key], ""))

        # clear cache
        frappe.clear_cache()

    def get_defaults(self):
        return frappe.defaults.get_defaults()

    def validate(self):
        from frappe.custom.doctype.property_setter.property_setter import (
            make_property_setter,
        )

        if self.get("instructor_created_by") == "Naming Series":
            make_property_setter(
                "Instructor",
                "naming_series",
                "hidden",
                0,
                "Check",
                validate_fields_for_doctype=False,
            )
        else:
            make_property_setter(
                "Instructor",
                "naming_series",
                "hidden",
                1,
                "Check",
                validate_fields_for_doctype=False,
            )


@frappe.whitelist()
def check_payments_app():
    installed_apps = frappe.get_installed_apps()
    if "payments" not in installed_apps:
        return False

    filters = {
        "doctype_or_field": "DocField",
        "doc_type": "Seminary Settings",
        "field_name": "payment_gateway",
    }
    if frappe.db.exists("Property Setter", filters):
        return True

    link_property = frappe.new_doc("Property Setter")
    link_property.update(filters)
    link_property.property = "fieldtype"
    link_property.value = "Link"
    link_property.save()

    options_property = frappe.new_doc("Property Setter")
    options_property.update(filters)
    options_property.property = "options"
    options_property.value = "Payment Gateway"
    options_property.save()

    return True
