# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/091: agreements and required documents for students and instructors."""

import hashlib
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from seminary.seminary import requirements as req
from seminary.seminary.tests import cohort_fixtures as fx


def _doc_type(needs_review=1, valid_months=None, extensions="pdf, txt"):
    return frappe.get_doc(
        {
            "doctype": "Document Type",
            "type_name": fx.uid("Diploma"),
            "needs_review": needs_review,
            "valid_months": valid_months,
            "allowed_extensions": extensions,
        }
    ).insert(ignore_permissions=True)


def _template(body="<p>I, {{ person.full_name }}, agree.</p>", countersign_role=None):
    return frappe.get_doc(
        {
            "doctype": "Agreement Template",
            "title": fx.uid("Contract"),
            "body": body,
            "countersign_role": countersign_role,
        }
    ).insert(ignore_permissions=True)


def _rule(kind, target, **kw):
    row = {"kind": kind, "due_days": 10, "renewal": "Not needed"}
    row["agreement_template" if kind == "Agreement" else "document_type"] = target
    row.update(kw)
    return row


def _program(rules):
    program = fx.make_program()
    for r in rules:
        program.append("enrollment_requirements", r)
    program.save(ignore_permissions=True)
    return program


def _student():
    user = fx.make_user(roles=("Student",))
    person = fx.make_person("Student", user=user.name)
    return fx.make_student(person), person


def _rows(reference_name, **filters):
    return frappe.get_all(
        "Person Requirement",
        filters={"reference_name": reference_name, **filters},
        fields=[
            "name",
            "status",
            "kind",
            "document_type",
            "agreement_template",
            "academic_term",
            "academic_year",
            "due_date",
            "blocking",
        ],
        order_by="creation asc",
    )


def _upload_as(user, name="diploma.txt", content=b"adr091 test file"):
    frappe.set_user(user)
    f = frappe.get_doc(
        {"doctype": "File", "file_name": name, "content": content, "is_private": 1}
    ).insert(ignore_permissions=True)
    return f.file_url


class ADR091Case(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.savepoint("adr091_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="adr091_test")
        super().tearDown()


class TestEnrollmentRequirements(ADR091Case):
    def test_rules_are_copied_on_submit_and_program_edits_do_not_reach_back(self):
        dt = _doc_type()
        program = _program([_rule("Document", dt.name, blocking=1)])
        student, _p = _student()
        pe = fx.make_enrollment(student, program)
        rows = _rows(pe.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "Pending")
        self.assertEqual(getdate(rows[0].due_date), getdate(add_days(today(), 10)))

        later = _doc_type()
        program.append("enrollment_requirements", _rule("Document", later.name))
        program.save(ignore_permissions=True)
        self.assertEqual(len(_rows(pe.name)), 1)
        self.assertEqual(req.add_missing_requirements(program.name), 1)
        self.assertEqual(len(_rows(pe.name)), 2)
        self.assertEqual(req.add_missing_requirements(program.name), 0)

    def test_upload_review_accept_and_expiry(self):
        dt = _doc_type(valid_months=12)
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        pe = fx.make_enrollment(student, program)
        row = _rows(pe.name)[0]

        url = _upload_as(person.user)
        self.assertEqual(req.upload_document(row.name, url)["status"], "Submitted")
        frappe.set_user("Administrator")
        pdoc = frappe.get_value("Person Document", {"person": person.name}, "name")
        req.accept_document(pdoc)
        self.assertEqual(
            frappe.db.get_value("Person Requirement", row.name, "status"), "Satisfied"
        )
        valid_until = frappe.db.get_value("Person Document", pdoc, "valid_until")
        self.assertEqual(
            getdate(valid_until), getdate(frappe.utils.add_months(today(), 12))
        )

        req.expire_documents(on=add_days(valid_until, 1))
        self.assertEqual(
            frappe.db.get_value("Person Document", pdoc, "status"), "Expired"
        )
        self.assertEqual(
            frappe.db.get_value("Person Requirement", row.name, "status"), "Pending"
        )

    def test_a_type_without_review_counts_at_once(self):
        dt = _doc_type(needs_review=0)
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        url = _upload_as(person.user)
        self.assertEqual(req.upload_document(row.name, url)["status"], "Satisfied")

    def test_rejection_reopens_the_row_and_tells_the_person(self):
        dt = _doc_type()
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        req.upload_document(row.name, _upload_as(person.user))
        frappe.set_user("Administrator")
        pdoc = frappe.get_value("Person Document", {"person": person.name}, "name")
        with self.assertRaises(frappe.ValidationError):
            req.reject_document(pdoc, "")
        req.reject_document(pdoc, "Unreadable scan")
        self.assertEqual(
            frappe.db.get_value("Person Requirement", row.name, "status"), "Pending"
        )
        self.assertTrue(
            frappe.db.exists(
                "Communication Log", {"idempotency_key": f"req-rejected-{pdoc}-app"}
            )
        )

    def test_a_document_on_file_satisfies_the_next_enrollment(self):
        dt = _doc_type()
        student, person = _student()
        first = _rows(
            fx.make_enrollment(student, _program([_rule("Document", dt.name)])).name
        )[0]
        req.upload_document(first.name, _upload_as(person.user))
        frappe.set_user("Administrator")
        req.accept_document(
            frappe.get_value("Person Document", {"person": person.name}, "name")
        )

        second = fx.make_enrollment(student, _program([_rule("Document", dt.name)]))
        self.assertEqual(_rows(second.name)[0].status, "Satisfied")

    def test_upload_refuses_someone_elses_row_or_file(self):
        dt = _doc_type()
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        _other, other_person = _student()

        url = _upload_as(other_person.user)
        with self.assertRaises(frappe.PermissionError):
            req.upload_document(row.name, url)  # not their row
        frappe.set_user(person.user)
        with self.assertRaises(frappe.PermissionError):
            req.upload_document(row.name, url)  # not their file

    def test_extension_is_checked(self):
        dt = _doc_type(extensions="pdf")
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        url = _upload_as(person.user, name="diploma.exe", content=b"x")
        with self.assertRaises(frappe.ValidationError):
            req.upload_document(row.name, url)

    def test_people_read_only_their_own(self):
        dt = _doc_type()
        program = _program([_rule("Document", dt.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        req.upload_document(row.name, _upload_as(person.user))
        frappe.set_user("Administrator")
        pdoc = frappe.get_value("Person Document", {"person": person.name}, "name")
        _other, other_person = _student()

        frappe.set_user(other_person.user)
        self.assertFalse(frappe.has_permission("Person Document", "read", pdoc))
        self.assertFalse(frappe.has_permission("Person Requirement", "read", row.name))
        self.assertNotIn(pdoc, frappe.get_list("Person Document", pluck="name"))
        frappe.set_user(person.user)
        self.assertTrue(frappe.has_permission("Person Document", "read", pdoc))
        self.assertIn(row.name, frappe.get_list("Person Requirement", pluck="name"))


class TestBlocking(ADR091Case):
    def test_overdue_blocking_stops_self_enrollment_until_waived(self):
        from seminary.seminary import api

        dt = _doc_type()
        program = _program([_rule("Document", dt.name, blocking=1, due_days=0)])
        student, person = _student()
        pe = fx.make_enrollment(student, program)
        row = _rows(pe.name)[0]
        frappe.db.set_value(
            "Person Requirement", row.name, "due_date", add_days(today(), -1)
        )
        frappe.db.set_single_value("Seminary Settings", "allow_portal_enroll", 1)

        frappe.set_user(person.user)
        with self.assertRaises(frappe.ValidationError) as cm:
            api._assert_may_course_enroll(pe.name)
        self.assertIn(dt.name, str(cm.exception))
        self.assertIn(dt.name, req.overdue_labels(pe.name))

        frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            req.waive_requirement(row.name, " ")
        req.waive_requirement(row.name, "Diploma seen in person")
        frappe.set_user(person.user)
        api._assert_may_course_enroll(pe.name)  # no longer blocked
        self.assertEqual(req.overdue_labels(pe.name), "")

    def test_staff_endpoints_refuse_a_student(self):
        _s, person = _student()
        frappe.set_user(person.user)
        for fn, args in (
            (req.waive_requirement, ("x", "y")),
            (req.accept_document, ("x",)),
            (req.reject_document, ("x", "y")),
            (req.countersign, ("x", "y")),
            (req.add_missing_requirements, ("x",)),
        ):
            with self.subTest(fn=fn.__name__), self.assertRaises(
                frappe.PermissionError
            ):
                fn(*args)


class TestAgreements(ADR091Case):
    def test_versions_lock_once_signed(self):
        t = _template()
        self.assertEqual(t.current_version, 1)
        t.body = "<p>Edited before anyone signed.</p>"
        t.save(ignore_permissions=True)
        self.assertEqual((t.current_version, len(t.versions)), (1, 1))

        program = _program([_rule("Agreement", t.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        frappe.set_user(person.user)
        req.sign_agreement(row.name, "Test Signer", consent=1)
        frappe.set_user("Administrator")

        t.reload()
        t.body = "<p>Edited after a signature.</p>"
        t.save(ignore_permissions=True)
        self.assertEqual((t.current_version, len(t.versions)), (2, 2))
        sa = frappe.get_doc("Signed Agreement", {"person_requirement": row.name})
        self.assertEqual(sa.template_version, 1)
        self.assertIn("Edited before anyone signed.", sa.rendered_html)

    def test_bad_jinja_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            _template(body="<p>{{ person.full_name </p>")

    def test_signing_records_the_evidence(self):
        t = _template(
            body="<p>{{ person.full_name }} / {{ person.position }} / {{ program.program_name }}</p>"
        )
        program = _program([_rule("Agreement", t.name)])
        student, person = _student()
        frappe.db.set_value(
            "Person", person.name, "position", "<script>alert(1)</script>"
        )
        row = _rows(fx.make_enrollment(student, program).name)[0]

        frappe.set_user(person.user)
        with self.assertRaises(frappe.ValidationError):
            req.sign_agreement(row.name, "Test Signer", consent=0)
        with self.assertRaises(frappe.ValidationError):
            req.sign_agreement(row.name, "  ", consent=1)
        preview = req.agreement_preview(row.name)
        self.assertIn(program.program_name, preview["html"])
        self.assertNotIn("<script>", preview["html"])
        self.assertIn("&lt;script&gt;", preview["html"])

        out = req.sign_agreement(row.name, "Test  Signer", consent=1)
        self.assertEqual(out["status"], "Satisfied")
        with self.assertRaises(frappe.ValidationError):
            req.sign_agreement(row.name, "Test Signer", consent=1)  # once only

        frappe.set_user("Administrator")
        sa = frappe.get_doc("Signed Agreement", out["signed_agreement"])
        self.assertEqual(
            (sa.docstatus, sa.status, sa.signer_name), (1, "Complete", "Test Signer")
        )
        self.assertEqual(sa.signed_by, person.user)
        self.assertEqual(
            sa.html_sha256, hashlib.sha256(sa.rendered_html.encode()).hexdigest()
        )
        content = frappe.get_doc("File", {"file_url": sa.pdf}).get_content()
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertEqual(sa.pdf_sha256, hashlib.sha256(content).hexdigest())

    def test_countersignature_completes_it(self):
        t = _template(countersign_role="Registrar")
        program = _program([_rule("Agreement", t.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        frappe.set_user(person.user)
        sa_name = req.sign_agreement(row.name, "Test Signer", consent=1)[
            "signed_agreement"
        ]
        self.assertEqual(
            frappe.db.get_value("Person Requirement", row.name, "status"), "Submitted"
        )

        registrar = fx.make_user(roles=("Registrar",))
        frappe.set_user(registrar.name)
        self.assertEqual(req.countersign(sa_name, "School Registrar"), "Complete")
        frappe.set_user("Administrator")
        sa = frappe.get_doc("Signed Agreement", sa_name)
        self.assertEqual(sa.countersigned_by, registrar.name)
        self.assertTrue(sa.final_pdf and sa.final_pdf_sha256)
        self.assertEqual(
            frappe.db.get_value("Person Requirement", row.name, "status"), "Satisfied"
        )
        with self.assertRaises(frappe.ValidationError):
            req.countersign(sa_name, "Again")

    def test_countersign_needs_the_templates_role(self):
        t = _template(countersign_role="Seminary Manager")
        program = _program([_rule("Agreement", t.name)])
        student, person = _student()
        row = _rows(fx.make_enrollment(student, program).name)[0]
        frappe.set_user(person.user)
        sa_name = req.sign_agreement(row.name, "Test Signer", consent=1)[
            "signed_agreement"
        ]
        frappe.set_user(fx.make_user(roles=("Registrar",)).name)
        with self.assertRaises(frappe.PermissionError):
            req.countersign(sa_name, "Registrar")


class TestRenewalAndInstructors(ADR091Case):
    def _terms(self):
        year = frappe.get_doc(
            {
                "doctype": "Academic Year",
                "academic_year_name": fx.uid("AY"),
                "year_start_date": "2093-01-01",
                "year_end_date": "2093-12-31",
            }
        ).insert(ignore_permissions=True)
        terms = []
        for start, end in (("2093-01-10", "2093-05-10"), ("2093-08-10", "2093-12-10")):
            terms.append(
                frappe.get_doc(
                    {
                        "doctype": "Academic Term",
                        "academic_year": year.name,
                        "term_name": fx.uid("T"),
                        "term_start_date": start,
                        "term_end_date": end,
                    }
                ).insert(ignore_permissions=True)
            )
        return year, terms

    def test_every_term_adds_a_row_when_a_new_term_is_current(self):
        year, (t1, t2) = self._terms()
        t = _template()
        program = _program([_rule("Agreement", t.name, renewal="Every Academic Term")])
        student, _person = _student()
        with patch("seminary.seminary.api.current_academic_term", return_value=t1.name):
            pe = fx.make_enrollment(student, program)
            self.assertEqual([r.academic_term for r in _rows(pe.name)], [t1.name])
            req.sweep()
            self.assertEqual(len(_rows(pe.name)), 1)
        with patch("seminary.seminary.api.current_academic_term", return_value=t2.name):
            req.sweep()
        rows = _rows(pe.name)
        self.assertEqual([r.academic_term for r in rows], [t1.name, t2.name])
        self.assertTrue(all(r.academic_year == year.name for r in rows))

    def test_every_year_does_not_renew_within_the_year(self):
        _year, (t1, t2) = self._terms()
        dt = _doc_type()
        program = _program([_rule("Document", dt.name, renewal="Every Academic Year")])
        student, _p = _student()
        with patch("seminary.seminary.api.current_academic_term", return_value=t1.name):
            pe = fx.make_enrollment(student, program)
        with patch("seminary.seminary.api.current_academic_term", return_value=t2.name):
            req.sweep()
        self.assertEqual(len(_rows(pe.name)), 1)

    def test_instructors_follow_seminary_settings(self):
        t = _template(
            body="<p>{{ instructor.instructor_name }} affirms {{ doctrinal_statement.title }}</p>"
        )
        settings = frappe.get_single("Seminary Settings")
        settings.set("instructor_requirements", [])
        settings.save(ignore_permissions=True)
        instructor = fx.make_instructor()
        self.assertEqual(_rows(instructor.name), [])

        settings.append(
            "instructor_requirements",
            _rule("Agreement", t.name, renewal="Every Academic Year"),
        )
        settings.save(ignore_permissions=True)
        req.sweep()
        rows = _rows(instructor.name)
        self.assertEqual(len(rows), 1)

        newcomer = fx.make_instructor()
        self.assertEqual(len(_rows(newcomer.name)), 1)  # on becoming Active

        person = frappe.db.get_value("Instructor", instructor.name, "person")
        frappe.set_user(frappe.db.get_value("Person", person, "user"))
        self.assertIn(rows[0].name, [r["name"] for r in req.my_requirements()["open"]])
        self.assertEqual(
            req.sign_agreement(rows[0].name, "Test Instructor", consent=1)["status"],
            "Satisfied",
        )


class TestApplicantDocuments(ADR091Case):
    def test_application_files_become_person_documents(self):
        from seminary.seminary.doctype.student_applicant.test_student_applicant import (
            make_applicant,
        )

        dt = _doc_type()
        program = _program([_rule("Document", dt.name, ask_on_application=1)])
        self.assertEqual(
            [d["document_type"] for d in req.application_documents(program.name)],
            [dt.name],
        )
        url = _upload_as("Guest")
        frappe.set_user("Administrator")
        applicant = make_applicant(
            program=program.name,
            documents=[{"document_type": dt.name, "file": url}],
        )
        row = applicant.documents[0]
        row.reload()
        self.assertTrue(row.person_document)
        pdoc = frappe.get_doc("Person Document", row.person_document)
        self.assertEqual(
            (pdoc.person, pdoc.status, pdoc.file), (applicant.person, "Submitted", url)
        )
