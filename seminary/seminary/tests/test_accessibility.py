# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""102 §3–§5: the portal and public pages against WCAG 2.2 A and AA.

The routes test needs nothing but the files. The page test opens every route in
docs/accessibility/routes.yaml on the running site with axe-core, signed in as a
student, an instructor, a registrar and a partner picked from the site's own records,
and fails on any serious or critical violation. It skips when the site isn't served.

Write docs/accessibility/conformance.json from the same run with
SEMINARY_WRITE_CONFORMANCE=1 (see docs/accessibility/README.md).
"""

import datetime
import os

import frappe
import requests
from frappe.tests import IntegrationTestCase

from seminary.seminary import accessibility as a


def _served(url):
	try:
		return requests.get(url, timeout=10).status_code == 200
	except requests.RequestException:
		return False


def _report(*visits, rules=None):
	return {"rules": rules or {}, "visits": list(visits)}


class TestRoutesListed(IntegrationTestCase):
	def test_every_router_path_is_in_routes_yaml(self):
		missing = a.unlisted_routes()
		self.assertEqual(
			missing, [], "Add these portal routes to docs/accessibility/routes.yaml: " + ", ".join(missing)
		)

	def test_routes_yaml_names_only_router_paths(self):
		spec = a._load("routes.yaml")
		stale = sorted({r["path"] for r in spec["portal"]} - set(a.router_paths()))
		self.assertEqual(
			stale, [], "These routes.yaml paths are no longer in the router: " + ", ".join(stale)
		)

	def test_each_route_is_visited_or_says_why_not(self):
		for r in a._load("routes.yaml")["portal"]:
			with self.subTest(path=r["path"]):
				self.assertTrue(r.get("skip") or r.get("as"), "Give `as` or `skip`.")
				for role in r.get("as") or []:
					self.assertIn(role, a.ROLE_USERS)

	def test_a_missing_sample_is_listed_as_not_visited(self):
		spec = {
			"portal": [
				{"path": "/quiz/:quizID", "as": ["student"], "params": {"quizID": "quiz"}},
				{"path": "/grades", "as": ["student"]},
				{"path": "/mock", "skip": "Not linked."},
			],
			"website": ["/programs"],
		}
		visits, missed = a.plan(spec, found={"student_user": "s@example.test"})
		self.assertEqual(
			[v["path"] for v in visits], ["/seminary/grades", "/programs"], "the quiz has no sample"
		)
		self.assertEqual({m["route"] for m in missed}, {"/quiz/:quizID", "/mock"})

	def test_an_optional_param_without_a_sample_is_dropped(self):
		spec = {"portal": [{"path": "/development-plans/:student?", "as": ["student"]}]}
		visits, _ = a.plan(spec, found={"student_user": "s@example.test"})
		self.assertEqual(visits[0]["path"], "/seminary/development-plans")


RULES = {
	"image-alt": {"tags": ["wcag2a", "wcag111"], "help": ""},
	"html-has-lang": {"tags": ["wcag2a", "wcag311"], "help": ""},
}


class TestConformance(IntegrationTestCase):
	"""§5: how a run and the manual rows become one result per criterion."""

	def _row(self, data, cid):
		return next(r for r in data["criteria"] if r["id"] == cid)

	def _conformance(self, report, manual):
		original = a._manual_rows
		a._manual_rows = lambda: manual
		self.addCleanup(setattr, a, "_manual_rows", original)
		return a.conformance(report, today=datetime.date(2026, 11, 22), version="1.0.0", commit="abc")

	def test_every_wcag_22_a_and_aa_criterion_is_reported(self):
		data = self._conformance(_report(), {})
		self.assertEqual(len(data["criteria"]), 55)
		self.assertNotIn("4.1.1", {r["id"] for r in data["criteria"]})
		self.assertEqual(data["format"], 1)
		self.assertEqual({r["level"] for r in data["criteria"]}, {"A", "AA"})

	def test_automated_criterion_supports_when_axe_passes(self):
		visit = {"key": "student /grades", "violations": [], "passes": ["html-has-lang"]}
		data = self._conformance(_report(visit, rules=RULES), {})
		self.assertEqual(self._row(data, "3.1.1")["result"], a.SUPPORTS)

	def test_unchecked_manual_row_is_partial(self):
		visit = {"key": "student /grades", "violations": [], "passes": ["image-alt"]}
		data = self._conformance(_report(visit, rules=RULES), {"1.1.1": {"id": "1.1.1"}})
		self.assertEqual(self._row(data, "1.1.1")["result"], a.PARTIAL)

	def test_a_checked_row_supports_only_when_axe_passes_too(self):
		manual = {
			"1.1.1": {"id": "1.1.1", "result": a.SUPPORTS, "checked_on": "2026-11-01", "checked_by": "me"}
		}
		passing = {"key": "student /grades", "violations": [], "passes": ["image-alt"]}
		self.assertEqual(
			self._row(self._conformance(_report(passing, rules=RULES), manual), "1.1.1")["result"],
			a.SUPPORTS,
		)
		failing = {
			"key": "student /grades",
			"violations": [{"id": "image-alt", "impact": "critical", "help": "", "count": 1, "nodes": []}],
			"passes": [],
		}
		row = self._row(self._conformance(_report(failing, rules=RULES), manual), "1.1.1")
		self.assertEqual(row["result"], a.PARTIAL)
		self.assertIn("image-alt fails on 1 of 1 pages", row["remarks"])

	def test_a_row_older_than_a_year_counts_as_unchecked(self):
		manual = {"1.1.1": {"id": "1.1.1", "result": a.SUPPORTS, "checked_on": "2025-11-01"}}
		visit = {"key": "student /grades", "violations": [], "passes": ["image-alt"]}
		row = self._row(self._conformance(_report(visit, rules=RULES), manual), "1.1.1")
		self.assertEqual(row["result"], a.PARTIAL)
		self.assertIn("not checked in the last 12 months", row["evidence"])

	def test_does_not_support_and_not_applicable_come_from_the_person(self):
		manual = {
			"1.2.4": {"id": "1.2.4", "result": a.NOT_APPLICABLE, "checked_on": "2026-11-01"},
			"2.2.1": {
				"id": "2.2.1",
				"result": a.DOES_NOT,
				"checked_on": "2026-11-01",
				"remarks": "No extension.",
			},
		}
		data = self._conformance(_report(), manual)
		self.assertEqual(self._row(data, "1.2.4")["result"], a.NOT_APPLICABLE)
		self.assertEqual(self._row(data, "2.2.1")["result"], a.DOES_NOT)
		self.assertEqual(self._row(data, "2.2.1")["remarks"], "No extension.")

	def test_every_manual_row_names_a_known_criterion(self):
		known = {c[0] for c in a.CRITERIA}
		for cid in a._manual_rows():
			self.assertIn(cid, known)
		for cid, *_ in a.CRITERIA:
			if cid not in a.AUTOMATED:
				self.assertIn(cid, a._manual_rows(), f"{cid} needs a row in manual.yaml")


class TestPortalAccessibility(IntegrationTestCase):
	def test_portal_and_public_pages_have_no_serious_violations(self):
		base = a.base_url()
		if not _served(base + "/login"):
			self.skipTest(f"The site is not served at {base}: start the bench to check its pages.")
		visits, missed = a.plan()
		if not any(v["user"] for v in visits):
			self.skipTest("No student, instructor, registrar or partner on this site to sign in as.")
		report = a.check(visits)
		if os.environ.get("SEMINARY_WRITE_CONFORMANCE"):
			print("Wrote", a.write_conformance(report, missed))
		problems = a.blocking(report)
		self.assertEqual(problems, [], "\n".join(problems))
		frappe.logger("seminary").info(f"accessibility: {len(visits)} pages, {len(missed)} not visited")
