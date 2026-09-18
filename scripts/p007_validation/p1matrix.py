"""p007 §4 matrix (the API-checkable rows) against potestas.localhost:8006.
Run after p1fixtures.py:  cd <here> && /home/drmrmelo/lms/env/bin/python p1matrix.py

Rows are grouped as in the ADR (§4.1 DocPerms/hooks/permlevels, §4.2 course
gates, §4.3 student-scoped reads, §4.4 staff-only gates, §4.5 un-whitelisted,
§4.6 tiers / unit scope / category governance, §4.7 announcement filter).
Not idempotent in a strict sense, but it restores what it changes.
"""

import json
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, "..", "p006_validation"))
from p0check import RESULTS, USERS, call, check, jar, summary, H  # noqa: E402,F401

FX = json.load(open(os.path.join(S, "fx1.json")))
USERS["instr3"] = FX["U3"]  # of record, listed on CS only
USERS["gta"] = FX["GTA_USER"]  # Student + Instructor (Grader) on CS; enrolled in CS_B
USERS["instrU"] = FX["U_USER"]  # of record, member of the ST unit, listed nowhere
CS, CS_B, COURSE = FX["CS"], FX["CS_B"], FX["COURSE"]
ST_CS = FX["ST_CS_A"]
STU_A, STU_B = FX["STU_A"], FX["STU_B"]
STU_A_USER, STU_B_USER = USERS["stuA"], USERS["stuB"]
OF_RECORD = "Instructor of Record"


def client(who, method, params, http="POST"):
    return call(who, "frappe.client." + method, params, http=http)


def gv(doctype, name, field):
    r = call(
        "admin",
        "frappe.client.get_value",
        {
            "doctype": doctype,
            "filters": name if isinstance(name, dict) else {"name": name},
            "fieldname": field,
        },
    )
    if r.status_code != 200:
        return None
    m = r.json().get("message") or {}
    return m.get(field) if isinstance(field, str) else m


def sv(doctype, name, fieldname, value):
    return call(
        "admin",
        "frappe.client.set_value",
        {"doctype": doctype, "name": name, "fieldname": fieldname, "value": value},
    )


def is_403(r):
    return (r.status_code == 403), f"got {r.status_code}"


def not_403(r):
    return r.status_code != 403, f"got {r.status_code} {r.text[:100]}"


def status_in(*codes):
    def _f(r):
        return r.status_code in codes, f"got {r.status_code} {r.text[:100]}"

    return _f


def ok_json(pred, note="ok"):
    def _f(r):
        if r.status_code != 200:
            return False, f"got {r.status_code} {r.text[:140]}"
        try:
            m = r.json().get("message")
        except Exception:
            return False, "non-json"
        try:
            return bool(pred(m)), note
        except Exception as e:  # noqa: BLE001
            return False, f"pred raised {e!r}"

    return _f


def names(m):
    return [row.get("name") for row in (m or [])]


def gl(who, doctype, fields=None, filters=None, limit=500):
    return client(
        who,
        "get_list",
        {
            "doctype": doctype,
            "fields": fields or ["name"],
            "filters": filters or {},
            "limit_page_length": limit,
        },
    )


def set_as(who, doctype, name, fieldname, value=None):
    params = {"doctype": doctype, "name": name, "fieldname": fieldname}
    if value is not None:
        params["value"] = value
    return client(who, "set_value", params)


# ================================================================ 4.1
check(
    "4.1 stuA lists own Student only",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Student", "fields": ["name"]},
    ok_json(lambda m: names(m) == [STU_A], "one row"),
)
check(
    "4.1 stuA get_value classmate Student",
    "stuA",
    "frappe.client.get_value",
    {"doctype": "Student", "filters": {"name": STU_B}, "fieldname": "student_name"},
    lambda r: (
        r.status_code == 403 or not (r.json().get("message") or {}),
        f"got {r.status_code} {r.text[:80]}",
    ),
)
check(
    "4.1 stuA roster list own rows",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Scheduled Course Roster", "fields": ["name", "stuemail_rc"]},
    ok_json(lambda m: m and all(r["stuemail_rc"] == STU_A_USER for r in m)),
)
check(
    "4.1 stuA set roster fscore",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Scheduled Course Roster",
        "name": FX["ROSTER_A"],
        "fieldname": "fscore",
        "value": 100,
    },
    is_403,
)
check(
    "4.1 stuA unpublish CS",
    "stuA",
    "frappe.client.set_value",
    {"doctype": "Course Schedule", "name": CS, "fieldname": "published", "value": 0},
    is_403,
    after=lambda: (gv("Course Schedule", CS, "published") == 1, "still published"),
)
check(
    "4.1 stuA set web_meeting",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Course Schedule",
        "name": CS,
        "fieldname": "web_meeting",
        "value": "https://evil.example",
    },
    is_403,
)
check(
    "4.1 stuA edit lesson",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Course Lesson",
        "name": FX["LESSON"],
        "fieldname": "lesson_title",
        "value": "x",
    },
    is_403,
)
check(
    "4.1 stuA edit quiz",
    "stuA",
    "frappe.client.set_value",
    {"doctype": "Quiz", "name": FX["QUIZ"], "fieldname": "title", "value": "x"},
    is_403,
)
check(
    "4.1 stuA lists own exam submissions",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Exam Submission", "fields": ["name", "member"]},
    ok_json(
        lambda m: m
        and all(r["member"] == STU_A_USER for r in m)
        and FX["ES_B"] not in names(m)
    ),
)
check(
    "4.1 stuA score classmate exam",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Exam Submission",
        "name": FX["ES_B"],
        "fieldname": "score",
        "value": 100,
    },
    is_403,
)
before_score = gv("Exam Submission", FX["ES_A"], "score")
check(
    "4.1 stuA score own exam (permlevel 1)",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Exam Submission",
        "name": FX["ES_A"],
        "fieldname": "score",
        "value": 100,
    },
    status_in(200, 403),
    after=lambda: (
        gv("Exam Submission", FX["ES_A"], "score") == before_score,
        "score unchanged",
    ),
)
check(
    "4.1 stuA edit own answer",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": "answer",
        "value": "<p>P1 edit</p>",
    },
    200,
    after=lambda: (
        "P1 edit" in (gv("Assignment Submission", FX["AS_A"], "answer") or ""),
        "answer stored",
    ),
)
before_grade = gv("Assignment Submission", FX["AS_A"], "grade")
before_status = gv("Assignment Submission", FX["AS_A"], "status")
check(
    "4.1 stuA self-grade own assignment (permlevel 1)",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": {"status": "Graded", "grade": 100},
    },
    status_in(200, 403),
    after=lambda: (
        gv("Assignment Submission", FX["AS_A"], "grade") == before_grade
        and gv("Assignment Submission", FX["AS_A"], "status") == before_status,
        "grade/status unchanged",
    ),
)
check(
    "4.1 stuA delete own assignment",
    "stuA",
    "frappe.client.delete",
    {"doctype": "Assignment Submission", "name": FX["AS_A"]},
    is_403,
)
check(
    "4.1 stuA insert discussion post as stuB",
    "stuA",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Discussion Submission",
            "disc_activity": FX["DA"],
            "coursesc": CS,
            "course": COURSE,
            "member": STU_B_USER,
            "student": STU_B,
            "original_post": "<p>P1 forged</p>",
        }
    },
    status_in(403, 417),
)
check(
    "4.1 stuA lists own discussion posts",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Discussion Submission", "fields": ["name", "member"]},
    ok_json(
        lambda m: all(r["member"] == STU_A_USER for r in m)
        and FX["DS_B"] not in names(m)
    ),
)
check(
    "4.1 stuA lists own CEIs",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Course Enrollment Individual", "fields": ["name", "student_ce"]},
    ok_json(lambda m: m and all(r["student_ce"] == STU_A for r in m)),
)
check(
    "4.1 stuA delete classmate CEI",
    "stuA",
    "frappe.client.delete",
    {"doctype": "Course Enrollment Individual", "name": FX["CEI_B"]},
    is_403,
)
check(
    "4.1 stuA lists own withdrawals",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Withdrawal Request", "fields": ["name", "student"]},
    ok_json(lambda m: FX["WDR_A"] in names(m) and FX["WDR_B"] not in names(m)),
)
check(
    "4.1 stuA file withdrawal for stuB",
    "stuA",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Withdrawal Request",
            "student": STU_B,
            "program_enrollment": FX["PE_B"],
            "course_enrollment_individual": FX["CEI_B"],
            "withdrawal_scope": "Single Course",
            "student_comment": "P1 forged",
        }
    },
    status_in(403, 417),
)
r = check(
    "4.1 stuA file own withdrawal (SPA path)",
    "stuA",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Withdrawal Request",
            "student": STU_A,
            "program_enrollment": FX["PE_A"],
            "course_enrollment_individual": FX["CEI_A"],
            "withdrawal_scope": "Single Course",
            "withdrawal_reason": gv(
                "Withdrawal Request", FX["WDR_A"], "withdrawal_reason"
            ),
            "student_comment": "P1 own",
        }
    },
    200,
)
if r is not None and r.status_code == 200:
    call(
        "admin",
        "frappe.client.delete",
        {"doctype": "Withdrawal Request", "name": r.json()["message"]["name"]},
    )
before_sep = gv("Withdrawal Request", FX["WDR_A"], "separation_effective_date")
check(
    "4.1 stuA set registrar field on own withdrawal",
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Withdrawal Request",
        "name": FX["WDR_A"],
        "fieldname": "separation_effective_date",
        "value": "2030-01-01",
    },
    status_in(200, 403),
    after=lambda: (
        gv("Withdrawal Request", FX["WDR_A"], "separation_effective_date")
        == before_sep,
        "unchanged",
    ),
)
check(
    "4.1 stuA lists own letters",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Recommendation Letter", "fields": ["name", "student"]},
    ok_json(lambda m: FX["RL_A"] in names(m) and all(r["student"] == STU_A for r in m)),
)
check(
    "4.1 stuA own letter body hidden",
    "stuA",
    "frappe.client.get",
    {"doctype": "Recommendation Letter", "name": FX["RL_A"]},
    ok_json(
        lambda m: not m.get("letter_body") and not m.get("request_token"),
        "no body, no token",
    ),
)
check(
    "4.1 reg reads letter body",
    "reg",
    "frappe.client.get",
    {"doctype": "Recommendation Letter", "name": FX["RL_A"]},
    ok_json(lambda m: "P1 confidential" in (m.get("letter_body") or "")),
)
check(
    "4.1 instr3 lists every Student",
    "instr3",
    "frappe.client.get_list",
    {"doctype": "Student", "fields": ["name"], "limit_page_length": 500},
    ok_json(lambda m: len(m) > 3, "school-wide"),
)
check(
    "4.1 instr3 grades stuA (own section)",
    "instr3",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": "grade",
        "value": 90,
    },
    200,
    after=lambda: (gv("Assignment Submission", FX["AS_A"], "grade") == 90, "stored"),
)
sv("Assignment Submission", FX["AS_A"], "grade", before_grade or 0)
check(
    "4.1 stuA lists own chapel attendance",
    "stuA",
    "frappe.client.get_list",
    {"doctype": "Chapel Attendance", "fields": ["name", "student"]},
    ok_json(
        lambda m: FX["CHAPEL_A"] in names(m) and all(r["student"] == STU_A for r in m)
    ),
)

# ================================================================ 4.2 course gates
SCOPED = [
    ("seminary.seminary.utils.get_gradebook", {"course": "{cs}"}, True),
    ("seminary.seminary.utils.get_course_meetingdates", {"course": "{cs}"}, True),
    ("seminary.seminary.api.get_course_rosters", {"name": "{cs}"}, True),
    ("seminary.seminary.api.get_student_groups", {"course_name": "{cs}"}, False),
    (
        "seminary.seminary.api.get_discussion_submission_summary",
        {"course_name": "{cs}", "discussion_id": FX["DA"]},
        False,
    ),
    (
        "seminary.seminary.api.get_quiz_dashboard",
        {"course_name": "{cs}", "quiz_id": FX["QUIZ"]},
        False,
    ),
    (
        "seminary.seminary.api.get_exam_dashboard",
        {"course_name": "{cs}", "exam_id": FX["EA"]},
        False,
    ),
    (
        "seminary.seminary.api.get_assignment_dashboard",
        {"course_name": "{cs}", "assignment_id": FX["AA"]},
        False,
    ),
    (
        "seminary.seminary.utils.get_lesson_creation_details",
        {"course": "{cs}", "chapter": 1, "lesson": 1},
        False,
    ),
    ("seminary.seminary.utils.missing_exams", {"course": "{cs}"}, False),
    ("seminary.seminary.utils.get_course_exams", {"course": "{cs}"}, False),
    ("seminary.seminary.utils.get_assessments_tograde", {"course": "{cs}"}, False),
    ("seminary.seminary.api.get_virtual_meetings", {"course_schedule": "{cs}"}, True),
    (
        "seminary.seminary.doctype.student_attendance_tool.student_attendance_tool.get_student_attendance_records",
        {"course_schedule": "{cs}"},
        True,
    ),
    (
        "seminary.seminary.api.mark_attendance",
        {"students_present": "[]", "students_absent": "[]", "course_schedule": "{cs}"},
        True,
    ),
]


def fill(params, cs):
    return {
        k: (v.replace("{cs}", cs) if isinstance(v, str) else v)
        for k, v in params.items()
    }


for fn, params, reg_ok in SCOPED:
    short = fn.rsplit(".", 1)[1]
    check(f"4.2 instr3 {short} on CS", "instr3", fn, fill(params, CS), not_403)
    check(f"4.2 instr2 {short} on CS", "instr2", fn, fill(params, CS), is_403)
    check(f"4.2 instr2 {short} on CS_B", "instr2", fn, fill(params, CS_B), not_403)
    check(f"4.2 chair {short} on CS", "chair", fn, fill(params, CS), not_403)
    check(f"4.2 gta {short} on CS", "gta", fn, fill(params, CS), not_403)
    check(f"4.2 gta {short} on CS_B", "gta", fn, fill(params, CS_B), is_403)
    check(f"4.2 stuA {short}", "stuA", fn, fill(params, CS), is_403)
    if reg_ok:
        check(
            f"4.2 reg {short} on CS (switch on)", "reg", fn, fill(params, CS), not_403
        )
    else:
        check(f"4.2 reg {short} on CS", "reg", fn, fill(params, CS), is_403)

before_dg = gv("Discussion Submission", FX["DS_A"], "grade")
check(
    "4.2 instr2 grade discussion in CS",
    "instr2",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_A"], "grade": 77},
    is_403,
)
check(
    "4.2 instr3 grade discussion in CS",
    "instr3",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_A"], "grade": 77},
    200,
)
check(
    "4.2 gta grade discussion in CS",
    "gta",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_A"], "grade": 78},
    200,
)
sv("Discussion Submission", FX["DS_A"], "grade", before_dg or 0)
check(
    "4.2 instr2 delete_chapter in CS",
    "instr2",
    "seminary.seminary.api.delete_chapter",
    {"chapter": FX["CHAPTER"]},
    is_403,
    after=lambda: (
        bool(gv("Course Schedule Chapter", FX["CHAPTER"], "name")),
        "chapter kept",
    ),
)
check(
    "4.2 instr2 send_grades CS",
    "instr2",
    "seminary.seminary.api.send_grades",
    {"doc": json.dumps({"name": CS})},
    is_403,
)
check(
    "4.2 reg send_grades CS (state check, not the gate)",
    "reg",
    "seminary.seminary.api.send_grades",
    {"doc": json.dumps({"name": CS})},
    not_403,
)

# ================================================================ 4.3 student-scoped reads
check(
    "4.3 stuA get_student_programs(stuB) -> own",
    "stuA",
    "seminary.seminary.api.get_student_programs",
    {"student": STU_B},
    ok_json(lambda m: all(r["student"] == STU_A for r in m)),
)
check(
    "4.3 stuA get_pgmenrollments(stuB) -> own",
    "stuA",
    "seminary.seminary.api.get_pgmenrollments",
    {"name": STU_B},
    ok_json(lambda m: FX["PE_A"] in names(m) and FX["PE_B"] not in names(m)),
)
check(
    "4.3 stuA get_program_audit(PE_B)",
    "stuA",
    "seminary.seminary.api.get_program_audit",
    {"program_enrollment": FX["PE_B"]},
    is_403,
)
check(
    "4.3 stuA get_program_audit(PE_A)",
    "stuA",
    "seminary.seminary.api.get_program_audit",
    {"program_enrollment": FX["PE_A"]},
    200,
)
check(
    "4.3 stuA get_pe_unpaid_invoices(PE_B)",
    "stuA",
    "seminary.seminary.api.get_pe_unpaid_invoices",
    {"program_enrollment": FX["PE_B"]},
    is_403,
)
check(
    "4.3 stuA get_user_discussion_submission(owner=stuB) -> own",
    "stuA",
    "seminary.seminary.api.get_user_discussion_submission",
    {"course_name": CS, "discussion_id": FX["DA"], "owner": STU_B_USER},
    ok_json(lambda m: all(r["owner"] == STU_A_USER for r in m)),
)
check(
    "4.3 stuA get_grading_comments(DS_B)",
    "stuA",
    "seminary.seminary.api.get_grading_comments",
    {"submission_name": FX["DS_B"]},
    is_403,
)
check(
    "4.3 stuA get_grading_comments(DS_A)",
    "stuA",
    "seminary.seminary.api.get_grading_comments",
    {"submission_name": FX["DS_A"]},
    200,
)
check(
    "4.3 stuA get_discussion_submissions(CS_B)",
    "stuA",
    "seminary.seminary.api.get_discussion_submissions",
    {"course_name": CS_B, "discussion_id": FX["DA"]},
    is_403,
)
check(
    "4.3 stuA get_roster(CS): names only",
    "stuA",
    "seminary.seminary.utils.get_roster",
    {"course": CS},
    ok_json(
        lambda m: m and all("stuemail_rc" not in r and "gender" not in r for r in m)
    ),
)
check(
    "4.3 stuA get_roster(CS_B)",
    "stuA",
    "seminary.seminary.utils.get_roster",
    {"course": CS_B},
    is_403,
)
check(
    "4.3 instr3 get_roster(CS): emails",
    "instr3",
    "seminary.seminary.utils.get_roster",
    {"course": CS},
    ok_json(lambda m: m and all("stuemail_rc" in r for r in m)),
)
check(
    "4.3 stuA get_announcements(CS_B)",
    "stuA",
    "seminary.seminary.api.get_announcements",
    {"cs": CS_B},
    is_403,
)
check(
    "4.3 stuA get_assessments(CS_B)",
    "stuA",
    "seminary.seminary.utils.get_assessments",
    {"course": CS_B},
    is_403,
)
check(
    "4.3 stuA get_assessments(CS)",
    "stuA",
    "seminary.seminary.utils.get_assessments",
    {"course": CS},
    200,
)
unpub = gv(
    "Course Schedule", {"published": 0, "workflow_state": ["!=", "Cancelled"]}, "name"
)
check(
    "4.3 stuA get_course_outline(CS_B published, not enrolled) (§8.1)",
    "stuA",
    "seminary.seminary.utils.get_course_outline",
    {"course": CS_B},
    is_403,
)
if unpub:
    check(
        "4.3 stuA get_course_outline(unpublished)",
        "stuA",
        "seminary.seminary.utils.get_course_outline",
        {"course": unpub},
        is_403,
    )
lesson_b = gv("Course Lesson", {"course_sc": CS_B}, "name")
if lesson_b:
    check(
        "4.3 stuA get_discussion_topics(lesson of CS_B)",
        "stuA",
        "seminary.seminary.utils.get_discussion_topics",
        {"doctype": "Course Lesson", "docname": lesson_b, "single_thread": ""},
        is_403,
    )
check(
    "4.3 stuA get_discussion_topics(own lesson)",
    "stuA",
    "seminary.seminary.utils.get_discussion_topics",
    {"doctype": "Course Lesson", "docname": FX["LESSON"], "single_thread": ""},
    200,
)
check(
    "4.3 stuA get_missingassessments(member=stuB) -> own",
    "stuA",
    "seminary.seminary.utils.get_missingassessments",
    {"course": CS, "member": STU_B_USER},
    ok_json(lambda m: all(r["stuemail_rc"] == STU_A_USER for r in m)),
)
private_file = FX.get("PRIVATE_FILE_B")
if private_file:
    check(
        "4.3 stuA get_file_info(other's private file)",
        "stuA",
        "seminary.seminary.api.get_file_info",
        {"file_url": private_file},
        is_403,
    )
check(
    "4.3 stuA get_courses_for_student(stuB) -> own",
    "stuA",
    "seminary.seminary.utils.get_courses_for_student",
    {"student": STU_B_USER},
    ok_json(lambda m: CS in names(m) and CS_B not in names(m)),
)

# ================================================================ 4.4 staff-only gates
check(
    "4.4 stuA save_course",
    "stuA",
    "seminary.seminary.api.save_course",
    {"course": CS, "course_data": json.dumps({"published": 0})},
    is_403,
    after=lambda: (gv("Course Schedule", CS, "published") == 1, "still published"),
)
check(
    "4.4 instr2 save_course CS",
    "instr2",
    "seminary.seminary.api.save_course",
    {"course": CS, "course_data": json.dumps({"published": 0})},
    is_403,
)
check(
    "4.4 gta save_course CS_B",
    "gta",
    "seminary.seminary.api.save_course",
    {"course": CS_B, "course_data": json.dumps({"published": 0})},
    is_403,
)
for label, fn, params in (
    (
        "enroll_student",
        "seminary.seminary.api.enroll_student",
        {"source_name": FX["APP"]},
    ),
    ("course_event", "seminary.seminary.api.course_event", {"name": CS}),
    (
        "room_search",
        "seminary.seminary.api.room_search",
        {
            "doctype": "Room",
            "txt": "",
            "searchfield": "name",
            "start": 0,
            "page_len": 5,
            "filters": "{}",
        },
    ),
    (
        "get_course_schedule_events",
        "seminary.seminary.api.get_course_schedule_events",
        {"start": "2026-01-01", "end": "2026-12-31", "filters": "{}"},
    ),
    (
        "preview_announcement_recipients",
        "seminary.seminary.api.preview_announcement_recipients",
        {"name": "x"},
    ),
    ("get_timezones", "seminary.seminary.utils.get_timezones", {}),
    (
        "create_student_group",
        "seminary.seminary.utils.create_student_group",
        {
            "course": CS,
            "group_name": "P1",
            "group_instructor": FX["INSTR3"],
            "members": "[]",
        },
    ),
    (
        "resnapshot_milestones",
        "seminary.seminary.doctype.culminating_project.culminating_project.resnapshot_milestones",
        {"name": "x"},
    ),
    (
        "lift_hold",
        "seminary.seminary.student_standing.lift_hold",
        {"student": STU_A, "hold_row_name": "x"},
    ),
):
    check(f"4.4 stuA {label}", "stuA", fn, params, is_403)
check(
    "4.4 reg enroll_student (gate passes)",
    "reg",
    "seminary.seminary.api.enroll_student",
    {"source_name": "ZZT-no-such"},
    not_403,
)
person_b = gv("Student", STU_B, "person")
if person_b:
    check(
        "4.4 stuA get_person_timeline(stuB person) -> []",
        "stuA",
        "seminary.seminary.comms.get_person_timeline",
        {"person": person_b},
        ok_json(lambda m: m == [], "empty"),
    )

# ================================================================ 4.5 un-whitelisted
for fn in (
    "seminary.seminary.api.sanitize_html",
    "seminary.seminary.api.sanitize_submission",
    "seminary.seminary.api.sanitize_reply",
    "seminary.seminary.api.get_course",
    "seminary.seminary.api.credits_pe_track",
    "seminary.seminary.api.check_attendance_records_exist",
    "seminary.seminary.api.get_student_contacts",
    "seminary.seminary.api.get_assessment_criteria",
    "seminary.seminary.api.get_grade",
    "seminary.seminary.api.quizresult_to_card",
    "seminary.seminary.api.get_scholarship",
    "seminary.seminary.api.copy_data_to_scheduled_course_roster",
    "seminary.seminary.api.copy_data_to_program_enrollment_course",
    "seminary.seminary.api.update_card",
    "seminary.seminary.api.get_gradepass",
    "seminary.seminary.api.get_fields",
    "seminary.seminary.api.get_my_announcements",
    "seminary.seminary.utils.get_user_info",
    "seminary.seminary.utils.has_course_moderator_role",
    "seminary.seminary.utils.has_course_instructor_role",
    "seminary.seminary.utils.has_course_evaluator_role",
    "seminary.seminary.utils.has_student_role",
    "seminary.seminary.utils.get_lesson_due_date",
    "seminary.seminary.utils.get_open_question_details",
    "seminary.seminary.utils.get_all_open_questions_details",
    "seminary.seminary.utils.enroll_in_program",
    "seminary.seminary.utils.insert_discussion_reply",
    "seminary.seminary.doctype.quiz.quiz.get_all_question_results",
):
    check(
        f"4.5 admin {fn.rsplit('.', 1)[1]} not an endpoint",
        "admin",
        fn,
        {},
        status_in(403, 404),
    )

# ================================================================ 4.6 tiers
before_intro = gv("Course Schedule", CS, "short_introduction")
check(
    "4.6 instr2 set CS intro",
    "instr2",
    "frappe.client.set_value",
    {
        "doctype": "Course Schedule",
        "name": CS,
        "fieldname": "short_introduction",
        "value": "x",
    },
    is_403,
)
check(
    "4.6 instr2 get CS (record tier reads)",
    "instr2",
    "frappe.client.get",
    {"doctype": "Course Schedule", "name": CS},
    200,
)
check(
    "4.6 instr2 edit lesson of CS",
    "instr2",
    "frappe.client.set_value",
    {
        "doctype": "Course Lesson",
        "name": FX["LESSON"],
        "fieldname": "lesson_title",
        "value": "x",
    },
    is_403,
)
check(
    "4.6 instr2 grade AS_A via set_value",
    "instr2",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": "grade",
        "value": 1,
    },
    is_403,
)
check(
    "4.6 instr2 lists CS submissions (read)",
    "instr2",
    "frappe.client.get_list",
    {"doctype": "Assignment Submission", "fields": ["name"], "limit_page_length": 500},
    ok_json(lambda m: FX["AS_A"] in names(m)),
)
check(
    "4.6 instr3 set CS intro",
    "instr3",
    "frappe.client.set_value",
    {
        "doctype": "Course Schedule",
        "name": CS,
        "fieldname": "short_introduction",
        "value": "P1 intro",
    },
    200,
)
sv("Course Schedule", CS, "short_introduction", before_intro or "")
check(
    "4.6 gta lists sections: CS in",
    "gta",
    "frappe.client.get_list",
    {"doctype": "Course Schedule", "fields": ["name"], "limit_page_length": 500},
    ok_json(lambda m: CS in names(m) and (not unpub or unpub not in names(m))),
)
if unpub:
    check(
        "4.6 gta get unpublished non-own section",
        "gta",
        "frappe.client.get",
        {"doctype": "Course Schedule", "name": unpub},
        is_403,
    )
check(
    "4.6 gta lists submissions: CS rows only",
    "gta",
    "frappe.client.get_list",
    {
        "doctype": "Assignment Submission",
        "fields": ["name", "course", "member"],
        "limit_page_length": 500,
    },
    ok_json(
        lambda m: FX["AS_A"] in names(m)
        and FX["AS_B"] not in names(m)
        and all(r["course"] == CS or r["member"] == FX["GTA_USER"] for r in m)
    ),
)
check(
    "4.6 gta grades AS_A (section staff)",
    "gta",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": "grade",
        "value": 90,
    },
    200,
)
sv("Assignment Submission", FX["AS_A"], "grade", before_grade or 0)
other_student = gv(
    "Student", {"name": ["not in", [STU_A, STU_B, FX["GTA_STU"]]]}, "name"
)
check(
    "4.6 gta lists students of CS only",
    "gta",
    "frappe.client.get_list",
    {"doctype": "Student", "fields": ["name"], "limit_page_length": 500},
    ok_json(lambda m: STU_A in names(m) and len(m) < 20),
)
check(
    "4.6 gta get_courses_for_student(stuB) -> own (no super access)",
    "gta",
    "seminary.seminary.utils.get_courses_for_student",
    {"student": STU_B_USER},
    ok_json(lambda m: CS not in names(m) and CS_B not in names(m), "not stuB's list"),
)
check(
    "4.6 gta get_gradebook CS",
    "gta",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS},
    200,
)
check(
    "4.6 gta get_gradebook CS_B",
    "gta",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS_B},
    is_403,
)
check(
    "4.6 gta promote self (permlevel 1)",
    "gta",
    "frappe.client.set_value",
    {
        "doctype": "Instructor",
        "name": FX["GTA"],
        "fieldname": "default_inst_category",
        "value": OF_RECORD,
    },
    status_in(200, 403),
    after=lambda: (
        gv("Instructor", FX["GTA"], "default_inst_category") == "Grader",
        "still Grader",
    ),
)
check(
    "4.6 gta edits own bio",
    "gta",
    "frappe.client.set_value",
    {
        "doctype": "Instructor",
        "name": FX["GTA"],
        "fieldname": "shortbio",
        "value": "P1 bio",
    },
    200,
    after=lambda: (gv("Instructor", FX["GTA"], "shortbio") == "P1 bio", "stored"),
)
check(
    "4.6 gta user info: section tier, no All Courses",
    "gta",
    "seminary.seminary.api.get_user_info",
    {},
    ok_json(
        lambda m: m["instructor_tier"] == "section" and not m["can_list_all_courses"]
    ),
)
check(
    "4.6 instr3 user info: record tier, All Courses",
    "instr3",
    "seminary.seminary.api.get_user_info",
    {},
    ok_json(lambda m: m["instructor_tier"] == "record" and m["can_list_all_courses"]),
)
r_mine = call(
    "instr3",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000, "scope": "mine"},
)
check(
    "4.6 instr3 get_courses scope=all wider than mine",
    "instr3",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000, "scope": "all"},
    ok_json(lambda m: len(m) > len(r_mine.json()["message"]) and CS_B in names(m)),
)
r_im = call("instr", "seminary.seminary.utils.get_courses", {"page_length": 1000})
check(
    "4.6 chair+instructor: My Courses is their own sections only",
    "instr",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000, "scope": "mine"},
    ok_json(lambda m: CS in names(m) and CS_B not in names(m)),
)
check(
    "4.6 chair+instructor: All Courses is wider",
    "instr",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000, "scope": "all"},
    ok_json(lambda m: len(m) > len(r_im.json()["message"]) and CS_B in names(m)),
)
check(
    "4.6 chair (no Instructor role) sees every section by default",
    "chair",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000},
    ok_json(lambda m: CS in names(m) and CS_B in names(m)),
)
check(
    "4.6 gta get_courses scope=all stays own (graded + enrolled, §8.1)",
    "gta",
    "seminary.seminary.utils.get_courses",
    {"page_length": 1000, "scope": "all"},
    ok_json(lambda m: sorted(names(m)) == sorted([CS, CS_B])),
)


# category governance through the Desk path (frappe.client.insert on a child row
# appends to the parent and saves it, so Course Schedule.validate runs)
def add_row(who, cs, inst, cat):
    return client(
        who,
        "insert",
        {
            "doc": {
                "doctype": "Course Schedule Instructors",
                "parent": cs,
                "parenttype": "Course Schedule",
                "parentfield": "instructor1",
                "instructor": inst,
                "instructor_category": cat,
            }
        },
    )


def drop_rows(cs, inst):
    for n in (
        call(
            "admin",
            "frappe.client.get_list",
            {
                "doctype": "Course Schedule Instructors",
                "filters": {"parent": cs, "instructor": inst},
                "fields": ["name"],
                "parent": "Course Schedule",
            },
        )
        .json()
        .get("message")
        or []
    ):
        call(
            "admin",
            "frappe.client.delete",
            {"doctype": "Course Schedule Instructors", "name": n["name"]},
        )


check(
    "4.6 reg promotes gta to of-record on CS_B",
    "reg",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Course Schedule Instructors",
            "parent": CS_B,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": FX["GTA"],
            "instructor_category": OF_RECORD,
        }
    },
    status_in(417, 403),
)
drop_rows(CS_B, FX["GTA"])
check(
    "4.6 reg lists instrU (of record by default) on CS_B",
    "reg",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Course Schedule Instructors",
            "parent": CS_B,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": FX["INSTRU"],
            "instructor_category": OF_RECORD,
        }
    },
    200,
)
drop_rows(CS_B, FX["INSTRU"])
empty_default = gv(
    "Instructor",
    {"default_inst_category": ["is", "not set"], "name": ["not in", [FX["GTA"]]]},
    "name",
)
if empty_default:
    check(
        "4.6 reg lists an Instructor with empty default as of-record",
        "reg",
        "frappe.client.insert",
        {
            "doc": {
                "doctype": "Course Schedule Instructors",
                "parent": CS_B,
                "parenttype": "Course Schedule",
                "parentfield": "instructor1",
                "instructor": empty_default,
                "instructor_category": OF_RECORD,
            }
        },
        200,
    )
    drop_rows(CS_B, empty_default)
check(
    "4.6 chair promotes gta on CS_B",
    "chair",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Course Schedule Instructors",
            "parent": CS_B,
            "parenttype": "Course Schedule",
            "parentfield": "instructor1",
            "instructor": FX["GTA"],
            "instructor_category": OF_RECORD,
        }
    },
    200,
)
drop_rows(CS_B, FX["GTA"])

# unit scope
call(
    "admin",
    "frappe.client.set_value",
    {
        "doctype": "Seminary Settings",
        "name": "Seminary Settings",
        "fieldname": "faculty_read_scope",
        "value": "Academic Unit",
    },
)
check(
    "4.6 instrU (unit scope) lists ST section, not CS",
    "instrU",
    "frappe.client.get_list",
    {"doctype": "Course Schedule", "fields": ["name"], "limit_page_length": 500},
    ok_json(lambda m: ST_CS in names(m) and CS not in names(m)),
)
check(
    "4.6 instrU get CS under unit scope",
    "instrU",
    "frappe.client.get",
    {"doctype": "Course Schedule", "name": CS},
    is_403,
)
if FX.get("CS_NO_UNIT"):
    check(
        "4.6 instrU get section of course with no unit",
        "instrU",
        "frappe.client.get",
        {"doctype": "Course Schedule", "name": FX["CS_NO_UNIT"]},
        200,
    )
call(
    "admin",
    "frappe.client.set_value",
    {
        "doctype": "Seminary Settings",
        "name": "Seminary Settings",
        "fieldname": "faculty_read_scope",
        "value": "School",
    },
)
check(
    "4.6 instrU get CS under school scope",
    "instrU",
    "frappe.client.get",
    {"doctype": "Course Schedule", "name": CS},
    200,
)

# ================================================================ 4.7 announcement custom filter
r = check(
    "4.7 chair custom filter on User/api_key refused",
    "chair",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Seminary Announcement",
            "subject": "P1",
            "message": "<p>P1</p>",
            "custom_filter_doctype": "User",
            "custom_email_field": "api_key",
            "custom_filters": "[]",
        }
    },
    status_in(417, 403),
)
r = check(
    "4.7 chair custom filter on Student/student_email_id accepted",
    "chair",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Seminary Announcement",
            "subject": "P1",
            "message": "<p>P1</p>",
            "custom_filter_doctype": "Student",
            "custom_email_field": "student_email_id",
            "custom_filters": "[]",
        }
    },
    status_in(200, 417),
)
if r is not None and r.status_code == 200:
    call(
        "admin",
        "frappe.client.delete",
        {"doctype": "Seminary Announcement", "name": r.json()["message"]["name"]},
    )

# ---------------------------------------------------------------- §8.1 / §8.2
# Published AND enrolled; private files read through their host document.
from urllib.parse import quote  # noqa: E402


def fetch(label, who, url, expect):
    path = quote(url) if url.startswith("/private") or url.startswith("/files") else url
    r = jar(who).get(H + path, allow_redirects=False)
    ok = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    RESULTS.append((label, ok, f"got {r.status_code}"))
    print(("PASS " if ok else "FAIL ") + f" {label}: got {r.status_code}")


def new_file(who, **fields):
    doc = {"doctype": "File", "content": "p007 probe " + fields["file_name"], **fields}
    r = call(who, "frappe.client.insert", {"doc": doc})
    return (r.json().get("message") or {}) if r.status_code == 200 else {}


PROBES = []
f_cs = new_file(
    "admin",
    file_name="p007-cs.txt",
    is_private=1,
    attached_to_doctype="Course Schedule",
    attached_to_name=ST_CS,
)
f_loose = new_file("admin", file_name="p007-loose.txt", is_private=1)
PROBES += [f_cs.get("name"), f_loose.get("name")]
fetch(
    "8.2 stuA reads a file attached to an enrolled, published section",
    "stuA",
    f_cs["file_url"],
    200,
)
f_a = new_file(
    "admin",
    file_name="p007-cs-a.txt",
    is_private=1,
    attached_to_doctype="Course Schedule",
    attached_to_name=CS,
)
PROBES.append(f_a.get("name"))
fetch(
    "8.2 stuB (not on CS) is refused a file attached to CS",
    "stuB",
    f_a["file_url"],
    403,
)
fetch("8.2 gta (grades CS) reads it", "gta", f_a["file_url"], 200)
fetch("8.2 guest is refused", "guest", f_cs["file_url"], 403)
fetch(
    "8.2 stuA is refused a private file attached to nothing",
    "stuA",
    f_loose["file_url"],
    403,
)

check(
    "8.1 stuA get_courses lists only enrolled sections",
    "stuA",
    "seminary.seminary.utils.get_courses",
    {},
    ok_json(
        lambda m: ST_CS in [c["name"] for c in m] and CS_B not in [c["name"] for c in m]
    ),
)
sv("Course Schedule", ST_CS, "published", 0)
try:
    fetch(
        "8.1 unpublished: the enrolled student loses the file",
        "stuA",
        f_cs["file_url"],
        403,
    )
    check(
        "8.1 unpublished: outline refused to the enrolled student",
        "stuA",
        "seminary.seminary.utils.get_course_outline",
        {"course": ST_CS},
        is_403,
    )
    check(
        "8.1 unpublished: frappe.client.get refused",
        "stuA",
        "frappe.client.get",
        {"doctype": "Course Schedule", "name": ST_CS},
        is_403,
    )
    check(
        "8.1 unpublished: get_courses drops it",
        "stuA",
        "seminary.seminary.utils.get_courses",
        {},
        ok_json(lambda m: ST_CS not in [c["name"] for c in m]),
    )
    check(
        "8.1 unpublished: a chair still reads it",
        "chair",
        "frappe.client.get",
        {"doctype": "Course Schedule", "name": ST_CS},
        200,
    )
finally:
    sv("Course Schedule", ST_CS, "published", 1)
fetch("8.1 republished: the file is back", "stuA", f_cs["file_url"], 200)


def upload(label, who, public_expected):
    s = jar(who)
    r = s.post(
        H + "/api/method/upload_file",
        files={
            "file": (f"p007-up-{who}.txt", b"p007 upload " + who.encode(), "text/plain")
        },
        data={"is_private": "0", "folder": "Home"},
    )
    m = (r.json().get("message") or {}) if r.status_code == 200 else {}
    ok = r.status_code == 200 and bool(m.get("is_private")) != public_expected
    RESULTS.append((label, ok, f"got {r.status_code} is_private={m.get('is_private')}"))
    print(("PASS " if ok else "FAIL ") + f" {label}: is_private={m.get('is_private')}")
    if m.get("name"):
        PROBES.append(m["name"])
    return m


up_stu = upload("8.2 a student's public upload lands private", "stuA", False)
upload("8.2 an instructor's public upload lands private", "instr3", False)
upload("8.2 Administrator may publish", "admin", True)
if up_stu.get("name"):
    check(
        "8.2 a student cannot flip their file public",
        "stuA",
        "frappe.client.set_value",
        {
            "doctype": "File",
            "name": up_stu["name"],
            "fieldname": "is_private",
            "value": 0,
        },
        is_403,
        after=lambda: (gv("File", up_stu["name"], "is_private") == 1, "still private"),
    )

person = gv("Person", {"name": ["like", "%"]}, "name")
if person:
    f_av = new_file(
        "admin",
        file_name="p007-avatar.txt",
        is_private=1,
        attached_to_doctype="Person",
        attached_to_name=person,
        attached_to_field="image",
    )
    PROBES.append(f_av.get("name"))
    fetch(
        "8.2 an avatar is readable by any signed-in user", "stuB", f_av["file_url"], 200
    )
    fetch("8.2 an avatar is not readable by a guest", "guest", f_av["file_url"], 403)

for name in filter(None, PROBES):
    call("admin", "frappe.client.delete", {"doctype": "File", "name": name})


sys.exit(summary())
