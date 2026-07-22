import frappe


@frappe.whitelist()
def install_demo():
    frappe.only_for(["Administrator", "System Manager"])
    # A financial app (oikonomos) can register a billing-inclusive demo installer
    # via the `seminary_demo_installer` hook. With one present, defer to it so the
    # demo also gets a fee catalog and the enrollments invoice; otherwise install
    # the academic-only demo (the Frappe-only experience).
    installers = frappe.get_hooks("seminary_demo_installer")
    if installers:
        frappe.get_attr(installers[-1])()
    else:
        from seminary.demo.demo_data import install_demo_data

        install_demo_data()
    return {"status": "ok"}


@frappe.whitelist()
def remove_demo():
    frappe.only_for(["Administrator", "System Manager"])
    from seminary.demo.cleanup import remove_demo_data

    return remove_demo_data()
