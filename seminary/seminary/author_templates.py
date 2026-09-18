# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Rendering of author-written personalisation text (p006 F10).

Announcement subject/message/short_message and Communication Template Version
subject/body are written by staff in the browser and carry `{{ recipient.* }}`
style tokens. They are *not* application templates: they get the context the
sender hands them and Jinja's formatting filters, and nothing else.

Frappe's own `render_template(..., restrict_globals=True)` still binds a
`frappe` global with read-only SQL, `get_all` (permission-ignoring) and
`get_doc`, so it is not used here. This environment has no `frappe` object,
no session, no URL helper and no app Jinja hooks; an unknown name raises
instead of rendering to a marker, so `{{ frappe.db.sql(...) }}` fails at
validation and never executes.
"""

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

import frappe
from frappe.model.base_document import BaseDocument
from frappe.utils import cint, cstr, flt

_JINJA_MARKERS = ("{{", "{%")


class AuthorTextEnvironment(SandboxedEnvironment):
    """Sandbox that also refuses Frappe's unsafe attributes and any callable
    reached through a Document in the context (`{{ doc.delete() }}`)."""

    def is_safe_attribute(self, obj, attr, value):
        from frappe.utils.safe_exec import UNSAFE_ATTRIBUTES

        if attr in UNSAFE_ATTRIBUTES:
            return False
        if isinstance(obj, BaseDocument) and callable(value):
            return False
        return super().is_safe_attribute(obj, attr, value)

    def is_safe_callable(self, obj):
        if isinstance(getattr(obj, "__self__", None), BaseDocument):
            return False
        return super().is_safe_callable(obj)


def _build_env():
    from frappe.utils.jinja import _get_jenv

    env = AuthorTextEnvironment(undefined=StrictUndefined, autoescape=False)
    # Jinja's builtin filters plus Frappe's formatting ones (json, len, int,
    # str, flt). App hook filters are not copied.
    env.filters = _get_jenv().filters.copy()
    # Globals: translation and plain helpers only. Deliberately absent:
    # frappe, session, user, get_url, and every safe_exec callable.
    env.globals = {
        "_": frappe._,
        "dict": dict,
        "len": len,
        "range": range,
        "str": cstr,
        "int": cint,
        "flt": flt,
    }
    return env


def get_env():
    """One environment per request; the compiled-template cache lives on it."""
    env = getattr(frappe.local, "author_text_env", None)
    if env is None:
        env = _build_env()
        frappe.local.author_text_env = env
    return env


def has_markers(text) -> bool:
    return bool(text) and any(m in text for m in _JINJA_MARKERS)


def render_author_text(template: str, ctx: dict) -> str:
    """Render author text against `ctx`. Text without Jinja markers is returned
    as-is. Syntax errors, unknown names and refused attributes raise; callers
    decide whether to surface (validation) or fall back (send-time)."""
    if not template:
        return template or ""
    if not has_markers(template):
        return template
    return get_env().from_string(template).render(ctx or {})
