# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""p010 Block E: residual access control that needed no new model.

A01-17 is the one that matters. Six endpoints take a caller-supplied target and
gate on nothing. They are harmless on this Frappe-only bench because
`NullFinancialBackend` returns `[]` for everybody -- **which is exactly why they
were missed**, and exactly why a test written against that backend would pass
for the same reason. So the ownership tests here install a stub backend that
actually returns rows.
"""

import json
import pathlib

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.tests.test_p006_api import _make_user


class _StubBackend:
    """Only the two methods the ownership check touches. Stands in for the
    oikonomos bridge: without it, "refuse everything" and "refuse the right
    things" are indistinguishable."""

    MINE = "SINV-MINE-0001"
    THEIRS = "SINV-THEIRS-0001"

    def student_invoices(self, student=None):
        return [{"name": self.MINE, "grand_total": 100}]

    def invoice_payment_url(self, invoice_name):
        return {"url": "https://gateway.test/%s" % invoice_name}


class TestP010FinancialTargets(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = _make_user("Student", "p010fin")
        cls.chair = _make_user("Program Chair", "p010chair")

    def setUp(self):
        frappe.set_user("Administrator")
        self._real = None

    def tearDown(self):
        frappe.set_user("Administrator")
        if self._real is not None:
            from seminary.seminary.financial import backend

            backend.get_financial_backend = self._real

    def _install_stub(self):
        from seminary.seminary.financial import backend

        self._real = backend.get_financial_backend
        backend.get_financial_backend = lambda: _StubBackend()

    # -------------------------------------------------- student-keyed targets

    def test_student_invoices_refuses_another_student(self):
        from seminary.seminary import api

        other = frappe.db.get_value("Student", {}, "name") or "STU-00001"
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            api.get_student_invoices(other)

    def test_scholarship_reads_refuse_another_student(self):
        from seminary.seminary import scholarship

        other = frappe.db.get_value("Student", {}, "name") or "STU-00001"
        frappe.set_user(self.student)
        for fn in (
            scholarship.get_student_scholarship,
            scholarship.get_available_scholarships,
        ):
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(frappe.PermissionError):
                    fn(other)

    def test_applying_for_a_scholarship_refuses_another_enrollment(self):
        from seminary.seminary import scholarship

        other = frappe.db.get_value("Program Enrollment", {}, "name") or "PE-0001"
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            scholarship.apply_for_scholarship(other, "Some Scholarship")

    def test_staff_still_reach_a_students_record(self):
        """The registrar looking at a student's fees is the workflow this gate
        must not break."""
        from seminary.seminary import api

        other = frappe.db.get_value("Student", {}, "name") or "STU-00001"
        frappe.set_user(self.chair)
        try:
            api.get_student_invoices(other)
        except frappe.PermissionError as exc:
            self.fail("Program Chair refused: %s" % exc)

    # -------------------------------------------------- invoice-keyed targets

    def test_a_foreign_invoice_is_refused_with_a_backend_that_returns_rows(self):
        from seminary.seminary import api

        self._install_stub()
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            api.get_invoice_payment_url(_StubBackend.THEIRS)

    def test_my_own_invoice_still_pays(self):
        """The half a stub backend exists to prove: with `NullFinancialBackend`
        every name is refused, so "refuses a stranger's invoice" would pass on a
        gate that refused everything."""
        from seminary.seminary import api

        self._install_stub()
        frappe.set_user(self.student)
        result = api.get_invoice_payment_url(_StubBackend.MINE)
        self.assertIn(_StubBackend.MINE, result["url"])

    def test_a_partial_payment_cannot_smuggle_a_foreign_invoice(self):
        from seminary.seminary import api

        self._install_stub()
        frappe.set_user(self.student)
        with self.assertRaises(frappe.PermissionError):
            api.get_student_partial_balance_payment_url(
                amount=10, invoices=json.dumps([_StubBackend.MINE, _StubBackend.THEIRS])
            )


class TestP010PlagiarismHookPair(IntegrationTestCase):
    def test_the_hook_takes_ptype(self):
        """It was `(doc, user=None, permission_type=None)`. Frappe passes
        `ptype`, and `frappe.call` drops what the function does not declare, so
        the hook never saw it and could not tell a read from a delete."""
        import inspect

        from seminary.seminary.plagiarism import permissions

        args = list(inspect.signature(permissions.has_permission).parameters)
        self.assertEqual(args[:3], ["doc", "ptype", "user"])

    def test_the_registration_is_paired(self):
        """The only unpaired registration of the 41: `has_permission` applies
        per document, so without a query condition the second gate covered
        opening a result and not listing them."""
        self.assertIn(
            "Plagiarism Check Result",
            frappe.get_hooks("permission_query_conditions") or {},
        )
        self.assertIn(
            "Plagiarism Check Result", frappe.get_hooks("has_permission") or {}
        )

    def test_a_non_staff_list_is_closed_not_open(self):
        """`None` would read as *no restriction* -- the A01-20 fail-open shape."""
        from seminary.seminary.plagiarism import permissions

        student = _make_user("Student", "p010plag")
        self.assertEqual(permissions.get_permission_query_conditions(student), "1 = 0")


class TestP010PermlevelGaps(IntegrationTestCase):
    """A08-7: configuration that looked done and was not."""

    def _doctype_json(self, folder):
        return json.loads(
            pathlib.Path(
                frappe.get_app_path(
                    "seminary", "seminary", "doctype", folder, folder + ".json"
                )
            ).read_text(encoding="utf-8")
        )

    def test_the_roster_grade_fields_moved(self):
        """The doctype p005 A01-1 named explicitly for
        `frappe.client.set_value(..., {"fscore": 100})` had no permlevel-1 field
        and no permlevel-1 row, while twelve others got them. Safe only because
        Student lost `write` altogether -- one DocPerm edit from live again."""
        doc = self._doctype_json("scheduled_course_roster")
        moved = {f["fieldname"] for f in doc["fields"] if f.get("permlevel")}
        self.assertEqual(moved, {"fscore", "fgrade", "fgradepass"})
        roles = {p["role"] for p in doc["permissions"] if p.get("permlevel")}
        self.assertEqual(
            roles,
            {"Instructor", "Program Chair", "Seminary Manager", "System Manager"},
        )
        self.assertNotIn("Student", roles)

    def test_the_section_fields_moved(self):
        doc = self._doctype_json("course_schedule")
        moved = {f["fieldname"] for f in doc["fields"] if f.get("permlevel")}
        self.assertIn("published", moved)
        self.assertIn("web_meeting", moved)
        self.assertIn("calendar_token", moved)

    def test_no_doctype_carries_a_permlevel_row_with_no_permlevel_field(self):
        """Dead configuration, and evidence the p007 F3 sweep was done by hand
        (`Graduation Requirement Item` was the one).

        **A child table's permlevel fields resolve against the parent's rows**,
        so the sweep has to follow `Table` options before calling a row dead.
        Written without that, this test flagged `Exam Activity` -- whose
        permlevel-1 rows p008a G8 added on purpose, to cover
        `Exam Question.standard_comments`, the exam's model answer. Deleting
        them would have re-opened that leak.
        """
        root = pathlib.Path(frappe.get_app_path("seminary"))
        docs = {}
        for path in root.rglob("doctype/*/*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # nosec B112 -- a sweep skips what it cannot parse
                continue
            if (
                isinstance(doc, dict)
                and doc.get("doctype") == "DocType"
                and doc.get("name")
            ):
                docs[doc["name"]] = (path.name, doc)

        def permlevel_fields(doc, seen=()):
            found = [f for f in doc.get("fields") or [] if f.get("permlevel")]
            for field in doc.get("fields") or []:
                if field.get("fieldtype") not in ("Table", "Table MultiSelect"):
                    continue
                child = field.get("options")
                if not child or child in seen or child not in docs:
                    continue
                found += permlevel_fields(docs[child][1], seen + (child,))
            return found

        dead = [
            name
            for name, doc in docs.values()
            if [
                p
                for p in doc.get("permissions") or []
                if isinstance(p, dict) and p.get("permlevel")
            ]
            and not permlevel_fields(doc)
        ]
        self.assertEqual(dead, [], f"permlevel rows with no permlevel fields: {dead}")


class TestP010StudentShare(IntegrationTestCase):
    def test_no_student_docperm_grants_share(self):
        """A `DocShare` ORs past every `permission_query_conditions` hook
        (`frappe/model/db_query.py:1084-1085`), and the share list is fetched
        whenever a doctype has an `if_owner` row -- now true for all four
        submissions and Withdrawal Request. 50 doctypes let a Student mint one;
        no `frappe.share.add` exists in app code, so this costs nothing."""
        root = pathlib.Path(frappe.get_app_path("seminary"))
        offenders = []
        for path in root.rglob("doctype/*/*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # nosec B112 -- a sweep skips what it cannot parse
                continue
            if not isinstance(doc, dict):
                continue
            for row in doc.get("permissions") or []:
                if (
                    isinstance(row, dict)
                    and row.get("role") == "Student"
                    and row.get("share")
                ):
                    offenders.append(path.name)
        self.assertEqual(offenders, [], f"Student may still share: {offenders}")


class TestP010DirectoryReads(IntegrationTestCase):
    def test_the_internal_roster_projection_is_staff_only(self):
        """`get_unit_roster`'s default `public=False` returns bios and photos
        **including** people flagged `Person.block_from_web` -- a flag the
        school set to keep somebody off the directory, which the endpoint
        ignored (p005a A01-23)."""
        body = pathlib.Path(
            frappe.get_app_path("seminary", "seminary", "faculty.py")
        ).read_text(encoding="utf-8")
        self.assertIn(
            'if not (guards.is_school_role() or guards.instructor_tier() == "record"):',
            body,
        )

    def test_the_website_team_page_still_gets_its_rows(self):
        """`our_team.py` already passes `public=True`, so the coercion is a
        no-op there. A fix that blanked the public team page would be worse
        than the finding."""
        body = pathlib.Path(
            frappe.get_app_path("seminary", "www", "our_team.py")
        ).read_text(encoding="utf-8")
        self.assertIn("get_unit_roster(u.name, public=True)", body)

    def test_the_desk_pickers_refuse_a_student(self):
        from seminary.seminary import faculty

        student = _make_user("Student", "p010dir")
        frappe.set_user(student)
        try:
            for fn in (faculty.instructors_in_unit, faculty.capability_holders):
                with self.subTest(fn=fn.__name__):
                    with self.assertRaises(frappe.PermissionError):
                        fn("Instructor", "", "name", 0, 20, {"unit": "X"})
        finally:
            frappe.set_user("Administrator")
