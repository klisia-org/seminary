# Copyright (c) 2026, Murilo Melo and contributors
# For license information, please see license.txt
"""Standalone tests for the internal plagiarism engine. The engine is pure
Python (no frappe), so these run under ``bench run-tests`` and as a plain
``python -m unittest`` alike."""

import unittest

from seminary.seminary.plagiarism.base import (
    STATUS_COMPLETED,
    STATUS_SKIPPED,
)
from seminary.seminary.plagiarism.internal import InternalPlagiarismAdapter

ESSAY_A = (
    "The doctrine of justification by faith stands at the heart of the "
    "Reformation. Luther argued that sinners are declared righteous through "
    "trust in Christ alone, apart from the works of the law, and that this "
    "righteousness is imputed rather than infused into the believer."
)
# Same argument, lightly reworded — should read as highly similar.
ESSAY_A_COPY = (
    "The doctrine of justification by faith stands at the heart of the "
    "Reformation. Luther argued that sinners are declared righteous through "
    "trust in Christ alone, apart from works of the law, and that this "
    "righteousness is imputed and not infused into the believer."
)
ESSAY_B = (
    "Monastic communities in the early medieval period organized daily life "
    "around the canonical hours. Bells summoned the brothers to prayer, manual "
    "labor filled the afternoons, and the scriptorium preserved classical "
    "texts that might otherwise have been lost to later generations entirely."
)

CONFIG = {
    "ngram_size": 5,
    "min_document_length": 100,
    "exclude_same_student": True,
}


def _corpus(*texts):
    return [
        {
            "name": f"AS-{i}",
            "student": f"STU-{i}",
            "member_name": f"Student {i}",
            "course": f"CS-{i}",
            "text": t,
        }
        for i, t in enumerate(texts)
    ]


class TestInternalEngine(unittest.TestCase):
    def setUp(self):
        self.adapter = InternalPlagiarismAdapter()

    def test_near_identical_scores_high(self):
        report = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": ESSAY_A},
            _corpus(ESSAY_A_COPY, ESSAY_B),
            CONFIG,
        )
        self.assertEqual(report.status, STATUS_COMPLETED)
        self.assertGreaterEqual(report.overall_score, 80)
        top = report.matched_sources[0]
        self.assertEqual(top.source_submission, "AS-0")
        # difflib should surface verbatim shared passages on the top match.
        self.assertTrue(top.matched_passages)

    def test_unrelated_scores_low(self):
        report = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": ESSAY_A},
            _corpus(ESSAY_B),
            CONFIG,
        )
        self.assertEqual(report.status, STATUS_COMPLETED)
        self.assertLessEqual(report.overall_score, 15)

    def test_short_text_is_skipped(self):
        report = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": "Too short."},
            _corpus(ESSAY_A),
            CONFIG,
        )
        self.assertEqual(report.status, STATUS_SKIPPED)
        self.assertEqual(report.overall_score, 0)

    def test_same_student_excluded_from_headline(self):
        # The only match is the same student's own other submission → headline
        # stays 0 while the row is still listed and flagged.
        report = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": ESSAY_A},
            [
                {
                    "name": "AS-OLD",
                    "student": "STU-T",
                    "member_name": "Same Student",
                    "course": "CS-OLD",
                    "text": ESSAY_A_COPY,
                }
            ],
            CONFIG,
        )
        self.assertEqual(report.overall_score, 0)
        self.assertTrue(report.matched_sources)
        self.assertTrue(report.matched_sources[0].same_student)

    def test_stripping_question_lowers_score(self):
        question = (
            "Discuss the relationship between the canonical hours and daily "
            "labor in early medieval monastic communities and the scriptorium."
        )
        target = question + " I think the bells were the key organizing force."
        source = question + " My view is that prayer shaped the entire rhythm."

        without = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": target},
            _corpus(source),
            CONFIG,
        ).overall_score
        with_strip = self.adapter.check(
            {"name": "AS-T", "student": "STU-T", "text": target},
            _corpus(source),
            {**CONFIG, "question_text": question},
        ).overall_score

        self.assertLess(with_strip, without)


if __name__ == "__main__":
    unittest.main()
