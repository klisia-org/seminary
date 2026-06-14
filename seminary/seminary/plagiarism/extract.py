"""Extract comparable plain text from a submission: the rich-text ``answer``
plus any PDF/DOCX attachment.

Attachment bytes are read straight off disk through the File doc
(``get_content()``), the same private-file-safe path comms.py uses — no HTTP
fetch, so private uploads work without ACL juggling. Every parser is wrapped so
a single bad file degrades to "no attachment text", never a failed check.
"""

import frappe

from .fingerprint import strip_html

# Bound the work: cap extracted text so a pathological 500-page PDF can't blow
# memory or wall-clock. 200k chars is ~30-40k words, far past any real paper.
MAX_CHARS = 200_000

# Assignment Activity types whose submission carries no comparable prose.
NON_TEXT_TYPES = {"Image", "YouTube", "URL"}


def _file_doc(file_url: str):
    """Resolve a File by its url, tolerating the desk editor's ``?fid=`` suffix."""
    if not file_url:
        return None
    base = file_url.split("?")[0]
    name = frappe.db.get_value(
        "File", {"file_url": base}, "name"
    ) or frappe.db.get_value("File", {"file_url": file_url}, "name")
    return frappe.get_doc("File", name) if name else None


def _pdf_to_text(content: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _docx_to_text(content: bytes) -> str:
    from io import BytesIO

    import docx

    document = docx.Document(BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs)


def _attachment_text(file_url: str) -> str:
    file_doc = _file_doc(file_url)
    if not file_doc:
        return ""
    try:
        content = file_doc.get_content()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Plagiarism: read {file_url}")
        return ""
    if isinstance(content, str):
        # Plain-text attachment.
        return content
    lower = (file_doc.file_name or file_url).lower()
    try:
        if lower.endswith(".pdf"):
            return _pdf_to_text(content)
        if lower.endswith(".docx"):
            return _docx_to_text(content)
        if lower.endswith((".txt", ".md")):
            return content.decode("utf-8", errors="ignore")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Plagiarism: parse {file_url}")
    return ""


def extract_text(submission) -> str:
    """Combined comparable text for a submission doc (or dict-like). Returns a
    capped plain-text string; empty when there is nothing to compare (e.g. an
    Image/URL/YouTube submission)."""
    answer = submission.get("answer") if hasattr(submission, "get") else None
    parts = []
    if answer:
        parts.append(strip_html(answer))
    file_url = (
        submission.get("assignment_attachment") if hasattr(submission, "get") else None
    )
    if file_url:
        parts.append(_attachment_text(file_url))
    text = "\n".join(p for p in parts if p).strip()
    return text[:MAX_CHARS]
