# 104 — Tagged PDFs

**Date:** 2026-11-23
**Status:** Accepted 2026-11-23; implemented 2026-11-23
**Amends:** 099 §1 (what `seminary.pdf.render` takes for a header or footer)
**Related:** 102 (accessibility conformance), 099 (PDFs through Chrome)

## Context

Every PDF made by `seminary.pdf.render` is untagged, so a screen reader gets one unstructured
run of text: no headings, no table structure, no alt text, no language. Chrome can tag what it
prints, but Frappe leaves that off. When a header or footer is added, Frappe rebuilds the file
to place it, and the tags, language and title are lost. It also asks Chrome for bookmarks under
the wrong parameter name, so none are made. All three were checked on testable on 2026-11-23.

## Decision

1. **`render` always asks for a tagged PDF with bookmarks.** Chrome tags from the HTML, and
   makes a bookmark for each heading. Until Frappe uses the right parameter name
   (`generateDocumentOutline`), `render` corrects it on the options it passes. A fix goes
   upstream.
2. **Running text goes in the page margins, not in a separate band.** Page numbers and running
   heads become CSS page-margin boxes (`@page { @bottom-center { … } }`). Chrome prints them on
   the page itself, so nothing is rebuilt and the tags survive. `render` turns
   `header-center`/`footer-center` and `[page]`/`[topage]` into those boxes. It no longer takes
   HTML bands: no caller uses one for more than text.
3. **Every PDF states its language and title.** `render` adds `<html lang>` from the user's
   language and a `<title>` from the first heading when the caller's HTML has neither. Chrome
   then opens the file showing that title.
4. **Running text is marked as decoration.** Chrome leaves margin-box text untagged. `render`
   marks it as an artifact, so a PDF/UA checker doesn't report it and a screen reader skips it.
5. **Each template is written for it:** real headings, `<th>` with `scope`, alt text, lists as
   lists, and no layout tables. A test renders each PDF template with sample data and checks
   the structure tree, the language, the title, bookmarks when there is more than one heading,
   alt text on every figure, and that no content is left untagged.
6. **Joined PDFs aren't covered.** Joining files drops their structure trees. A caller that
   joins PDFs says so in its own conformance file.
7. **Before any PDF is claimed as Supports,** veraPDF checks one of each kind against PDF/UA-1,
   once, as the IBM trial was run for the pages.

## Consequences

Every PDF through `render` is tagged with no change to its callers, apart from the move from
HTML bands to margin text. A PDF is only as accessible as its HTML, so the template pass is the
real work. Desk print formats printed through Frappe's own print view are outside this, and so
are documents people upload.

## As built

- §1: `render` makes the bookmarks itself, not Chrome. Frappe's semgrep rules forbid patching
  its classes, so the parameter name isn't corrected. Chrome tags every heading in order, and
  each tagged heading is paired with the HTML's heading for its text and its tag for its page.
- §3: headings are also numbered for a screen reader. An `aria-level` makes them start at 1 and
  never skip, so the print looks the same. Text written for a web page often starts at `h2`.
- §2: a print view's own `#header-html` and `#footer-html` (Repeat Header and Footer) print in
  the page, once, and their page numbers go in the margin.
- PDF/UA asks for XMP metadata, which Chrome doesn't write: `render` adds the title and the
  PDF/UA identifier.
- An empty table cell is left out of the tags, which leaves a short row. `problems()` reports
  it, and templates print a dash for a missing value.
- §7: veraPDF 1.30.4 passed 22 kinds of PDF against PDF/UA-1 on 2026-11-23, from seminary and
  the apps that use `render`.
