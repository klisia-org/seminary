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
    context.invalid_link = False

    if applicant_name:
        try:
            context.payment_data = get_application_payment_url(applicant_name, key)
        except frappe.PermissionError:
            # Expected: a stale, mistyped or guessed link. One generic page for
            # "no such applicant" and "wrong key" alike (p005 A10-2). This used
            # to fall into the bare `except` below and write a full traceback to
            # Error Log, so hitting the URL in a loop filled the log -- a guest
            # could do it (p005 A10-1). Counting the denial is Phase 3 (A09-1,
            # the `seminary.security` logger).
            frappe.clear_last_message()
            context.invalid_link = True
        except Exception:
            frappe.log_error(frappe.get_traceback(), "applicant_payment.get_context")
            context.invalid_link = True
    elif frappe.form_dict.get("applicant") is not None:
        context.invalid_link = True

    return context
