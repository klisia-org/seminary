# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Guest endpoints for the external recommender portal.

The recommender receives an email containing a tokenized link
(/recommender-form/<rl_name>?token=<token>). These endpoints validate the
token without requiring a Frappe login and let the recommender retrieve the
request details and submit their letter.
"""

import hmac

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, now_datetime, today


# Keyed on the letter, not the IP: this is the token *attempt counter*
# p005a A06-6 says the recommender path never had. 60 an hour is far more than
# a real recommender needs and meaningless against a 256-bit token, and capping
# per letter means rotating addresses does not buy more guesses (p010 H6).
@frappe.whitelist(allow_guest=True)
@rate_limit(key="name", limit=60, seconds=3600, ip_based=False)
def get_request(name, token):
    """Return the public-facing details of a Recommendation Letter request."""
    doc = _validate_token(name, token)

    student_name = frappe.db.get_value("Student", doc.student, "student_name") or ""
    program = (
        frappe.db.get_value("Program Enrollment", doc.program_enrollment, "program")
        or ""
    )

    return {
        "name": doc.name,
        "recommender_name": doc.recommender_name,
        "recommender_email": doc.recommender_email,
        "recommender_role": doc.recommender_role,
        "student_name": student_name,
        "program": program,
        "token_expires_on": doc.token_expires_on,
        "already_submitted": bool(doc.submitted_on),
    }


# This one reads the *entire request body* and inserts a File. Token-gated,
# but with no per-token quota it was the cheapest way to fill a disk from
# outside the session (p005a A09-4).
@frappe.whitelist(allow_guest=True)
@rate_limit(key="name", limit=20, seconds=3600, ip_based=False)
def upload_attachment(name, token):
    """Token-gated file upload for the recommender portal.

    The standard `upload_file` endpoint requires an authenticated user.
    Recommenders are unauthenticated guests, so we accept the upload
    here after validating the token, then create the File doc attached
    to the Recommendation Letter on their behalf.

    Returns the new file_url, which the form then submits via
    `submit_letter` as `attachment_url`.
    """
    doc = _validate_token(name, token)
    if doc.submitted_on:
        frappe.throw(
            _("This recommendation has already been submitted."),
            frappe.PermissionError,
        )

    files = frappe.request.files
    if not files or "file" not in files:
        frappe.throw(_("No file uploaded."))

    upload = files["file"]
    content = upload.stream.read()
    if not content:
        frappe.throw(_("Uploaded file is empty."))

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": upload.filename,
            "is_private": 1,
            "attached_to_doctype": "Recommendation Letter",
            "attached_to_name": doc.name,
            "content": content,
        }
    )
    file_doc.save(ignore_permissions=True)

    return {"file_url": file_doc.file_url, "file_name": file_doc.file_name}


@frappe.whitelist(allow_guest=True)
@rate_limit(key="name", limit=20, seconds=3600, ip_based=False)
def submit_letter(name, token, body, attachment_url=None):
    """Persist the recommender's letter and advance the workflow to Submitted."""
    doc = _validate_token(name, token)

    if doc.submitted_on:
        frappe.throw(
            _("This recommendation has already been submitted."), frappe.PermissionError
        )
    if not body or not body.strip():
        frappe.throw(_("Letter body is required."))

    doc.letter_body = body
    if attachment_url and _is_own_attachment(doc.name, attachment_url):
        doc.letter_attachment = attachment_url
    doc.submitted_on = now_datetime()
    doc.save(ignore_permissions=True)

    # Workflow advance via db.set_value — bypasses validate_workflow's
    # role check, which would reject the Guest session running this
    # endpoint. The token already authenticated the recommender's
    # identity. (See feedback_workflow_conditions memory.)
    doc.db_set("workflow_state", "Submitted", update_modified=False)

    # Reflect onto SGR via the doctype's own hook.
    doc.run_method("on_update_after_submit")

    return {"name": doc.name, "submitted_on": str(doc.submitted_on)}


def _is_own_attachment(name, file_url):
    """Only a File that `upload_attachment` attached to this very letter may be
    recorded as its attachment; any other URL is ignored rather than linked."""
    return bool(
        frappe.db.exists(
            "File",
            {
                "file_url": file_url,
                "attached_to_doctype": "Recommendation Letter",
                "attached_to_name": name,
            },
        )
    )


def _validate_token(name, token):
    """Authenticate the recommender's link. A missing letter, a wrong token and
    an expired token all fail with the same message and without loading the
    document, so the endpoint cannot be used to probe which letters exist."""
    invalid = _("Invalid or expired link.")
    if not name or not token:
        frappe.throw(invalid, frappe.PermissionError)

    row = frappe.db.get_value(
        "Recommendation Letter",
        name,
        ["request_token", "token_expires_on"],
        as_dict=True,
    )
    if (
        not row
        or not row.request_token
        or not hmac.compare_digest(str(row.request_token), str(token))
    ):
        frappe.throw(invalid, frappe.PermissionError)

    if row.token_expires_on and getdate(row.token_expires_on) < getdate(today()):
        frappe.throw(invalid, frappe.PermissionError)

    doc = frappe.get_doc("Recommendation Letter", name)

    if doc.workflow_state == "Approved" or doc.workflow_state == "Rejected":
        frappe.throw(
            _("This recommendation is no longer accepting input."),
            frappe.PermissionError,
        )

    return doc
