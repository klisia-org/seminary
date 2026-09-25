# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
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
    def validate(self):
        self._warn_if_unit_scope_restricts_nothing()
        self._warn_if_direct_uploads_are_unbounded()
        self._validate_financial_backend()

    def _validate_financial_backend(self):
        """The active billing app must be one that is installed and registered
        as a financial backend; the resolver silently falls back otherwise."""
        if not self.financial_backend:
            return
        from seminary.seminary.financial.backend import registered_financial_backends

        installed = list(registered_financial_backends())
        if self.financial_backend not in installed:
            frappe.throw(
                _("{0} is not an installed billing app. Choose one of: {1}").format(
                    frappe.bold(self.financial_backend),
                    ", ".join(installed) or _("none"),
                ),
                title=_("Unknown Billing App"),
            )

    def _warn_if_direct_uploads_are_unbounded(self):
        """Say so when the direct upload path has no policy to answer to.

        p005a A10-6 read this as "``direct_limit_for_user`` falls back to 2 GiB".
        It does not, where anything is configured: ``limit_for_user`` already
        resolves the per-role exceptions and then **Default Max Upload**, and the
        constant is only reached when *neither* exists. Measured 2026-09-20, all
        three sites were configured (potestas 10/40/100 MB, testable 25/400 MB,
        tlink 30/75/100 MB), so the constant bound nobody but Administrator.

        What is real is the state the finding named: a site with object storage
        wired up and no upload policy at all. The direct path deliberately
        escapes Frappe's ``max_file_size`` and nginx's body cap (ADR 040, p004),
        so there the constant is the only ceiling — and nothing says so."""
        if self.default_max_upload_mb:
            return
        if any(row.max_file_size_mb for row in (self.upload_limits or [])):
            return
        try:
            from seminary.storage import get_storage_backend

            if not get_storage_backend().is_configured():
                return  # no direct path: Frappe's global cap governs everything
        except Exception:  # nosec B110 -- a settings hint must never block a save
            return

        from seminary.storage.limits import MB, DEFAULT_MAX_DIRECT_BYTES

        frappe.msgprint(
            _(
                "Object storage is configured but no upload policy is. Direct "
                "browser uploads bypass Frappe's Max File Size, so they are "
                "bounded only by the built-in ceiling of {0} MB. Set a Default "
                "Max Upload below to govern them."
            ).format(round(DEFAULT_MAX_DIRECT_BYTES / MB)),
            title=_("Direct uploads have no configured limit"),
            indicator="orange",
        )

    def _warn_if_unit_scope_restricts_nothing(self):
        """Say so when ``Academic Unit`` scope is on but reaches everything.

        p005a A01-20: the scope has two fallbacks to School, and with both left
        open on a school that has not populated memberships the setting
        restricts nothing while the form shows it enabled. The fallbacks are
        deliberate (ADR 059 §2.1) and stay the default — but the admin should
        not have to read the source to find out they are in that state."""
        if self.faculty_read_scope != "Academic Unit":
            return

        notes = []
        if self.unit_scope_no_membership != "Own sections only":
            if not frappe.db.count("Academic Unit Membership", {"is_active": 1}):
                notes.append(
                    _(
                        "No active Academic Unit Membership exists, so every "
                        "instructor of record still reads school-wide."
                    )
                )
        if self.unit_scope_unassigned_course != "Exclude":
            unassigned = frappe.db.count(
                "Course", {"academic_unit": ["in", [None, ""]]}
            )
            if unassigned:
                notes.append(
                    _(
                        "{0} course(s) have no academic unit, so their sections "
                        "read school-wide."
                    ).format(unassigned)
                )
        if notes:
            frappe.msgprint(
                "<br>".join(notes),
                title=_("Academic Unit scope is not restricting much"),
                indicator="orange",
            )

    def on_update(self):
        for key, fieldname in seminary_keydict.items():
            frappe.db.set_default(key, self.get(fieldname))

        # Settings are read all over the app and cached per site.
        frappe.clear_cache()


@frappe.whitelist()
def financial_backend_choices():
    """Settings-form helper: the installed billing apps, so the form shows the
    Active Billing App choice only when there is a choice to make."""
    frappe.only_for("System Manager")
    from seminary.seminary.financial.backend import registered_financial_backends

    return list(registered_financial_backends())


@frappe.whitelist()
def check_payments_app():
    """Settings-form helper: is the payments app installed, and is the gateway
    field wired up as a Link to it?

    p008a G6: it had no check, and its second half CREATES two Property Setters
    -- a schema change. The ``save`` is permission-checked, so a caller without
    Property Setter write was refused there; but this is a System Manager's
    settings form, and an endpoint that alters the schema should say so before
    it starts rather than after."""
    frappe.only_for("System Manager")
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
