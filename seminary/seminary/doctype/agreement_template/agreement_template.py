# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class AgreementTemplate(Document):
    """The text people sign (ADR 091 §7). The latest `versions` row is the text
    in force; once anyone has signed it, a changed body becomes a new version so
    every Signed Agreement keeps pointing at the words it was made from."""

    def validate(self):
        self._check_jinja()
        self._version()

    def _check_jinja(self):
        from frappe.utils.jinja import get_jenv
        from jinja2 import TemplateSyntaxError

        if ".__" in (self.body or ""):
            frappe.throw(_("The text contains a field name that is not allowed."))
        try:
            get_jenv(restrict_globals=True).parse(self.body or "")
        except TemplateSyntaxError as e:
            frappe.throw(
                _(
                    "A field in the text is not written correctly (line {0}): {1}"
                ).format(e.lineno, e.message)
            )

    def _version(self):
        latest = self.versions[-1] if self.versions else None
        if latest and (latest.body or "") == (self.body or ""):
            self.current_version = latest.version
            return
        signed = latest and frappe.db.exists(
            "Signed Agreement",
            {"agreement_template": self.name, "template_version": latest.version},
        )
        if latest and not signed:
            latest.body = self.body
            latest.published_on = now_datetime()
            latest.published_by = frappe.session.user
        else:
            self.append(
                "versions",
                {
                    "version": (latest.version + 1) if latest else 1,
                    "body": self.body,
                    "published_on": now_datetime(),
                    "published_by": frappe.session.user,
                },
            )
        self.current_version = self.versions[-1].version
