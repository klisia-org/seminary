# Copyright (c) 2025, Klisia, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from seminary.seminary.integrations import bible
from seminary.seminary.utils import (
    has_course_instructor_role,
    has_course_moderator_role,
)


class Question(Document):
    def validate(self):
        validate_correct_answers(self)
        update_question_title(self)


def validate_correct_answers(question):
    if question.type == "Choices":
        validate_duplicate_options(question)
        validate_minimum_options(question)
        validate_correct_options(question)
    elif question.type == "User Input":
        validate_possible_answer(question)
    elif question.type == "Reading Report":
        validate_reading_report(question)
    elif question.type == "Scripture Matching":
        validate_scripture_matching(question)
    elif question.type == "Scripture Memorization":
        validate_scripture_memorization(question)


def validate_duplicate_options(question):
    options = []

    for num in range(1, 5):
        if question.get(f"option_{num}"):
            options.append(question.get(f"option_{num}"))

    if len(set(options)) != len(options):
        frappe.throw(_("Duplicate options found for this question."))


def validate_correct_options(question):
    correct_options = get_correct_options(question)

    if len(correct_options) > 1:
        question.multiple = 1

    if not len(correct_options):
        frappe.throw(_("At least one option must be correct for this question."))


def validate_minimum_options(question):
    if question.type == "Choices" and (not question.option_1 or not question.option_2):
        frappe.throw(
            _("Minimum two options are required for multiple choice questions.")
        )


def validate_possible_answer(question):
    possible_answers = []
    possible_answers_fields = [
        "possibility_1",
        "possibility_2",
        "possibility_3",
        "possibility_4",
    ]

    for field in possible_answers_fields:
        if question.get(field):
            possible_answers.append(field)

    if not len(possible_answers):
        frappe.throw(
            _("Add at least one possible answer for this question: {0}").format(
                frappe.bold(question.question)
            )
        )


def validate_reading_report(question):
    if cint(question.pages_total) <= 0:
        frappe.throw(
            _("Set a Pages Total greater than zero for the Reading Report: {0}").format(
                frappe.bold(question.question)
            )
        )


def validate_scripture_matching(question):
    """For each matching row, fetch the verse text from api.bible and cache it
    on the row. Throws (blocking save) if the prof entered fewer than 2 rows or
    any reference fails to parse / fetch."""
    rows = list(question.matching_items or [])
    if len(rows) < 2:
        frappe.throw(_("Scripture Matching needs at least 2 references to match."))
    seen_refs = set()
    bible_id = question.scripture_bible_id or None
    for idx, row in enumerate(rows, start=1):
        if not row.reference:
            frappe.throw(_("Row {0}: reference is required.").format(idx))
        norm_ref = row.reference.strip()
        if norm_ref in seen_refs:
            frappe.throw(_("Row {0}: duplicate reference '{1}'.").format(idx, norm_ref))
        seen_refs.add(norm_ref)
        try:
            result = bible.fetch_text_for_passage(norm_ref, bible_id)
        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.throw(
                _("Row {0}: could not fetch '{1}' from api.bible: {2}").format(
                    idx, norm_ref, str(e)
                )
            )
        row.resolved_ref = result["resolved_ref"]
        row.fetched_text = result["text"]


_WORD_STRIP = re.compile(r"[^\w]+", re.UNICODE)


def _count_eligible_words(text: str, min_word_length: int) -> int:
    """How many whitespace tokens have alphanumeric length >= min_word_length.
    Mirrors the eligibility rule the frontend's pickBlankPositions uses, so
    save-time clamping matches what students will see."""
    if not text:
        return 0
    count = 0
    for tok in text.split():
        stripped = _WORD_STRIP.sub("", tok)
        if len(stripped) >= min_word_length:
            count += 1
    return count


def validate_scripture_memorization(question):
    """Fetch the verse, populate memorization_text, clamp hide_word_count
    against eligible words so a too-greedy setting can't render a broken quiz."""
    if not question.memorization_ref:
        frappe.throw(_("Memorization reference is required."))
    bible_id = question.scripture_bible_id or None
    try:
        result = bible.fetch_text_for_passage(question.memorization_ref, bible_id)
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(
            _("Could not fetch '{0}' from api.bible: {1}").format(
                question.memorization_ref, str(e)
            )
        )
    question.memorization_resolved_ref = result["resolved_ref"]
    question.memorization_text = result["text"]

    min_len = max(1, cint(question.min_word_length) or 4)
    if cint(question.min_word_length) != min_len:
        question.min_word_length = min_len
    hide = cint(question.hide_word_count) or 3
    eligible = _count_eligible_words(result["text"], min_len)
    if eligible == 0:
        frappe.throw(
            _(
                "No words in '{0}' meet the minimum length of {1}. Lower the Minimum Word Length."
            ).format(result["reference"], min_len)
        )
    if hide > eligible:
        frappe.msgprint(
            _(
                "Only {0} word(s) in '{1}' meet the minimum length of {2}. Clamped Words to Hide from {3} to {0}."
            ).format(eligible, result["reference"], min_len, hide),
            alert=True,
        )
        hide = eligible
    if hide < 1:
        hide = 1
    question.hide_word_count = hide


def update_question_title(question):
    if not question.is_new():
        question_rows = frappe.get_all(
            "Quiz Question", {"question": question.name}, pluck="name"
        )

        for row in question_rows:
            frappe.db.set_value(
                "Quiz Question", row, "question_detail", question.question
            )


def get_correct_options(question):
    correct_options = []
    correct_option_fields = [
        "is_correct_1",
        "is_correct_2",
        "is_correct_3",
        "is_correct_4",
    ]
    for field in correct_option_fields:
        if question.get(field) == 1:
            correct_options.append(field)

    return correct_options


@frappe.whitelist()
def replace_matching_items(question, items):
    """Replace all matching_items child rows for a Question, then re-save.

    Used by the frontend edit modal because frappe.client.set_value can't
    update child tables. items is a JSON list of {reference: str} dicts.
    Empty references are dropped silently. Re-save triggers validate() which
    re-fetches all verse texts.
    """
    import json as _json

    doc = frappe.get_doc("Question", question)
    rows = items if isinstance(items, list) else _json.loads(items or "[]")
    doc.matching_items = []
    for row in rows:
        ref = ((row or {}).get("reference") or "").strip()
        if ref:
            doc.append("matching_items", {"reference": ref})
    doc.save()
    return {"name": doc.name, "count": len(doc.matching_items)}


@frappe.whitelist()
def refresh_scripture_text(name):
    """Force-refetch verse text for a Scripture Matching/Memorization question.

    Used by the Desk form's 'Refresh from api.bible' button so profs can pull
    fresh text after upstream changes or after editing the Bible ID. Since
    validate() unconditionally re-fetches, this just re-saves the doc."""
    doc = frappe.get_doc("Question", name)
    if doc.type not in ("Scripture Matching", "Scripture Memorization"):
        frappe.throw(_("This question is not a Scripture type."))
    doc.save()
    return {"name": doc.name, "type": doc.type}


@frappe.whitelist()
def get_question_details(question):
    if not has_course_instructor_role() or not has_course_moderator_role():
        return

    fields = ["question", "type", "name"]
    for i in range(1, 5):
        fields.append(f"option_{i}")
        fields.append(f"is_correct_{i}")
        fields.append(f"explanation_{i}")
        fields.append(f"possibility_{i}")

    return frappe.db.get_value("Question", question, fields, as_dict=1)
