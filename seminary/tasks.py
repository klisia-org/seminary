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

#Daily
@frappe.whitelist()
def daily():
    set_iscurrent_acterm()
    

@frappe.whitelist()
def set_iscurrent_acterm(academic_term=None):
    academic_terms = frappe.get_all("Academic Term", filters={}, fields=["name", "term_start_date", "term_end_date"])
    today = getdate()
    
    for term in academic_terms:
        if term.term_start_date <= today <= term.term_end_date:
            if term.iscurrent_acterm == 0:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
                advance_pe()
                need_acadterm()
            elif term.iscurrent_acterm == 1:
                pass
            else:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)

def advance_pe():
    pe = frappe.get_all("Program Enrollment", filters={"pgmenrol_active": 1}, fields=["name", "current_std_term"])
    for p in pe:
        p.current_std_term = p.current_std_term + 1

def need_acadterm():
    today = getdate()
    terms = frappe.db.sql("""select count(name) from `tabAcademic Term` where term_start_date >=  %s""", (today))
    if terms[0][0] < 2:
        users1=[]
        users1 = frappe.db.sql("""select distinct parent from `tabUserRole` where role = 'Academics User'""", as_dict=True)
        users1 = [d['parent'] for d in users1]  # Convert the list of dictionaries to a list of strings
        users = frappe.db.sql("""select email from `tabUser` where name in (%s)""" % ', '.join(['%s']*len(users1)), tuple(users1))
        terms_count = terms[0][0]
        subject = "Few Academic Terms"
        body = f"There are only {terms_count} academic terms in the pipeline. Please create more to avoid disruptions."

        for user in users:
            frappe.sendmail(recipients=user.email, subject=subject, message=body)
    else:
        return
			
#Monthly

