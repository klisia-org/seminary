"""Pure helpers to scan and rewrite the cross-references embedded in lesson and
activity content. Two concerns:

* **Activity references** (docnames of Quiz/Exam/Assignment/Discussion/Folder)
  live structurally — in EditorJS `content` blocks and in legacy `body`
  `{{ Tool('id') }}` macros (the grammar `LessonForm.vue::convertToJSON` parses).
* **Media URLs** — both on-disk (`/files/...`, `/private/files/...`) and
  object-storage-backed (`/api/method/seminary.storage.api.download_file?key=...`)
  — can appear anywhere: in EditorJS upload/image blocks, body macros, and inside
  Text Editor HTML (question text, explanations, prompts). These are handled with
  a generic URL scan/replace, which is simpler and catches embedded images in
  rich text too.

Dependency-free (no frappe) so it unit-tests in isolation.
"""

import json
import re

from .constants import ACTIVITY_BLOCKS

# Local file URLs. Frappe stores filenames with literal spaces (e.g.
# "/files/My Diagram.png"), so we allow spaces and stop only at the delimiters
# that always bound a URL in our content: quotes (HTML attrs / JSON values),
# angle brackets (HTML), close-paren (markdown links) and newlines.
_DISK_URL = r"/(?:private/)?files/[^\"'<>)\r\n]+"

# Object-storage URLs (privatedocs/p004). These MUST be scanned too: a lesson
# video offloaded to object storage would otherwise be invisible here, and a
# Course Pack would export successfully while silently omitting the media — the
# pack imports with broken playback and no error anywhere.
#
# The endpoint path is written out rather than imported from
# `seminary.storage.backend.URL_PREFIX`, to keep this module frappe-free (it is
# unit-tested in isolation). That is safe from drift because the path is frozen by
# construction: it is embedded in the `file_url` of every offloaded File row ever
# written, so renaming it would break existing databases and can never happen.
# Keys are hex and slashes only, so no space allowance is needed.
_OFFLOAD_URL = (
    r"/api/method/seminary\.storage\.api\.download_file\?key=media/[A-Za-z0-9/._-]+"
)

_URL_RE = re.compile(f"{_DISK_URL}|{_OFFLOAD_URL}")


def scan_urls(text):
    """Return the set of local file URLs referenced anywhere in `text`."""
    if not text or not isinstance(text, str):
        return set()
    return set(_URL_RE.findall(text))


def rewrite_urls(text, url_map):
    """Replace every old->new URL from `url_map` in `text` (literal substring
    replacement, longest-first so no prefix clobbers a longer match)."""
    if not text or not isinstance(text, str) or not url_map:
        return text
    for old in sorted(url_map, key=len, reverse=True):
        if old in text:
            text = text.replace(old, url_map[old])
    return text


# --- Activity references in EditorJS JSON ------------------------------------


def _load(content):
    if not content:
        return None
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("blocks"), list):
        return None
    return data


def scan_content_refs(content):
    """Return [(doctype, docname), ...] for activity blocks in EditorJS content."""
    refs = []
    data = _load(content)
    if not data:
        return refs
    for block in data["blocks"]:
        if not isinstance(block, dict):
            continue
        spec = ACTIVITY_BLOCKS.get(block.get("type"))
        if not spec:
            continue
        field, doctype = spec
        value = (block.get("data") or {}).get(field)
        if value:
            refs.append((doctype, value))
    return refs


def rewrite_content_refs(content, ref_map):
    """Return EditorJS content with activity-block refs remapped (old->new name)."""
    data = _load(content)
    if not data:
        return content
    for block in data["blocks"]:
        if not isinstance(block, dict):
            continue
        spec = ACTIVITY_BLOCKS.get(block.get("type"))
        if not spec:
            continue
        field, _doctype = spec
        bdata = block.get("data")
        if isinstance(bdata, dict) and bdata.get(field) in ref_map:
            bdata[field] = ref_map[bdata[field]]
    return json.dumps(data)


# --- Activity references in legacy `body` macros -----------------------------

_BODY_ACTIVITY_MACROS = {
    "Quiz": "Quiz",
    "Exam": "Exam Activity",
    "DiscussionActivity": "Discussion Activity",
    "Folder": "Course Folder",
}


def _macro_re(tool):
    # {{ Tool("arg") }} / {{ Tool('arg') }}
    return re.compile(r"(\{\{\s*%s\(\s*[\"'])([^\"']+)([\"']\s*\)\s*\}\})" % tool)


def scan_body_refs(body):
    """Return [(doctype, docname), ...] for activity macros in legacy body."""
    refs = []
    if not body:
        return refs
    for tool, doctype in _BODY_ACTIVITY_MACROS.items():
        for m in _macro_re(tool).finditer(body):
            refs.append((doctype, m.group(2)))
    return refs


def rewrite_body_refs(body, ref_map):
    """Return legacy body with activity-macro ids remapped (old->new name)."""
    if not body:
        return body

    def repl(m):
        return f"{m.group(1)}{ref_map.get(m.group(2), m.group(2))}{m.group(3)}"

    for tool in _BODY_ACTIVITY_MACROS:
        body = _macro_re(tool).sub(repl, body)
    return body
