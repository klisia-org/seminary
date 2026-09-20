"""p008 browser-pass follow-ups: the two errors a Student hits on a lesson page.

Read-only except for save_progress, which writes the caller's own roster row.
Both rows are VULNERABLE (here: broken) before the fix and safe after.

    python3 scripts/p008_validation/repro_student_lesson.py
"""

import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import call  # noqa: E402

COURSE = "Identity in Christ-2026-2027 (FA27)-A"
FOLDER_LESSON = ("3", "2")  # a lesson whose body is NULL (folder fixture)
PLAIN_LESSON = ("1", "1")  # a lesson with a legacy body, for contrast

ROWS = []


def verdict(label, broken, detail=""):
    ROWS.append((label, broken))
    print(f"  {'BROKEN' if broken else 'ok    '}  {label}\n      {detail}\n")


def body(r):
    try:
        return r.json()
    except Exception:
        return {"_text": r.text[:200]}


print("=== get_lesson as an enrolled Student ===")
for label, (ch, ls) in (
    ("folder lesson", FOLDER_LESSON),
    ("plain lesson", PLAIN_LESSON),
):
    r = call(
        "stuA",
        "seminary.seminary.utils.get_lesson",
        {"course": COURSE, "chapter": ch, "lesson": ls},
        http="GET",
    )
    j = body(r)
    verdict(
        f"get_lesson {ch}.{ls} ({label})",
        r.status_code != 200,
        f"HTTP {r.status_code}; "
        + (
            str(j.get("exc_type") or j.get("_text"))[:160]
            if r.status_code != 200
            else f"title={(j.get('message') or {}).get('lesson_title')!r}"
        ),
    )

print("=== save_progress as an enrolled Student ===")
for label, (ch, ls) in (
    ("folder lesson", FOLDER_LESSON),
    ("plain lesson", PLAIN_LESSON),
):
    lesson_name = chapter_name = None
    r = call(
        "stuA",
        "seminary.seminary.utils.get_lesson",
        {"course": COURSE, "chapter": ch, "lesson": ls},
        http="GET",
    )
    if r.status_code == 200:
        msg = body(r).get("message") or {}
        lesson_name, chapter_name = msg.get("name"), msg.get("chapter_name")
    if not lesson_name:
        verdict(
            f"save_progress {ch}.{ls} ({label})",
            True,
            "no lesson name: get_lesson failed",
        )
        continue
    # the SPA sends the chapter DOCNAME here, not the index
    r = call(
        "stuA",
        "seminary.seminary.doctype.course_lesson.course_lesson.save_progress",
        {"lesson": lesson_name, "chapter": chapter_name, "course": COURSE},
    )
    j = body(r)
    verdict(
        f"save_progress {ch}.{ls} ({label})",
        r.status_code != 200,
        f"HTTP {r.status_code}; "
        + (
            str(j.get("exc_type") or j.get("_text"))[:160]
            if r.status_code != 200
            else f"progress={j.get('message')!r}"
        ),
    )

print("=== a Student still may not write the rest of their roster row ===")
r = call(
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Scheduled Course Roster",
        "name": "Identity in Christ-2026-2027 (FA27)-A-26-00001",
        "fieldname": "active",
        "value": 0,
    },
)
verdict(
    "frappe.client.set_value on the roster row is refused",
    r.status_code == 200,
    f"HTTP {r.status_code} (403 expected)",
)

print("=== summary ===")
for label, b in ROWS:
    print(f"  {'BROKEN' if b else 'ok':7} {label}")
