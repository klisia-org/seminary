# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p009 S5/S6: launching a package, and what it is allowed to tell us (§2.7, §2.9).

The question these tests answer is not "does the data model work" but **what a
hostile package can achieve through it**: it can lie about its own state within
closed vocabularies and clamped ranges, and it can do nothing at all to another
student's attempt, another package, or a grade.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.scorm import cmi, launch as launch_module, runtime, tokens
from seminary.seminary.tests.test_p009_lifecycle import _ScormCase, _zip
from seminary.seminary.tests.test_p006_api import _make_user

DELIVERY_HOST = "scorm.test.invalid"


class TestP009CMI(IntegrationTestCase):
    """The data model rules, which are frappe-free and worth testing alone."""

    def test_unknown_elements_are_dropped_not_refused(self):
        out = cmi.normalise(
            {"cmi.location": "p3", "cmi.interactions.0.id": "q1", "cmi.nonsense": "x"}
        )
        self.assertEqual(out, {"location": "p3"})

    def test_lesson_status_expands_into_both_2004_fields(self):
        self.assertEqual(
            cmi.normalise({cmi.LESSON_STATUS: "passed"}),
            {"completion_status": "completed", "success_status": "passed"},
        )
        # 1.2 has no success vocabulary of its own, so `completed` must not
        # overwrite a pass already recorded.
        self.assertEqual(
            cmi.normalise({cmi.LESSON_STATUS: "completed"}),
            {"completion_status": "completed"},
        )
        self.assertEqual(
            cmi.normalise({cmi.LESSON_STATUS: "browsed"}),
            {"completion_status": "incomplete"},
        )

    def test_an_invented_lesson_status_is_refused(self):
        with self.assertRaises(cmi.CMIError):
            cmi.normalise({cmi.LESSON_STATUS: "definitely-passed"})

    def test_times_must_be_scorm_durations(self):
        self.assertEqual(cmi.check_time("t", "0000:10:00.00"), "0000:10:00.00")
        self.assertEqual(cmi.check_time("t", "PT10M30S"), "PT10M30S")
        for bad in ("10 minutes", "PT", "99:99:99", "'; drop table"):
            with self.subTest(bad=bad), self.assertRaises(cmi.CMIError):
                cmi.check_time("t", bad)

    def test_lengths_are_refused_not_truncated(self):
        with self.assertRaises(cmi.CMIError) as caught:
            cmi.check_length("suspend_data", "x" * 100, 10)
        self.assertEqual(caught.exception.code, cmi.ERR_OUT_OF_RANGE)


class TestP009Launch(_ScormCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "p9-student")
        cls.outsider = _make_user("Student", "p9-outsider")

    def setUp(self):
        super().setUp()
        self.conf = patch.dict(
            frappe.conf,
            {"scorm_delivery_host": DELIVERY_HOST, "host_name": "https://app.invalid"},
        )
        self.conf.start()
        self.addCleanup(self.conf.stop)

        self._with_section()
        self._enrol(self.student, "p9s")
        self.chapter = self._chapter()
        self.package_name = self._unpack(
            self.chapter,
            _zip(
                [("A", "One", "a.html"), ("B", "Two", "b.html")],
                nonce=frappe.generate_hash(length=6),
            ),
        )
        self.package = frappe.get_doc("SCORM Package", self.package_name)
        self.assertEqual(self.package.status, "Ready", self.package.failure_reason)

    def test_a_launch_carries_the_scos_their_lessons_and_the_base_url(self):
        payload = launch_module.launch(self.chapter.name)
        self.assertEqual(payload["status"], "Ready")
        self.assertEqual([s["id"] for s in payload["scos"]], ["A", "B"])
        self.assertTrue(all(s["lesson"] for s in payload["scos"]))
        self.assertTrue(
            payload["launcher"].startswith(f"https://{DELIVERY_HOST}/scorm/")
        )
        self.assertIn(self.package.package_id, payload["launcher"])

    def test_a_launch_is_refused_to_someone_not_in_the_section(self):
        frappe.set_user(self.outsider)
        with self.assertRaises(frappe.PermissionError):
            launch_module.launch(self.chapter.name)
        frappe.set_user("Administrator")

    def test_a_package_that_is_not_ready_says_so_without_a_token(self):
        frappe.db.set_value("SCORM Package", self.package_name, "status", "Exploding")
        payload = launch_module.launch(self.chapter.name)
        self.assertEqual(payload["status"], "Exploding")
        self.assertNotIn("token", payload)

    def test_no_delivery_host_means_no_launch(self):
        with patch.dict(frappe.conf, {"scorm_delivery_host": None}):
            with self.assertRaises(frappe.DoesNotExistError):
                launch_module.launch(self.chapter.name)

    def test_the_learner_id_is_opaque_and_not_the_email(self):
        payload = launch_module.launch(self.chapter.name)
        learner = payload["scos"][0]["cmi"]["learner_id"]
        self.assertNotIn("@", learner)
        self.assertNotIn(frappe.session.user, learner)
        # Stable for this learner and SCO, different for another SCO.
        self.assertEqual(learner, payload["scos"][0]["cmi"]["learner_id"])
        self.assertNotEqual(learner, payload["scos"][1]["cmi"]["learner_id"])

    def test_staff_launch_in_review_mode(self):
        payload = launch_module.launch(self.chapter.name)
        self.assertEqual(payload["mode"], launch_module.MODE_REVIEW)

    def test_a_heartbeat_is_only_for_the_user_it_was_issued_to(self):
        token = tokens.mint(
            "someone@else.invalid", self.package_name, self.chapter.name
        )
        self.assertFalse(launch_module.heartbeat(token)["ok"])


class _CommitCase(_ScormCase):
    """A student, a section, an unpacked package and a launch token.

    Not a `Test*` class: `test_p009_grades` builds on this setup, and
    subclassing a class that holds tests would re-run every one of them there.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "p9-committer")

    def setUp(self):
        super().setUp()
        self.conf = patch.dict(frappe.conf, {"scorm_delivery_host": DELIVERY_HOST})
        self.conf.start()
        self.addCleanup(self.conf.stop)

        self._with_section()
        self._enrol(self.student, "p9c")
        self.chapter = self._chapter()
        self.package_name = self._unpack(
            self.chapter,
            _zip([("A", "One", "a.html")], nonce=frappe.generate_hash(length=6)),
        )
        # Commit as a student: staff launches are previews and store nothing.
        frappe.set_user(self.student)
        self.token = tokens.mint(self.student, self.package_name, self.chapter.name)
        self.addCleanup(lambda: frappe.set_user("Administrator"))

    def _commit(self, data, sco="A", token=None):
        with patch.object(runtime, "_mode", return_value=launch_module.MODE_NORMAL):
            return runtime.commit(token or self.token, sco, data)

    def _attempt(self):
        return frappe.get_doc(
            "SCORM Attempt",
            {
                "package": self.package_name,
                "sco_identifier": "A",
                "member": self.student,
            },
        )


class TestP009Commit(_CommitCase):
    # ------------------------------------------------------------- identity

    def test_a_commit_against_someone_elses_launch_writes_nothing(self):
        stolen = tokens.mint(
            "someone@else.invalid", self.package_name, self.chapter.name
        )
        result = self._commit({"cmi.location": "p1"}, token=stolen)
        self.assertFalse(result["ok"])
        self.assertFalse(
            frappe.db.exists("SCORM Attempt", {"package": self.package_name})
        )

    def test_a_commit_with_no_launch_writes_nothing(self):
        result = self._commit({"cmi.location": "p1"}, token="0" * 64)
        self.assertFalse(result["ok"])

    def test_a_commit_for_a_sco_the_package_does_not_have_is_refused(self):
        self.assertFalse(self._commit({"cmi.location": "p1"}, sco="NOPE")["ok"])

    # ---------------------------------------------------------- the values

    def test_a_good_commit_is_stored(self):
        result = self._commit(
            {
                cmi.LESSON_STATUS: "incomplete",
                "cmi.core.lesson_location": "page-3",
                "cmi.core.session_time": "0000:05:00.00",
            }
        )
        self.assertTrue(result["stored"])
        attempt = self._attempt()
        self.assertEqual(attempt.completion_status, "incomplete")
        self.assertEqual(attempt.location, "page-3")

    def test_a_score_outside_the_declared_range_is_clamped_not_refused(self):
        self._commit(
            {
                "cmi.core.score.min": "0",
                "cmi.core.score.max": "50",
                "cmi.core.score.raw": "9999",
            }
        )
        self.assertEqual(self._attempt().score_raw, 50.0)

    def test_an_invented_status_is_refused_and_stores_nothing(self):
        result = self._commit({cmi.LESSON_STATUS: "definitely-passed"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], cmi.ERR_TYPE_MISMATCH)
        self.assertFalse(
            frappe.db.exists("SCORM Attempt", {"package": self.package_name})
        )

    def test_oversize_suspend_data_is_refused(self):
        with patch.dict(frappe.conf, {"scorm_max_suspend_bytes": 32}):
            result = self._commit({"cmi.suspend_data": "x" * 100})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], cmi.ERR_OUT_OF_RANGE)

    def test_an_element_outside_the_allow_list_never_reaches_the_row(self):
        self._commit(
            {"cmi.location": "p1", "cmi.comments_from_learner.0.comment": "hi"}
        )
        attempt = self._attempt()
        self.assertEqual(attempt.location, "p1")
        self.assertFalse(
            [f for f in attempt.as_dict() if "comment" in f],
            "an unlisted element created a field",
        )

    def test_a_locked_attempt_is_not_rewritten(self):
        self._commit({"cmi.core.score.raw": "10"})
        attempt = self._attempt()
        attempt.db_set("locked", 1)
        result = self._commit({"cmi.core.score.raw": "99"})
        self.assertTrue(result["ok"])
        self.assertFalse(result["stored"])
        self.assertEqual(self._attempt().score_raw, 10.0)

    # ------------------------------------------------------------ progress

    def test_completion_marks_the_lesson_through_save_progress(self):
        lesson = frappe.db.get_value(
            "Course Lesson",
            {"chapter": self.chapter.name, "scorm_sco_identifier": "A"},
            "name",
        )
        self._commit({cmi.LESSON_STATUS: "passed"})
        self.assertEqual(
            frappe.db.get_value(
                "Course Schedule Progress",
                {"lesson": lesson, "member": self.student},
                "status",
            ),
            "Complete",
        )

    def test_an_incomplete_sco_records_partial_progress(self):
        lesson = frappe.db.get_value(
            "Course Lesson",
            {"chapter": self.chapter.name, "scorm_sco_identifier": "A"},
            "name",
        )
        self._commit(
            {cmi.LESSON_STATUS: "incomplete", "cmi.core.lesson_location": "p2"}
        )
        self.assertEqual(
            frappe.db.get_value(
                "Course Schedule Progress",
                {"lesson": lesson, "member": self.student},
                "status",
            ),
            "Partially Complete",
        )

    def test_a_later_incomplete_never_takes_completion_away(self):
        lesson = frappe.db.get_value(
            "Course Lesson",
            {"chapter": self.chapter.name, "scorm_sco_identifier": "A"},
            "name",
        )
        self._commit({cmi.LESSON_STATUS: "passed"})
        self._commit({cmi.LESSON_STATUS: "incomplete"})
        self.assertEqual(
            frappe.db.get_value(
                "Course Schedule Progress",
                {"lesson": lesson, "member": self.student},
                "status",
            ),
            "Complete",
        )

    def test_no_score_ever_reaches_a_grade_on_its_own(self):
        # §2.12: a score is a claim from code the student can reach. It lands on
        # the attempt and goes no further without an explicit mapping (S10).
        self._commit({cmi.LESSON_STATUS: "passed", "cmi.core.score.raw": "100"})
        self.assertEqual(self._attempt().score_raw, 100.0)
        self.assertFalse(
            frappe.db.exists("Activity Competency Grade", {"student": self.student}),
            "a SCORM score reached the gradebook with no mapping",
        )

    def test_a_review_launch_stores_nothing(self):
        with patch.object(runtime, "_mode", return_value=launch_module.MODE_REVIEW):
            result = runtime.commit(self.token, "A", {cmi.LESSON_STATUS: "passed"})
        self.assertTrue(result["ok"])
        self.assertFalse(result["stored"])
        self.assertFalse(
            frappe.db.exists("SCORM Attempt", {"package": self.package_name})
        )
