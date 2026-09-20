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


def _safe_html(value):
    """Sanitise an author-supplied HTML value and mark it safe to emit raw.

    The escape hatch for the autoescaping environment, and the reason turning
    autoescape on does not cost anyone their formatting (p005a A05-7). A
    template that genuinely needs HTML *from the context* -- `{{ doc.body |
    safe_html }}` -- still gets HTML; it is repaired, not dropped, by the same
    `clean_rich` policy p008 F1 applies to stored rich text.

    Without this the only options were escaping everything (breaking such a
    template) or escaping nothing (the finding)."""
    from markupsafe import Markup

    from seminary.seminary.content_safety import clean_rich

    # Reviewed B704: Markup is the point here. `clean_rich` applies the p008 F1
    # allow-list (nh3; no script, no event handlers, safe URL schemes) on this
    # very line, so what is marked safe is the sanitiser's OUTPUT, never the
    # caller's input. Re-escaping it is exactly what this filter exists to undo.
    return Markup(clean_rich(cstr(value)))  # nosec B704


def _build_env(autoescape: bool = False):
    from frappe.utils.jinja import _get_jenv

    env = AuthorTextEnvironment(undefined=StrictUndefined, autoescape=autoescape)
    # Jinja's builtin filters plus Frappe's formatting ones (json, len, int,
    # str, flt). App hook filters are not copied.
    env.filters = _get_jenv().filters.copy()
    env.filters["safe_html"] = _safe_html
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


def get_env(html: bool = False):
    """One environment per request per mode; the template cache lives on it.

    Two modes, because author text feeds two kinds of sink: an HTML body
    (Email, In-App, Print) and a plain-text one (SMS, WhatsApp, Telegram,
    Voice, and every `Data` subject). Escaping the plain-text one would put
    `&amp;` and `&#39;` in a text message, so the mode has to follow the sink
    rather than being global."""
    attr = "author_text_env_html" if html else "author_text_env"
    env = getattr(frappe.local, attr, None)
    if env is None:
        env = _build_env(autoescape=html)
        setattr(frappe.local, attr, env)
    return env


def has_markers(text) -> bool:
    return bool(text) and any(m in text for m in _JINJA_MARKERS)


def render_author_text(template: str, ctx: dict, html: bool = False) -> str:
    """Render author text against `ctx`. Text without Jinja markers is returned
    as-is. Syntax errors, unknown names and refused attributes raise; callers
    decide whether to surface (validation) or fall back (send-time).

    `html=True` autoescapes the *interpolated values* (p005a A05-7). The
    template's own markup is literal text to Jinja and is never escaped, so an
    author's `<b>` survives untouched -- only what comes out of `{{ ... }}`
    is escaped, which is exactly the untrusted half. A context value that is
    meant to be HTML opts back in with `| safe_html`, which sanitises it.

    Defaults to False so a caller that has not decided its sink keeps today's
    behaviour rather than silently escaping a text message."""
    if not template:
        return template or ""
    if not has_markers(template):
        return template
    return get_env(html).from_string(template).render(ctx or {})
