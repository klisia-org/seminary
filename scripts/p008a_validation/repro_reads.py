"""p008a: read-only reproductions of the p005a findings. Changes nothing."""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
sys.path.insert(0, os.path.join(S, "..", "p007_validation"))
from p0check import USERS, call  # noqa

FX = json.load(open(os.path.join(S, "..", "p007_validation", "fx1.json")))
USERS["gta"] = FX["GTA_USER"]
USERS["instr3"] = FX["U3"]
USERS["instrU"] = FX["U_USER"]
CS, CS_B, QUIZ = FX["CS"], FX["CS_B"], FX["QUIZ"]


def show(tag, r, extract=None):
    body = r.text[:200]
    if r.status_code == 200 and extract:
        try:
            body = repr(extract(r.json().get("message")))[:220]
        except Exception:
            pass
    print(f"  [{r.status_code}] {tag}\n      {body}\n")


print("=== A04-3: calendar_token readable at permlevel 0 by an enrolled student ===")
r = call(
    "stuA",
    "frappe.client.get_value",
    {
        "doctype": "Course Schedule",
        "filters": json.dumps({"name": CS}),
        "fieldname": json.dumps(["calendar_token", "web_meeting"]),
    },
)
show("stuA client.get_value calendar_token on own section", r, lambda m: m)
r = call("stuA", "seminary.seminary.utils.get_course_details", {"course": CS})
show(
    "stuA get_course_details (p006 gate nulls it here)",
    r,
    lambda m: (
        {k: m.get(k) for k in ("calendar_token", "web_meeting")}
        if isinstance(m, dict)
        else m
    ),
)

print("=== A01-18: whole-section attendance standings, no gate ===")
for who in ("stuA", "stuB"):
    r = call(
        who,
        "seminary.seminary.attendance.get_course_attendance_standings",
        {"course_schedule": CS},
    )
    show(
        f"{who} get_course_attendance_standings(CS)",
        r,
        lambda m: f"{len(m)} roster rows: {list(m)[:3]}" if isinstance(m, dict) else m,
    )
r = call(
    "stuA",
    "seminary.seminary.attendance.get_course_attendance_standings",
    {"course_schedule": CS_B},
)
show(
    "stuA on CS_B (a section stuA is NOT in)",
    r,
    lambda m: f"{len(m)} roster rows" if isinstance(m, dict) else m,
)

print("=== A01-15: answer keys / question bank unscoped for Student ===")
for dt in (
    "Exam Activity",
    "Quiz",
    "Assignment Activity",
    "Open Question",
    "Discussion Activity",
    "Course Folder",
):
    r = call(
        "stuA",
        "frappe.client.get_list",
        {"doctype": dt, "limit_page_length": 5},
        http="GET",
    )
    show(
        f"stuA client.get_list({dt!r})",
        r,
        lambda m: f"{len(m)} rows: {[x.get('name') for x in m][:3]}",
    )

print("=== A01-16: disciplinary occurrence oracle ===")
r = call(
    "stuA",
    "seminary.seminary.disciplinary.compute_occurrence_number",
    {"student": FX["STU_B"], "reason": "Academic Dishonesty"},
)
show("stuA compute_occurrence_number(stuB, 'Academic Dishonesty')", r, lambda m: m)
