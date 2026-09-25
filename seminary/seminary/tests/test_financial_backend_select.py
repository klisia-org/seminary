# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Choosing the active financial backend when two billing apps are installed
(aretenic decision 049 §1: a school changing ledgers keeps the old app's
history, but only one app is active)."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from seminary.seminary.financial import backend as fb


class _Alpha(fb.NullFinancialBackend):
    pass


class _Beta(fb.NullFinancialBackend):
    pass


_CLASSES = {"alpha.backend.Alpha": _Alpha, "beta.backend.Beta": _Beta}


class TestFinancialBackendSelect(IntegrationTestCase):
    def _with_backends(self, paths):
        real_get_hooks, real_get_attr = frappe.get_hooks, frappe.get_attr

        def get_hooks(hook=None, *args, **kwargs):
            if hook == "seminary_financial_backend":
                return list(paths)
            return real_get_hooks(hook, *args, **kwargs)

        def get_attr(path):
            return _CLASSES.get(path) or real_get_attr(path)

        return (
            patch.object(frappe, "get_hooks", get_hooks),
            patch.object(frappe, "get_attr", get_attr),
        )

    def _resolve(self, paths, setting=None):
        hooks, attrs = self._with_backends(paths)
        with hooks, attrs, patch.object(
            frappe.db, "get_single_value", return_value=setting
        ):
            return fb.get_financial_backend()

    def test_no_backend_is_null(self):
        backend = self._resolve([])
        self.assertIs(type(backend), fb.NullFinancialBackend)

    def test_single_backend_ignores_the_setting(self):
        backend = self._resolve(["alpha.backend.Alpha"], setting="beta")
        self.assertIsInstance(backend, _Alpha)

    def test_setting_picks_among_two(self):
        paths = ["alpha.backend.Alpha", "beta.backend.Beta"]
        self.assertIsInstance(self._resolve(paths, setting="alpha"), _Alpha)
        self.assertIsInstance(self._resolve(paths, setting="beta"), _Beta)

    def test_unset_or_uninstalled_falls_back_to_last(self):
        paths = ["alpha.backend.Alpha", "beta.backend.Beta"]
        self.assertIsInstance(self._resolve(paths, setting=None), _Beta)
        self.assertIsInstance(self._resolve(paths, setting="gamma"), _Beta)

    def test_settings_refuse_an_unknown_app(self):
        hooks, attrs = self._with_backends(["alpha.backend.Alpha", "beta.backend.Beta"])
        settings = frappe.get_single("Seminary Settings")
        settings.financial_backend = "gamma"
        with hooks, attrs:
            self.assertRaises(
                frappe.ValidationError, settings._validate_financial_backend
            )
            settings.financial_backend = "beta"
            settings._validate_financial_backend()
