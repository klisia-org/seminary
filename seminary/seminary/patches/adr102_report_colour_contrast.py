"""102 §8: list the Website Branding colours that already fall below 4.5:1.

From now on a save that changes a colour into a failing pair is refused. Colours a
school saved before that rule stay as they are: this patch reports them, in the
console and the Error Log, and changes nothing."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Website Branding"):
		return
	from seminary.seminary.doctype.website_branding.website_branding import failing_pairs

	problems = failing_pairs(frappe.get_single("Website Branding"))
	if not problems:
		return
	report = "\n".join(p["message"] for p in problems)
	print("Website Branding colours below the 4.5:1 contrast minimum (left unchanged):\n" + report)
	frappe.log_error(
		title="Website Branding: colours below the contrast minimum",
		message=report
		+ "\n\nNothing was changed. Saving a new colour for one of these pairs will need it to reach 4.5:1.",
	)
