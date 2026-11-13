# 099 — PDFs through Chrome, not wkhtmltopdf

**Date:** 2026-11-04
**Status:** Accepted 2026-11-04
**Related:** 091 (agreements), 063 (bridge apps)

## Context

Frappe 16 marks wkhtmltopdf deprecated and will remove it in version 17. Two print formats still
use it: Seminary Diploma, and Seminary Sales Invoice, which oikonomos ships. Their fixture copies
name no generator. Four places call `frappe.utils.pdf.get_pdf` directly, which always uses
wkhtmltopdf, so Frappe never warns about them:
- mailing labels;
- signed agreements (091);
- announcement letters;
- the document export in `api.py`.

Frappe's Chrome renderer works without a print format.

## Decision

1. **One helper: `seminary.pdf.render(html, options=None)`.** It renders through Frappe's Chrome
   generator. It takes the same page options as before: page size, margins, and a header or
   footer as HTML. wkhtmltopdf's `[page]` and `[topage]` become Chrome's page-number spans.
   Every PDF seminary makes goes through it, and so may any app that requires seminary.
2. **The print formats switch to Chrome.** Seminary Diploma, and Seminary Sales Invoice in
   oikonomos, get `pdf_generator: chrome`, in their JSON and in the fixtures.
3. **Each document is checked by eye before the switch is merged.** Chrome renders flexbox, web
   fonts and page breaks differently. Mailing labels are placed in millimetres and need a test
   print.
4. **Chrome must exist where the site runs.** Frappe finds or downloads Chromium for the bench
   (`chromium_path` in the common site config). A site without it gets a clear error, not a
   silent fallback to wkhtmltopdf.

## Consequences

- No wkhtmltopdf in seminary or oikonomos, ready for Frappe 17.
- The image-size workaround in `comms.pdf_html` stays: it is harmless in Chrome.
- The first PDF after a worker starts is slower while Chromium starts.

## Built 2026-11-04

- `seminary/pdf.py`: `render(html, options, header, footer)`, used by mailing labels, signed
  agreements, announcement letters and the letter preview in `api.py`.
- Margins and page size are written as a `.print-format` rule, which Frappe's Chrome path reads
  after it forces its own 15mm defaults. A second rule stops that rule from moving the header and
  footer bands.
- The Seminary Diploma and Seminary Sales Invoice print formats and both fixtures use Chrome.
- **Found while building:**
  - The Diploma fixture was older than the module copy. It called
    `frappe.defaults.get_defaults()`, which Frappe 16's template sandbox refuses, so the
    Diploma failed on sites where the fixture won. It now matches the module copy.
  - Chrome ignores `@page { size }`, so the Diploma states its landscape Letter size in its
    `.print-format` rule.
- **Checked by eye:**
  - The Diploma.
  - An agreement, with its signature line and evidence block.
  - Mailing labels: on Avery 5160 they sit on the grid, 30 to a page. wkhtmltopdf placed them
    3mm low and fitted only 27.
