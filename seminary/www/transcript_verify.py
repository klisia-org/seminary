import frappe

from seminary.seminary.transcripts import verify


def get_context(context):
	"""Confirm an official transcript (decisions/119 §5).

	Guest-reachable on purpose: the recipient is a school or employer with no
	portal account. It shows the student's name, the date issued and the PDF's
	SHA-256, never the grades. The visitor can drop the PDF on the page and the
	browser computes its hash; the file never leaves their machine.
	"""
	context.no_cache = 1
	context.title = frappe._("Verify a transcript")
	code = (frappe.form_dict.get("code") or "").strip()
	context.code = code
	context.result = verify(code) if code else None
	context.searched = bool(code)
