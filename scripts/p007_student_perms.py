#!/usr/bin/env python3
"""One-shot maintenance script: the p007 Phase 1 DocPerm rewrite.

Applies privatedocs/p007 §2.1 (Student rows), §2.3 (grading / registrar /
confidential fields at permlevel 1) and §2.8 (Instructor.default_inst_category
at permlevel 1) to the doctype JSON source of truth. Idempotent; run from the
app root. Every other role and every permlevel>0 row it does not name is
preserved.
"""

import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seminary")
FLAG = {"C": "create", "R": "read", "W": "write", "D": "delete", "S": "submit"}
BASE_KEYS = ("email", "export", "print", "report", "share")
GRADERS = ("Instructor", "Program Chair", "Seminary Manager", "System Manager")
REGISTRAR_L1 = (
    "Registrar",
    "Seminary Manager",
    "Accounts User",
    "Accounts Manager",
    "System Manager",
)
LETTER_L1 = ("Registrar", "Program Chair", "Seminary Manager", "System Manager")
CHAIR_L1 = ("Program Chair", "Seminary Manager", "System Manager")

# doctype dir -> Student rows as (flags, if_owner, permlevel). Every existing
# Student row (any permlevel) is replaced. A level-1 read row lets the student
# see their grade and the grader's comments without being able to write them.
STUDENT_ROWS = {
    "scheduled_course_roster": [("R", 0, 0)],
    "course_schedule": [("R", 0, 0)],
    "course_schedule_chapter": [("R", 0, 0)],
    "course_lesson": [("R", 0, 0)],
    "quiz": [("R", 0, 0)],
    "exam_submission": [("RC", 0, 0), ("W", 1, 0), ("R", 0, 1)],
    "assignment_submission": [("RC", 0, 0), ("W", 1, 0), ("R", 0, 1)],
    "discussion_submission": [("RC", 0, 0), ("W", 1, 0), ("R", 0, 1)],
    "quiz_submission": [("RWC", 1, 0), ("R", 0, 1)],
    "course_enrollment_individual": [("R", 0, 0)],
    "course_schedule_progress": [("R", 1, 0)],
    "withdrawal_request": [("RC", 0, 0), ("W", 1, 0), ("R", 0, 1)],
    "graduation_request": [("R", 0, 0)],
    "recommendation_letter": [("R", 0, 0)],
    "culminating_project": [("R", 0, 0)],
    "student": [("R", 0, 0)],
    "chapel_attendance": [("R", 0, 0)],
}

# doctype dir -> (fields moved to permlevel 1, roles with a level-1 rw row)
PERMLEVEL_1 = {
    "assignment_submission": (
        [
            "status",
            "grade",
            "percentage",
            "evaluator",
            "comments",
            "comment_attach",
            "extra_credit",
            "comments_thread",
            "plagiarism_text",
            "plagiarism_text_hash",
        ],
        GRADERS,
    ),
    "discussion_submission": (
        [
            "status",
            "grade",
            "percentage",
            "score_out_of",
            "fudge_points",
            "extra_credit",
            "comments",
            "grading_comments",
        ],
        GRADERS,
    ),
    "exam_submission": (
        [
            "status",
            "score",
            "score_out_of",
            "percentage",
            "passing_percentage",
            "fudge_points",
            "extra_credit",
            "comments",
            "grading_comments",
            "result",
        ],
        GRADERS,
    ),
    "quiz_submission": (
        [
            "score",
            "score_out_of",
            "percentage",
            "passing_percentage",
            "extra_credit",
            "result",
        ],
        GRADERS,
    ),
    "withdrawal_request": (
        [
            "separation_timing",
            "separation_effective_date",
            "withdrawal_rule",
            "withdrawal_courses",
            "transfer_to_institution",
            "transfer_to_program",
            "transfer_to_country",
            "destination_contact",
            "transcript_sent_on",
            "transfer_notes",
            "is_parent",
            "has_parent",
        ],
        REGISTRAR_L1,
    ),
    "recommendation_letter": (
        ["letter_body", "letter_attachment", "request_token", "review_notes"],
        LETTER_L1,
    ),
    "instructor": (["default_inst_category"], CHAIR_L1),
}


def perm(role, flags, if_owner=0, permlevel=0):
    p = {"role": role, "permlevel": permlevel}
    if permlevel == 0:
        for k in BASE_KEYS:
            p[k] = 1
    for ch in flags:
        p[FLAG[ch]] = 1
    if if_owner:
        p["if_owner"] = 1
    return p


def load(path):
    return json.load(open(path))


def dump(path, d):
    with open(path, "w") as f:
        f.write(json.dumps(d, indent=1, sort_keys=True))


def find(dirname):
    for base in ("seminary/doctype", "alumni/doctype"):
        p = os.path.join(ROOT, base, dirname, dirname + ".json")
        if os.path.exists(p):
            return p
    raise SystemExit(f"doctype json not found: {dirname}")


def main():
    for dirname, rows in STUDENT_ROWS.items():
        path = find(dirname)
        d = load(path)
        perms = [p for p in d.get("permissions", []) if p.get("role") != "Student"]
        for flags, if_owner, permlevel in rows:
            perms.append(perm("Student", flags, if_owner=if_owner, permlevel=permlevel))
        d["permissions"] = perms
        dump(path, d)
        print(f"{d['name']}: Student -> {rows}")

    for dirname, (fields, roles) in PERMLEVEL_1.items():
        path = find(dirname)
        d = load(path)
        moved = []
        for f in d["fields"]:
            if f["fieldname"] in fields:
                f["permlevel"] = 1
                moved.append(f["fieldname"])
        missing = set(fields) - set(moved)
        if missing:
            raise SystemExit(f"{d['name']}: fields not found {missing}")
        perms = [
            p
            for p in d.get("permissions", [])
            if not (p.get("permlevel") == 1 and p.get("role") in roles)
        ]
        for role in roles:
            perms.append(perm(role, "RW", permlevel=1))
        d["permissions"] = perms
        dump(path, d)
        print(f"{d['name']}: permlevel 1 on {moved}; rows for {roles}")


if __name__ == "__main__":
    main()
