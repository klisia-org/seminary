"""p006 §4 matrix (the API-checkable rows). Run after p0fixtures*.py.
cd <scratchpad> && /home/drmrmelo/lms/env/bin/python p0matrix.py
"""

import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p0check import USERS, call, check, jar, summary, H  # noqa: E402

FX = json.load(
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx.json"))
)
USERS["stuC"] = "demo.cspurgeon@seminary.edu"  # in no Identity section
USERS["instr3"] = FX["U3"]  # pure Instructor, on CS-A only
CS, CS_B, CS_C, COURSE = FX["CS"], FX["CS_B"], FX["CS_C"], FX["COURSE"]
STU_A_USER, STU_B_USER = USERS["stuA"], USERS["stuB"]


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


def ok_json(pred, note="ok"):
    def _f(r):
        if r.status_code != 200:
            return False, f"got {r.status_code} {r.text[:120]}"
        try:
            m = r.json().get("message")
        except Exception:
            return False, "non-json"
        return pred(m), note

    return _f


def not_403(r):
    return r.status_code != 403, f"got {r.status_code}"


# ---------------------------------------------------------------- 4.1 F1
check(
    "4.1 stuA delete_chapter",
    "stuA",
    "seminary.seminary.api.delete_chapter",
    {"chapter": FX["CHAPTER"]},
    403,
    after=lambda: (
        bool(gv("Course Schedule Chapter", FX["CHAPTER"], "name")),
        "chapter still exists",
    ),
)
r = call(
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Course Schedule Chapter",
        "name": FX["CHAPTER"],
        "fieldname": "scorm_package_path",
        "value": "/x",
    },
)
check(
    "4.1 stuA set scorm_package_path (permlevel 1)",
    "admin",
    "frappe.client.get_value",
    {
        "doctype": "Course Schedule Chapter",
        "filters": {"name": FX["CHAPTER"]},
        "fieldname": "scorm_package_path",
    },
    ok_json(
        lambda m: (m or {}).get("scorm_package_path") != "/x",
        f"set_value returned {r.status_code}; stored value not /x",
    ),
)
check(
    "4.1 stuA update_chapter_index",
    "stuA",
    "seminary.seminary.api.update_chapter_index",
    {"course": CS, "chapter": FX["CHAPTER"], "idx": 1},
    403,
)
r = check(
    "4.1 instr3 upsert throwaway chapter",
    "instr3",
    "seminary.seminary.api.upsert_chapter",
    {
        "chapter_title": "P0 throwaway",
        "course": CS,
        "is_scorm_package": 0,
        "scorm_package": "",
    },
    not_403,
)
tmp_ch = gv(
    "Course Schedule Chapter", {"coursesc": CS, "chapter_title": "P0 throwaway"}, "name"
)
if tmp_ch:
    check(
        "4.1 instr3 delete throwaway chapter",
        "instr3",
        "seminary.seminary.api.delete_chapter",
        {"chapter": tmp_ch},
        200,
        after=lambda: (not gv("Course Schedule Chapter", tmp_ch, "name"), "gone"),
    )

# ---------------------------------------------------------------- 4.2 F2
check(
    "4.2 stuA download Home",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"folder_id": "Home"},
    403,
    http="GET",
)
check(
    "4.2 stuA download Home/Attachments",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"folder_id": "Home/Attachments"},
    403,
    http="GET",
)
check(
    "4.2 stuA list Course folder",
    "stuA",
    "seminary.api.folder_upload.get_files_in_folder",
    {"course_folder": FX["F_COURSE"]["name"]},
    ok_json(lambda m: "entries" in m),
)
check(
    "4.2 stuA download Course folder",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": FX["F_COURSE"]["name"]},
    lambda r: (r.status_code == 200 and r.content[:2] == b"PK", f"got {r.status_code}"),
    http="GET",
)
check(
    "4.2 stuC (not in course) download Course folder",
    "stuC",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": FX["F_COURSE"]["name"]},
    403,
    http="GET",
)
check(
    "4.2 stuB (other section, same course) download Course folder",
    "stuB",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": FX["F_COURSE"]["name"]},
    200,
    http="GET",
)
check(
    "4.2 foldername param refused",
    "stuA",
    "seminary.api.folder_upload.get_files_in_folder",
    {"foldername": "IDX"},
    lambda r: (r.status_code in (403, 417), f"got {r.status_code}"),
)
check(
    "4.2 guest list Course folder",
    "guest",
    "seminary.api.folder_upload.get_files_in_folder",
    {"course_folder": FX["F_COURSE"]["name"]},
    403,
)

# Section folder on CS-A: readers = stuA; writers = instructors of CS-A (instr3) not gwetherby (instr2)
SEC = FX["F_SECTION_A"]["name"]
check(
    "4.2 stuA (in CS-A) download Section folder",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": SEC},
    200,
    http="GET",
)
check(
    "4.2 stuB (in CS-B) download Section folder of CS-A",
    "stuB",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": SEC},
    403,
    http="GET",
)


def upload(who, folder_id, fname, label):
    s = jar(who)
    r = s.post(
        f"{H}/api/method/upload_file",
        files={"file": (fname, b"p0 bytes")},
        data={
            "method": "seminary.api.folder_upload.upload_to_folder",
            "is_private": "1",
            "folder_id": folder_id,
            "course_schedule": CS,
        },
    )
    ok = r.status_code == 200
    from p0check import RESULTS

    RESULTS.append(
        (
            label,
            ok if "403" not in label else r.status_code == 403,
            f"got {r.status_code}",
        )
    )
    print(("PASS " if RESULTS[-1][1] else "FAIL ") + f" {label}: got {r.status_code}")
    return r


upload(
    "instr3",
    FX["F_SECTION_A"]["file_reference"],
    "p0_sec_instr3.txt",
    "4.2 instr3 (teaches CS-A) upload to Section folder",
)
upload(
    "instr2",
    FX["F_SECTION_A"]["file_reference"],
    "p0_sec_instr2.txt",
    "4.2 instr2 (teaches CS-B only) upload to Section folder -> 403",
)
check(
    "4.2 activity row logged for upload",
    "admin",
    "frappe.client.get",
    {"doctype": "Course Folder", "name": SEC},
    ok_json(
        lambda m: any(
            (x.get("file_name") or "").startswith("p0_sec_instr3")
            and x.get("action") == "added"
            for x in m.get("activity", [])
        ),
        "added row present",
    ),
)

# Instructor folder (mluther, INST-00013): readers = students in sections taught by mluther (CS-A, CS-C) -> stuA yes, stuB no
INS = FX["F_INSTR1"]["name"]
check(
    "4.2 stuA (section taught by owner) download Instructor folder",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": INS},
    200,
    http="GET",
)
check(
    "4.2 stuB (section taught by other) download Instructor folder",
    "stuB",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": INS},
    403,
    http="GET",
)
check(
    "4.2 instr2 (grader) reads any folder",
    "instr2",
    "seminary.api.folder_upload.get_files_in_folder",
    {"course_folder": INS},
    200,
)
upload(
    "instr2",
    FX["F_INSTR1"]["file_reference"],
    "p0_ins_instr2.txt",
    "4.2 instr2 upload to another's Instructor folder -> 403",
)
# share with instr2 -> stuB (taught by instr2 in CS-B) may read
r = call(
    "admin",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Course Folder Instructor Share",
            "parent": INS,
            "parenttype": "Course Folder",
            "parentfield": "shared_with_instructors",
            "instructor": "INST-00003",
        }
    },
)
check(
    "4.2 stuB after share_with_instructors download Instructor folder",
    "stuB",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": INS},
    200,
    http="GET",
)
upload(
    "instr2",
    FX["F_INSTR1"]["file_reference"],
    "p0_ins_instr2b.txt",
    "4.2 instr2 upload after read-only share -> 403",
)

# School folder: any student incl. stuC; guest 403
SCH = FX["F_SCHOOL1"]["name"]
check(
    "4.2 stuC download School folder",
    "stuC",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": SCH},
    200,
    http="GET",
)
check(
    "4.2 guest download School folder",
    "guest",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": SCH},
    403,
    http="GET",
)
# supersedes
r = call(
    "admin",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Course Folder",
            "foldername": "P0 School v2",
            "scope": "School",
            "supersedes": SCH,
        }
    },
)
v2 = (r.json().get("message") or {}) if r.status_code == 200 else {}
if v2:
    check(
        "4.2 old School docname resolves to v2 root",
        "stuA",
        "seminary.api.folder_upload.get_files_in_folder",
        {"course_folder": SCH},
        ok_json(
            lambda m: m.get("folder_id") == v2.get("file_reference"),
            f"folder_id == v2 root {v2.get('file_reference')}",
        ),
    )
else:
    print("SKIP  supersedes: could not create v2", r.status_code, r.text[:200])
check(
    "4.2 folder_context no args",
    "instr2",
    "seminary.seminary.doctype.course_folder.course_folder.folder_context",
    {},
    ok_json(lambda m: "can_school" in m and m.get("course") is None),
)
check(
    "4.2 list_embeddable_folders instr2 on CS-B",
    "instr2",
    "seminary.seminary.doctype.course_folder.course_folder.list_embeddable_folders",
    {"course_schedule": CS_B},
    ok_json(
        lambda m: any(f["name"] == FX["F_COURSE"]["name"] for f in m)
        and any(f["name"] == INS for f in m)
        and not any(f["name"] == SEC for f in m),
        "course + shared instr folder, no CS-A section folder",
    ),
)
check(
    "4.2 list_embeddable_folders student",
    "stuA",
    "seminary.seminary.doctype.course_folder.course_folder.list_embeddable_folders",
    {"course_schedule": CS},
    403,
)


# Template import, same instructor first (CS-A -> CS-C, both taught by mluther)
def run_doc(who, dt, dn, method, args):
    return call(
        who, "run_doc_method", {"dt": dt, "dn": dn, "method": method, "args": args}
    )


def tb(r):
    try:
        e = json.loads(r.json().get("exc", "[]"))[0]
        return " | ".join(
            l.strip() for l in e.splitlines() if "seminary" in l or "Error" in l
        )[-700:]
    except Exception:
        return r.text[:300]


r = check(
    "4.2 reg import template CS-A -> CS-C (same instructor)",
    "reg",
    "run_doc_method",
    {
        "dt": "Course Schedule",
        "dn": CS_C,
        "method": "import_template",
        "args": {"source_cs": CS},
    },
    ok_json(
        lambda m: isinstance(m, dict) and m.get("chapters", 0) >= 1, "chapters copied"
    ),
)
if r is not None and r.status_code == 200:
    print("      result:", json.dumps(r.json().get("message"))[:400])
elif r is not None:
    print("      TRACE:", tb(r))
check(
    "4.2 Section folder re-scoped to Instructor(mluther)",
    "admin",
    "frappe.client.get_value",
    {
        "doctype": "Course Folder",
        "filters": {"name": SEC},
        "fieldname": ["scope", "instructor"],
    },
    ok_json(
        lambda m: m.get("scope") == "Instructor"
        and m.get("instructor") == "INST-00013",
        "scope=Instructor, instructor=INST-00013",
    ),
)
check(
    "4.2 stuA still reads re-scoped folder",
    "stuA",
    "seminary.api.folder_upload.download_folder",
    {"course_folder": SEC},
    200,
    http="GET",
)
r = check(
    "4.2 reg import template CS-A -> CS-B (different instructor)",
    "reg",
    "run_doc_method",
    {
        "dt": "Course Schedule",
        "dn": CS_B,
        "method": "import_template",
        "args": {"source_cs": CS},
    },
    ok_json(
        lambda m: isinstance(m, dict) and m.get("chapters", 0) >= 1, "chapters copied"
    ),
)
if r is not None and r.status_code == 200:
    print("      result:", json.dumps(r.json().get("message"))[:600])
new_ins = (
    call(
        "admin",
        "frappe.client.get_list",
        {
            "doctype": "Course Folder",
            "filters": {
                "scope": "Instructor",
                "instructor": "INST-00003",
                "course": COURSE,
            },
            "fields": ["name", "foldername"],
        },
    )
    .json()
    .get("message")
    or []
)
check(
    "4.2 copies created for instr2 (Instructor folders of mluther incl. re-scoped Section)",
    "admin",
    "frappe.client.get_list",
    {
        "doctype": "Course Folder",
        "filters": {
            "scope": "Instructor",
            "instructor": "INST-00003",
            "course": COURSE,
        },
        "fields": ["name"],
    },
    ok_json(
        lambda m: len(m) >= 2,
        f"{len(new_ins)} instructor folders for INST-00003: {[x['name'] for x in new_ins]}",
    ),
)
for f in new_ins:
    check(
        f"4.2 stuB (CS-B) reads copied folder {f['name']}",
        "stuB",
        "seminary.api.folder_upload.download_folder",
        {"course_folder": f["name"]},
        200,
        http="GET",
    )
    upload(
        "instr3",
        gv("Course Folder", f["name"], "file_reference"),
        "x.txt",
        f"4.2 instr3 upload into instr2's copied folder {f['name']} -> 403",
    )
lessons_b = (
    call(
        "admin",
        "frappe.client.get_list",
        {
            "doctype": "Course Lesson",
            "filters": {"course_sc": CS_B, "lesson_title": ["like", "P0 lesson%"]},
            "fields": ["lesson_title", "content"],
        },
    )
    .json()
    .get("message")
    or []
)
refs = {
    l["lesson_title"]: (
        json.loads(l["content"])["blocks"][1]["data"].get("folder_ref")
        if l.get("content")
        else None
    )
    for l in lessons_b
}
print("      CS-B lesson folder refs:", refs)
from p0check import RESULTS

ok = (
    refs.get("P0 lesson F_COURSE") == FX["F_COURSE"]["name"]
    and refs.get("P0 lesson F_SCHOOL1") == SCH
    and refs.get("P0 lesson F_INSTR1") in {x["name"] for x in new_ins}
    and refs.get("P0 lesson F_SECTION_A") in {x["name"] for x in new_ins}
)
RESULTS.append(
    (
        "4.2 CS-B lesson refs: Course/School kept, Instructor/Section -> copies",
        ok,
        str(refs),
    )
)
print(("PASS " if ok else "FAIL ") + " 4.2 CS-B lesson refs")
check(
    "4.2 stuA cannot import template",
    "stuA",
    "run_doc_method",
    {
        "dt": "Course Schedule",
        "dn": CS_B,
        "method": "import_template",
        "args": {"source_cs": CS},
    },
    403,
)

# ---------------------------------------------------------------- 4.3 F3
check(
    "4.3 stuA roll_pe not whitelisted",
    "stuA",
    "seminary.seminary.api.roll_pe",
    {},
    lambda r: (r.status_code in (403, 404), f"got {r.status_code}"),
)
check(
    "4.3 reg roll_pe not whitelisted",
    "reg",
    "seminary.seminary.api.roll_pe",
    {},
    lambda r: (r.status_code in (403, 404), f"got {r.status_code}"),
)
check(
    "4.3 stuA petb_enroll not whitelisted",
    "stuA",
    "seminary.seminary.api.petb_enroll",
    {"pe_name": FX["PE_A"], "pe_term": 1},
    lambda r: (r.status_code in (403, 404), f"got {r.status_code}"),
)

# ---------------------------------------------------------------- 4.4 F4
att = {
    "course_schedule": CS,
    "date": "2026-09-17",
    "students_present": [{"student": FX["STU_A"], "stuname_roster": "P0"}],
    "students_absent": [],
}
check(
    "4.4 stuA mark_attendance",
    "stuA",
    "seminary.seminary.api.mark_attendance",
    att,
    403,
)
check(
    "4.4 instr3 mark_attendance",
    "instr3",
    "seminary.seminary.api.mark_attendance",
    att,
    not_403,
)
check(
    "4.4 reg mark_attendance (switch on)",
    "reg",
    "seminary.seminary.api.mark_attendance",
    att,
    not_403,
)
sv("Seminary Settings", "Seminary Settings", "registrar_academic_records", 0)
check(
    "4.4 reg mark_attendance (switch off)",
    "reg",
    "seminary.seminary.api.mark_attendance",
    att,
    403,
)
check(
    "4.4 reg get_gradebook (switch off)",
    "reg",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS},
    403,
)
sv("Seminary Settings", "Seminary Settings", "registrar_academic_records", 1)
check(
    "4.4 reg get_gradebook (switch on)",
    "reg",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS},
    200,
)


# ---------------------------------------------------------------- 4.5 F5
def hold():
    m = (
        call("admin", "frappe.client.get", {"doctype": "Student", "name": FX["STU_A"]})
        .json()
        .get("message")
        or {}
    )
    return next(
        (h for h in m.get(FX["hold_field"], []) if h["name"] == FX["hold_row"]), {}
    )


check(
    "4.5 stuA lift_hold",
    "stuA",
    "seminary.seminary.student_standing.lift_hold",
    {"student": FX["STU_A"], "hold_row_name": FX["hold_row"]},
    403,
    after=lambda: (hold().get("is_active") == 1, "hold still active"),
)
check(
    "4.5 reg lift_hold",
    "reg",
    "seminary.seminary.student_standing.lift_hold",
    {"student": FX["STU_A"], "hold_row_name": FX["hold_row"]},
    200,
    after=lambda: (
        hold().get("is_active") == 0 and hold().get("lifted_by") == USERS["reg"],
        "lifted, lifted_by=reg",
    ),
)

# ---------------------------------------------------------------- 4.6 F6
sep = {
    "program_enrollment": FX["PE_B"],
    "withdrawal_reason": FX.get("WREASON") or "P0",
    "separation_status": "Withdrawn",
}
check(
    "4.6 stuA initiate_program_separation",
    "stuA",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request.initiate_program_separation",
    sep,
    403,
)
check(
    "4.6 reg initiate_program_separation",
    "reg",
    "seminary.seminary.doctype.withdrawal_request.withdrawal_request.initiate_program_separation",
    sep,
    not_403,
)

# ---------------------------------------------------------------- 4.7 F7
check(
    "4.7 stuA save_discussion_submission_grade",
    "stuA",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_A"], "grade": 100},
    403,
    after=lambda: (
        (gv("Discussion Submission", FX["DS_A"], "grade") or 0) != 100,
        "grade unchanged",
    ),
)
check(
    "4.7 stuA save_exam_grade",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    {
        "submission_name": FX["ES_A"],
        "status": "Graded",
        "score": 100,
        "percentage": 100,
        "fudge_points": 0,
        "result": [],
    },
    403,
)
check(
    "4.7 stuA save_exam_comment",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_comment",
    {"submission_name": FX["ES_A"], "row_name": FX["ES_A_row"], "comments": "x"},
    403,
)
check(
    "4.7 stuA grade_assignment",
    "stuA",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.grade_assignment",
    {"name": FX["AS_A"], "result": "Graded", "comments": "x"},
    403,
)
check(
    "4.7 stuA fgrade_this_std",
    "stuA",
    "seminary.seminary.api.fgrade_this_std",
    {"name": FX["ROSTER_A"]},
    403,
)
check(
    "4.7 stuA grade_thisstudent",
    "stuA",
    "seminary.seminary.api.grade_thisstudent",
    {"name": FX["ROSTER_A"]},
    403,
)
check(
    "4.7 stuA save_course_assessment",
    "stuA",
    "seminary.seminary.api.save_course_assessment",
    {"course": CS, "assessment_data": []},
    403,
)
check(
    "4.7 stuA insert_cs_assessment",
    "stuA",
    "seminary.seminary.api.insert_cs_assessment",
    {"criteria": {}},
    403,
)
r = check(
    "4.7 stuA save_exam_draft with member=stuB",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_draft",
    {
        "exam": FX["EA"],
        "course": CS,
        "member": STU_B_USER,
        "answers": [],
        "time_taken": 0,
    },
    not_403,
)
if r is not None and r.status_code == 200:
    m = r.json().get("message")
    nm = m.get("name") if isinstance(m, dict) else m
    check(
        "4.7 draft member == stuA",
        "admin",
        "frappe.client.get_value",
        {"doctype": "Exam Submission", "filters": {"name": nm}, "fieldname": "member"},
        ok_json(lambda x: x.get("member") == STU_A_USER, "member is session user"),
    )
else:
    print(
        "      save_exam_draft response:",
        r.status_code if r is not None else None,
        (r.text[:300] if r is not None else ""),
    )
check(
    "4.7 stuA save_exam_draft not enrolled",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_draft",
    {
        "exam": FX["EA"],
        "course": FX["CS2_notA"],
        "member": STU_A_USER,
        "answers": [],
        "time_taken": 0,
    },
    403,
)
check(
    "4.7 stuA submit_exam on stuB draft",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.submit_exam",
    {"submission_name": FX["ES_B"]},
    403,
)
check(
    "4.7 stuA submit_exam own draft",
    "stuA",
    "seminary.seminary.doctype.exam_submission.exam_submission.submit_exam",
    {"submission_name": FX["ES_A"]},
    not_403,
)
check(
    "4.7 stuA upload_assignment on stuB submission",
    "stuA",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.upload_assignment",
    {"submission": FX["AS_B"], "assignment": FX["AA"], "answer": "x"},
    403,
)
check(
    "4.7 stuA upload_assignment own with status=Passed",
    "stuA",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.upload_assignment",
    {
        "submission": FX["AS_A"],
        "assignment": FX["AA"],
        "answer": "<p>own</p>",
        "status": "Graded",
    },
    not_403,
    after=lambda: (
        gv("Assignment Submission", FX["AS_A"], "status") == "Not Graded",
        "status still Not Graded",
    ),
)


# quiz User Input: wrong answer with is_correct [1] -> 0 points; right answer with [0] -> 1 point
def quiz_call(answer, flag):
    return call(
        "stuA",
        "seminary.seminary.doctype.quiz.quiz.quiz_summary",
        {
            "quiz": FX["QUIZ"],
            "course": FX["ST_CS_A"],
            "time_taken": 1,
            "results": [
                {
                    "question_name": FX["Q_USER_INPUT"],
                    "answer": answer,
                    "is_correct": [flag],
                }
            ],
        },
    )


def drop_quiz_subs():
    for qs in (
        call(
            "admin",
            "frappe.client.get_list",
            {
                "doctype": "Quiz Submission",
                "filters": {"quiz": FX["QUIZ"], "member": STU_A_USER},
                "fields": ["name"],
            },
        )
        .json()
        .get("message")
        or []
    ):
        call(
            "admin",
            "frappe.client.delete",
            {"doctype": "Quiz Submission", "name": qs["name"]},
        )


drop_quiz_subs()
r2 = quiz_call("alpha", 0)
drop_quiz_subs()
r1 = quiz_call("wrong", 1)


def score_of(r):
    try:
        m = r.json().get("message")
        return (
            float(m.get("score"))
            if isinstance(m, dict) and m.get("score") is not None
            else None
        )
    except Exception:
        return None


print(
    "      quiz responses:",
    r1.status_code,
    str(r1.text[:150]).replace("\n", " "),
    "|",
    r2.status_code,
    str(r2.text[:150]).replace("\n", " "),
)
RESULTS.append(
    (
        "4.7 quiz User Input server-graded",
        r1.status_code == 200
        and r2.status_code == 200
        and (score_of(r1) or 0) < (score_of(r2) or 0),
        f"wrong={score_of(r1)} right={score_of(r2)}",
    )
)
print(
    ("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.7 quiz User Input server-graded:",
    RESULTS[-1][2],
)
# graders
# p007 §2.4: grading is course-scoped, so instr3 (on CS-A only) grades the
# CS-A submission; the CS-B one is refused.
check(
    "4.7 instr3 save_discussion_submission_grade",
    "instr3",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_A"], "grade": 90},
    not_403,
)
check(
    "4.7 instr3 save_discussion_submission_grade (other section, p007)",
    "instr3",
    "seminary.seminary.api.save_discussion_submission_grade",
    {"submission_name": FX["DS_B"], "grade": 90},
    403,
)
# p008a G2 (p005a A01-12): the grade writers are section-scoped as well as
# role-gated. ES_B / AS_B live in section P0B, where instr3 is NOT staff (they
# are of record on section A only) -- so these two rows used to assert the
# vulnerability itself: an Instructor grading a section they have no stake in.
# They now expect the refusal; instr2, of record on P0B, is the positive case.
check(
    "4.7 instr3 (not on P0B) save_exam_grade is refused (p008a G2)",
    "instr3",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    {
        "submission_name": FX["ES_B"],
        "status": "Graded",
        "score": 1,
        "percentage": 100,
        "fudge_points": 0,
        "result": [],
    },
    403,
)
check(
    "4.7 instr2 (of record on P0B) save_exam_grade",
    "instr2",
    "seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade",
    {
        "submission_name": FX["ES_B"],
        "status": "Graded",
        "score": 1,
        "percentage": 100,
        "fudge_points": 0,
        "result": [],
    },
    not_403,
)
check(
    "4.7 instr3 (not on P0B) grade_assignment is refused (p008a G2)",
    "instr3",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.grade_assignment",
    {"name": FX["AS_B"], "result": "Graded", "comments": "x"},
    403,
)
check(
    "4.7 instr2 (of record on P0B) grade_assignment",
    "instr2",
    "seminary.seminary.doctype.assignment_submission.assignment_submission.grade_assignment",
    {
        "name": FX["AS_B"],
        "result": "Graded",
        "comments": "<!--><img src=x onerror=alert(1)>-->ok",
    },
    not_403,
    after=lambda: (
        "onerror" not in (gv("Assignment Submission", FX["AS_B"], "comments") or ""),
        "comments sanitised",
    ),
)
check(
    "4.7 reg fgrade_this_std",
    "reg",
    "seminary.seminary.api.fgrade_this_std",
    {"name": FX["ROSTER_A"]},
    not_403,
)

# ---------------------------------------------------------------- 4.8 F8
s = jar("stuA")
r = s.get(f"{H}/seminary/courses")
RESULTS.append(
    (
        "4.8 no sid in SPA page",
        r.status_code == 200 and '"sid"' not in r.text and "csrf_token" in r.text,
        f"status {r.status_code}, sid count {r.text.count(chr(34) + 'sid' + chr(34))}, csrf present {'csrf_token' in r.text}",
    )
)
print(("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.8 no sid:", RESULTS[-1][2])

# ---------------------------------------------------------------- 4.9 F9
payload = [
    "x') UNION SELECT name,0,`password`,name,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL FROM `__Auth` WHERE ('1'='1"
]
check(
    "4.9 sqli payload",
    "stuA",
    "seminary.seminary.utils.get_all_questions_details",
    {"questions": payload},
    lambda r: (
        r.status_code in (200, 417)
        and "__Auth" not in r.text
        and "$" not in r.text
        and (r.status_code != 200 or r.json().get("message") == []),
        f"got {r.status_code}, body {r.text[:80]!r}",
    ),
    as_json=True,
)
check(
    "4.9 real question names",
    "stuA",
    "seminary.seminary.utils.get_all_questions_details",
    {"questions": [FX["QQ_ROW"]]},
    ok_json(lambda m: isinstance(m, list) and len(m) == 1, "one row"),
    as_json=True,
)
check(
    "4.9 stuA get_gradebook",
    "stuA",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS},
    403,
)
check(
    "4.9 instr3 get_gradebook",
    "instr3",
    "seminary.seminary.utils.get_gradebook",
    {"course": CS},
    200,
)

# ---------------------------------------------------------------- 4.10 F10
r = call(
    "chair",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Seminary Announcement",
            "subject": '{{ frappe.db.sql("select 1") }}',
            "message": "x",
            "audience_alumni": 1,
        }
    },
)
RESULTS.append(
    (
        "4.10 announcement with sql in subject rejected",
        r.status_code == 417 and "Personalization" in r.text,
        f"got {r.status_code} {r.text[:120]!r}",
    )
)
print(("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.10 sql subject:", RESULTS[-1][2])
r = call(
    "chair",
    "frappe.client.insert",
    {
        "doc": {
            "doctype": "Seminary Announcement",
            "subject": "Hello {{ recipient.first_name }}",
            "message": "P0 {{ recipient.first_name | upper }}",
            "audience_alumni": 1,
        }
    },
)
RESULTS.append(
    (
        "4.10 announcement with recipient token accepted",
        r.status_code == 200,
        f"got {r.status_code} {r.text[:120]!r}",
    )
)
print(("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.10 token subject:", RESULTS[-1][2])

# ---------------------------------------------------------------- 4.11 F11
check(
    "4.11 guest has_student_role",
    "guest",
    "seminary.seminary.utils.has_student_role",
    {"member": STU_A_USER},
    403,
)
check(
    "4.11 guest get_courses_for_student",
    "guest",
    "seminary.seminary.utils.get_courses_for_student",
    {"student": STU_A_USER},
    403,
)
check(
    "4.11 guest get_course_details",
    "guest",
    "seminary.seminary.utils.get_course_details",
    {"course": CS},
    403,
)
check(
    "4.11 stuB get_courses_for_student(student=stuA) -> own",
    "stuB",
    "seminary.seminary.utils.get_courses_for_student",
    {"student": STU_A_USER},
    ok_json(lambda m: all(c["name"] != CS for c in m), "no CS-A (stuA only) in result"),
)
check(
    "4.11 stuA get_course_details CS-A has token",
    "stuA",
    "seminary.seminary.utils.get_course_details",
    {"course": CS},
    ok_json(lambda m: bool(m.get("calendar_token")), "calendar_token present"),
)
check(
    "4.11 stuA get_course_details CS2 no token",
    "stuA",
    "seminary.seminary.utils.get_course_details",
    {"course": FX["CS2_notA"]},
    ok_json(
        lambda m: not m.get("calendar_token")
        and not m.get("web_meeting")
        and all(not d.get("cs_web_meeting") for d in m.get("meeting_dates", [])),
        "token/meeting stripped",
    ),
)
check(
    "4.11 stuA get_courses published=0 forced",
    "stuA",
    "seminary.seminary.utils.get_courses",
    {"filters": {"published": 0}},
    as_json=True,
    expect=ok_json(
        lambda m: all(
            c.get("published", 1) == 1
            for c in (m if isinstance(m, list) else m.get("courses", []))
        ),
        "only published",
    ),
)
check(
    "4.11 reg get_courses published=0",
    "reg",
    "seminary.seminary.utils.get_courses",
    {"filters": {"published": 0}},
    as_json=True,
    expect=ok_json(
        lambda m: len(m if isinstance(m, list) else m.get("courses", [])) > 0,
        "unpublished rows returned",
    ),
)
check(
    "4.11 guest payment url wrong key",
    "guest",
    "seminary.seminary.api.get_application_payment_url",
    {"applicant_name": FX["APP"], "key": "wrong"},
    403,
)
check(
    "4.11 stuA payment url no key",
    "stuA",
    "seminary.seminary.api.get_application_payment_url",
    {"applicant_name": FX["APP"]},
    403,
)
check(
    "4.11 guest payment url right key",
    "guest",
    "seminary.seminary.api.get_application_payment_url",
    {"applicant_name": FX["APP"], "key": FX["APP_KEY"]},
    200,
)
r = jar("guest").get(
    f"{H}/applicant-payment", params={"applicant": FX["APP"], "key": FX["APP_KEY"]}
)
RESULTS.append(
    (
        "4.11 applicant-payment page renders",
        r.status_code == 200,
        f"got {r.status_code}",
    )
)
print(
    ("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.11 applicant page:", RESULTS[-1][2]
)

# ---------------------------------------------------------------- 4.12 F12
check(
    "4.12 stuA regenerate_token",
    "stuA",
    "seminary.seminary.doctype.recommendation_letter.recommendation_letter.regenerate_token",
    {"name": FX["RL_A"]},
    403,
)
check(
    "4.12 reg regenerate_token",
    "reg",
    "seminary.seminary.doctype.recommendation_letter.recommendation_letter.regenerate_token",
    {"name": FX["RL_A"]},
    ok_json(
        lambda m: "token" not in m and "expires_on" in m,
        "no token key, expires_on present",
    ),
)
r1 = call(
    "guest",
    "seminary.seminary.recommender.get_request",
    {"name": "RL-999999", "token": "x"},
)
r2 = call(
    "guest",
    "seminary.seminary.recommender.get_request",
    {"name": FX["RL_A"], "token": "x"},
)


def msg(r):
    try:
        return r.json().get("exception", "")
    except Exception:
        return r.text[:60]


RESULTS.append(
    (
        "4.12 identical error for missing name / wrong token",
        r1.status_code == r2.status_code and msg(r1) == msg(r2),
        f"{r1.status_code}/{r2.status_code} {msg(r1)[:80]!r}",
    )
)
print(
    ("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.12 identical errors:", RESULTS[-1][2]
)
tok = gv("Recommendation Letter", FX["RL_A"], "request_token")
check(
    "4.12 guest get_request with real token",
    "guest",
    "seminary.seminary.recommender.get_request",
    {"name": FX["RL_A"], "token": tok},
    200,
)

# ---------------------------------------------------------------- 4.13 F13
BYPASS = "<!--><img src=x onerror=alert(1)>-->"
ML = '<p>Ação, coração — “aspas” … § ¶ †</p><p>ἐν ἀρχῇ ἦν ὁ λόγος</p><p><span dir="rtl" lang="he">בְּרֵאשִׁית בָּרָא</span></p><p>Text<sup id="fnref1"><a href="#fn1">1</a></sup> H<sub>2</sub>O</p><blockquote cite="x"><p>Quote</p></blockquote><abbr title="Septuagint">LXX</abbr> <cite>Book</cite><table><tbody><tr><td>a</td></tr></tbody></table><strong>b</strong><em>i</em>'
r = call(
    "stuA",
    "frappe.client.set_value",
    {
        "doctype": "Assignment Submission",
        "name": FX["AS_A"],
        "fieldname": "answer",
        "value": BYPASS + ML,
    },
)
if r.status_code == 200:
    nm = FX["AS_A"]
    stored = gv("Assignment Submission", nm, "answer") or ""
    RESULTS.append(
        (
            "4.13 assignment answer: bypass neutralised, multilingual kept",
            "onerror" not in stored
            and "ἐν ἀρχῇ ἦν ὁ λόγος" in stored
            and 'dir="rtl"' in stored
            and "<sup" in stored
            and "<abbr" in stored
            and "coração" in stored,
            f"len {len(stored)}",
        )
    )
else:
    RESULTS.append(
        ("4.13 assignment answer insert", False, f"got {r.status_code} {r.text[:150]}")
    )
print(("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.13 assignment:", RESULTS[-1][2])
r = check(
    "4.13 stuA send_portal_message with bypass",
    "stuA",
    "seminary.seminary.comms.send_portal_message",
    {"recipients": ["PERS-00004"], "subject": "P0", "message": BYPASS + ML},
    not_403,
)
if r is not None:
    print("      portal message:", r.status_code, r.text[:160].replace("\n", " "))
    if r.status_code == 200:
        logs = (
            call(
                "admin",
                "frappe.client.get_list",
                {
                    "doctype": "Communication Log",
                    "filters": {"subject": "P0", "channel": "In-App"},
                    "fields": ["message"],
                    "order_by": "creation desc",
                    "limit_page_length": 1,
                },
            )
            .json()
            .get("message")
            or []
        )
        stored = logs[0]["message"] if logs else ""
        RESULTS.append(
            (
                "4.13 portal message sanitised, multilingual kept",
                bool(logs) and "onerror" not in stored and "ἐν ἀρχῇ" in stored,
                f"logs {len(logs)}",
            )
        )
        print(
            ("PASS " if RESULTS[-1][1] else "FAIL ") + " 4.13 portal message stored:",
            RESULTS[-1][2],
        )

# ---------------------------------------------------------------- 4.14b F14
check(
    "4.14 stuA course_enroll other PE",
    "stuA",
    "seminary.seminary.api.course_enroll",
    {"pe_name": FX["PE_B"], "course": FX["OPEN_CS"]},
    403,
)
sv("Seminary Settings", "Seminary Settings", "allow_portal_enroll", 0)
check(
    "4.14 stuA course_enroll own PE, portal enroll off",
    "stuA",
    "seminary.seminary.api.course_enroll",
    {"pe_name": FX["PE_A"], "course": FX["OPEN_CS"]},
    403,
)
sv("Seminary Settings", "Seminary Settings", "allow_portal_enroll", 1)
check(
    "4.14 stuA course_enroll own PE, portal enroll on",
    "stuA",
    "seminary.seminary.api.course_enroll",
    {"pe_name": FX["PE_A"], "course": FX["OPEN_CS"]},
    not_403,
)

sys.exit(summary())
