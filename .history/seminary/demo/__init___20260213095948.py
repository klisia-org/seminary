import frappe

@frappe.whitelist()
def install_demo():
    frappe.only_for("Administrator")
    from seminary.demo.demo_data import install_demo_data
    install_demo_data()
    return {"status": "ok"}

@frappe.whitelist()
def remove_demo():
    frappe.only_for("Administrator")
    from seminary.demo.clean import remove_demo_data
    return remove_demo_data()