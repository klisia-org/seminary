import frappe
from frappe.website.website_generator import WebsiteGenerator

def get_context(context):
    context.title = "Financials"
    context.list_title = "Financials"
    context.show_sidebar = True
    students = frappe.get_all("Student", filters={"student_email_id": frappe.session.user}, fields=["name", "student_name"])
    context.student = students[0]["name"] if students else '25-00043'
    context.fullname = students[1]["student_name"] if len(students) > 1 else 'Nikolay Rimsky-Korsakov'
    context.invoices = []
    if context.student:
        context.invoices = frappe.get_all("Sales Invoice", filters={"custom_student": context.student}, fields=["name", "customer", "posting_date", "total", "outstanding_amount", "status"])
    for invoice in context.invoices:
        invoice["url"] = "/desk#Form/Sales Invoice/" + invoice["name"]
        invoice["name"] = frappe.get_value("Sales Invoice", invoice["name"], "name")
        invoice["customer"] = frappe.get_value("Customer", invoice["customer"], "customer_name")
        invoice["posting_date"] = frappe.utils.formatdate(invoice["posting_date"])
        invoice["status"] = "Paid" if invoice["status"] == "Paid" else "Unpaid"
        invoice["total"] = "{:,.2f}".format(invoice["total"])
        invoice["outstanding_amount"] = "{:,.2f}".format(invoice["outstanding_amount"])
    context.invoices = sorted(context.invoices, key=lambda x: (x["status"], x["posting_date"]), reverse=True)
    context.scholarship = frappe.get_all("Payers Fee Category PE", filters={"pf_student": context.student, "pf_active": 1}, fields=["scholarship"])
    context.scholarship = context.scholarship[0]["scholarship"] if context.scholarship else 'You have no scholarship'
   