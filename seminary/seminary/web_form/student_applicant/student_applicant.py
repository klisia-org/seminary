import frappe

@frappe.whitelist()
def get_context(context):
    at = frappe.db.get_value('Academic Term', {'iscurrent_acterm': 1}, 'name')
    context.academic_term = at
    return context
    
    
@frappe.whitelist()
def get_doctrinal_statement():
	print("Method DS called from SA")
	doctrinal_statement = frappe.get_doc('Doctrinal Statement')
	doctrinal_statement = doctrinal_statement.doctrinalst
	print(doctrinal_statement)
	return doctrinal_statement


