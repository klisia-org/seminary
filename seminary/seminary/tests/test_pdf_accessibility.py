"""decisions/104 §5: every PDF seminary makes is readable with a screen reader.

Each PDF is rendered from in-memory sample data, with the database lookups patched, so the test
writes nothing to the site."""

import io
import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from pypdf import PdfReader

from seminary import pdf as seminary_pdf
from seminary.seminary import api, mailing_labels
from seminary.seminary import requirements as req
from seminary.seminary.doctype.seminary_announcement import announcement_recipients
from seminary.seminary.doctype.seminary_announcement import seminary_announcement as sa

PNG = (
	"data:image/png;base64,"
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
LETTER_HEAD = frappe._dict(
	name="Test Letterhead",
	# Frappe's image letter head names the image after the Letter Head.
	content=f'<div style="text-align: center;"><img src="{PNG}" alt="Test Letterhead" height="40"'
	f' style="height: 40px;"><img src="{PNG}" style="width:100%;height:2px"></div>',
	footer=f'<img src="{PNG}" style="width:100%;height:2px"><p>1 College Road</p>',
)
RECIPIENTS = [
	frappe._dict(
		party_type="Student",
		party=f"STU-{i}",
		party_name=f"Student {i}",
		email=f"student{i}@example.invalid",
		user=None,
	)
	for i in range(3)
]


def _keep_sample(kind, content):
	"""Write the PDF to $PDF_SAMPLES_DIR as seminary-<kind>.pdf, for a PDF/UA check by hand."""
	folder = os.environ.get("PDF_SAMPLES_DIR")
	if folder:
		os.makedirs(folder, exist_ok=True)
		with open(os.path.join(folder, f"seminary-{kind}.pdf"), "wb") as fh:
			fh.write(content)


def _outline(content):
	return PdfReader(io.BytesIO(content)).outline


def _announcement(**values):
	doc = frappe.get_doc(
		{
			"doctype": "Seminary Announcement",
			"subject": "Term opens Monday",
			"message": "<p>Dear {{ recipient.first_name }},</p><h2>Dates</h2>"
			"<ul><li>Registration</li><li>Classes</li></ul><h2>Fees</h2><p>See the portal.</p>",
			"print_subject_heading": 1,
			"print_letterhead_mode": "Seminary Default",
			**values,
		}
	)
	doc.name = "ANN-TEST-PDF"
	return doc


class TestPdfAccessibility(IntegrationTestCase):
	def assertReadable(self, content, kind=None):
		if kind:
			_keep_sample(kind, content)
		self.assertEqual(seminary_pdf.problems(content), [])

	def test_mailing_labels(self):
		addresses = [
			{"name": f"Person {i}", "lines": [f"Person {i}", f"{i} Main Street", "Springfield, IL 62701"]}
			for i in range(35)
		]
		with patch.object(mailing_labels, "recipient_address", side_effect=addresses):
			content, placed, omitted = mailing_labels.render_labels_pdf(
				[{"party_name": a["name"]} for a in addresses]
			)
		self.assertEqual((placed, omitted), (35, []))
		self.assertReadable(content, "labels")
		reader = PdfReader(io.BytesIO(content))
		self.assertEqual(reader.metadata.title, frappe._("Mailing labels"))
		self.assertEqual(len(reader.pages), 2)

	def test_label_sheet_is_a_list_not_a_table(self):
		spec = {"cols": 3, "rows": 10, "cell_w": 66.7, "cell_h": 25.4}
		html = mailing_labels._labels_html([{"lines": ["A", "B"]}] * 4, spec)
		self.assertNotIn("<table", html)
		self.assertEqual(html.count("<li>"), 4)

	def test_signed_agreement(self):
		body = (
			"<p>I agree to the following.</p><h2>Conduct</h2><ul><li>Attend</li><li>Pay</li></ul>"
			"<h2>Signatures</h2>"
		)
		signed = req.fill_slots(
			body + req._slot("signature", "Ana Lima"),
			signature=req._signed_line("Ana Lima", frappe.utils.now_datetime(), PNG),
		)
		when = frappe.utils.now_datetime()
		evidence = [
			req._signer_evidence("Signed electronically", "Ana Lima", "ana@example.invalid", when, "", ""),
			req._signer_evidence(
				"Countersigned electronically", "Registrar", "r@example.invalid", when, "", ""
			),
		]
		with patch.object(req, "_letterhead", return_value=LETTER_HEAD):
			content = req._pdf("Student Agreement", signed, evidence)
		self.assertReadable(content, "agreement")
		self.assertTrue(_outline(content), "a multi-heading agreement has bookmarks")
		self.assertEqual(PdfReader(io.BytesIO(content)).metadata.title, "Student Agreement")

	def test_announcement_letters(self):
		doc = _announcement()
		with (
			patch.object(announcement_recipients, "resolve_recipients", return_value=RECIPIENTS),
			patch("seminary.seminary.person.find_person", return_value=None),
			patch.object(sa, "_resolve_letter_head", return_value=LETTER_HEAD),
		):
			content, count = sa.build_letters_pdf(doc)
		self.assertEqual(count, 3)
		self.assertReadable(content, "letters")
		self.assertTrue(_outline(content))
		self.assertEqual(PdfReader(io.BytesIO(content)).metadata.title, "Term opens Monday")

	def test_letters_without_a_heading_still_have_a_title(self):
		doc = _announcement(print_subject_heading=0, message="<p>Hello {{ recipient.first_name }}.</p>")
		with (
			patch.object(announcement_recipients, "resolve_recipients", return_value=RECIPIENTS[:1]),
			patch("seminary.seminary.person.find_person", return_value=None),
			patch.object(sa, "_resolve_letter_head", return_value=None),
		):
			content, _count = sa.build_letters_pdf(doc)
		self.assertReadable(content)

	def test_letter_preview(self):
		doc = _announcement()
		with (
			patch.object(announcement_recipients, "resolve_recipients", return_value=RECIPIENTS),
			patch("seminary.seminary.person.find_person", return_value=None),
			patch.object(sa, "_resolve_letter_head", return_value=LETTER_HEAD),
		):
			html, title = api._letter_preview_html(doc)
		content = seminary_pdf.render(html, title=title)
		self.assertReadable(content, "letter-preview")
		self.assertTrue(_outline(content))

	def test_letterhead_images_get_alt_text(self):
		with patch.object(sa, "school_name", return_value="Grace Seminary"):
			html = sa._wrap_letterhead(LETTER_HEAD, "<p>Body</p>")
		self.assertIn('<img alt="Grace Seminary"', html)
		# The rule under the logo and the footer's band are decoration.
		self.assertEqual(html.count('alt=""'), 2)
		self.assertNotIn('alt="Test Letterhead"', html)
		kept = frappe._dict(name="X", content=f'<img src="{PNG}" alt="Crest of the school">', footer="")
		self.assertIn('alt="Crest of the school"', sa._wrap_letterhead(kept, ""))
