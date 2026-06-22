# Copyright (c) 2025, Klisia, FOSS United and contributors
# For license information, please see license.txt

import json
import frappe
import re
from frappe import _, safe_decode
from frappe.model.document import Document
from frappe.utils import cstr, comma_and, cint
from fuzzywuzzy import fuzz
from seminary.seminary.utils import generate_slug
from binascii import Error as BinasciiError
from frappe.utils.file_manager import safe_b64decode
from frappe.core.doctype.file.utils import get_random_filename


class Quiz(Document):
    def validate(self):
        self.validate_duplicate_questions()
        self.validate_limit()
        self.calculate_total_points()

    def validate_duplicate_questions(self):
        questions = [row.question for row in self.questions]
        rows = [i + 1 for i, x in enumerate(questions) if questions.count(x) > 1]
        if len(rows):
            frappe.throw(
                _("Rows {0} have duplicate questions.").format(
                    frappe.bold(comma_and(rows))
                )
            )

    def validate_limit(self):
        if self.limit_questions_to and cint(self.limit_questions_to) >= len(
            self.questions
        ):
            frappe.throw(
                _(
                    "Limit cannot be greater than or equal to the number of questions in the quiz. Use limit to offer a subset of questions."
                )
            )

        if self.limit_questions_to and cint(self.limit_questions_to) < len(
            self.questions
        ):
            points = [question.points for question in self.questions]
            if len(set(points)) > 1:
                frappe.throw(
                    _(
                        "All questions should have the same points if a limit is set, as students will receive a subset of questions."
                    )
                )

    def calculate_total_points(self):
        if self.limit_questions_to:
            self.total_points = sum(
                question.points
                for question in self.questions[: cint(self.limit_questions_to)]
            )
        else:
            self.total_points = sum(
                cint(question.points) for question in self.questions
            )

    def autoname(self):
        if not self.name:
            self.name = generate_slug(self.title, "Quiz")

    def get_last_submission_details(self):
        """Returns the latest submission for this user."""
        user = frappe.session.user
        if not user or user == "Guest":
            return

        result = frappe.get_all(
            "Quiz Submission",
            fields="*",
            filters={"owner": user, "quiz": self.name},
            order_by="creation desc",
            page_length=1,
        )

        if result:
            return result[0]


def set_total_points(questions):
    points = 0
    for question in questions:
        points += question.get("points")
    return points


@frappe.whitelist()
def quiz_summary(
    quiz,
    course=None,
    time_taken=None,
    results=None,
    document_distribution=None,
    document_distribution_registry=None,
):
    score = 0
    results = results and json.loads(results)
    percentage = 0

    quiz_details = frappe.db.get_value(
        "Quiz",
        quiz,
        ["total_points", "passing_percentage", "standalone"],
        as_dict=1,
    )

    score_out_of = quiz_details.total_points

    for result in results:
        question_details = frappe.db.get_value(
            "Quiz Question",
            {"parent": quiz, "question": result["question_name"]},
            ["question", "points", "question_detail", "type"],
            as_dict=1,
        )

        result["question_name"] = question_details.question
        result["question"] = question_details.question_detail
        result["points_out_of"] = question_details.points

        if question_details.type == "Reading Report":
            # Partial credit: score = (pages_read / pages_total) * points.
            # Reject out-of-range page counts by clamping to [0, pages_total].
            pages_total = cint(
                frappe.db.get_value("Question", result["question_name"], "pages_total")
            )
            pages_read = min(max(cint(result.get("answer")), 0), pages_total)

            points = (
                round((pages_read / pages_total) * question_details.points, 2)
                if pages_total
                else 0
            )
            result["answer"] = cstr(pages_read)
            result["is_correct"] = 1 if pages_total and pages_read >= pages_total else 0
            result["points"] = points
            score += points

        elif question_details.type in ("Scripture Matching", "Scripture Memorization"):
            # Re-validate server-side from result["answer"] (JSON-stringified
            # by the frontend). Never trust client-submitted is_correct here.
            payload = _parse_scripture_payload(result.get("answer"))
            if question_details.type == "Scripture Matching":
                outcome = check_scripture_matching(result["question_name"], payload)
            else:
                outcome = check_scripture_memorization(result["question_name"], payload)
            correct_n = cint(outcome.get("correct", 0))
            total_n = cint(outcome.get("total", 0)) or 1
            points = round((correct_n / total_n) * question_details.points, 2)
            result["is_correct"] = 1 if correct_n == total_n and total_n > 0 else 0
            result["points"] = points
            score += points

        elif question_details.type != "Open Ended":
            correct = result["is_correct"][0]
            for point in result["is_correct"]:
                correct = correct and point
            result["is_correct"] = correct

            points = question_details.points if correct else 0
            result["points"] = points
            score += points

        else:
            result["is_correct"] = 0

        percentage = (score / score_out_of) * 100
        result["answer"] = re.sub(
            r'<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']', _save_file, result["answer"]
        )

    # avoid duplication of quiz submission
    existing_submission = frappe.get_value(
        "Quiz Submission",
        {
            "quiz": quiz,
            "owner": frappe.session.user,
            "creation": [
                ">=",
                frappe.utils.add_to_date(frappe.utils.now(), seconds=-5),
            ],
        },
        "name",  # Fetch the name of the existing submission
    )
    if existing_submission:
        print("Submission already exists, skipping")
        # Fetch the existing submission details
        submission = frappe.get_doc("Quiz Submission", existing_submission)
        return {
            "score": submission.score,
            "score_out_of": submission.score_out_of,
            "submission": submission.name,
            "pass": submission.percentage >= submission.passing_percentage,
            "percentage": submission.percentage,
        }

    submission = frappe.new_doc("Quiz Submission")
    # Score and percentage are calculated by the controller function
    data = {
        "quiz": quiz,
        "result": results,
        "time_taken": time_taken,
        "score": 0,
        "score_out_of": score_out_of,
        "member": frappe.session.user,
        "percentage": 0,
        "passing_percentage": quiz_details.passing_percentage,
        "standalone": quiz_details.standalone,
    }
    if course:
        data["course"] = course
    # Standalone context (e.g. Aretenic document training); fields are custom-added by the consumer.
    if document_distribution:
        data["document_distribution"] = document_distribution
    if document_distribution_registry:
        data["document_distribution_registry"] = document_distribution_registry
    submission.update(data)
    submission.save(ignore_permissions=True)
    print("Submission ", submission.name, " saved at ", submission.creation)

    # Lesson progress is recorded by the frontend via api.mark_lesson_progress,
    # which has the course/chapter/lesson route context. The Quiz doctype has
    # no lesson/chapter fields, so progress cannot be derived here.

    return {
        "score": round(score, 2),
        "score_out_of": score_out_of,
        "submission": submission.name,
        "pass": percentage == quiz_details.passing_percentage,
        "percentage": percentage,
    }


def _question_answer_key(question_name):
    """Returns (type, correct_answer, explanation) for a Question, used to show
    the expected answer in a result summary. Reading Report has no fixed answer."""
    fields = ["type"]
    for n in range(1, 5):
        fields += [
            f"option_{n}",
            f"is_correct_{n}",
            f"explanation_{n}",
            f"possibility_{n}",
        ]
    q = (
        frappe.db.get_value("Question", question_name, fields, as_dict=1)
        or frappe._dict()
    )

    if q.type == "Choices":
        correct = [
            q.get(f"option_{n}") for n in range(1, 5) if q.get(f"is_correct_{n}")
        ]
        explanation = " ".join(
            q.get(f"explanation_{n}")
            for n in range(1, 5)
            if q.get(f"is_correct_{n}") and q.get(f"explanation_{n}")
        )
        return q.type, ", ".join(filter(None, correct)), explanation or None

    if q.type == "User Input":
        accepted = [
            q.get(f"possibility_{n}") for n in range(1, 5) if q.get(f"possibility_{n}")
        ]
        return q.type, ", ".join(accepted), None

    if q.type == "Scripture Matching":
        rows = frappe.get_all(
            "Scripture Matching Item",
            filters={"parent": question_name},
            fields=["reference", "fetched_text"],
            order_by="idx",
        )
        pairs = [f"{r['reference']} → {r['fetched_text']}" for r in rows]
        return q.type, "\n".join(pairs), None

    if q.type == "Scripture Memorization":
        text = frappe.db.get_value("Question", question_name, "memorization_text") or ""
        return q.type, text, None

    return q.type, None, None


@frappe.whitelist()
def get_last_submission(quiz):
    """Read-only summary of the current user's most recent submission for this
    quiz. Used to show the result when revisiting an already-taken quiz.
    Does NOT create anything (unlike `quiz_summary`)."""
    user = frappe.session.user
    if not user or user == "Guest":
        return

    name = frappe.db.get_value(
        "Quiz Submission",
        {"member": user, "quiz": quiz},
        "name",
        order_by="creation desc",
    )
    if not name:
        return

    submission = frappe.get_doc("Quiz Submission", name)
    result = []
    for row in submission.result:
        qtype, correct_answer, explanation = _question_answer_key(row.question_name)
        row_out = {
            "question_name": row.question_name,
            "question_detail": row.question,
            "type": qtype,
            "answer": row.answer,
            "is_correct": row.is_correct,
            "points": row.points,
            "points_out_of": row.points_out_of,
            "correct_answer": correct_answer,
            "explanation": explanation,
        }
        if qtype == "Scripture Matching":
            row_out["matching_items"] = frappe.get_all(
                "Scripture Matching Item",
                filters={"parent": row.question_name},
                fields=["reference", "fetched_text", "idx"],
                order_by="idx",
            )
        elif qtype == "Scripture Memorization":
            mem = (
                frappe.db.get_value(
                    "Question",
                    row.question_name,
                    [
                        "memorization_text",
                        "memorization_ref",
                        "memorization_resolved_ref",
                    ],
                    as_dict=True,
                )
                or {}
            )
            row_out["memorization_text"] = mem.get("memorization_text") or ""
            row_out["memorization_ref"] = mem.get("memorization_ref") or ""
            row_out["memorization_resolved_ref"] = (
                mem.get("memorization_resolved_ref") or ""
            )
        result.append(row_out)
    return {
        "submission": submission.name,
        "score": submission.score,
        "score_out_of": submission.score_out_of,
        "percentage": submission.percentage,
        "passing_percentage": submission.passing_percentage,
        "result": result,
    }


def _save_file(match):
    data = match.group(1).split("data:")[1]
    headers, content = data.split(",")
    mtype = headers.split(";", 1)[0]

    if isinstance(content, str):
        content = content.encode("utf-8")
    if b"," in content:
        content = content.split(b",")[1]

    try:
        content = safe_b64decode(content)
    except BinasciiError:
        frappe.flags.has_dataurl = True
        return f'<img src="#broken-image" alt="{get_corrupted_image_msg()}"'

    if "filename=" in headers:
        filename = headers.split("filename=")[-1]
        filename = safe_decode(filename).split(";", 1)[0]

    else:
        filename = get_random_filename(content_type=mtype)

    _file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "content": content,
            "decode": False,
            "is_private": False,
        }
    )
    _file.save(ignore_permissions=True)
    file_url = _file.unique_url
    frappe.flags.has_dataurl = True

    return f'<img src="{file_url}"'


def get_corrupted_image_msg():
    return _("Image: Corrupted Data Stream")


@frappe.whitelist()
def get_question_details(question):
    if frappe.db.exists("Quiz Question", question):
        fields = ["name", "question", "type"]
        for num in range(1, 5):
            fields.append(f"option_{cstr(num)}")
            fields.append(f"is_correct_{cstr(num)}")
            fields.append(f"explanation_{cstr(num)}")
            fields.append(f"possibility_{cstr(num)}")

        return frappe.db.get_value("Quiz Question", question, fields, as_dict=1)
    return


@frappe.whitelist()
def get_all_question_results(questions):
    if isinstance(questions, str):
        questions = json.loads(questions)

    results = []
    for question in questions:
        _qtype, correct_answer, explanation = _question_answer_key(question)
        results.append(
            {
                "name": question,
                "correct_option": correct_answer,
                "correct_explanation": explanation,
            }
        )
    return results


@frappe.whitelist()
def check_answer(question, type, answers):
    answers = json.loads(answers)
    print("Answers", answers)
    if type == "Choices":
        return check_choice_answers(question, answers)
    elif type == "Reading Report":
        return check_reading_report(question, answers[0])
    elif type == "Scripture Matching":
        return check_scripture_matching(question, _parse_scripture_payload(answers[0]))
    elif type == "Scripture Memorization":
        return check_scripture_memorization(
            question, _parse_scripture_payload(answers[0])
        )
    else:
        return check_input_answers(question, answers[0])


def _parse_scripture_payload(answer):
    """Frontend sends scripture answers as a JSON-stringified payload (so it can
    pass through the existing string-based answer plumbing). Decode it here."""
    if isinstance(answer, (dict, list)):
        return answer
    if not answer:
        return None
    try:
        return json.loads(answer)
    except (json.JSONDecodeError, TypeError):
        return None


def check_reading_report(question, answer):
    """Returns 1 only when the student read every page (full credit);
    partial scoring is computed authoritatively in `quiz_summary`."""
    pages_total = cint(frappe.db.get_value("Question", question, "pages_total"))
    pages_read = min(max(cint(answer), 0), pages_total)
    return 1 if pages_total and pages_read >= pages_total else 0


def check_choice_answers(question, answers):
    fields = ["multiple"]
    is_correct = []
    for num in range(1, 5):
        fields.append(f"option_{cstr(num)}")
        fields.append(f"is_correct_{cstr(num)}")

    question_details = frappe.db.get_value("Question", question, fields, as_dict=1)

    for num in range(1, 5):
        if question_details[f"option_{num}"] in answers:
            is_correct.append(question_details[f"is_correct_{num}"])
        elif question_details[f"is_correct_{num}"]:
            is_correct.append(2)
        else:
            is_correct.append(0)

    return is_correct


def check_input_answers(question, answer):
    fields = []
    for num in range(1, 5):
        fields.append(f"possibility_{cstr(num)}")

    question_details = frappe.db.get_value("Question", question, fields, as_dict=1)
    for num in range(1, 5):
        current_possibility = question_details[f"possibility_{num}"]
        if (
            current_possibility
            and fuzz.token_sort_ratio(current_possibility, answer) > 85
        ):
            return 1

    return 0


_WORD_NORMALIZE = re.compile(r"[^\w]+", re.UNICODE)


def _normalize_word(w):
    """Lowercase + strip surrounding punctuation, for case-insensitive,
    punctuation-tolerant memorization comparison."""
    if w is None:
        return ""
    return _WORD_NORMALIZE.sub("", str(w)).lower()


def check_scripture_matching(question, answer):
    """answer = [{"ref_idx": int, "text_orig_idx": int, ...}, ...] — one entry
    per displayed slot, in shuffled display order. A slot is correct when the
    student's chosen reference index equals the original index of the text
    that slot displays (because matching_items[N] pairs reference N with text N).

    Returns {"correct": N, "total": M}."""
    rows = frappe.get_all(
        "Scripture Matching Item",
        filters={"parent": question},
        fields=["fetched_text", "idx"],
        order_by="idx",
    )
    total = len(rows)
    if total == 0 or not isinstance(answer, list):
        return {"correct": 0, "total": total or 1}
    correct = 0
    for entry in answer:
        if not isinstance(entry, dict):
            continue
        chosen = entry.get("ref_idx")
        text_orig = entry.get("text_orig_idx")
        if chosen is None or text_orig is None:
            continue
        try:
            if int(chosen) == int(text_orig):
                correct += 1
        except (TypeError, ValueError):
            continue
    return {"correct": correct, "total": total}


def check_scripture_memorization(question, answer):
    """answer = {"positions": [int, ...], "words": [str, ...]} — positions are
    whitespace-token indices into memorization_text; words are what the student
    typed. Returns {"correct": N, "total": len(positions)}."""
    if not isinstance(answer, dict):
        return {"correct": 0, "total": 1}
    positions = answer.get("positions") or []
    words = answer.get("words") or []
    if not positions or len(positions) != len(words):
        return {"correct": 0, "total": len(positions) or 1}
    stored_text = frappe.db.get_value("Question", question, "memorization_text") or ""
    tokens = stored_text.split()
    correct = 0
    for pos, typed in zip(positions, words):
        try:
            pos_i = int(pos)
        except (TypeError, ValueError):
            continue
        if pos_i < 0 or pos_i >= len(tokens):
            continue
        if _normalize_word(typed) == _normalize_word(tokens[pos_i]):
            correct += 1
    return {"correct": correct, "total": len(positions)}
