"""p008a: live reproductions of the p005a HIGH findings that require a write.
Each row captures before-state, acts as the low-privilege persona, reports, and
RESTORES. Run after p15fixtures.py. Nothing here is imported by the app."""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import USERS, call  # noqa

FX = json.load(open(os.path.join(S, "..", "p007_validation", "fx1.json")))
FX15 = json.load(open(os.path.join(S, "fx15.json")))
USERS["gta"] = FX["GTA_USER"]
USERS["p15sec"] = FX15["USER"]
CS, PE_B, ES_A, ES_A_ROW = FX["CS"], FX["PE_B"], FX["ES_A"], FX["ES_A_row"]
VERDICTS = []


def adm(method, params, http="POST"):
    return call("admin", method, params, http=http)


def gv(doctype, name, field):
    """Read a field. Child doctypes are not reachable via frappe.client.get_value,
    so go through get_list, which accepts a child doctype with parent= set."""
    r = adm(
        "frappe.client.get_list",
        {
            "doctype": doctype,
            "parent": "Course Schedule",
            "filters": json.dumps([["name", "=", name]]),
            "fields": json.dumps(["name", field]),
            "limit_page_length": 1,
        },
        http="GET",
    )
    if r.status_code == 200:
        rows = r.json().get("message") or []
        if rows:
            return rows[0].get(field)
    r = adm(
        "frappe.client.get_value",
        {"doctype": doctype, "filters": json.dumps({"name": name}), "fieldname": field},
    )
    return (r.json().get("message") or {}).get(field) if r.status_code == 200 else None


def sv(doctype, name, field, value):
    return adm(
        "frappe.client.set_value",
        {"doctype": doctype, "name": name, "fieldname": field, "value": value},
    )


def verdict(fid, label, vulnerable, detail):
    VERDICTS.append((fid, vulnerable))
    print(
        f"  {'VULNERABLE' if vulnerable else 'safe      '}  {fid}  {label}\n      {detail}\n"
    )


print("=== A01-11: any logged-in user places any Program Enrollment on leave ===")
before = gv("Program Enrollment", PE_B, "status")
r = call(
    "stuA",
    "seminary.seminary.program_status.place_on_leave",
    {"program_enrollment": PE_B, "reason": "p008a repro"},
)
after = gv("Program Enrollment", PE_B, "status")
verdict(
    "A01-11",
    "stuA place_on_leave(PE_B)",
    r.status_code == 200 and after != before,
    f"HTTP {r.status_code}; status {before!r} -> {after!r}; body {r.text[:120]}",
)
if after != before:
    sv("Program Enrollment", PE_B, "status", before)
    sv("Program Enrollment", PE_B, "pgmenrol_active", 1)
    print(f"      restored status -> {gv('Program Enrollment', PE_B, 'status')!r}\n")

print("=== A01-12: a grader with no stake in the section rewrites its grades ===")
before = gv("Exam Submission", ES_A, "score")
r = call(
    "instr2",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    {
        "submission_name": ES_A,
        "status": "Graded",
        "score": 99,
        "percentage": 99,
        "fudge_points": 0,
        "result": json.dumps([]),
    },
)
after = gv("Exam Submission", ES_A, "score")
verdict(
    "A01-12",
    "instr2 (Instructor, not staff on CS) save_exam_grade(ES_A)",
    r.status_code == 200 and str(after) != str(before),
    f"HTTP {r.status_code}; score {before!r} -> {after!r}; body {r.text[:120]}",
)
if str(after) != str(before):
    call(
        "admin",
        "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
        {
            "submission_name": ES_A,
            "status": "Not Graded",
            "score": before or 0,
            "percentage": 0,
            "fudge_points": 0,
            "result": json.dumps([]),
        },
    )
    print(f"      restored score -> {gv('Exam Submission', ES_A, 'score')!r}\n")

print("=== A01-13: section-tier instructor with a blank default self-promotes ===")
ROW = FX15["ROW"]
before = gv("Course Schedule Instructors", ROW, "instructor_category")
r = call(
    "p15sec",
    "frappe.client.set_value",
    {
        "doctype": "Course Schedule Instructors",
        "name": ROW,
        "fieldname": "instructor_category",
        "value": "Instructor of Record",
    },
)
after = gv("Course Schedule Instructors", ROW, "instructor_category")
verdict(
    "A01-13",
    "p15sec promotes own row Grader -> Instructor of Record",
    r.status_code == 200 and after == "Instructor of Record",
    f"HTTP {r.status_code}; category {before!r} -> {after!r}; body {r.text[:160]}",
)
if after != before:
    sv("Course Schedule Instructors", ROW, "instructor_category", before)
    print(
        f"      restored category -> {gv('Course Schedule Instructors', ROW, 'instructor_category')!r}\n"
    )

print(
    "=== A01-14: scheduler batch as an HTTP endpoint (hourly only; daily NOT run) ==="
)
r = call("stuA", "seminary.tasks.hourly", {})
verdict(
    "A01-14",
    "stuA POST seminary.tasks.hourly",
    r.status_code == 200,
    f"HTTP {r.status_code}; body {r.text[:120]}",
)
print("      (seminary.tasks.daily deliberately NOT executed: it flips Academic Term")
print("       flags app-wide and recomputes all attendance, which would corrupt the")
print("       p006/p007 fixtures. Same decorator, same reachability.)\n")

print("=== summary ===")
for fid, v in VERDICTS:
    print(f"  {fid}: {'REPRODUCED' if v else 'not reproduced'}")
