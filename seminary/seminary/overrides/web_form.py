import json

import frappe
from frappe.desk.form.meta import get_code_files_via_hooks
from frappe.website.doctype.web_form.web_form import WebForm


class SeminaryWebForm(WebForm):
    def get_context(self, context):
        """Apply Frappe's own `disabled` convention to web form pickers.

        In Desk, a Link picker silently drops rows whose target doctype has a
        Check called `disabled` — `frappe/desk/search.py` adds the filter for
        you. **A web form never goes near that code.** `process_link_field`
        rewrites a Link into an `Autocomplete` and preloads its options from
        `get_link_options`, which is a bare `frappe.get_all(doctype, filters,
        fields)` with `filters` empty on a guest form. So the one surface where
        a curated list matters most — the public application form — is the one
        surface that ignores the curation.

        Concretely: a seminary switches five of Frappe's seven seeded genders
        off, Desk honours it everywhere, and applicants are still offered all
        seven. `Web Form Field` has no `link_filters` column either, so there
        is nowhere to declare the filter per field. Hence here, generically for
        any doctype that follows the convention, rather than a special case for
        Gender.
        """
        # Captured before `super()`: `process_link_field` overwrites
        # `field.options` with the option list, so afterwards there is no
        # record of which doctype the field pointed at.
        link_targets = {
            field.fieldname: field.options
            for field in self.web_form_fields
            if field.fieldtype == "Link" and field.options
        }
        result = super().get_context(context)
        _drop_disabled_options(context, link_targets)
        return result

    def add_custom_context_and_script(self, context):
        super().add_custom_context_and_script(context)

        # Frappe core only wires up `webform_include_js` for *standard* web
        # forms (the loop lives inside an `if self.is_standard` branch). Custom,
        # desk-built forms therefore never receive shared scripts. We inject them
        # here so a seminary's own Student Applicant forms render the doctrinal
        # statement (etc.) without each author pasting a client script.
        if self.is_standard:
            return

        scripts = []
        for hook_name in (self.doc_type, "*"):
            for path in get_code_files_via_hooks("webform_include_js", hook_name):
                with open(path) as f:
                    scripts.append(frappe.render_template(f.read(), context))

        if scripts:
            existing = context.get("script") or ""
            context.script = "\n\n".join([existing, *scripts] if existing else scripts)


def _disabled_names(doctype):
    """Rows Frappe's Desk pickers would hide, or None if the doctype opts out."""
    if not frappe.get_meta(doctype).get_field("disabled"):
        return None
    return set(frappe.get_all(doctype, filters={"disabled": 1}, pluck="name"))


def _drop_disabled_options(context, link_targets):
    """Strip disabled rows from each preloaded Autocomplete option list.

    `get_link_options` returns one of three shapes depending on the target
    doctype's own settings — a JSON string of `{value,label}` when it has a
    title field shown in links, a list of `{value,label}` when it is a
    translated doctype (Gender and Country both are), and otherwise a
    newline-joined string of names. All three are handled because which one
    applies is a property of the *target*, not of our form, so a later doctype
    edit would silently switch shapes.
    """
    fields = getattr(context.get("web_form_doc"), "web_form_fields", None) or []
    for field in fields:
        doctype = link_targets.get(field.fieldname)
        if not doctype:
            continue
        hidden = _disabled_names(doctype)
        if not hidden:
            continue

        options = field.options
        if isinstance(options, str) and options.startswith("["):
            kept = [
                row for row in json.loads(options) if row.get("value") not in hidden
            ]
            field.options = json.dumps(kept, default=str)
        elif isinstance(options, list):
            field.options = [
                row
                for row in options
                if (row.get("value") if isinstance(row, dict) else row) not in hidden
            ]
        elif isinstance(options, str):
            field.options = "\n".join(
                name for name in options.split("\n") if name not in hidden
            )
