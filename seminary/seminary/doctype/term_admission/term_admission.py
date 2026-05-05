import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class TermAdmission(Document):
    def before_insert(self):
        if not self.program_details:
            self.populate_timed_programs()

    def validate(self):
        if (
            self.admission_start_date
            and self.admission_end_date
            and getdate(self.admission_end_date) < getdate(self.admission_start_date)
        ):
            frappe.throw(
                _("Admission End Date cannot be earlier than Admission Start Date.")
            )

        seen = set()
        for row in self.program_details or []:
            if row.program in seen:
                frappe.throw(
                    _("Program {0} is listed more than once.").format(row.program)
                )
            seen.add(row.program)

    def populate_timed_programs(self):
        existing = {row.program for row in self.program_details or []}
        timed_programs = frappe.get_all(
            "Program",
            filters={"enrollment_mode": "Timed"},
            fields=["name"],
            order_by="program_name asc",
        )
        added = 0
        for program in timed_programs:
            if program["name"] in existing:
                continue
            self.append("program_details", {"program": program["name"]})
            added += 1
        return added


@frappe.whitelist()
def refresh_programs(name):
    """Add any Timed Programs not already listed in the given Term Admission's child table."""
    doc = frappe.get_doc("Term Admission", name)
    if doc.docstatus == 2:
        frappe.throw(_("Cannot refresh a cancelled Term Admission."))
    added = doc.populate_timed_programs()
    if added:
        doc.save()
    return {"added": added}
