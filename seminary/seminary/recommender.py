# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Guest endpoints for the external recommender portal.

The recommender receives an email containing a tokenized link
(/recommender-form/<rl_name>?token=<token>). These endpoints validate the
token without requiring a Frappe login and let the recommender retrieve the
request details and submit their letter.
"""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today


@frappe.whitelist(allow_guest=True)
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


@frappe.whitelist(allow_guest=True)
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
    if attachment_url:
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


def _validate_token(name, token):
    if not name or not token:
        frappe.throw(_("Invalid link."), frappe.PermissionError)

    doc = frappe.get_doc("Recommendation Letter", name)

    if not doc.request_token or doc.request_token != token:
        frappe.throw(_("Invalid or expired link."), frappe.PermissionError)

    if doc.token_expires_on and getdate(doc.token_expires_on) < getdate(today()):
        frappe.throw(
            _("This link has expired. Please request a new one."),
            frappe.PermissionError,
        )

    if doc.workflow_state == "Approved" or doc.workflow_state == "Rejected":
        frappe.throw(
            _("This recommendation is no longer accepting input."),
            frappe.PermissionError,
        )

    return doc
