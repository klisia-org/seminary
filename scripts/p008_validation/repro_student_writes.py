"""p008 student-path sweep: student endpoints that p007's DocPerm rewrite closed.

`save_progress` was the first of these (see repro_student_lesson.py). This runs
the rest of the candidates that scripts/p008a_validation/sweep_student_writes.py
turned up, as a real enrolled student over HTTP.

Read-mostly: the discussion rows create a topic on a lesson the fixture student
is enrolled in, which the lesson page would create anyway.

    ../../env/bin/python scripts/p008_validation/repro_student_writes.py
"""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import call  # noqa: E402

COURSE = "Identity in Christ-2026-2027 (FA27)-A"
ROWS = []


def verdict(label, broken, detail=""):
    ROWS.append((label, broken))
    print(f"  {'BROKEN' if broken else 'ok    '}  {label}\n      {detail}\n")


def body(r):
    try:
        return r.json()
    except Exception:
        return {"_text": r.text[:200]}


def exc(r):
    j = body(r)
    return str(j.get("exc_type") or j.get("_text"))[:120]


# The lesson the fixture student can open, to hang a discussion thread on.
r = call(
    "stuA",
    "seminary.seminary.utils.get_lesson",
    {"course": COURSE, "chapter": "1", "lesson": "1"},
    http="GET",
)
LESSON = (body(r).get("message") or {}).get("name")
print(f"=== lesson discussions (Course Lesson {LESSON}) ===")

r = call(
    "stuA",
    "seminary.seminary.utils.get_discussion_topics",
    {"doctype": "Course Lesson", "docname": LESSON, "single_thread": 1},
    http="GET",
)
topic = body(r).get("message") or {}
verdict(
    "get_discussion_topics(single_thread=1) opens the lesson thread",
    r.status_code != 200,
    f"HTTP {r.status_code}; {exc(r) if r.status_code != 200 else topic.get('name')}",
)

topic_name = topic.get("name") if isinstance(topic, dict) else None
if topic_name:
    r = call(
        "stuA",
        "seminary.seminary.utils.add_discussion_reply",
        {
            "reply": "<p>p008 sweep</p>",
            "topic": topic_name,
            "reference_doctype": "Course Lesson",
            "reference_docname": LESSON,
            "single_thread": 1,
            "new_topic_title": "",
        },
    )
    verdict(
        "add_discussion_reply posts to it",
        r.status_code != 200,
        f"HTTP {r.status_code}; {exc(r) if r.status_code != 200 else 'posted'}",
    )
else:
    verdict("add_discussion_reply posts to it", True, "no topic to reply to")

# start_recommendation_letter is the third of these -- it submitted a
# Recommendation Letter, which a Student holds no submit on -- but a fake
# enrollment is refused before the letter is ever built, so there is nothing to
# observe from here. It is pinned in
# seminary/seminary/tests/test_p008_student_lesson.py instead.

print("=== summary ===")
for label, b in ROWS:
    print(f"  {'BROKEN' if b else 'ok':7} {label}")
