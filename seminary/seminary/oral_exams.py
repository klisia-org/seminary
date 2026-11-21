# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

"""Oral answers in exams (decisions/100a).

An Exam Question's ``response_mode`` makes it *Oral* or *Student chooses*. The
answer is still an Exam Question Result row: its recording points at the row,
the row's ``oral_recording`` names the take that counts (the last), and once
``transcribe`` has run the row's ``answer`` holds the transcript, so grading
and the question-level outcome maps read it as they read a written answer.

A student whose override says ``written_instead`` (100 §9) answers every oral
question of that assessment in writing.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, escape_html

from seminary.seminary import oral

ORAL_MODES = ("Oral", "Student chooses")


def _row(row_name):
    row = frappe.db.get_value(
        "Exam Question Result",
        row_name,
        ["name", "parent", "parenttype", "question", "oral_recording", "takes_used"],
        as_dict=True,
    )
    if not row or row.parenttype != "Exam Submission":
        frappe.throw(_("Exam answer not found."), frappe.PermissionError)
    return row


def _question(exam_question):
    return (
        frappe.db.get_value(
            "Exam Question",
            exam_question,
            [
                "name",
                "response_mode",
                "prepare_s",
                "max_answer_s",
                "takes",
                "question_detail",
            ],
            as_dict=True,
        )
        or frappe._dict()
    )


def _written_instead(sub):
    from seminary.seminary.deadlines import get_override

    ov = get_override(sub.course_assess, sub.student)
    return bool(ov and cint(ov.written_instead))


def _steps(exam):
    raw = frappe.db.get_value("Exam Activity", exam, "oral_steps") or "[]"
    try:
        steps = json.loads(raw)
    except ValueError:
        steps = [s.strip() for s in raw.split(",")]
    return [s for s in steps if s in oral.PIPELINE]


def resolve(row_name, user):
    row = _row(row_name)
    sub = frappe.db.get_value(
        "Exam Submission",
        row.parent,
        [
            "name",
            "member",
            "student",
            "course",
            "course_assess",
            "exam",
            "status",
            "docstatus",
        ],
        as_dict=True,
    )
    q = _question(row.question)
    is_oral = q.response_mode in ORAL_MODES and not _written_instead(sub)
    takes = max(1, cint(q.takes) or 1)
    used = frappe.db.count(
        "Oral Recording",
        {"reference_doctype": "Exam Question Result", "reference_name": row.name},
    )
    return {
        "course_schedule": sub.course,
        "participants": [(sub.member, sub.student)],
        "may_record": bool(
            is_oral
            and user == sub.member
            and sub.docstatus == 0
            and sub.status == "Not Submitted"
            and used < takes
        ),
        # Exam answers are recorded live (100a §2).
        "allow_upload": False,
        "steps": _steps(sub.exam),
        "expected_speakers": 1,
        "prompt": q.question_detail,
        "on_start": "seminary.seminary.oral_exams.on_start",
        "after_step": "seminary.seminary.oral_exams.after_step",
    }


def on_start(recording):
    """A new take replaces the last one: it is the take that will be graded."""
    ref = frappe.db.get_value("Oral Recording", recording, "reference_name")
    used = frappe.db.count(
        "Oral Recording",
        {"reference_doctype": "Exam Question Result", "reference_name": ref},
    )
    frappe.db.set_value(
        "Exam Question Result",
        ref,
        {"oral_recording": recording, "takes_used": used, "answer": ""},
    )


def transcript_html(segments):
    paragraphs = [escape_html(s.get("text", "").strip()) for s in segments]
    return "".join(f"<p>{p}</p>" for p in paragraphs if p)


def after_step(recording, step):
    """The graded take's transcript becomes the row's answer (100a §3)."""
    if step != "transcribe":
        return
    doc = frappe.get_doc("Oral Recording", recording)
    current = frappe.db.get_value(
        "Exam Question Result", doc.reference_name, "oral_recording"
    )
    if current != recording:
        return
    frappe.db.set_value(
        "Exam Question Result",
        doc.reference_name,
        "answer",
        transcript_html(json.loads(doc.transcript or "[]")),
    )


@frappe.whitelist()
def my_oral_state(submission):
    """For the student taking the exam: per answer row, whether it is oral, its
    timing, takes left and the graded take's status."""
    sub = frappe.db.get_value(
        "Exam Submission",
        submission,
        ["name", "member", "student", "course_assess", "exam"],
        as_dict=True,
    )
    if not sub or sub.member != frappe.session.user:
        frappe.throw(_("Exam submission not found."), frappe.PermissionError)
    written = _written_instead(sub)
    steps = [s for s in _steps(sub.exam) if s in oral.available_steps()]
    notice = {
        "steps": [_(oral.STEP_LABELS[s]) for s in steps],
        "retention_days": cint(
            frappe.db.get_single_value("Seminary Settings", "oral_audio_retention_days")
            or 365
        ),
    }
    out = {}
    for row in frappe.get_all(
        "Exam Question Result",
        filters={"parent": sub.name, "parenttype": "Exam Submission"},
        fields=["name", "question", "oral_recording", "takes_used"],
    ):
        q = _question(row.question)
        out[row.question] = {
            "row": row.name,
            "oral": q.response_mode in ORAL_MODES and not written,
            "mode": "Written" if written else (q.response_mode or "Written"),
            "prepare_s": cint(q.prepare_s),
            "max_answer_s": cint(q.max_answer_s) or 180,
            "takes": max(1, cint(q.takes) or 1),
            "takes_used": cint(row.takes_used),
            "recording": row.oral_recording,
            "status": (
                frappe.db.get_value("Oral Recording", row.oral_recording, "status")
                if row.oral_recording
                else None
            ),
        }
    return {"questions": out, "notice": notice}
