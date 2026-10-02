import frappe
from frappe.tests import UnitTestCase

from seminary.seminary.gpa import _points_from_code


class TestWithdrawalFailingPoints(UnitTestCase):
    """On a Descriptive scale WF cannot be an interval (F already holds the 0
    threshold), so the scale's wf_gpa / fa_gpa flag decides whether the code
    counts as zero."""

    def scale(self, wf_gpa=0, fa_gpa=0):
        return frappe._dict(
            grscale_type="Descriptive",
            wf_code="WF",
            wf_gpa=wf_gpa,
            fa_code="FA",
            fa_gpa=fa_gpa,
            intervals=[
                frappe._dict(grade_code="A", threshold=4.0),
                frappe._dict(grade_code="F", threshold=0.0),
            ],
        )

    def test_wf_counts_as_zero_when_the_scale_says_so(self):
        pec = frappe._dict(pec_finalgradecode="WF")
        self.assertEqual(_points_from_code(pec, self.scale(wf_gpa=1), 4.0), 0.0)

    def test_wf_stays_out_when_the_scale_says_so(self):
        pec = frappe._dict(pec_finalgradecode="WF")
        self.assertIsNone(_points_from_code(pec, self.scale(wf_gpa=0), 4.0))

    def test_fa_follows_its_own_flag(self):
        pec = frappe._dict(pec_finalgradecode="FA")
        self.assertEqual(_points_from_code(pec, self.scale(fa_gpa=1), 4.0), 0.0)
        self.assertIsNone(_points_from_code(pec, self.scale(fa_gpa=0), 4.0))

    def test_ordinary_codes_still_read_the_interval(self):
        pec = frappe._dict(pec_finalgradecode="A")
        self.assertEqual(_points_from_code(pec, self.scale(wf_gpa=1), 4.0), 4.0)
