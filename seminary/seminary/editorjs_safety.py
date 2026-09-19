# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""Block-level sanitising of EditorJS lesson content (privatedocs p008 F4).

``Course Lesson.content`` / ``instructor_content`` are EditorJS JSON. Frappe's
save-time sanitiser returns anything that parses as JSON unchanged, so until this
module nothing on the server ever looked inside a lesson -- and the lesson view
renders several block types as HTML (p005a A05-10, A05-2 row 4).

The rule of this module is **repair, never reject, and never drop on shape**:

* a lesson written in 2024 must still save in 2026, so nothing here throws;
* an unknown block type, or an unknown key on a known one, is KEPT with any
  markup-bearing string cleaned. Dropping what we do not recognise would silently
  eat the blocks of any tool added after this was written -- and the stored data
  already disagrees with the constants in places (a discussion block stores its
  reference under ``discussion``, not ``discussionID``);
* only two things are removed: a URL whose scheme is not allowed (blanked), and
  an embed that yields no usable URL at all (the block goes, and the author is
  told which).

Plain strings -- docnames, labels, file types -- are never rewritten: only a
string that actually contains markup is cleaned (``content_safety.has_markup``),
which is also what keeps an untouched lesson byte-identical through a save.
"""

import json
import re

import frappe
from frappe import _

from seminary.seminary.content_safety import clean_code, clean_rich, has_markup
from seminary.seminary.url_policy import is_safe_url, safe_embed_url

# data keys that hold a URL, per block type
_URL_KEYS = {
    "image": ("url",),
    "upload": ("file_url",),
    "recordVideo": ("file_url",),
    "embed": ("source", "embed"),
}
_IFRAME_SRC = re.compile(
    r"""<\s*iframe\b[^>]*?\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I
)


def _deep_clean(value, cleaner=clean_rich):
    if isinstance(value, str):
        return cleaner(value)
    if isinstance(value, list):
        return [_deep_clean(v, cleaner) for v in value]
    if isinstance(value, dict):
        return {k: _deep_clean(v, cleaner) for k, v in value.items()}
    return value


def _embed_url(html) -> str:
    """The URL of an iframe block: a bare URL, or the first iframe's src."""
    text = (html or "").strip()
    if not text:
        return ""
    m = _IFRAME_SRC.search(text)
    if m:
        text = next((g for g in m.groups() if g is not None), "")
    elif has_markup(text):
        return ""
    return safe_embed_url(text)


def sanitize_block(block):
    """Return (block, note). ``block`` is None when it has to go; ``note`` says
    what was repaired, or None when nothing was."""
    if not isinstance(block, dict):
        return None, _("not a block")
    btype = block.get("type")
    data = block.get("data")
    if not isinstance(data, dict):
        return block, None
    before = json.dumps(data, sort_keys=True)

    if btype == "iframe":
        url = _embed_url(data.get("html"))
        if not url:
            return None, _("an embed with no usable https:// address on another site")
        data = dict(data, html=url)
    elif btype in ("codeBox", "code"):
        data = dict(_deep_clean(data), code=clean_code(data.get("code")))
    else:
        data = _deep_clean(data)

    note = None
    for key in _URL_KEYS.get(btype, ()):
        if data.get(key) and not is_safe_url(data[key], allow_relative=True):
            data[key] = ""
            note = _("an address that is not a web link was removed")
    if btype == "embed" and not (data.get("embed") and data.get("source")):
        return None, _("an embed with no usable web address")

    if note is None and json.dumps(data, sort_keys=True) != before:
        note = _("markup that cannot be displayed safely was removed")
    block["data"] = data
    return block, note


def sanitize_content(content):
    """Clean one EditorJS JSON string. Returns (content, notes). Content that is
    not EditorJS JSON is returned untouched -- it is not ours to interpret."""
    from seminary.seminary.course_pack.editorjs import load_blocks

    doc = load_blocks(content)
    if doc is None:
        return content, []
    kept, notes = [], []
    for idx, block in enumerate(doc["blocks"], start=1):
        clean, note = sanitize_block(block)
        if note:
            btype = block.get("type") if isinstance(block, dict) else "?"
            notes.append(_("Block {0} ({1}): {2}.").format(idx, btype, note))
        if clean is not None:
            kept.append(clean)
    if not notes:
        return content, []  # untouched lessons stay byte-identical
    doc["blocks"] = kept
    return json.dumps(doc), notes
