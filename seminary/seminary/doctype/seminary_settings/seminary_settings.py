# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

#: Site defaults published from this doctype on save: {default key: fieldname}.
#:
#: **Empty, and deliberately so.** It held three entries — `academic_year` and
#: `academic_term` (from `current_academic_year` / `current_academic_term`) and
#: `validate_course` — and *none* of the three fields existed on this doctype.
#: They are ERPNext Education's shape, inherited wholesale; the fields went
#: during the ERPNext decoupling and the keydict stayed. Every save therefore
#: published three empty defaults, silently, because `Document.get` returns
#: None for an unknown key and `set_default` stores it without complaint.
#:
#: The term is not coming back here. `Academic Term.iscurrent_acterm` is the
#: app-wide answer to "what term is it", `tasks._update_term_flags` is its only
#: writer, and `api.current_academic_term()` is the read. A settings field
#: restating the same fact would be a second source of truth kept in step by
#: hand — the failure ADR 068 exists to stop.
#:
#: A new entry is fine, but `test_seminary_settings` asserts its field exists.
seminary_keydict = {}


# `instructor_created_by` (Full Name / Naming Series / Employee Number) and the
# `validate` that acted on it are gone (ADR 068 §7). It toggled the `hidden`
# property setter of `Instructor.naming_series` — a field Instructor does not
# have, which is why both calls passed `validate_fields_for_doctype=False` and
# why nobody ever noticed. ADR 068 §5 then made the docname opaque
# (`INST-.#####`) unconditionally, so even the intent is gone: an instructor
# record is never named after its holder again.


class SeminarySettings(Document):
    def on_update(self):
        for key, fieldname in seminary_keydict.items():
            frappe.db.set_default(key, self.get(fieldname))

        # Settings are read all over the app and cached per site.
        frappe.clear_cache()


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
