"""p008a G8 (p005a A01-15): what answer material a Student actually receives.
Read-only. VULNERABLE before the fix, safe after."""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import call  # noqa: E402

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
r = call("stuA", "seminary.seminary.utils.get_question_details", {"question": QUESTION})
m = msg(r) or {}
verdict(
    "get_question_details serves explanation_* before the answer (no quiz context)",
    any(k.startswith("explanation_") for k in m),
    f"HTTP {r.status_code}; explanation keys: {[k for k in m if k.startswith('explanation_')]}",
)
r = call(
    "stuA",
    "seminary.seminary.utils.get_all_questions_details",
    {"questions": json.dumps([QQ_ROW])},
)
m = (msg(r) or [{}])[0] if msg(r) else {}
verdict(
    "get_all_questions_details serves explanation_* before the answer",
    any(k.startswith("explanation_") for k in m),
    f"HTTP {r.status_code}; explanation keys: {[k for k in m if k.startswith('explanation_')]}",
)
r = call(
    "stuA",
    "seminary.seminary.doctype.quiz.quiz.check_answer",
    {"question": QUESTION, "type": "User Input", "answers": json.dumps(["guess"])},
)
verdict(
    "check_answer gives a verdict with no quiz context (oracle)",
    r.status_code == 200 and msg(r) is not None,
    f"HTTP {r.status_code}; message: {msg(r)!r}",
)
for dead in (
    "seminary.seminary.doctype.quiz.quiz.get_question_details",
    "seminary.seminary.doctype.exam_activity.exam_activity.get_question_details",
    "seminary.seminary.doctype.question.question.get_question_details",
):
    r = call("stuA", dead, {"question": QUESTION})
    verdict(
        f"dead endpoint still whitelisted: {dead.rsplit('.', 2)[-2]}.get_question_details",
        r.status_code != 403 or "not whitelisted" not in r.text,
        f"HTTP {r.status_code}; {r.text[:90]}",
    )

print("=== Course Folder ===")
r = call(
    "stuA",
    "frappe.client.get_list",
    {
        "doctype": "Course Folder",
        "fields": json.dumps(["name", "scope"]),
        "limit_page_length": 50,
    },
    http="GET",
)
folders = msg(r) or []
inst = [f["name"] for f in folders if f.get("scope") == "Instructor"]
verdict(
    "Student lists Instructor-scope (personal) Course Folders",
    bool(inst),
    f"HTTP {r.status_code}; {len(folders)} folders listed, {len(inst)} Instructor-scope: {inst[:3]}",
)

print("=== summary ===")
for label, v in VERDICTS:
    print(f"  {'VULNERABLE' if v else 'safe':10}  {label}")
