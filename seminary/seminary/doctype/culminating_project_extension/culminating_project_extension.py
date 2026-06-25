# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CulminatingProjectExtension(Document):
    """Academic record of a culminating-project extension.

    Billing (charging the 'Culminating Project Extension' fee on submit and
    cancelling those invoices on cancel) is owned by the oikonomos bridge, which
    subscribes to this doctype's on_submit / on_cancel via doc_events. With no
    bridge installed the extension submits with no charge. The `invoiced` /
    `sales_invoices` fields are written by oikonomos.
    """

    pass
