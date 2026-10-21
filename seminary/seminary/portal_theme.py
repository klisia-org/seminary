# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""The portal theme slot (p017).

An installed app may recolour the portal by registering a `portal_theme` hook: a
function returning

    {
        "light": {"--surface-white": "#ffffff", ...},
        "dark": {"--surface-white": "#0f0f0f", ...},
        "fonts": {"heading": "Poppins", "body": "Inter"},
        "logo": {"placement": "Wide", "size": "Large"},
    }

Seminary renders it into the portal page's <head>. Without such an app nothing is
rendered and the portal looks as it always has.

What the hook may set is fixed here, not by the app: only the variables below, only
colour values, only the self-hosted fonts and the listed logo options. Anything else is
dropped and logged. The hook is a theme, not a way to put arbitrary CSS in the portal.

koinonia has a copy of this module for its donor portal (it does not depend on
seminary). The two must match.
"""

import os
import re

import frappe
from markupsafe import Markup

#: The frappe-ui variables a theme may set (aretenic decisions/068 item 3).
ALLOWED_VARS = frozenset(
    {
        "--portal-brand",
        "--surface-selected",
        "--surface-gray-7",
        "--surface-gray-6",
        "--ink-white",
        "--ink-blue-link",
        "--ink-blue-3",
        "--ink-blue-2",
        "--outline-blue-1",
        "--surface-white",
        "--surface-cards",
        "--surface-modal",
        "--surface-menu-bar",
        "--surface-gray-1",
        "--surface-gray-2",
        "--surface-gray-3",
        "--ink-gray-9",
        "--ink-gray-8",
        "--ink-gray-7",
        "--ink-gray-6",
        "--ink-gray-5",
        "--ink-gray-4",
        "--outline-gray-1",
        "--outline-gray-2",
        "--outline-gray-3",
        "--outline-gray-4",
    }
)

_COLOUR = re.compile(
    r"^(?:#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}"
    r"|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*(?:0|1|0?\.\d+)\s*)?\))$"
)

#: The self-hosted set in brand_fonts.css. Inter is the portal's own font.
FONTS = ("Inter", "Poppins", "Lora", "Source Serif 4")
PLACEMENTS = ("Compact", "Wide", "Wide with name")
SIZES = ("Small", "Medium", "Large")

_FONTS_CSS = ("seminary", "public", "css", "brand_fonts.css")
_FONTS_URL = "/assets/seminary/css/brand_fonts.css"
_FALLBACK_STACK = (
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
)


def get_portal_theme():
    """The theme an installed app supplies, cleaned; None when no app supplies one.

    The last registered hook wins. A hook that fails leaves the portal unthemed rather
    than breaking the page.
    """
    hooks = frappe.get_hooks("portal_theme")
    if not hooks:
        return None
    try:
        raw = frappe.get_attr(hooks[-1])()
    except Exception:
        frappe.log_error(title="Portal theme hook failed")
        return None
    return clean(raw) if raw else None


def clean(raw):
    """Keep only what a theme may set; log what was dropped."""
    dropped = []
    theme = {"light": {}, "dark": {}, "fonts": {}, "logo": {}}

    for mode in ("light", "dark"):
        for name, value in (raw.get(mode) or {}).items():
            value = str(value).strip()
            if name in ALLOWED_VARS and _COLOUR.match(value):
                theme[mode][name] = value
            else:
                dropped.append(f"{mode} {name}: {value}")

    for role in ("heading", "body"):
        font = (raw.get("fonts") or {}).get(role)
        if font in FONTS:
            theme["fonts"][role] = font
        elif font:
            dropped.append(f"font {role}: {font}")

    logo = raw.get("logo") or {}
    for key, allowed in (("placement", PLACEMENTS), ("size", SIZES)):
        value = logo.get(key)
        if value in allowed:
            theme["logo"][key] = value
        elif value:
            dropped.append(f"logo {key}: {value}")

    if dropped:
        frappe.logger("seminary").warning("Portal theme: dropped " + "; ".join(dropped))
    return theme


def render_head(theme):
    """The <link> and <style> for the portal page's <head>; empty without a theme.

    Light values sit under `html:not([data-theme='dark'])` and dark ones under
    `html[data-theme='dark']`. Both outrank frappe-ui's own `:root` and
    `[data-theme=dark]` whatever order the stylesheets load in (the dev server injects
    its CSS last), and a light value never leaks into dark mode.
    """
    if not theme:
        return ""

    blocks = []
    for selector, values in (
        ("html:not([data-theme='dark'])", theme["light"]),
        ("html[data-theme='dark']", theme["dark"]),
    ):
        if values:
            body = "".join(f"{name}:{value};" for name, value in sorted(values.items()))
            blocks.append(f"{selector}{{{body}}}")

    fonts = theme["fonts"]
    if fonts.get("body"):
        blocks.append(f'html body{{font-family:"{fonts["body"]}", {_FALLBACK_STACK};}}')
    if fonts.get("heading"):
        blocks.append(
            f'html :is(h1,h2,h3,h4){{font-family:"{fonts["heading"]}", {_FALLBACK_STACK};}}'
        )

    head = ""
    if any(f != "Inter" for f in fonts.values()):
        head += f'<link rel="stylesheet" href="{_FONTS_URL}?v={_fonts_version()}">'
    if blocks:
        head += f'<style id="portal-theme">{"".join(blocks)}</style>'
    # Every value above passed an allow-list or the colour pattern, so nothing here can
    # close the <style> element (test_only_allowed_values_get_through).
    return Markup(head)  # nosec B704


def boot_logo(theme):
    """How the SPA lays out the logo; None leaves today's compact tile."""
    return dict(theme["logo"]) if theme and theme["logo"] else None


def _fonts_version():
    try:
        return str(int(os.path.getmtime(frappe.get_app_path(*_FONTS_CSS))))
    except OSError:
        return "0"
