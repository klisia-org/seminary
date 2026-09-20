"""
The plugins module provides various plugins to change the default
behaviour some parts of the Seminary app.

A site specify what plugins to use using appropriate entries in the frappe
hooks, written in the `hooks.py`.

This module exposes two plugins: ProfileTab and PageExtension.

The ProfileTab is used to specify any additional tabs to be displayed
on the profile page of the user.

The PageExtension is used to load additinal stylesheets and scripts to
be loaded in a webpage.
"""

import frappe
from urllib.parse import quote
from frappe import _
from frappe.utils import escape_html


class PageExtension:
    """PageExtension is a plugin to inject custom styles and scripts
    into a web page.

    The subclasses should overwrite the `render_header()` and
    `render_footer()` methods to inject whatever styles/scripts into
    the webpage.
    """

    def __init__(self):
        self.context = frappe._dict()

    def set_context(self, context):
        self.context = context

    def render_header(self):
        """Returns the HTML snippet to be included in the head section
        of the web page.

        Typically used to include the stylesheets and javascripts to be
        included in the <head> of the webpage.
        """
        return ""

    def render_footer(self):
        """Returns the HTML snippet to be included in the body tag at
        the end of web page.

        Typically used to include javascripts that need to be executed
        after the page is loaded.
        """
        return ""


class ProfileTab:
    """Base class for profile tabs.

    Every subclass of ProfileTab must implement two methods:
        - get_title()
        - render()
    """

    def __init__(self, user):
        self.user = user

    def get_title(self):
        """Returns the title of the tab.

        Every subclass must implement this.
        """
        raise NotImplementedError()

    def render(self):
        """Renders the contents of the tab as HTML.

        Every subclass must implement this.
        """
        raise NotImplementedError()


class LiveCodeExtension(PageExtension):
    def render_header(self):
        livecode_url = frappe.get_value("Seminary Settings", None, "livecode_url")
        context = {"livecode_url": livecode_url}
        return frappe.render_template(
            "templates/livecode/extension_header.html", context
        )

    def render_footer(self):
        livecode_url = frappe.get_value("Seminary Settings", None, "livecode_url")
        context = {"livecode_url": livecode_url}
        return frappe.render_template(
            "templates/livecode/extension_footer.html", context
        )


def youtube_video_renderer(video_id):
    # `class="youtube-video` was never closed, so the attribute swallowed
    # everything up to the next quote and `allow`/`allowfullscreen` were silently
    # part of the class name. The id is escaped because it comes from a lesson
    # macro, and it is a path segment, not a whole URL (p008 F5).
    video_id = quote(escape_html(video_id), safe="")
    return f"""
    <iframe width="100%" height="400"
        src="https://www.youtube.com/embed/{video_id}"
        title="YouTube video player"
        frameborder="0"
        class="youtube-video"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen>
    </iframe>
    """


def _media_src(src):
    """A quoted, scheme-checked `src` for the media renderers (p008 F5).

    These interpolated `src={quote(src)}` **unquoted**: `quote` leaves `/` and
    `:` alone, so a `javascript:` argument survived it intact, and any character
    it does not escape ended the attribute.
    """
    from seminary.seminary.url_policy import is_safe_url

    if not is_safe_url(src, schemes=("http", "https"), allow_relative=True):
        return ""
    return escape_html(src)


def embed_renderer(details):
    type = details.split("|||")[0]
    src = details.split("|||")[1]
    width = "100%"
    height = "400"

    if type == "pdf":
        width = "75%"
        height = "600"

    # Every attribute quoted, and the src checked rather than interpolated
    # (p008 F5/F7). `src={src}` unquoted ended the attribute at the first space,
    # so a macro argument could add attributes of its own -- `onload=` among
    # them.
    #
    # Scheme check only, NOT `safe_embed_url`: that helper refuses a URL on this
    # site, which is right for an author-pasted external embed but wrong here --
    # the `type == "pdf"` branch above exists precisely to frame a PDF uploaded
    # to this site, and a same-origin refusal would blank every one of them.
    src = _media_src(src)
    if not src:
        return ""

    return f"""
	<iframe width="{width}" height="{height}"
		src="{src}"
		title="Embedded Content"
		frameborder="0"
		style="border-radius: var(--border-radius-lg)"
		allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
		allowfullscreen>
	</iframe>
	"""


def video_renderer(src):
    src = _media_src(src)
    if not src:
        return ""
    return (
        f"<video controls width='100%' controlsList='nodownload'>"
        f'<source src="{src}" type="video/mp4"></video>'
    )


def audio_renderer(src):
    src = _media_src(src)
    if not src:
        return ""
    return (
        f"<audio width='100%' controls controlsList='nodownload'>"
        f'<source src="{src}" type="audio/mp3"></audio>'
    )


def pdf_renderer(src):
    return f"<iframe src='{quote(src)}#toolbar=0' width='100%' height='700px'></iframe>"
