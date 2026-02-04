import json

import frappe
from frappe import _
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate
from frappe.model.document import Document
import calendar
from datetime import timedelta
from dateutil import relativedelta
import erpnext
from datetime import datetime

# This file is for scheduler hooks
# Documentation: https://frappeframework.com/docs/user/en/api/background_jobs

# Daily
@frappe.whitelist()
def daily():
    set_iscurrent_acterm()


@frappe.whitelist()
def set_iscurrent_acterm(academic_term=None):
    academic_terms = frappe.get_all(
        "Academic Term",
        filters={},
        fields=["name", "term_start_date", "term_end_date", "iscurrent_acterm"],
    )
    today = getdate()
    # check if outgoing email is set
    outgoing_email = frappe.db.get_all("Email Account", {"enable_outgoing": 1}, "name")

    # Update academic terms
    for term in academic_terms:
        if term.term_end_date <= today:
            frappe.db.set_value("Academic Term", term.name, "open", 0)
            if term.iscurrent_acterm == 1:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)
                if outgoing_email:
                    need_acadterm()
        elif term.term_start_date <= today <= term.term_end_date:
            if term.iscurrent_acterm == 0:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
                advance_pe()


def advance_pe():
    pe = frappe.get_all(
        "Program Enrollment",
        filters={"pgmenrol_active": 1},
        fields=["name", "current_std_term"],
    )
    for p in pe:
        frappe.db.set_value(
            "Program Enrollment", p.name, "current_std_term", p.current_std_term + 1
        )


def need_acadterm():
    today = getdate()

    # Check if outgoing email is enabled
    outgoing_email = frappe.db.get_all("Email Account", {"enable_outgoing": 1}, "name")
    if not outgoing_email:
        frappe.log_error(
            "No outgoing email account is configured.", "Need Academic Term"
        )
        return

    terms = frappe.db.sql(
        """SELECT COUNT(name) FROM `tabAcademic Term` WHERE term_start_date >= %s""",
        (today,),
    )
    if terms[0][0] < 2:
        users1 = frappe.db.sql(
            """SELECT DISTINCT parent FROM `tabUserRole` WHERE role = 'Academics User'""",
            as_dict=True,
        )
        users1 = [d["parent"] for d in users1]
        if not users1:
            frappe.log_error(
                "No users found with the Academics User role.", "Need Academic Term"
            )
            return

        users = frappe.db.sql(
            """SELECT email FROM `tabUser` WHERE name IN ({})""".format(
                ", ".join(["%s"] * len(users1))
            ),
            tuple(users1),
        )
        terms_count = terms[0][0]
        subject = "Few Academic Terms"
        body = f"There are only {terms_count} academic terms in the pipeline. Please create more to avoid disruptions."

        for user in users:
            try:
                frappe.sendmail(recipients=user.email, subject=subject, message=body)
            except Exception as e:
                frappe.log_error(
                    f"Failed to send email to {user.email}: {str(e)}",
                    "Need Academic Term",
                )


# Monthly
