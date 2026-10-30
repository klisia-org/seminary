import os

import frappe

_BRAND_CSS_PATH = ("seminary", "public", "css", "website_brand.css")
_BRAND_CSS_URL = "/assets/seminary/css/website_brand.css"

# Map each Website Branding colour field to the CSS custom property it feeds.
# Blank fields are skipped so the static fallbacks in website_brand.css apply.
_BRAND_COLOR_VARS = {
    "primary_color": "--brand-primary",
    "secondary_color": "--brand-secondary",
    "tertiary_color": "--brand-tertiary",
    "accent_color": "--brand-accent",
    "background_color": "--brand-bg",
    "text_color": "--brand-text",
}

# The navbar and footer each take their own background, falling back to
# Primary, and get a derived ink so their text stays readable (061a).
_BAR_FIELDS = {"navbar": "navbar_background", "footer": "footer_background"}
_LIGHT_INK = "#ffffff"
_DARK_INK = "#1a2330"


def _luminance(hex_colour):
    """WCAG relative luminance of a #rgb/#rrggbb colour, or None."""
    value = (hex_colour or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        return None
    try:
        channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    except ValueError:
        return None
    r, g, b = (
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    )
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def bar_ink(background, text_colour=None):
    """The ink with the higher contrast on `background`: white, or the
    school's Text colour (near-black when that is blank or too light).
    None when the background can't be read, so the CSS fallback applies."""
    bg = _luminance(background)
    if bg is None:
        return None
    text = _luminance(text_colour)
    dark = text_colour.strip() if text is not None and text < 0.2 else _DARK_INK
    if _contrast(bg, _luminance(dark)) > _contrast(bg, 1.0):
        return dark
    return _LIGHT_INK


def _website_branding():
    """Return the Website Branding singleton, or None if it isn't available
    yet (e.g. mid-install before the doctype has synced)."""
    if not frappe.db.exists("DocType", "Website Branding"):
        return None
    try:
        return frappe.get_cached_doc("Website Branding")
    except Exception:
        return None


def _append_brand_css(context):
    """Add website_brand.css to web_include_css with an mtime-based cache-buster.

    A raw web_include_css path is emitted without a ?v= query (bundled_asset only
    versions *.bundle.* paths), so browsers cache it forever and brand/style
    edits never surface. Appending here (rather than via the hook) also keeps the
    file loading *after* Frappe's website bundle, so our overrides win."""
    try:
        version = str(int(os.path.getmtime(frappe.get_app_path(*_BRAND_CSS_PATH))))
    except OSError:
        version = "1"
    href = f"{_BRAND_CSS_URL}?v={version}"

    existing = context.get("web_include_css") or []
    if not isinstance(existing, list):
        existing = list(existing)
    if not any(str(item).startswith(_BRAND_CSS_URL) for item in existing):
        context["web_include_css"] = existing + [href]


def apply_branding(context):
    """Expose the Website Branding singleton to web templates and inject the
    public site's `--brand-*` CSS custom properties + favicon (ADR 061).

    The custom navbar/footer Web Templates read `branding` (passed through as
    base.html renders them with the full page context); website_brand.css
    consumes the `:root` variables emitted here."""
    _append_brand_css(context)

    branding = _website_branding()
    if not branding:
        return

    context.branding = branding

    if branding.favicon and not context.get("favicon"):
        context.favicon = branding.favicon

    declarations = []
    for field, var in _BRAND_COLOR_VARS.items():
        value = (branding.get(field) or "").strip()
        if value:
            declarations.append(f"{var}: {value};")
    for bar, field in _BAR_FIELDS.items():
        background = (branding.get(field) or "").strip()
        if background:
            declarations.append(f"--brand-{bar}-bg: {background};")
        ink = bar_ink(background or branding.primary_color, branding.text_color)
        if ink:
            declarations.append(f"--brand-{bar}-ink: {ink};")
    if branding.heading_font:
        declarations.append(f'--brand-heading-font: "{branding.heading_font}";')
    if branding.body_font:
        declarations.append(f'--brand-body-font: "{branding.body_font}";')

    if declarations:
        style = "<style>:root{" + "".join(declarations) + "}</style>"
        context["head_html"] = (context.get("head_html") or "") + style


def update_website_context(context):
    apply_branding(context)

    try:
        context.show_student_application = frappe.db.get_single_value(
            "Seminary Settings", "show_student_application_on_login"
        )
    except Exception:
        context.show_student_application = 0

    if context.show_student_application:
        from seminary.seminary.api import get_application_web_form_route

        apply_route = get_application_web_form_route()
        # Inject via head script that runs on login page only
        script = """
        <script>
        document.addEventListener("DOMContentLoaded", function () {
            if (window.location.pathname === "/login") {
                var loginContainer = document.querySelector(".page-card");
                if (loginContainer) {
                    var div = document.createElement("div");
                    div.className = "text-center";
                    div.style.marginTop = "20px";
                    div.innerHTML = '<p>%s</p>' +
                        '<a href="/%s/new" class="btn btn-primary btn-md">%s</a>';
                    loginContainer.appendChild(div);
                }
            }
        });
        </script>
        """ % (
            frappe._("Want to join us?"),
            apply_route,
            frappe._("Apply to be our Student"),
        )

        # Guard against `context["head_html"]` being explicitly None
        # (Builder pages initialise it that way). `setdefault` leaves an
        # existing None value alone, which would TypeError on the +=.
        context["head_html"] = (context.get("head_html") or "") + script
