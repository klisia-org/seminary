"""The data behind the public program pages (p021).

The program page, the programs page and anything else that shows them (aretenic's
website widgets) read it from website_data, so these pin what it returns.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from seminary.seminary import website_data
from seminary.seminary.tests.cohort_fixtures import make_program, uid


def _program(published=1, **values):
    doc = make_program()
    doc.update(
        {
            "published": published,
            "enrollment_mode": "Timed",
            "display_enrollment_window": 1,
            "display_cta": 1,
            **values,
        }
    )
    doc.save(ignore_permissions=True)
    return doc


def _term():
    # A Term Admission is named after its term, so each window needs its own.
    name = uid("AT")
    frappe.get_doc(
        {
            "doctype": "Academic Term",
            "name": name,
            "title": name,
            "term_name": name,
            "term_start_date": add_days(today(), 30),
            "term_end_date": add_days(today(), 120),
        }
    ).db_insert()
    return name


def _window(*programs, start=-2, end=10, published=1):
    doc = frappe.get_doc(
        {
            "doctype": "Term Admission",
            "academic_term": _term(),
            "admission_start_date": add_days(today(), start),
            "admission_end_date": add_days(today(), end),
            "published": published,
            "program_details": [{"program": p.name} for p in programs],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


class TestWebsiteData(IntegrationTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_catalogue_holds_published_programs_only(self):
        shown = _program()
        hidden = _program(published=0)
        names = {p.name for p in website_data.programs_catalogue().programs}
        self.assertIn(shown.name, names)
        self.assertNotIn(hidden.name, names)

    def test_a_programs_windows_are_its_own_open_ones(self):
        prog = _program()
        other = _program()
        mine = _window(prog)
        _window(other)
        _window(prog, start=-20, end=-1)  # closed
        _window(prog, published=0)
        windows = website_data.open_admission_windows(prog.name)
        self.assertEqual([w.name for w in windows], [mine.name])
        self.assertEqual(windows[0].status, "open")

    def test_all_windows_carry_the_programs_that_show_them(self):
        shown = _program()
        not_shown = _program(display_enrollment_window=0)
        unpublished = _program(published=0)
        window = _window(shown, not_shown, unpublished)
        by_name = {w.name: w for w in website_data.open_admission_windows()}
        self.assertEqual([p.name for p in by_name[window.name].programs], [shown.name])

    def test_a_window_with_no_program_to_show_is_left_out(self):
        window = _window(_program(display_enrollment_window=0))
        self.assertNotIn(
            window.name, [w.name for w in website_data.open_admission_windows()]
        )

    def test_status_follows_the_dates(self):
        prog = _program()
        _window(prog, start=3, end=10)
        self.assertEqual(
            website_data.open_admission_windows(prog.name)[0].status, "opens_soon"
        )
