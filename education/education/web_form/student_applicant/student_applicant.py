import frappe

@frappe.whitelist()
def get_context(context):
    doctrinal_statement = frappe.get_doc('Doctrinal Statement')
    context.doctrinal_statement = doctrinal_statement.doctrinalst
    
@frappe.whitelist()
def get_doctrinal_statement():
	print("Method DS called from SA")
	doctrinal_statement = frappe.get_doc('Doctrinal Statement')
	doctrinal_statement = doctrinal_statement.doctrinalst
	print(doctrinal_statement)
	return doctrinal_statement