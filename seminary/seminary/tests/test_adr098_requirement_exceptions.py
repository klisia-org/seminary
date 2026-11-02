# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/098: course substitutions and waivers with approval."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary import exceptions
from seminary.seminary.api import _program_audit
from seminary.seminary.graduation import waive_sgr
from seminary.seminary.tests import cohort_fixtures as fx


def _course():
    name = fx.uid("C098")
    frappe.get_doc(
        {
            "doctype": "Course",
            "name": name,
            "course_name": name,
            "coursecode": name[-10:],
        }
    ).db_insert()
    return name


def _program(required, optional=()):
    program = fx.make_program("Credits-based")
    for idx, (course, is_required) in enumerate(
        [(c, 1) for c in required] + [(c, 0) for c in optional], 1
    ):
        frappe.get_doc(
            {
                "doctype": "Program Course",
                "name": frappe.generate_hash(length=10),
                "parent": program.name,
                "parenttype": "Program",
                "parentfield": "courses",
                "idx": idx,
                "course": course,
                "course_name": course,
                "required": is_required,
                "pgmcourse_credits": 3,
            }
        ).db_insert()
    frappe.clear_document_cache("Program", program.name)
    return frappe.get_doc("Program", program.name)


def _pass(pe, course, credits=3):
    frappe.get_doc(
        {
            "doctype": "Program Enrollment Course",
            "name": frappe.generate_hash(length=10),
            "parent": pe.name,
            "parenttype": "Program Enrollment",
            "parentfield": "courses",
            "course_name": course,
            "credits": credits,
            "status": "Pass",
        }
    ).db_insert()


def _sgr(pe, name="Ministry Interview"):
    row = frappe.get_doc(
        {
            "doctype": "Student Graduation Requirement",
            "name": frappe.generate_hash(length=10),
            "parent": pe.name,
            "parenttype": "Program Enrollment",
            "parentfield": "graduation_requirements",
            "requirement_name": name,
            "requirement_type": "Manual Verification",
            "mandatory": 1,
            "status": "Not Started",
        }
    )
    row.db_insert()
    return row.name


def _user(*roles):
    user = fx.make_user()
    for role in roles:
        user.add_roles(role)
    return user.name


def _exception(pe, **values):
    return frappe.get_doc(
        {
            "doctype": "Requirement Exception",
            "program_enrollment": pe.name,
            "reason": "Took the equivalent elsewhere",
            **values,
        }
    ).insert(ignore_permissions=True)


class ADR098Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("adr098_test")
        notify = patch.object(exceptions, "_notify")
        notify.start()
        self.addCleanup(notify.stop)
        self.req_a, self.req_b = _course(), _course()
        self.elective = _course()
        self.program = _program([self.req_a, self.req_b], [self.elective])
        self.student = fx.make_student()
        self.pe = fx.make_enrollment(self.student, self.program)
        self.registrar = _user("Registrar")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="adr098_test")
        super().tearDown()

    def as_student(self):
        frappe.set_user(self.student.user)


class TestSubstitution(ADR098Case):
    def test_registrar_records_an_approved_substitution(self):
        frappe.set_user(self.registrar)
        ex = _exception(
            self.pe,
            kind="Substitution",
            required_course=self.req_a,
            substitute_course=self.elective,
        )
        self.assertEqual(ex.status, "Approved")
        self.assertEqual(ex.decided_by, self.registrar)
        self.assertEqual(ex.requested_by, self.registrar)

    def test_satisfied_only_once_the_substitute_is_passed(self):
        _exception(
            self.pe,
            kind="Substitution",
            required_course=self.req_a,
            substitute_course=self.elective,
        )
        self.assertNotIn(self.req_a, exceptions.satisfied_courses(self.pe.name))
        line = self._audit_line(self.req_a)
        self.assertEqual(line["status"], "Not Started")
        self.assertEqual(line["exception"]["substitute_course"], self.elective)

        _pass(self.pe, self.elective, credits=2)
        self.assertIn(self.req_a, exceptions.satisfied_courses(self.pe.name))
        line = self._audit_line(self.req_a)
        self.assertEqual(line["status"], "Completed")
        self.assertEqual(line["earned_credits"], 2)

    def test_audit_and_graduation_check_agree(self):
        _exception(
            self.pe,
            kind="Substitution",
            required_course=self.req_a,
            substitute_course=self.elective,
        )
        _exception(self.pe, kind="Course Waiver", required_course=self.req_b)
        _pass(self.pe, self.elective)
        audit = _program_audit(self.pe.name)
        self.assertEqual(
            {mc["course"]: mc["status"] for mc in audit["mandatory_courses"]},
            {self.req_a: "Completed", self.req_b: "Waived"},
        )
        self.assertEqual(
            exceptions.satisfied_courses(self.pe.name) >= {self.req_a, self.req_b},
            True,
        )

    def test_substitute_cannot_be_a_required_course(self):
        with self.assertRaises(frappe.ValidationError):
            _exception(
                self.pe,
                kind="Substitution",
                required_course=self.req_a,
                substitute_course=self.req_b,
            )

    def test_required_course_must_be_required(self):
        with self.assertRaises(frappe.ValidationError):
            _exception(self.pe, kind="Course Waiver", required_course=self.elective)

    def test_substitute_stands_in_once(self):
        other = _course()
        _exception(
            self.pe,
            kind="Substitution",
            required_course=self.req_a,
            substitute_course=other,
        )
        with self.assertRaises(frappe.ValidationError):
            _exception(
                self.pe,
                kind="Substitution",
                required_course=self.req_b,
                substitute_course=other,
            )

    def test_one_open_exception_per_requirement(self):
        _exception(self.pe, kind="Course Waiver", required_course=self.req_a)
        with self.assertRaises(frappe.ValidationError):
            _exception(
                self.pe,
                kind="Substitution",
                required_course=self.req_a,
                substitute_course=self.elective,
            )

    def _audit_line(self, course):
        audit = _program_audit(self.pe.name)
        return next(mc for mc in audit["mandatory_courses"] if mc["course"] == course)


class TestRequestAndDecide(ADR098Case):
    def test_student_requests_and_registrar_approves(self):
        self.as_student()
        out = exceptions.request(
            self.pe.name,
            "Substitution",
            "Took it at my previous school",
            required_course=self.req_a,
            substitute_course=self.elective,
        )
        self.assertEqual(out["status"], "Requested")
        with self.assertRaises(frappe.PermissionError):
            exceptions.decide(out["name"], 1)

        frappe.set_user(self.registrar)
        self.assertEqual(exceptions.decide(out["name"], 1, "OK")["status"], "Approved")
        ex = frappe.get_doc("Requirement Exception", out["name"])
        self.assertEqual(ex.decided_by, self.registrar)
        self.assertEqual(ex.requested_by, self.student.user)

    def test_student_cannot_request_for_another_student(self):
        other = fx.make_enrollment(fx.make_student(), self.program)
        self.as_student()
        with self.assertRaises(frappe.PermissionError):
            exceptions.request(
                other.name, "Course Waiver", "x", required_course=self.req_a
            )

    def test_student_cannot_record_directly(self):
        self.as_student()
        with self.assertRaises(frappe.PermissionError):
            _exception(self.pe, kind="Course Waiver", required_course=self.req_a)

    def test_requester_withdraws(self):
        self.as_student()
        out = exceptions.request(
            self.pe.name, "Course Waiver", "x", required_course=self.req_a
        )
        self.assertEqual(exceptions.withdraw(out["name"])["status"], "Withdrawn")
        # A withdrawn request frees the requirement for a new one.
        exceptions.request(
            self.pe.name, "Course Waiver", "again", required_course=self.req_a
        )

    def test_denied_counts_for_nothing(self):
        self.as_student()
        out = exceptions.request(
            self.pe.name, "Course Waiver", "x", required_course=self.req_a
        )
        frappe.set_user(self.registrar)
        exceptions.decide(out["name"], 0, "No")
        self.assertNotIn(self.req_a, exceptions.satisfied_courses(self.pe.name))

    def test_seminary_manager_decides_any_program(self):
        self.as_student()
        out = exceptions.request(
            self.pe.name, "Course Waiver", "x", required_course=self.req_a
        )
        frappe.set_user(_user("Seminary Manager"))
        self.assertEqual(exceptions.decide(out["name"], 1)["status"], "Approved")


class TestProgramChair(ADR098Case):
    def setUp(self):
        super().setUp()
        self.chair = _user("Program Chair")
        self.as_student()
        self.requested = exceptions.request(
            self.pe.name, "Course Waiver", "x", required_course=self.req_a
        )["name"]
        frappe.set_user("Administrator")

    def test_chair_of_another_program_cannot_decide_or_see(self):
        frappe.set_user(self.chair)
        with self.assertRaises(frappe.PermissionError):
            exceptions.decide(self.requested, 1)
        self.assertFalse(frappe.get_list("Requirement Exception", pluck="name"))

    def test_chair_decides_for_their_program(self):
        frappe.db.set_value(
            "Program", self.program.name, "program_director", self.chair
        )
        frappe.set_user(self.chair)
        self.assertIn(
            self.requested, frappe.get_list("Requirement Exception", pluck="name")
        )
        self.assertEqual(exceptions.decide(self.requested, 1)["status"], "Approved")


class TestRequirementWaiver(ADR098Case):
    def test_waive_sgr_leaves_an_approved_exception(self):
        sgr = _sgr(self.pe)
        frappe.set_user(self.registrar)
        waive_sgr(self.pe.name, sgr, "Interviewed at ordination")
        row = frappe.db.get_value(
            "Student Graduation Requirement",
            sgr,
            ["status", "waived", "waived_by", "requirement_exception"],
            as_dict=True,
        )
        self.assertEqual((row.status, row.waived), ("Waived", 1))
        self.assertEqual(row.waived_by, self.registrar)
        ex = frappe.get_doc("Requirement Exception", row.requirement_exception)
        self.assertEqual((ex.kind, ex.status), ("Requirement Waiver", "Approved"))
        self.assertEqual(ex.requirement_name, "Ministry Interview")

    def test_waive_sgr_needs_a_registrar(self):
        sgr = _sgr(self.pe)
        self.as_student()
        with self.assertRaises(frappe.PermissionError):
            waive_sgr(self.pe.name, sgr, "please")

    def test_revoke_restores_the_requirement(self):
        sgr = _sgr(self.pe)
        waive_sgr(self.pe.name, sgr, "x")
        name = frappe.db.get_value(
            "Student Graduation Requirement", sgr, "requirement_exception"
        )
        with self.assertRaises(frappe.ValidationError):
            exceptions.revoke(name, "")
        exceptions.revoke(name, "Granted in error")
        row = frappe.db.get_value(
            "Student Graduation Requirement",
            sgr,
            ["status", "waived", "requirement_exception"],
            as_dict=True,
        )
        self.assertEqual((row.status, row.waived), ("Not Started", 0))
        self.assertFalse(row.requirement_exception)


class TestOrphans(ADR098Case):
    def test_exception_for_a_course_no_longer_required_is_orphaned(self):
        ex = _exception(self.pe, kind="Course Waiver", required_course=self.req_a)
        self.assertNotIn(ex.name, [r.name for r in exceptions.orphaned([self.pe.name])])
        frappe.db.set_value(
            "Program Course",
            {"parent": self.program.name, "course": self.req_a},
            "required",
            0,
        )
        frappe.clear_document_cache("Program", self.program.name)
        self.assertIn(ex.name, [r.name for r in exceptions.orphaned([self.pe.name])])
