"""Orchestration: build the cross-term corpus, run the selected provider, and
persist a Plagiarism Check Result. This is the only layer that touches frappe
state; adapters stay pure.

Trigger model is manual (an instructor clicks "Run check"); the API queues
``run_check`` on the long worker. Extracted text is cached on each submission
(``plagiarism_text`` + a hash) so re-runs and corpus scans don't re-parse PDFs.
"""

import hashlib
import json

import frappe
from frappe.utils import now_datetime

from .extract import NON_TEXT_TYPES, extract_text
from .registry import get_adapter

RESULT_DOCTYPE = "Plagiarism Check Result"
SUBMISSION_DOCTYPE = "Assignment Submission"
# Safety valve: never compare against an unbounded corpus.
MAX_CORPUS = 1000


# ----------------------------------------------------------------- config


def _settings():
    return frappe.get_cached_doc("Seminary Settings")


def _resolve_config(submission, provider):
    s = _settings()
    config = {
        "similarity_threshold": s.get("plagiarism_similarity_threshold") or 30,
        "min_document_length": s.get("plagiarism_min_document_length") or 200,
        "ngram_size": s.get("plagiarism_ngram_size") or 5,
        "exclude_same_student": bool(s.get("plagiarism_exclude_same_student")),
    }
    if s.get("plagiarism_strip_question") and submission.get("assignment"):
        config["question_text"] = frappe.db.get_value(
            "Assignment Activity", submission.get("assignment"), "question"
        )
    if provider == "external-http":
        account = frappe.db.get_value(
            "Plagiarism Provider Account",
            {"provider": provider, "enabled": 1},
            "name",
        )
        if account:
            config.update(
                frappe.get_doc("Plagiarism Provider Account", account).get_config()
            )
    return config


# ----------------------------------------------------------------- text cache


def _text_hash(answer, attachment) -> str:
    raw = f"{answer or ''}\x00{attachment or ''}".encode("utf-8", errors="ignore")
    # Not security-sensitive: just a cache/dedup key for submission text.
    return hashlib.sha1(raw, usedforsecurity=False).hexdigest()


def cache_submission_text(submission_name: str) -> str:
    """Extract a submission's comparable text and cache it (+ hash) on the doc.
    Idempotent: a no-op when the cache is already current. Run on the long
    worker because PDF/DOCX parsing is slow."""
    row = frappe.db.get_value(
        SUBMISSION_DOCTYPE,
        submission_name,
        ["answer", "assignment_attachment", "plagiarism_text", "plagiarism_text_hash"],
        as_dict=True,
    )
    if not row:
        return ""
    current = _text_hash(row.answer, row.assignment_attachment)
    if row.plagiarism_text_hash == current and row.plagiarism_text is not None:
        return row.plagiarism_text
    text = extract_text(
        {"answer": row.answer, "assignment_attachment": row.assignment_attachment}
    )
    frappe.db.set_value(
        SUBMISSION_DOCTYPE,
        submission_name,
        {"plagiarism_text": text, "plagiarism_text_hash": current},
        update_modified=False,
    )
    return text


def _text_for(row) -> str:
    """Cached text for a corpus/target row dict, self-healing on a miss/stale."""
    current = _text_hash(row.get("answer"), row.get("assignment_attachment"))
    if (
        row.get("plagiarism_text_hash") == current
        and row.get("plagiarism_text") is not None
    ):
        return row["plagiarism_text"]
    return cache_submission_text(row["name"])


def on_submission_update(doc, method=None):
    """Doc-event: refresh the cached text in the background only when the answer
    or attachment actually changed (keeps saving fast)."""
    current = _text_hash(doc.get("answer"), doc.get("assignment_attachment"))
    if doc.get("plagiarism_text_hash") == current:
        return
    frappe.enqueue(
        "seminary.seminary.plagiarism.service.cache_submission_text",
        queue="long",
        enqueue_after_commit=True,
        submission_name=doc.name,
    )


# ----------------------------------------------------------------- corpus


_CORPUS_FIELDS = [
    "name",
    "student",
    "member_name",
    "course",
    "answer",
    "assignment_attachment",
    "plagiarism_text",
    "plagiarism_text_hash",
]


def build_corpus(submission) -> list:
    """Every other submission for the same assignment, across all terms — the
    `assignment` link is the cross-term key."""
    rows = frappe.get_all(
        SUBMISSION_DOCTYPE,
        filters={
            "assignment": submission.get("assignment"),
            "name": ("!=", submission.get("name")),
        },
        fields=_CORPUS_FIELDS,
        limit_page_length=MAX_CORPUS,
        order_by="modified desc",
    )
    corpus = []
    for row in rows:
        corpus.append(
            {
                "name": row.name,
                "student": row.student,
                "member_name": row.member_name,
                "course": row.course,
                "text": _text_for(row),
            }
        )
    return corpus


# ----------------------------------------------------------------- run


def enqueue_check(submission_name: str, provider=None, user=None) -> str:
    """Create a Queued result doc (so the panel can show progress immediately)
    and enqueue the worker. Returns the result doc name."""
    submission = frappe.db.get_value(
        SUBMISSION_DOCTYPE,
        submission_name,
        ["name", "assignment", "student"],
        as_dict=True,
    )
    if not submission:
        frappe.throw(frappe._("Submission not found."))
    provider = provider or _settings().get("plagiarism_default_provider") or "internal"
    result = frappe.get_doc(
        {
            "doctype": RESULT_DOCTYPE,
            "reference_doctype": SUBMISSION_DOCTYPE,
            "reference_name": submission.name,
            "assignment": submission.assignment,
            "student": submission.student,
            "provider": provider,
            "status": "Queued",
            "checked_by": user or frappe.session.user,
            "checked_on": now_datetime(),
        }
    )
    result.insert(ignore_permissions=True)
    frappe.enqueue(
        "seminary.seminary.plagiarism.service.run_check",
        queue="long",
        enqueue_after_commit=True,
        result_name=result.name,
    )
    return result.name


def run_check(result_name=None, submission_name=None, provider=None):
    """Worker entrypoint. With ``result_name`` it fills an existing Queued doc;
    with ``submission_name`` (bench execute / tests) it creates one first."""
    if not result_name:
        # Direct invocation path (bench execute / tests): build a result first.
        submission = frappe.db.get_value(
            SUBMISSION_DOCTYPE,
            submission_name,
            ["name", "assignment", "student"],
            as_dict=True,
        )
        provider = (
            provider or _settings().get("plagiarism_default_provider") or "internal"
        )
        result = frappe.get_doc(
            {
                "doctype": RESULT_DOCTYPE,
                "reference_doctype": SUBMISSION_DOCTYPE,
                "reference_name": submission.name,
                "assignment": submission.assignment,
                "student": submission.student,
                "provider": provider,
                "status": "Running",
                "checked_by": frappe.session.user,
                "checked_on": now_datetime(),
            }
        ).insert(ignore_permissions=True)
    else:
        result = frappe.get_doc(RESULT_DOCTYPE, result_name)
        result.db_set("status", "Running", update_modified=False)
        provider = result.provider

    try:
        _execute(result, provider)
    except Exception as e:
        frappe.db.rollback()
        result = frappe.get_doc(RESULT_DOCTYPE, result.name)
        result.db_set(
            {"status": "Failed", "error": str(e)[:500]}, update_modified=False
        )
        frappe.log_error(frappe.get_traceback(), "Plagiarism run_check")
    frappe.db.commit()
    return result.name


def _execute(result, provider):
    submission = frappe.db.get_value(
        SUBMISSION_DOCTYPE,
        result.reference_name,
        [
            "name",
            "assignment",
            "student",
            "type",
            "answer",
            "assignment_attachment",
            "plagiarism_text",
            "plagiarism_text_hash",
        ],
        as_dict=True,
    )

    # Non-text submission types carry no comparable prose.
    if submission.get("type") in NON_TEXT_TYPES:
        result.db_set(
            {
                "status": "Skipped",
                "error": f"{submission.type} submissions are not checked.",
            },
            update_modified=False,
        )
        return

    config = _resolve_config(submission, provider)
    adapter = get_adapter(provider)
    target = {
        "name": submission.name,
        "student": submission.student,
        "text": _text_for(submission),
    }
    corpus = build_corpus(submission) if not adapter.requires_account else []
    report = adapter.check(target, corpus, config)
    _persist(result, report)


def _persist(result, report):
    result.set("matched_sources", [])
    for src in report.matched_sources:
        result.append(
            "matched_sources",
            {
                "source_submission": src.source_submission,
                "source_student": src.source_student,
                "source_student_name": src.source_student_name,
                "source_course": src.source_course,
                "similarity": src.similarity,
                "same_student": 1 if src.same_student else 0,
                "matched_passages": json.dumps(src.matched_passages or []),
            },
        )
    result.status = report.status
    result.overall_score = report.overall_score
    result.checked_chars = report.checked_chars
    result.source_count = report.source_count
    result.error = report.error
    result.engine_meta = json.dumps(report.engine_meta or {})
    result.checked_on = now_datetime()
    result.save(ignore_permissions=True)
