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


def load_blocks(content):
    """Parse EditorJS JSON defensively: a dict with a ``blocks`` list, or None.
    Public because lesson sanitising (seminary.seminary.editorjs_safety) needs
    exactly this parser and must not grow a second one."""
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
    data = load_blocks(content)
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
    data = load_blocks(content)
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


# --- Folder references ------------------------------------------------------
#
# A folder block is `{"type": "folder", "data": {"folder_ref": <Course Folder
# docname>, "folder": <display label>}}`. Blocks written before p006 F2 carry
# `folder` (a foldername) alone; the patch `course_folder_scopes` adds
# `folder_ref` to every block it can resolve, and these helpers keep accepting
# the legacy shape so a pack or a lesson that slipped past the patch still works.


def scan_folder_refs(content):
    """Return [{"folder_ref": docname_or_None, "folder": label_or_None}, ...]
    for every folder block in EditorJS content, in document order."""
    refs = []
    data = load_blocks(content)
    if not data:
        return refs
    for block in data["blocks"]:
        if not isinstance(block, dict) or block.get("type") != "folder":
            continue
        bdata = block.get("data")
        if not isinstance(bdata, dict):
            continue
        ref = bdata.get("folder_ref") or None
        label = bdata.get("folder") or None
        if ref or label:
            refs.append({"folder_ref": ref, "folder": label})
    return refs


def rewrite_folder_refs(content, ref_map, labels=None):
    """Return EditorJS content with folder blocks remapped.

    `ref_map` maps the block's current key — its `folder_ref`, or its legacy
    `folder` name when it has no `folder_ref` — to the new Course Folder
    docname. `labels`, when given, maps a new docname to the display label to
    store in `folder`; without it the label is left as it was.
    """
    if not ref_map:
        return content
    data = load_blocks(content)
    if not data:
        return content
    changed = False
    for block in data["blocks"]:
        if not isinstance(block, dict) or block.get("type") != "folder":
            continue
        bdata = block.get("data")
        if not isinstance(bdata, dict):
            continue
        key = bdata.get("folder_ref") or bdata.get("folder")
        if not key or key not in ref_map:
            continue
        new_ref = ref_map[key]
        bdata["folder_ref"] = new_ref
        if labels and new_ref in labels:
            bdata["folder"] = labels[new_ref]
        changed = True
    return json.dumps(data) if changed else content


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
