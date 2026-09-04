import frappe

from seminary.seminary.api import get_application_payment_url


def get_context(context):
    """Render the post-application thank-you page with the Application fee
    payment options. Reached via a redirect from the Student Applicant web
    form (after_save) with `?applicant=<name>` in the query string."""
    context.no_cache = 1
    context.title = frappe._("Application received")

    applicant_name = (frappe.form_dict.get("applicant") or "").strip()
    # The applicant's `access_key`, carried through the web form's redirect.
    # Without it a guest could reach any applicant's payment link by guessing
    # docnames (ADR 068 phase 3).
    key = (frappe.form_dict.get("key") or "").strip()
    context.applicant_name = applicant_name
    context.payment_data = None

    if applicant_name:
        try:
            context.payment_data = get_application_payment_url(applicant_name, key)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "applicant_payment.get_context")

    return context
