import frappe
from frappe.desk.form.meta import get_code_files_via_hooks
from frappe.website.doctype.web_form.web_form import WebForm


class SeminaryWebForm(WebForm):
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
