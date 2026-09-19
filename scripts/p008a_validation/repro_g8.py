"""p008a G8 (p005a A01-15): what answer material a Student actually receives.
Read-only. VULNERABLE before the fix, safe after."""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import USERS, call  # noqa: E402

FX = json.load(open(os.path.join(S, "..", "p007_validation", "fx1.json")))
EA, AA, QUIZ = FX["EA"], FX["AA"], FX["QUIZ"]
QUESTION, QQ_ROW = FX["Q_USER_INPUT"], FX["QQ_ROW"]
VERDICTS = []


def verdict(label, vulnerable, detail=""):
    VERDICTS.append((label, vulnerable))
    print(
        f"  {'VULNERABLE' if vulnerable else 'safe      '}  {label}\n      {detail}\n"
    )


def msg(r):
    try:
        return r.json().get("message")
    except Exception:
        return None


print("=== fields served to a Student through frappe.client ===")
# Frappe blanks a permlevel-restricted value but as_dict still emits the key as
# None, so these rows test the VALUE. The fixtures are empty, so seed a marker
# as admin first and restore it afterwards.
MARK = "P008A-SECRET-MARKER"
ea_doc = (
    msg(
        call(
            "admin",
            "frappe.client.get",
            {"doctype": "Exam Activity", "name": EA},
            http="GET",
        )
    )
    or {}
)
ea_rows = ea_doc.get("questions") or []
# standard_comments is fetch_from question.explanation, so a marker written on
# the child row is overwritten on the next parent save. Seed the SOURCE (the Open
# Question's model answer) and re-save the exam so it is fetched -- which is
# also exactly how the real leak travelled.
oq = ea_rows[0]["question"] if ea_rows else None
oq_before = None
if oq:
    oq_before = (
        msg(
            call(
                "admin",
                "frappe.client.get_value",
                {
                    "doctype": "Open Question",
                    "filters": json.dumps({"name": oq}),
                    "fieldname": "explanation",
                },
            )
        )
        or {}
    ).get("explanation")
    call(
        "admin",
        "frappe.client.set_value",
        {
            "doctype": "Open Question",
            "name": oq,
            "fieldname": "explanation",
            "value": MARK,
        },
    )
    call(
        "admin",
        "frappe.client.set_value",
        {
            "doctype": "Exam Activity",
            "name": EA,
            "fieldname": "title",
            "value": ea_doc.get("title"),
        },
    )
aa_before = (
    msg(
        call(
            "admin",
            "frappe.client.get",
            {"doctype": "Assignment Activity", "name": AA},
            http="GET",
        )
    )
    or {}
)
call(
    "admin",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Activity",
        "name": AA,
        "fieldname": json.dumps({"answer": MARK, "show_answer": 1}),
    },
)

r = call(
    "stuA", "frappe.client.get", {"doctype": "Exam Activity", "name": EA}, http="GET"
)
rows = (msg(r) or {}).get("questions") or []
verdict(
    "Exam Question.standard_comments (fetch_from Open Question.explanation)",
    any(q.get("standard_comments") for q in rows),
    f"HTTP {r.status_code}; {len(rows)} child rows; values: {[q.get('standard_comments') for q in rows]}",
)
r = call(
    "instr", "frappe.client.get", {"doctype": "Exam Activity", "name": EA}, http="GET"
)
irows = (msg(r) or {}).get("questions") or []
print(
    f"      (instructor still reads it: {[q.get('standard_comments') for q in irows]})\n"
)

r = call(
    "stuA",
    "frappe.client.get",
    {"doctype": "Assignment Activity", "name": AA},
    http="GET",
)
m = msg(r) or {}
verdict(
    "Assignment Activity.answer / show_answer",
    bool(m.get("answer")) or m.get("show_answer") not in (None, 0),
    f"HTTP {r.status_code}; answer={m.get('answer')!r}; show_answer={m.get('show_answer')!r}",
)
r = call(
    "instr",
    "frappe.client.get",
    {"doctype": "Assignment Activity", "name": AA},
    http="GET",
)
im = msg(r) or {}
print(f"      (instructor still reads it: answer={im.get('answer')!r})\n")
r = call(
    "stuA",
    "frappe.client.get_list",
    {
        "doctype": "Assignment Activity",
        "fields": json.dumps(["name", "answer"]),
        "limit_page_length": 50,
    },
    http="GET",
)
lst = msg(r) if r.status_code == 200 else None
verdict(
    "Assignment Activity.answer through get_list(fields=[answer])",
    bool(lst) and any(x.get("answer") for x in lst),
    f"HTTP {r.status_code}; {r.text[:100]}",
)

# restore
if oq:
    call(
        "admin",
        "frappe.client.set_value",
        {
            "doctype": "Open Question",
            "name": oq,
            "fieldname": "explanation",
            "value": oq_before or "",
        },
    )
    call(
        "admin",
        "frappe.client.set_value",
        {
            "doctype": "Exam Activity",
            "name": EA,
            "fieldname": "title",
            "value": ea_doc.get("title"),
        },
    )
call(
    "admin",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Activity",
        "name": AA,
        "fieldname": json.dumps(
            {
                "answer": aa_before.get("answer") or "",
                "show_answer": aa_before.get("show_answer") or 0,
            }
        ),
    },
)

r = call(
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Open Question", "limit_page_length": 5},
    http="GET",
)
verdict(
    "Open Question readable by Student",
    r.status_code == 200 and bool(msg(r)),
    f"HTTP {r.status_code}; rows: {len(msg(r) or [])}",
)

print("=== quiz endpoints ===")
FX15 = json.load(open(os.path.join(S, "fx15.json")))
USERS["stuX"] = FX15["UNENROLLED_USER"]  # a Student NOT enrolled in the quiz's course
D = "seminary.seminary.utils.get_question_details"
DA = "seminary.seminary.utils.get_all_questions_details"
CA = "seminary.seminary.doctype.quiz.quiz.check_answer"
GUESS = {"question": QUESTION, "type": "User Input", "answers": json.dumps(["guess"])}


def expl(d):
    return [k for k in (d or {}) if k.startswith("explanation_")]


def set_show_answers(v):
    call(
        "admin",
        "frappe.client.set_value",
        {"doctype": "Quiz", "name": QUIZ, "fieldname": "show_answers", "value": v},
    )


# The fixture quiz has Show Answers ON, where explanations and verdicts travel by
# the instructor's choice. The leak is what happens when it is OFF.
set_show_answers(0)
r = call("stuA", D, {"question": QUESTION, "quiz": QUIZ})
verdict(
    "show_answers=0: get_question_details serves explanation_* pre-answer",
    bool(expl(msg(r))),
    f"HTTP {r.status_code}; {expl(msg(r))}",
)
r = call("stuA", DA, {"questions": json.dumps([QQ_ROW])})
row = (msg(r) or [{}])[0] if msg(r) else {}
verdict(
    "show_answers=0: get_all_questions_details serves explanation_* pre-answer",
    bool(expl(row)),
    f"HTTP {r.status_code}; {expl(row)}",
)
r = call("stuA", CA, dict(GUESS, quiz=QUIZ))
verdict(
    "show_answers=0: check_answer gives a verdict (oracle before the one attempt)",
    r.status_code == 200 and msg(r) is not None,
    f"HTTP {r.status_code}; {msg(r)!r}",
)
set_show_answers(1)

r = call("stuA", CA, GUESS)
verdict(
    "check_answer gives a verdict with no quiz context",
    r.status_code == 200 and msg(r) is not None,
    f"HTTP {r.status_code}; {msg(r)!r}",
)
for label, method, params in (
    ("get_question_details", D, {"question": QUESTION}),
    ("get_all_questions_details", DA, {"questions": json.dumps([QQ_ROW])}),
    ("check_answer", CA, dict(GUESS, quiz=QUIZ)),
):
    r = call("stuX", method, params)
    verdict(
        f"a Student NOT enrolled in the quiz's course reaches {label}",
        r.status_code == 200,
        f"HTTP {r.status_code}; {r.text[:80]}",
    )

# positive: with Show Answers ON the feature still works for an enrolled student
r = call("stuA", D, {"question": QUESTION, "quiz": QUIZ})
r2 = call("stuA", CA, dict(GUESS, quiz=QUIZ))
print(
    f"      (show_answers=1, enrolled: explanations {len(expl(msg(r)))}/4, "
    f"check_answer verdict {msg(r2)!r} -- the feature survives)\n"
)

for dead in (
    "seminary.seminary.doctype.quiz.quiz.get_question_details",
    "seminary.seminary.doctype.exam_activity.exam_activity.get_question_details",
    "seminary.seminary.doctype.question.question.get_question_details",
):
    r = call("instr", dead, {"question": QUESTION})
    verdict(
        f"dead endpoint still callable: {dead.rsplit('.', 2)[-2]}.get_question_details",
        r.status_code == 200,
        f"HTTP {r.status_code} (403 = not whitelisted, 417 = deleted)",
    )

print("=== Course Folder ===")
# Per-document read already followed course_folder.user_may_read (the controller
# override). The leak was the LIST, which applied the DocPerm alone. Note that an
# Instructor-scope folder is legitimately readable when its instructor teaches a
# section the student is on -- so the verdict is "listed but not openable", not
# "lists Instructor-scope folders".
all_folders = [
    f["name"]
    for f in (
        msg(
            call(
                "admin",
                "frappe.client.get_list",
                {"doctype": "Course Folder", "limit_page_length": 500},
                http="GET",
            )
        )
        or []
    )
]
for who in ("stuA", "stuX"):
    listed = {
        f["name"]
        for f in (
            msg(
                call(
                    who,
                    "frappe.client.get_list",
                    {"doctype": "Course Folder", "limit_page_length": 500},
                    http="GET",
                )
            )
            or []
        )
    }
    readable = {
        n
        for n in all_folders
        if call(
            who,
            "frappe.client.get",
            {"doctype": "Course Folder", "name": n},
            http="GET",
        ).status_code
        == 200
    }
    verdict(
        f"{who} lists Course Folders that a per-document read denies",
        bool(listed - readable),
        f"listed {len(listed)}, openable {len(readable)}; over-shown {sorted(listed - readable)}; "
        f"under-shown {sorted(readable - listed)}",
    )

print("=== summary ===")
for label, v in VERDICTS:
    print(f"  {'VULNERABLE' if v else 'safe':10}  {label}")
