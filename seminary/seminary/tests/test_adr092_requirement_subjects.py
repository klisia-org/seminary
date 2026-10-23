# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""decisions/092: requirements owed for other apps' records, through a hook."""

from unittest.mock import patch

import frappe

from seminary.seminary import requirements as req
from seminary.seminary.tests import cohort_fixtures as fx
from seminary.seminary.tests.test_adr091_requirements import (
    ADR091Case,
    _rows,
    _rule,
    _template,
)

# Note stands in for another app's doctype: installed everywhere, not a subject.
SUBJECT = "Note"
HANDLER = "seminary.seminary.tests.test_adr092_requirement_subjects.SUBJECT_HANDLER"


class _Handler:
    """What another app registers: who owes, which rules, and the label."""

    def __init__(self):
        self.owner = {}
        self.rules_ = []

    def person(self, name):
        return self.owner.get(name)

    def rules(self, name):
        return self.rules_

    def label(self, name):
        return frappe.db.get_value(SUBJECT, name, "title")

    def active(self):
        return list(self.owner)


SUBJECT_HANDLER = _Handler()


def _with_hook(subjects):
    real = frappe.get_hooks

    def get_hooks(hook=None, *args, **kwargs):
        if hook == req.SUBJECT_HOOK:
            return {dt: [path] for dt, path in subjects.items()}
        return real(hook, *args, **kwargs)

    return patch.object(frappe, "get_hooks", side_effect=get_hooks)


class TestHookedSubjects(ADR091Case):
    def setUp(self):
        super().setUp()
        SUBJECT_HANDLER.owner, SUBJECT_HANDLER.rules_ = {}, []
        user = fx.make_user()
        self.person = fx.make_person("Author", user=user.name)
        self.user = user.name
        self.note = frappe.get_doc(
            {"doctype": SUBJECT, "title": fx.uid("Manuscript")}
        ).insert(ignore_permissions=True)
        SUBJECT_HANDLER.owner[self.note.name] = self.person.name

    def test_seminary_subjects_and_missing_doctypes_are_skipped(self):
        with _with_hook(
            {SUBJECT: HANDLER, "Instructor": HANDLER, "No Such Doctype": HANDLER}
        ):
            self.assertEqual(list(req.hooked_subjects()), [SUBJECT])

    def test_unhooked_records_owe_nothing(self):
        SUBJECT_HANDLER.rules_ = [_rule("Agreement", _template().name)]
        self.assertEqual(req.ensure_requirements(SUBJECT, self.note.name), [])

    def test_rows_open_show_their_label_and_sign(self):
        t = _template(
            body="<p>{{ person.full_name }} agrees.[{{ doctrinal_statement.title }}]</p>"
        )
        SUBJECT_HANDLER.rules_ = [_rule("Agreement", t.name, blocking=1)]
        with _with_hook({SUBJECT: HANDLER}):
            created = req.ensure_requirements(SUBJECT, self.note.name)
            self.assertEqual(len(created), 1)
            self.assertEqual(req.ensure_requirements(SUBJECT, self.note.name), [])

            # No doctrinal statement unless the app's agreement_context adds one.
            row = frappe.get_doc("Person Requirement", created[0])
            self.assertIn("[]", req.render_agreement(row)[2])

            frappe.set_user(self.user)
            mine = req.my_requirements()["open"]
            self.assertEqual(
                [(r["name"], r["for"]) for r in mine],
                [(created[0], self.note.title)],
            )
            self.assertEqual(
                req.sign_agreement(created[0], "Test Author", consent=1)["status"],
                "Satisfied",
            )
        frappe.set_user("Administrator")
        self.assertEqual(req.overdue_blocking(SUBJECT, self.note.name), [])

    def test_the_sweep_reaches_a_rule_added_later(self):
        with _with_hook({SUBJECT: HANDLER}):
            req.sweep()
            self.assertEqual(_rows(self.note.name), [])
            SUBJECT_HANDLER.rules_ = [_rule("Agreement", _template().name)]
            req.sweep()
        self.assertEqual(len(_rows(self.note.name)), 1)

    def test_rows_outlive_an_uninstalled_app(self):
        SUBJECT_HANDLER.rules_ = [_rule("Agreement", _template().name)]
        with _with_hook({SUBJECT: HANDLER}):
            (name,) = req.ensure_requirements(SUBJECT, self.note.name)
        row = frappe.get_doc("Person Requirement", name)
        row.instructions = "still here"
        row.save(ignore_permissions=True)
        self.assertEqual(row.person, self.person.name)

        frappe.set_user(self.user)
        self.assertEqual(
            [r["for"] for r in req.my_requirements()["open"]], [self.note.name]
        )
