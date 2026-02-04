# Copyright (c) 2025, Klisia, Frappe Technologies and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.email.doctype.email_group.email_group import add_subscribers
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
    cstr,
    flt,
    getdate,
    unique,
    get_datetime,
    cint,
    now,
    add_days,
    format_date,
    date_diff,
    get_url,
)
from frappe.model.document import Document
from frappe.translate import get_all_translations
import calendar
from datetime import timedelta
from dateutil import relativedelta
import erpnext
from datetime import datetime
import zipfile
import os
import re
import shutil
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
from seminary.seminary.doctype.course_lesson.course_lesson import save_progress


@frappe.whitelist()
def get_student_group(course_name: str | None = None, user: str | None = None):
    group = frappe.db.sql(
        """
		select r.stuname_roster, r.student, r.stuemail_rc, k.student_group, k.group_instructor
		from `tabScheduled Course Roster` r, `tabStudent Group Link` k, `tabStudent Group` g, `tabStudent Group Members` m
		where r.course_sc = %s and k.parent = r.course_sc and k.student_group = g.name and g.name = m.parent and m.student = r.student and r.stuemail_rc = %s""",
        (course_name, user),
        as_dict=1,
    )
    print("Group fetched: ", group)
    return group[0] if group else {}


@frappe.whitelist()
def get_student_groups_simple(course_name: str | None = None):
    groups = frappe.db.sql(
        """
		select k.student_group, k.group_instructor
		from `tabCourse Schedule` cs, `tabStudent Group Link` k, `tabStudent Group` g
		where cs.name = %s and k.parent = cs.name and k.student_group = g.name""",
        course_name,
        as_dict=1,
    )
    return groups


@frappe.whitelist()
def get_student_groups(course_name: str | None = None):
    groups = frappe.db.sql(
        """
		select k.student_group, k.group_instructor, m.student, m.student_name
		from `tabCourse Schedule` cs, `tabStudent Group Link` k, `tabStudent Group` g, `tabStudent Group Members` m
		where cs.name = %s and k.parent = cs.name and k.student_group = g.name and g.name = m.parent""",
        course_name,
        as_dict=1,
    )
    return groups


def _get_discussion_replies(parent_name: str) -> list[dict]:
    """Return replies for a given discussion submission."""
    replies = frappe.get_all(
        "Discussion Submission Replies",
        filters={"parent": parent_name},
        fields=[
            "reply",
            "reply_attach",
            "member_name",
            "owner",
            "creation",
            "reply_dt",
        ],
        order_by="creation asc",
    )
    return replies


@frappe.whitelist()
def get_discussion_submissions(
    course_name: str | None = None, discussion_id: str | None = None
):
    """Fetch submissions for a discussion activity within a course."""
    if not course_name or not discussion_id:
        raise frappe.ValidationError(_("Course and discussion are required."))

    submissions = frappe.get_all(
        "Discussion Submission",
        filters={
            "coursesc": course_name,
            "disc_activity": discussion_id,
        },
        fields=[
            "name",
            "student_name",
            "student",
            "student_name",
            "original_post",
            "original_attachment",
            "owner",
            "creation",
        ],
        order_by="creation desc",
    )

    # Fetch student groups for the course
    student_groups = get_student_groups(course_name)

    # Append student group and group instructor to each submission
    for submission in submissions:
        submission["replies"] = _get_discussion_replies(submission["name"])
        submission["student_group"] = None
        submission["group_instructor"] = None
        for group in student_groups:
            if group["student"] == submission["student"]:
                submission["student_group"] = group["student_group"]
                submission["group_instructor"] = group["group_instructor"]
                break

    return submissions


@frappe.whitelist()
def get_user_discussion_submission(
    course_name: str | None = None,
    discussion_id: str | None = None,
    owner: str | None = None,
):

    submissions = frappe.get_all(
        "Discussion Submission",
        filters={
            "coursesc": course_name,
            "disc_activity": discussion_id,
            "owner": owner,
        },
        fields=[
            "name",
            "student_name",
            "student",
            "student_name",
            "original_post",
            "original_attachment",
            "owner",
            "creation",
        ],
        order_by="creation desc",
    )

    for submission in submissions:
        submission["replies"] = _get_discussion_replies(submission["name"])

    return submissions


@frappe.whitelist()
def get_user_discussion_replies(
    course_name: str | None = None,
    discussion_id: str | None = None,
    member: str | None = None,
):
    replies = frappe.db.sql(
        """
		select r.reply, r.reply_attach, r.member_name, r.reply_dt, s.original_post, s.student_name
		from `tabDiscussion Submission Replies` r, `tabDiscussion Submission` s
		where s.coursesc = %s and s.disc_activity = %s and r.parent = s.name and r.member = %s
		order by r.creation asc""",
        (course_name, discussion_id, member),
        as_dict=1,
    )
    return replies


@frappe.whitelist()
def save_discussion_submission_grade(submission_name: str, grade: float):
    """Save grade for a discussion submission."""
    if not submission_name:
        raise frappe.ValidationError(_("Submission name is required."))

    submission = frappe.get_doc("Discussion Submission", submission_name)
    submission.grade = grade
    submission.status = "Graded"
    submission.save()
    return {"status": "success", "message": "Grade saved successfully."}


@frappe.whitelist(allow_guest=True)
def get_translations():
    if frappe.session.user != "Guest":
        language = frappe.db.get_value("User", frappe.session.user, "language")
    else:
        language = frappe.db.get_single_value("System Settings", "language")
    return get_all_translations(language)


@frappe.whitelist()
def get_file_info(file_url):
    print("Get File Info called with file_url: ", file_url)
    """Get file info for the given file URL."""
    file_info = frappe.db.get_value(
        "File",
        {"file_url": file_url},
        ["file_name", "file_size", "file_url"],
        as_dict=1,
    )
    return file_info


@frappe.whitelist()
def save_course(course, course_data):

    try:
        if isinstance(course_data, str):
            course_data = json.loads(course_data)
        # Update course details
        frappe.db.set_value(
            "Course Schedule",
            course,
            "short_introduction",
            course_data["short_introduction"],
        )
        frappe.db.set_value(
            "Course Schedule",
            course,
            "course_description_for_lms",
            course_data["course_description_for_lms"],
        )
        frappe.db.set_value(
            "Course Schedule",
            course,
            "course_image",
            course_data["course_image"]["file_url"]
            if course_data["course_image"]
            else None,
        )
        frappe.db.set_value(
            "Course Schedule", course, "published", course_data["published"]
        )

        frappe.db.commit()
        return {"success": True}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error saving course")
        print("Error saving course:", str(e))
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def get_user_info():
    if frappe.session.user == "Guest":
        return None
    user = frappe.db.get_value(
        "User",
        frappe.session.user,
        [
            "name",
            "email",
            "enabled",
            "user_image",
            "full_name",
            "user_type",
            "username",
        ],
        as_dict=1,
    )
    user["roles"] = frappe.get_roles(user.name)
    user.is_instructor = "Academics User" in user.roles
    user.is_moderator = "Seminary Manager" in user.roles
    user.is_evaluator = "Instructor" in user.roles
    user.is_student = "Student" in user.roles
    user.is_system_manager = "System Manager" in user.roles
    user.student = frappe.db.get_value(
        "Student", {"user": user.name, "enabled": 1}, "name"
    )
    return user


@frappe.whitelist()
def get_instructor_info():
    instructor = frappe.db.get_value(
        "Instructor",
        {"user": frappe.session.user},
        [
            "name",
            "instructor_name",
            "user",
            "status",
            "bio",
            "shortbio",
            "profileimage",
        ],
        as_dict=1,
    )
    return instructor


@frappe.whitelist(allow_guest=True)
def get_school_abbr_logo():
    abbr = frappe.db.get_single_value("Website Settings", "app_name")
    logo = frappe.db.get_single_value("Seminary Settings", "logo_portal")
    return {"name": abbr, "logo": logo}


@frappe.whitelist()
def get_course(program):
    """Return list of courses for a particular program
    :param program: Program
    """
    courses = frappe.db.sql(
        """select course, course_name from `tabProgram Course` where parent=%s
		UNION select program_track_course from `tabProgram Track Courses` where parent=%s""",
        (program),
        as_dict=1,
    )
    return courses


@frappe.whitelist()
def get_student_programs(student):
    """Return list of programs for a particular student, with their grades
    :param student: Student
    """
    grades = frappe.db.sql(
        """select pe.program, pe.name as program_enrollment, pe.pgmenrol_active, pe.student, pec.course_name, pec.academic_term, pec.credits, pec.pec_finalgradecode, pec.pec_finalgradenum, pec.status
from `tabProgram Enrollment` pe, `tabProgram Enrollment Course` pec
where pe.name = pec.parent and pe.student = %s""",
        (student),
        as_dict=1,
    )
    return grades


@frappe.whitelist()
def first_term(doc):
    # Set the first term as the current term if no term is set as current
    currentterm = frappe.db.sql(
        """select name from `tabAcademic Term` where iscurrent_acterm = 1"""
    )
    print("Current term is: ", currentterm)
    print("Self.name is: ", doc)
    if not currentterm:
        frappe.db.set_value("Academic Term", doc, "iscurrent_acterm", 1)
        print("The current term has been set to this term.")
    else:
        return print(
            "There is already a current term. Terms will roll automatically according to their dates."
        )


@frappe.whitelist()
def set_iscurrent_acterm(academic_term=None):
    # This is a complex method, as it triggers many others in case there is a change in Academic Term
    # Refer to the other methods for their functionality in detail.
    # Essentially, students will be enrolled in courses for time-based programs, and invoices triggered by New Academic Term (and Year, if applicable) will be generated
    academic_terms = frappe.get_all(
        "Academic Term", filters={}, fields=["name", "term_start_date", "term_end_date"]
    )
    today = getdate()
    currentterm = frappe.db.sql(
        """select name from `tabAcademic Term` where iscurrent_acterm = 1"""
    )
    currentyear = frappe.db.sql(
        """select academic_year from `tabAcademic Term` where iscurrent_acterm = 1"""
    )

    for term in academic_terms:
        if term.term_start_date <= today <= term.term_end_date:
            if term.name != currentterm[0][0]:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
                newyear = frappe.db.get_value(
                    "Academic Term", term.name, "academic_year"
                )
                roll_pe()
                get_inv_data_nat()
                if newyear != currentyear:
                    get_inv_data_nayear()
            else:
                break

        else:
            frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)
    return "Term rolled successfully"


@frappe.whitelist()
def roll_pe():
    # Students' academic terms will advance. In case enrolled in a time-based program, petb_enroll will try to enroll them in courses
    tb = frappe.db.get_single_value("Seminary Settings", "advancetb")
    pes = frappe.get_all(
        "Program Enrollment",
        filters={"pgmenrol_active": 1, "docstatus": 1},
        fields=["name", "current_std_term"],
    )
    for pe in pes:
        pe_name = pe.name
        pe_term = pe.current_std_term
        pe_program = frappe.db.get_value("Program Enrollment", pe_name, "program")
        pe_program_type = frappe.db.get_value("Program", pe_program, "program_type")
        pe_term = pe_term + 1
        frappe.db.set_value("Program Enrollment", pe_name, "current_std_term", pe_term)
        if pe_program_type == "Time-based" and tb == 1:
            petb_enroll(pe_name, pe_term)
        else:
            continue


@frappe.whitelist()
def petb_enroll(pe_name, pe_term):
    # This will try to enroll all active students from time-based programs in courses scheduled for the new academic term and open for enrollment
    currentterm = frappe.db.sql(
        """select name from `tabAcademic Term` where iscurrent_acterm = 1"""
    )
    program = frappe.db.get_value("Program Enrollment", pe_name, "program")
    pecs = frappe.get_all(
        "Program Course",
        filters={"parent": program, "course_term": pe_term},
        fields=["name", "course"],
    )
    cs = frappe.get_all(
        "Course Schedule",
        filters={"academic_term": currentterm, "open_enroll": 1},
        fields=["name", "course"],
    )
    for pec in pecs:
        for cs_course in cs:
            if pec.course == cs_course.course:
                course = pec.course
                try:
                    course_enroll(pe_name, course)
                except Exception as e:
                    # Handle the error here
                    print(f"An error occurred: {str(e)}")

            else:
                continue
    return "No course to enroll"


@frappe.whitelist()
def course_enroll(pe_name, course):
    # This is called for each student in petb_enroll
    student = frappe.get_value("Program Enrollment", pe_name, "student")
    cs = frappe.db.sql(
        """select distinct name from `tabCourse Schedule`
	where academic_term in (select name from `tabAcademic Term` where iscurrent_acterm = 1) and open_enroll = 1 and
	course = %s""",
        course,
    )[0][0]
    doc = frappe.new_doc("Course Enrollment Individual")
    doc.program_ce = pe_name
    doc.student_ce = student
    doc.coursesc_ce = cs
    doc.docstatus = 0
    doc.insert()


@frappe.whitelist()
def credits_pe_track():
    pe = frappe.get_all(
        "Program Enrollment",
        filters={"pgmenrol_active": 1},
        fields=["name", "program", "emphasis_program_track"],
    )

    for p in pe:
        pe_name = p.name
        credits = frappe.db.sql(
            """select coalesce(sum(pec.credits), 0) from
		`tabProgram Enrollment Course` pec, `tabProgram Track Courses` ptc, `tabProgram Enrollment` pe
		where pe.name = pec.parent and
		ptc.parent = pe.program and
		ptc.program_track = pe.emphasis_program_track and pec.status = "Pass" and
		ptc.program_track_course = pec.course_name and pe.name = %s""",
            pe_name,
        )[0][0]
        if credits:
            frappe.db.set_value("Program Enrollment", pe_name, "trackcredits", credits)
        else:
            continue
    return


@frappe.whitelist()
def enroll_student(source_name):
    """Creates a Student Record and returns a Program Enrollment.

    :param source_name: Student Applicant.
    """
    frappe.publish_realtime(
        "enroll_student_progress", {"progress": [1, 4]}, user=frappe.session.user
    )
    student = get_mapped_doc(
        "Student Applicant",
        source_name,
        {
            "Student Applicant": {
                "doctype": "Student",
                "field_map": {
                    "name": "student_applicant",
                },
            }
        },
        ignore_permissions=True,
    )
    student.save()

    student_applicant = frappe.db.get_value(
        "Student Applicant",
        source_name,
        ["program", "academic_term"],
        as_dict=True,
    )
    program_enrollment = frappe.new_doc("Program Enrollment")
    program_enrollment.student = student.name
    program_enrollment.student_name = student.student_name
    program_enrollment.program = student_applicant.program
    program_enrollment.academic_term = student_applicant.academic_term
    program_enrollment.save()

    frappe.publish_realtime(
        "enroll_student_progress", {"progress": [2, 4]}, user=frappe.session.user
    )
    return program_enrollment


@frappe.whitelist()
def check_attendance_records_exist(course_schedule=None, date=None):
    """Check if Attendance Records are made against the specified Course Schedule

    :param course_schedule: Course Schedule.

    :param date: Date.
    """
    if course_schedule:
        return frappe.get_list(
            "Student Attendance", filters={"course_schedule": course_schedule}
        )


@frappe.whitelist()
def mark_attendance(students_present, students_absent, course_schedule=None, date=None):
    """Creates Multiple Attendance Records.

    :param students_present: Students Present JSON.
    :param students_absent: Students Absent JSON.
    :param course_schedule: Course Schedule.
    :param date: Date.
    """
    print(
        "Mark Attendance called with course_schedule: ", course_schedule, "date: ", date
    )

    if course_schedule:
        present = (
            students_present
            if isinstance(students_present, list)
            else json.loads(students_present)
        )
        absent = (
            students_absent
            if isinstance(students_absent, list)
            else json.loads(students_absent)
        )
    print("Present: ", present)
    print("Absent: ", absent)

    for d in present:
        status = "Present"
        make_attendance_records(
            d["student"], d["stuname_roster"], status, course_schedule, date
        )

    for d in absent:
        status = "Absent"
        make_attendance_records(
            d["student"], d["stuname_roster"], status, course_schedule, date
        )

    frappe.db.commit()
    return {"success": True}


def make_attendance_records(
    student, stuname_roster, status, course_schedule=None, date=None
):
    """Creates/Update Attendance Record.

    :param student: Student.
    :param stuname_roster: Student Name.
    :param status: Status (Present/Absent).
    :param course_schedule: Course Schedule.
    :param date: Date.
    """
    print(
        "Student: ",
        student,
        "Status: ",
        status,
        "Course Schedule: ",
        course_schedule,
        "Date: ",
        date,
    )

    # Check if the attendance record already exists
    HasAttendance = frappe.db.exists(
        "Student Attendance",
        {
            "student": student,
            "course_schedule": course_schedule,
            "date": date,
            "docstatus": ("!=", 2),
        },
    )

    if HasAttendance:
        # Fetch the existing record and update it
        student_attendance = frappe.get_doc("Student Attendance", HasAttendance)
        student_attendance.status = status
        student_attendance.stuname_roster = stuname_roster
        student_attendance.save(ignore_permissions=True)
        print(f"Updated existing attendance record for student: {student}")
    else:
        # Create a new attendance record
        student_attendance = frappe.new_doc("Student Attendance")
        student_attendance.student = student
        student_attendance.stuname_roster = stuname_roster
        student_attendance.course_schedule = course_schedule
        student_attendance.date = date
        student_attendance.status = status
        student_attendance.insert(ignore_permissions=True)
        print(f"Created new attendance record for student: {student}")

    # Update the attendance field in Course Schedule Meeting Dates
    csmtd = frappe.db.get_value(
        "Course Schedule Meeting Dates",
        {"cs_meetdate": date, "parent": course_schedule},
        "name",
    )
    frappe.db.set_value(
        "Course Schedule Meeting Dates",
        csmtd,
        "attendance",
        1,
    )


@frappe.whitelist()
def get_student_contacts(student):
    """Returns List of contacts of a Student.

    :param student: Student.
    """
    contacts = frappe.get_all(
        "Student Contacts", fields=["contact"], filters={"parent": student}
    )
    return contacts


@frappe.whitelist()
def get_course_schedule_events(start, end, filters=None):
    """Returns events for Course Schedule Calendar view rendering.

    :param start: Start date-time.
    :param end: End date-time.
    :param filters: Filters (JSON).
    """
    filters = json.loads(filters)
    from frappe.desk.calendar import get_event_conditions

    conditions = get_event_conditions("Course Schedule", filters)

    return frappe.db.sql(
        """SELECT CONCAT (cs.course, ' - ', COALESCE(cs.room, '')) as title,
			cs.course as course,
			timestamp(cm.cs_meetdate, cm.cs_fromtime) as dtstart,
			timestamp(cm.cs_meetdate, cm.cs_totime) as dtend,
			0 as 'allDay',
			cs.color as color
		from `tabCourse Schedule Meeting Dates` cm, `tabCourse Schedule` cs
		where
		cs.name = cm.parent and
		(cm.cs_meetdate between %(start)s and %(end)s )
		{conditions}
		union
		SELECT CONCAT (cs.course, ' - ', COALESCE(cs.room, '')) as title,
			cs.course as course,
			(scac.due_date - INTERVAL 5 HOUR) as dtstart,
			 scac.due_date as dtend,
			0 as 'allDay',
			cs.color as color
		from `tabScheduled Course Assess Criteria` scac, `tabCourse Schedule` cs
		where
		cs.name = scac.parent
		and (scac.due_date between %(start)s and %(end)s )""".format(
            conditions=conditions
        ),
        {"start": start, "end": end},
        as_dict=True,
        update={"allDay": 0},
    )


@frappe.whitelist()
def get_assessment_criteria(course):
    """Returns Assessmemt Criteria and their Weightage from Course Master.

    :param Course: Course
    """
    return frappe.get_all(
        "Course Assessment Criteria",
        fields=["assessment_criteria", "weightage"],
        filters={"parent": course},
        order_by="idx",
    )


@frappe.whitelist()
def get_grade(grading_scale, percentage):
    """Returns Grade based on the Grading Scale and Score.

    :param Grading Scale: Grading Scale
    :param Percentage: Score Percentage Percentage
    """
    grading_scale_intervals = {}
    if not hasattr(frappe.local, "grading_scale"):
        grading_scale = frappe.get_all(
            "Grading Scale Interval",
            fields=["grade_code", "threshold"],
            filters={"parent": grading_scale},
        )
        frappe.local.grading_scale = grading_scale
    for d in frappe.local.grading_scale:
        grading_scale_intervals.update({d.threshold: d.grade_code})
    intervals = sorted(grading_scale_intervals.keys(), key=float, reverse=True)
    for interval in intervals:
        if flt(percentage) >= interval:
            grade = grading_scale_intervals.get(interval)
            break
        else:
            grade = ""
    return grade


@frappe.whitelist()
def get_payers(program_enrollment, method):
    pe = program_enrollment
    pen = pe.name
    active = pe.pgmenrol_active
    student = pe.student
    turn = 1
    while turn <= 2:
        if (
            not frappe.db.exists({"doctype": "Payers Fee Category PE", "pf_pe": pen})
            and turn == 1
        ):
            print("Creating Payers Fee Category PE -turn " + str(turn) + pen)
            pfc = frappe.new_doc("Payers Fee Category PE")
            pfc.pf_pe = pen
            pfc.pf_student = student
            pfc.pf_active = active
            pfc.pf_custgroup = "Student"
            pfc.insert()
            pfc.save()
            turn += 1
        elif (
            frappe.db.exists({"doctype": "Payers Fee Category PE", "pf_pe": pen})
            and turn == 2
        ):
            print("Payers Fee Category PE already exists - turn " + str(turn))
            get_payers_fees(pen)
            break
    return


@frappe.whitelist()
def quizresult_to_card(doc, method):
    # Fetch max grade of the grading scale used for calculations
    max_grade = frappe.db.get_value("Course Schedule", doc.course, "maxnumgrade")
    # Fetch the corresponding Course Assess Results Detail record
    cardname = frappe.db.get_value(
        "Course Assess Results Detail",
        {"assessment_criteria": doc.course_assess, "student_card": doc.student},
        "name",
    )
    card = frappe.get_doc("Course Assess Results Detail", cardname)

    # Update the raw score and extra credit points
    card.rawscore_card = doc.percentage if not doc.extra_credit else ""
    card.actualextrapt_card = (
        (doc.percentage / max_grade) * card.maxextrapoints_card
        if doc.extra_credit
        else ""
    )
    # Save the updated card
    card.save(ignore_permissions=True)


@frappe.whitelist()
def get_payers_fees(pen):

    pfc = frappe.get_doc({"doctype": "Payers Fee Category PE", "pf_pe": pen})

    doc = []
    doc = frappe.db.sql(
        """select pf.pgm_feecategory as feecat, pf.pgm_feeevent as event, s.customer, '1' as percentage, fc.payment_term_template as term
			from `tabProgram Enrollment`pe, `tabStudent` s, `tabProgram` p, `tabProgram Fees` pf, `tabFee Category` fc
			where pe.student = s.name and
			pe.program = p.name and
			p.name = pf.parent and
			pf.pgm_feecategory = fc.name and
			pe.name = %s""",
        (pen),
        as_list=1,
    )
    row_count = frappe.db.sql(
        """select count(pf.pgm_feecategory) from `tabProgram Enrollment`pe, `tabStudent` s, `tabProgram` p, `tabProgram Fees` pf, `tabFee Category` fc
			where pe.student = s.name and
			pe.program = p.name and
			p.name = pf.parent and
			pf.pgm_feecategory = fc.name and
			pe.name = %s""",
        (pen),
    )[0][0]
    i = 0
    while i < row_count:
        feecat = doc[i][0]
        event = doc[i][1]
        customer = doc[i][2]
        term = doc[i][3]
        percentage = doc[i][4]
        print(pen, feecat, event, customer, term, percentage)
        ppe = frappe.new_doc("pgm_enroll_payers")
        ppe.parent = pen
        ppe.parentfield = "pf_payers"
        ppe.parenttype = "Payers Fee Category PE"
        ppe.fee_category = feecat
        ppe.pep_event = event
        ppe.payer = customer
        ppe.payterm_payer = term
        ppe.pay_percent = "100"
        ppe.insert()
        ppe.save()
        i += 1
    return


@frappe.whitelist()
def save_course_assessment(course, assessment_data):
    """Save Course Assessment Criteria.

    :param course: Course.
    :param assessment_data: Assessment Data (JSON).
    """
    import json

    print("Assessment Data:", assessment_data)
    print("Course:", course)

    # If assessment_data is a string, convert it to a dictionary/list
    if isinstance(assessment_data, str):
        assessment_data = json.loads(assessment_data)

    # Get existing documents for the course
    existing_docs = frappe.db.get_all(
        "Scheduled Course Assess Criteria", filters={"parent": course}, fields=["name"]
    )
    existing_doc_names = {doc["name"] for doc in existing_docs}
    print("Existing docs:", existing_doc_names)

    for data in assessment_data:
        # Check if the record exists by verifying if "name" is provided and is in existing_docs.
        if data.get("name") and data["name"] in existing_doc_names:
            # Update the existing record
            doc = frappe.get_doc("Scheduled Course Assess Criteria", data["name"])
            doc.title = data.get("title", "")
            doc.assesscriteria_scac = data.get("assesscriteria_scac", "")
            doc.type = data.get("type", "")
            doc.weight_scac = data.get("weight_scac", 0)
            doc.extracredit_scac = data.get("extracredit_scac", "")
            doc.fudgepoints_scac = data.get("fudgepoints_scac", "")
            doc.quiz = data.get("quiz", "")
            doc.assignment = data.get("assignment", "")
            doc.discussion = data.get("discussion", "")
            doc.exam = data.get("exam", "")
            doc.due_date = data.get("due_date", None)
            # These are usually already set, but include them if needed:
            doc.parent = course
            doc.parentfield = "courseassescrit_sc"
            doc.parenttype = "Course Schedule"
            doc.save(ignore_permissions=True)
            print("Updated doc:", doc.name)
        else:
            # Create a new record if no matching "name" is found.
            doc = frappe.get_doc(
                {
                    "doctype": "Scheduled Course Assess Criteria",
                    "parent": course,
                    "parentfield": "courseassescrit_sc",
                    "parenttype": "Course Schedule",
                    "title": data.get("title", ""),
                    "assesscriteria_scac": data.get("assesscriteria_scac", ""),
                    "type": data.get("type", ""),
                    "weight_scac": data.get("weight_scac", 0),
                    "extracredit_scac": data.get("extracredit_scac", ""),
                    "fudgepoints_scac": data.get("fudgepoints_scac", ""),
                    "quiz": data.get("quiz", ""),
                    "assignment": data.get("assignment", ""),
                    "exam": data.get("exam", ""),
                    "discussion": data.get("discussion", ""),
                }
            )
            doc.insert(ignore_permissions=True)
            print("Created new doc:", doc.name)

    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def get_scholarship(student):
    scholarship = frappe.get_all(
        "Payers Fee Category PE",
        filters={"stu_link": student, "pf_active": 1},
        fields=["scholarship"],
    )
    return scholarship


@frappe.whitelist()
def get_student_invoices(student):
    sales_invoice_list = []

    sales_invoice_list = frappe.get_all(
        "Sales Invoice",
        filters={"custom_student": student},
        fields=[
            "name",
            "customer",
            "posting_date",
            "total",
            "outstanding_amount",
            "status",
        ],
    )
    for invoice in sales_invoice_list:
        invoice["name"] = frappe.get_value("Sales Invoice", invoice["name"], "name")
        invoice["customer"] = frappe.get_value(
            "Customer", invoice["customer"], "customer_name"
        )
        invoice["posting_date"] = frappe.utils.formatdate(invoice["posting_date"])
        invoice["status"] = "Paid" if invoice["status"] == "Paid" else "Unpaid"
        invoice["total"] = "{:,.2f}".format(invoice["total"])
        invoice["outstanding_amount"] = "{:,.2f}".format(invoice["outstanding_amount"])
    sales_invoice_list = sorted(
        sales_invoice_list, key=lambda x: (x["status"], x["posting_date"]), reverse=True
    )
    print(sales_invoice_list)

    return sales_invoice_list


def get_posting_date_from_payment_entry_against_sales_invoice(sales_invoice):
    payment_entry = frappe.qb.DocType("Payment Entry")
    payment_entry_reference = frappe.qb.DocType("Payment Entry Reference")
    q = (
        frappe.qb.from_(payment_entry)
        .inner_join(payment_entry_reference)
        .on(payment_entry.name == payment_entry_reference.parent)
        .select(payment_entry.posting_date)
        .where(payment_entry_reference.reference_name == sales_invoice)
    ).run(as_dict=1)
    payment_date = q[0].get("posting_date")
    return payment_date


@frappe.whitelist()
def courses_for_student(program_ce):

    pgen_name = program_ce
    # This query is to get the available scheduled courses for the student based on the program enrollment, program track and the academic term, checking for pre-requisites

    courses = frappe.db.sql(
        """select cs.course
		from `tabCourse Schedule` cs, `tabAcademic Term` aterm
		where aterm.name = cs.academic_term and
		cs.open_enroll = '1' and
		aterm.iscurrent_acterm = '1' and cs.course in
		((select pc.course
		from `tabProgram Enrollment` pe, `tabProgram Course` pc
		where pe.program = pc.parent and
		pe.name = %s)
		UNION
		(select ptc.program_track_course
		from `tabProgram Enrollment` pe, `tabProgram Track Courses` ptc
		where pe.pgmenrol_active = '1' and
		ptc.parent = pe.program and
		pe.emphasis_program_track = ptc.program_track and
		pe.name = %s)) and
		cs.course not in (select c.name
		from `tabCourse` c, `tabCourse_prerequisite` cp
		where cp.parent = c.name and
		cp.prereq_mandatory = "Mandatory" and
		c.name not in
		(select pec.course
		from `tabCourse_prerequisite` cp, `tabProgram Enrollment Course` pec
		where cp.parent = pec.course and
		pec.parent = %s and
		pec.pec_finalgradecode is not null)) and
		cs.course not in (select pc.course
		from `tabProgram` p, `tabProgram Course` pc, `tabProgram Enrollment` pe
		where p.name = pc.parent and
		p.name = pe.program and
		pe.name = %s and
		p.program_type = 'Time-based' and
		pc.course_term > pe.current_std_term) and
		cs.course not in (select ptc.program_track_course
		from `tabProgram` p, `tabProgram Track Courses` ptc, `tabProgram Enrollment` pe
		where p.name = ptc.parent and
		p.name = pe.program and
		pe.name = %s and
		p.program_type = 'Time-based' and
		ptc.term > pe.current_std_term) and cs.course not in
		(select course_data from `tabCourse Enrollment Individual` where audit = 0 and
		docstatus != '2' and program_ce = %s)""",
        (pgen_name, pgen_name, pgen_name, pgen_name, pgen_name, pgen_name),
        as_list=1,
    )
    # Flatten the list of tuples into a list of strings
    courses = [course[0] for course in courses]
    return courses


@frappe.whitelist()
def copy_data_to_scheduled_course_roster(doc, method):
    student_ce = doc.student_ce
    program = doc.program_data
    coursesc_ce = doc.coursesc_ce
    audit = doc.audit
    student_name = doc.student_name
    student_email = doc.stu_user
    image = doc.stuimage

    if coursesc_ce and student_ce:
        items = []
        criteria = []
        enrollments = frappe.db.get_value("Course Schedule", coursesc_ce, "enrollments")
        if enrollments:
            enrollments += 1
        else:
            enrollments = 1
        frappe.db.set_value("Course Schedule", coursesc_ce, "enrollments", enrollments)
        criteria = frappe.db.sql(
            """select distinct scac.name, scac.weight_scac, extracredit_scac, fudgepoints_scac from `tabScheduled Course Assess Criteria` scac
			where scac.docstatus = 0 and
			scac.parent = %s""",
            coursesc_ce,
            as_list=1,
        )
        rows = frappe.db.sql(
            """select count(distinct scac.name) from `tabScheduled Course Assess Criteria` scac
			where scac.docstatus = 0 and
			scac.parent = %s""",
            coursesc_ce,
        )[0][0]
        i = 0
        while i < rows:
            if criteria:
                items.append(
                    {
                        "doctype": "Course Assess Results Detail",
                        "student_card": student_ce,
                        "assessment_criteria": criteria[i][0],
                        "maximum_score": criteria[i][1],
                        "extracredit_card": criteria[i][2],
                        "maxextrapoints_card": criteria[i][3],
                    }
                )
                i += 1

        roster = frappe.get_doc(
            {
                "doctype": "Scheduled Course Roster",
                "course_sc": coursesc_ce,
                "stuname_roster": student_name,
                "student": student_ce,
                "stuemail_rc": student_email,
                "program_std_scr": program,
                "audit_bool": audit,
                "active": 1,
                "stuimage": image,
                "fscore": "",
                "fgrade": "",
                "stdroster_grade": items,
            }
        )
        roster.insert()
        roster.save()
    return


@frappe.whitelist()
def copy_data_to_program_enrollment_course(doc, method):
    cei = doc.program_ce
    course_lnk = doc.coursesc_ce
    course = doc.course_data
    ac_term = doc.academic_term
    credits = doc.credits

    if cei:
        program_enrollment_course = frappe.new_doc("Program Enrollment Course")
        program_enrollment_course.parent = cei
        program_enrollment_course.parenttype = "Program Enrollment"
        program_enrollment_course.parentfield = "courses"
        program_enrollment_course.course = course_lnk
        program_enrollment_course.course_name = course
        program_enrollment_course.academic_term = ac_term
        program_enrollment_course.credits = credits
        program_enrollment_course.status = "Enrolled"
        program_enrollment_course.insert()


@frappe.whitelist()
def update_card(doc, method):
    # define who needs update
    existings = frappe.db.sql(
        """
				SELECT r.name
				FROM `tabCourse Assess Results Detail` r, `tabScheduled Course Roster` cr
				WHERE r.parent = cr.name
				AND cr.course_sc = %s
				AND EXISTS (
					SELECT 1
					FROM `tabScheduled Course Assess Criteria` scac
					WHERE scac.name = r.assessment_criteria
					AND scac.name = %s
				)
				""",
        (doc.parent, doc.name),
        as_dict=True,
    )
    if existings:
        for existing in existings:
            # Update the existing record
            changed = frappe.get_doc("Course Assess Results Detail", existing)
            changed.maximum_score = doc.weight_scac
            changed.extracredit_card = doc.extracredit_scac
            changed.maxextrapoints_card = doc.fudgepoints_scac
            changed.assessment_title = doc.title
            changed.save()
    else:
        # Get need data for new records
        new_records = frappe.db.sql(
            """
			SELECT DISTINCT cr.name, cr.student
			FROM `tabScheduled Course Roster` cr
			WHERE cr.course_sc = %s
			AND cr.name NOT IN (
				SELECT r.parent
				FROM `tabCourse Assess Results Detail` r
				WHERE r.assessment_criteria = %s
			)
			""",
            (doc.parent, doc.name),
            as_dict=True,
        )

        for record in new_records:
            new = frappe.new_doc("Course Assess Results Detail")
            new.parent = record.name
            new.parenttype = "Scheduled Course Roster"
            new.parentfield = "stdroster_grade"
            new.student_card = record.student
            new.assessment_criteria = doc.name
            new.maximum_score = doc.weight_scac
            new.extracredit_card = doc.extracredit_scac
            new.maxextrapoints_card = doc.fudgepoints_scac
            new.assessment_title = doc.title
            new.insert()


@frappe.whitelist()
def get_inv_data_nat():
    print("Method called")
    today = frappe.utils.today()
    company = frappe.defaults.get_defaults().company
    currency = erpnext.get_company_currency(company)
    receivable_account = frappe.db.get_single_value(
        "Seminary Settings", "receivable_account"
    )
    income_account = frappe.db.sql(
        """select default_income_account from `tabCompany` where name=%s""", company
    )[0][0]
    company = frappe.db.get_single_value("Seminary Settings", "company")
    cost_center = frappe.db.get_single_value("Seminary Settings", "cost_center") or None
    inv_data = []
    inv_data = frappe.db.sql(
        """select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Term'""",
        as_list=1,
    )
    rows = frappe.db.sql(
        """select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Term'"""
    )[0][0]

    i = 0
    while i < rows:
        print("Creating Invoice - " + str(i) + " of " + str(rows) + " rows")
        print(income_account)

        items = []
        items.append(
            {
                "doctype:": "Sales Invoice Item",
                "item_name": inv_data[i][9],
                "qty": inv_data[i][4] / 100,
                "rate": 0,
                "description": "Fee for " + inv_data[i][1],
                "income_account": income_account,
                "cost_center": cost_center,
                "base_rate": 0,
                "price_list_rate": inv_data[i][11],
            }
        )

        sales_invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "naming_series": "ACC-SINV-.YYYY.-",
                "posting_date": today,
                "company": company,
                "currency": currency,
                "debit_to": receivable_account,
                "income_account": income_account,
                "conversion_rate": 1,
                "customer": inv_data[i][2],
                "selling_price_list": inv_data[i][10],
                "base_grand_total": inv_data[i][11],
                "payment_terms_template": inv_data[i][5],
                "items": items,
            }
        )
        sales_invoice.run_method("set_missing_values")
        sales_invoice.insert()
        sales_invoice.save()
        i += 1
        print("Invoice Created")
    return "done"


@frappe.whitelist()
def get_inv_data_nayear():
    print("Method called")
    today = frappe.utils.today()
    company = frappe.defaults.get_defaults().company
    currency = erpnext.get_company_currency(company)
    receivable_account = frappe.db.get_single_value(
        "Seminary Settings", "receivable_account"
    )
    income_account = frappe.db.sql(
        """select default_income_account from `tabCompany` where name=%s""", company
    )[0][0]
    company = frappe.db.get_single_value("Seminary Settings", "company")
    cost_center = frappe.db.get_single_value("Seminary Settings", "cost_center") or None
    inv_data = []
    inv_data = frappe.db.sql(
        """select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Year'""",
        as_list=1,
    )
    rows = frappe.db.sql(
        """select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'New Academic Year'"""
    )[0][0]

    i = 0
    while i < rows:
        print("Creating Invoice - " + str(i) + " of " + str(rows) + " rows")
        print(income_account)

        items = []
        items.append(
            {
                "doctype:": "Sales Invoice Item",
                "item_name": inv_data[i][9],
                "qty": inv_data[i][4] / 100,
                "rate": 0,
                "description": "Fee for " + inv_data[i][1],
                "income_account": income_account,
                "cost_center": cost_center,
                "base_rate": 0,
                "price_list_rate": inv_data[i][11],
            }
        )

        sales_invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "naming_series": "ACC-SINV-.YYYY.-",
                "posting_date": today,
                "company": company,
                "currency": currency,
                "debit_to": receivable_account,
                "income_account": income_account,
                "conversion_rate": 1,
                "customer": inv_data[i][2],
                "selling_price_list": inv_data[i][10],
                "base_grand_total": inv_data[i][11],
                "payment_terms_template": inv_data[i][5],
                "items": items,
            }
        )
        sales_invoice.run_method("set_missing_values")
        sales_invoice.insert()
        sales_invoice.save()
        i += 1
        print("Invoice Created")
    return "done"


@frappe.whitelist()
def insert_cs_assessment(criteria):
    # If criteria is already a dict, use it directly.
    # If it's a string, then parse it.
    if isinstance(criteria, str):
        criteria = json.loads(criteria)

    # Now, criteria is a dict and you can work with it:
    frappe.logger().info(f"Received criteria: {criteria}")

    # Insert your logic to save the assessment, for example:
    doc = frappe.get_doc(
        {
            "doctype": "Scheduled Course Assess Criteria",
            "parent": criteria.get("parent"),
            "parenttype": "Course Schedule",
            "parentfield": "courseassescrit_sc",
            "title": criteria.get("title"),
            "assesscriteria_scac": criteria.get("assesscriteria_scac"),
            "type": criteria.get("type"),
            "weight_scac": criteria.get("weight_scac"),
            "quiz": criteria.get("quiz"),
            "exam": criteria.get("exam"),
            "assignment": criteria.get("assignment"),
            "extracredit_scac": criteria.get("extracredit_scac"),
            "fudgepoints_scac": criteria.get("fudgepoints_scac"),
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_inv_data_monthly():
    print("Method called")
    today = frappe.utils.today()
    company = frappe.defaults.get_defaults().company
    currency = erpnext.get_company_currency(company)
    receivable_account = frappe.db.get_single_value(
        "Seminary Settings", "receivable_account"
    )
    income_account = frappe.db.sql(
        """select default_income_account from `tabCompany` where name=%s""", company
    )[0][0]
    company = frappe.db.get_single_value("Seminary Settings", "company")
    cost_center = frappe.db.get_single_value("Seminary Settings", "cost_center") or None
    inv_data = []
    inv_data = frappe.db.sql(
        """select pfc.pf_student as student, pep.fee_category, pep.payer as Customer, pfc.pf_custgroup, pep.pay_percent, pep.payterm_payer, pep.pep_event, fc.feecategory_type, fc.is_credit, fc.item, cg.default_price_list, ip.price_list_rate
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg, `tabItem Price` ip
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		cg.default_price_list = ip.price_list and
		ip.item_code = fc.item and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'Monthly'""",
        as_list=1,
    )
    rows = frappe.db.sql(
        """select count(pep.fee_category)
		from `tabpgm_enroll_payers` pep, `tabPayers Fee Category PE` pfc, `tabFee Category` fc, `tabCustomer Group` cg
		where pep.parent = pfc.name and
		pep.fee_category = fc.category_name and
		pep.fee_category = fc.name and
		pfc.pf_custgroup = cg.customer_group_name and
		pfc.pf_active = 1 and
		pep.pep_event = 'Monthly'"""
    )[0][0]

    i = 0
    while i < rows:
        print("Creating Invoice - " + str(i) + " of " + str(rows) + " rows")
        print(income_account)

        items = []
        items.append(
            {
                "doctype:": "Sales Invoice Item",
                "item_name": inv_data[i][9],
                "qty": inv_data[i][4] / 100,
                "rate": 0,
                "description": "Fee for " + inv_data[i][1],
                "income_account": income_account,
                "cost_center": cost_center,
                "base_rate": 0,
                "price_list_rate": inv_data[i][11],
            }
        )

        sales_invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "naming_series": "ACC-SINV-.YYYY.-",
                "posting_date": today,
                "company": company,
                "currency": currency,
                "debit_to": receivable_account,
                "income_account": income_account,
                "conversion_rate": 1,
                "student": inv_data[i][0],
                "customer": inv_data[i][2],
                "selling_price_list": inv_data[i][10],
                "base_grand_total": inv_data[i][11],
                "payment_terms_template": inv_data[i][5],
                "items": items,
            }
        )
        sales_invoice.run_method("set_missing_values")
        sales_invoice.insert()
        sales_invoice.save()
        i += 1
        print("Invoice Created")
    return "done"


@frappe.whitelist()
def get_pgmenrollments(name):
    program_enrollments = []
    program_enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": name},
        fields=["program", "pgmenrol_active", "enrollment_date", "date_of_conclusion"],
    )
    if not program_enrollments:
        return
    else:
        return program_enrollments


@frappe.whitelist()
def get_course_rosters(name):
    course_rosters = []
    course_rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": name},
        fields=[
            "course_sc",
            "stuname_roster",
            "stuimage",
            "student",
            "stuemail_rc",
            "program_std_scr",
            "audit_bool",
            "active",
        ],
    )
    if not course_rosters:
        print("No course rosters found")
        return []
    else:
        return course_rosters


@frappe.whitelist()
def grade_thisstudent(name):

    csr = frappe.get_doc("Scheduled Course Roster", name)
    cs = csr.course_sc
    course = frappe.get_doc("Course Schedule", cs)
    gscale = course.gradesc_cs
    grading_scale = frappe.get_doc("Grading Scale", gscale)
    gmax = grading_scale.maxnumgrade
    detail = csr.stdroster_grade
    if grading_scale.grscale_type == "Points":
        for row in detail:
            score = row.rawscore_card
            maxscore = row.maximum_score
            named = row.name
            extracredit = row.extracredit_card
            if score is not None and extracredit == 0:
                wscore = round((score / gmax) * maxscore, 2)
                row.grade = get_grade(grading_scale, score)
                row.score = wscore

            frappe.db.set_value(
                "Course Assess Results Detail",
                named,
                {"grade": row.grade, "score": row.score},
            )
        csr.save()
        return "done"


@frappe.whitelist()
def get_gradepass(grading_scale, percentage):
    """Returns Grade based on the Grading Scale and Score.

    :param Grading Scale: Grading Scale
    :param Percentage: Score Percentage Percentage
    """
    grading_scale_intervals = {}
    if not hasattr(frappe.local, "grading_scale_pass"):
        grading_scale = frappe.get_all(
            "Grading Scale Interval",
            fields=["grade_pass", "threshold"],
            filters={"parent": grading_scale},
        )
        frappe.local.grading_scale = grading_scale
    for d in frappe.local.grading_scale:
        grading_scale_intervals.update({d.threshold: d.grade_pass})
    intervals = sorted(grading_scale_intervals.keys(), key=float, reverse=True)
    for interval in intervals:
        if flt(percentage) >= interval:
            gradepass = grading_scale_intervals.get(interval)
            print(gradepass)
            break
        else:
            gradepass = ""
    return gradepass


@frappe.whitelist()
def fgrade_this_std(name):
    print("fgrade_this_std called")
    csr = frappe.get_doc("Scheduled Course Roster", name)
    cs = csr.course_sc
    course = frappe.get_doc("Course Schedule", cs)
    gscale = course.gradesc_cs
    grading_scale = frappe.get_doc("Grading Scale", gscale)
    if grading_scale.grscale_type == "Points":
        fscore1 = frappe.db.sql(
            """select sum(score) from `tabCourse Assess Results Detail` where parent = %s""",
            (name),
        )
        fscore1 = fscore1[0][0] if fscore1 and fscore1[0][0] is not None else 0
        fscore2 = frappe.db.sql(
            """select sum(actualextrapt_card) from `tabCourse Assess Results Detail` where extracredit_card = 1 and parent = %s""",
            (name),
        )
        fscore2 = fscore2[0][0] if fscore2 and fscore2[0][0] is not None else 0
        fscore = fscore1 + fscore2
        if fscore >= 100:
            fscore = 100
        else:
            fscore = fscore
        frappe.db.set_value("Scheduled Course Roster", name, "fscore", fscore)
        print(fscore)
        fgrade = get_grade(grading_scale, fscore)
        frappe.db.set_value("Scheduled Course Roster", name, "fgrade", fgrade)
        fgradepass = get_gradepass(grading_scale, fscore)
        print(fgradepass)
        frappe.db.set_value("Scheduled Course Roster", name, "fgradepass", fgradepass)
        return "done"


@frappe.whitelist()
def send_grades(doc=None, **kwargs):

    if isinstance(doc, str):
        # Parse the JSON string if it's a string
        document_data = json.loads(doc)
        docname = document_data.get("name")
    else:
        # Use doc.get("name") if it's already a dictionary (fallback)
        docname = doc.get("name")
    print(docname)
    records = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": docname},
        fields=[
            "name",
            "course_sc",
            "stuname_roster",
            "student",
            "program_std_scr",
            "audit_bool",
            "active",
        ],
    )
    for record in records:
        # Process each record here
        named = record.name
        print(named)
        course_sc = record.course_sc
        student = record.student
        program = record.program_std_scr
        audit_bool = record.audit_bool
        active = record.active
        pe = frappe.db.get_value(
            "Program Enrollment", {"student": student, "program": program}, "name"
        )
        totalcredits = frappe.db.get_value("Program Enrollment", pe, "totalcredits")
        # Perform further operations with the record
        if audit_bool == 0 and active == 1:
            grade_thisstudent(named)
            fgrade_this_std(named)
            fscore = frappe.db.get_value("Scheduled Course Roster", named, "fscore")
            fgrade = frappe.db.get_value("Scheduled Course Roster", named, "fgrade")
            fgradepass = frappe.db.get_value(
                "Scheduled Course Roster", named, "fgradepass"
            )
            pec = frappe.db.get_value(
                "Program Enrollment Course", {"parent": pe, "course": course_sc}, "name"
            )
            credits = frappe.db.get_value("Program Enrollment Course", pec, "credits")
            if fgradepass == "Fail":
                credits = 0
            newcredits = totalcredits + (int(credits) if credits is not None else 0)
            print(newcredits)
            frappe.db.set_value(
                "Program Enrollment Course",
                pec,
                {
                    "pec_finalgradenum": fscore,
                    "pec_finalgradecode": fgrade,
                    "status": fgradepass,
                },
            )
            frappe.db.set_value("Program Enrollment", pe, "totalcredits", newcredits)
            frappe.db.set_value(
                "Scheduled Course Roster", named, {"active": "0", "docstatus": "1"}
            )
        else:
            continue
    frappe.db.set_value(
        "Course Schedule",
        docname,
        {"grades_sent": "1", "open_enroll": "0", "docstatus": "1"},
    )
    return "All grades sent"
    # Add a message to confirm to the user


@frappe.whitelist()
def course_event(name):
    course = frappe.get_doc("Course Schedule", name)
    color = course.color
    datest = str(course.c_datestart)  # Convert datet to a string
    timest = str(course.from_time)  # Convert timest to a string
    datetimest = datest + " " + timest
    datetimest = datetime.strptime(
        datetimest, "%Y-%m-%d %H:%M:%S"
    )  # Convert datetimest to a datetime object
    print(datetimest)
    datef = str(course.c_dateend)  # Convert datef to a string
    timef = str(course.to_time)  # Convert timef to a string
    datetimef = datef + " " + timef
    datetimef = datetime.strptime(datetimef, "%Y-%m-%d %H:%M:%S")
    datetimef2 = datest + " " + timef
    datetimef2 = datetime.strptime(datetimef2, "%Y-%m-%d %H:%M:%S")
    dateend = course.c_dateend
    print(datetimef)
    participants = []
    participants = frappe.get_all(
        "Scheduled Course Roster", filters={"course_sc": name}
    )
    event_participants = []  # Create an empty list for event participants
    for participant in participants:
        event_participants.append(
            {
                "reference_doctype": "Scheduled Course Roster",
                "reference_docname": participant.name,
                "email": participant.stuemail_rc,
            }
        )
    instructors = []
    instructors = frappe.get_all("Course Schedule Instructor", filters={"parent": name})
    for instructor in instructors:
        event_participants.append(
            {
                "reference_doctype": "Course Schedule Instructor",
                "reference_docname": instructor.name,
                "email": instructor.user,
            }
        )
    if datef == datest:
        # Create a new single day calendar event
        event = frappe.get_doc(
            {
                "doctype": "Event",
                "subject": name,
                "starts_on": datetimest,
                "ends_on": datetimef,
                "event_type": "Public",
                "event_category": "Event",
                "color": color,
                "description": name + " Room: " + (course.room or "N/A"),
                "event_participants": event_participants,
            }
        )
    elif datef > datest:
        # Create a new calendar event for meeting dates
        event = frappe.get_doc(
            {
                "doctype": "Event",
                "subject": name,
                "starts_on": datetimest,
                "ends_on": datetimef2,
                "repeat_this_event": 1,
                "repeat_on": "Weekly",
                "repeat_till": dateend,
                "monday": course.monday,
                "tuesday": course.tuesday,
                "wednesday": course.wednesday,
                "thursday": course.thursday,
                "friday": course.friday,
                "saturday": course.saturday,
                "sunday": course.sunday,
                "event_type": "Public",
                "event_category": "Event",
                "color": color,
                "description": name + " Room: " + (course.room or "N/A"),
                "event_participants": event_participants,
            }
        )
    event.insert()
    print(event)

    return "event created"


@frappe.whitelist(allow_guest=True)
def get_doctrinal_statement():
    doctrinal_statement = frappe.get_doc("Doctrinal Statement")
    doctrinal_statement = doctrinal_statement.doctrinalst

    return doctrinal_statement


@frappe.whitelist(allow_guest=True)
def active_term():
    at = frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "name")
    ay = frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "academic_year")
    return {"academic_term": at, "academic_year": ay}


@frappe.whitelist()
def upsert_chapter(chapter_title, course, is_scorm_package, scorm_package, name=None):
    course_title = frappe.get_value("Course Schedule", course, "course")
    values = frappe._dict(
        {
            "chapter_title": chapter_title,
            "coursesc": course,
            "is_scorm_package": is_scorm_package,
            "course_title": course_title,
        }
    )

    if is_scorm_package:
        scorm_package = frappe._dict(scorm_package)
        extract_path = extract_package(course, chapter_title, scorm_package)

        values.update(
            {
                "scorm_package": scorm_package.name,
                "scorm_package_path": extract_path.split("public")[1],
                "manifest_file": get_manifest_file(extract_path).split("public")[1],
                "launch_file": get_launch_file(extract_path).split("public")[1],
            }
        )

    if name:
        chapter = frappe.get_doc("Course Schedule Chapter", name)
    else:
        chapter = frappe.new_doc("Course Schedule Chapter")

    chapter.update(values)
    chapter.save()

    if is_scorm_package and not len(chapter.lessons):
        add_lesson(chapter_title, chapter.name, course)

    return chapter


def extract_package(course, chapter_title, scorm_package):
    package = frappe.get_doc("File", scorm_package.name)
    zip_path = package.get_full_path()
    # check_for_malicious_code(zip_path)
    extract_path = frappe.get_site_path("public", "scorm", course, chapter_title)
    zipfile.ZipFile(zip_path).extractall(extract_path)
    return extract_path


def check_for_malicious_code(zip_path):
    suspicious_patterns = [
        # Unsafe inline JavaScript
        r'on(click|load|mouseover|error|submit|focus|blur|change|keyup|keydown|keypress|resize)=".*?"',  # Inline event handlers (e.g., onerror, onclick)
        r'<script.*?src=["\']http',  # External script tags
        r"eval\(",  # Usage of eval()
        r"Function\(",  # Usage of Function constructor
        r"(btoa|atob)\(",  # Base64 encoding/decoding
        # Dangerous XML patterns
        r"<!ENTITY",  # XXE-related
        r"<\?xml-stylesheet .*?>",  # External stylesheets in XML
    ]

    with zipfile.ZipFile(zip_path, "r") as zf:
        for file_name in zf.namelist():
            if file_name.endswith((".html", ".js", ".xml")):
                with zf.open(file_name) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    for pattern in suspicious_patterns:
                        if re.search(pattern, content):
                            frappe.throw(
                                _("Suspicious pattern found in {0}: {1}").format(
                                    file_name, pattern
                                )
                            )


def get_manifest_file(extract_path):
    manifest_file = None
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file == "imsmanifest.xml":
                manifest_file = os.path.join(root, file)
                break
        if manifest_file:
            break
    return manifest_file


def get_launch_file(extract_path):
    launch_file = None
    manifest_file = get_manifest_file(extract_path)

    if manifest_file:
        with open(manifest_file) as file:
            data = file.read()
            dom = parseString(data)
            resource = dom.getElementsByTagName("resource")
            for res in resource:
                if (
                    res.getAttribute("adlcp:scormtype") == "sco"
                    or res.getAttribute("adlcp:scormType") == "sco"
                ):
                    launch_file = res.getAttribute("href")
                    break

        if launch_file:
            launch_file = os.path.join(os.path.dirname(manifest_file), launch_file)

    return launch_file


def add_lesson(lesson_title, chapter, course_sc):
    lesson = frappe.new_doc("Course Lesson")
    lesson.update(
        {
            "title": lesson_title,
            "chapter": chapter,
            "course": course_sc,
        }
    )
    lesson.insert()

    lesson_reference = frappe.new_doc("Course Schedule Lesson Reference")
    lesson_reference.update(
        {
            "lesson": lesson.name,
            "parent": chapter,
            "parenttype": "Course Schedule Chapter",
            "parentfield": "lessons",
        }
    )
    lesson_reference.insert()


@frappe.whitelist()
def delete_chapter(chapter):
    chapterInfo = frappe.db.get_value(
        "Course Schedule Chapter",
        chapter,
        ["is_scorm_package", "scorm_package_path"],
        as_dict=True,
    )

    if chapterInfo.is_scorm_package:
        delete_scorm_package(chapterInfo.scorm_package_path)

    frappe.db.delete("Course Schedule Chapter Reference", {"chapter": chapter})
    frappe.db.delete("Course Schedule Lesson Reference", {"parent": chapter})
    frappe.db.delete("Course Lesson", {"chapter": chapter})
    frappe.db.delete("Course Schedule Chapter", chapter)


def delete_scorm_package(scorm_package_path):
    scorm_package_path = frappe.get_site_path("public", scorm_package_path[1:])
    if os.path.exists(scorm_package_path):
        shutil.rmtree(scorm_package_path)


@frappe.whitelist()
def mark_lesson_progress(course, chapter_number, lesson_number):
    chapter_name = frappe.get_value(
        "Course Schedule Chapter Reference",
        {"parent": course, "idx": chapter_number},
        "chapter",
    )
    lesson_name = frappe.get_value(
        "Course Schedule Lesson Reference",
        {"parent": chapter_name, "idx": lesson_number},
        "lesson",
    )
    save_progress(lesson_name, course)


@frappe.whitelist()
def get_student_info():
    email = frappe.session.user
    if email == "Administrator":
        return
    student_list = frappe.db.get_list(
        "Student",
        fields=["*"],
        filters={"user": email},
    )

    if not student_list:
        return None

    student_info = student_list[0]

    program_enrollment_list = frappe.db.sql(
        """
		select
			name as program_enrollment, student_name, program,
			academic_term
		from
			`tabProgram Enrollment`
		where
			student = %s and pgmenrol_active = 1 and docstatus != 2
		order by creation""",
        (student_info.name),
        as_dict=1,
    )

    if program_enrollment_list:
        current_program = program_enrollment_list[0]
        student_info["current_program"] = current_program
    return student_info


@frappe.whitelist()
def get_program_fees(program):
    program_fees = []
    program_fees = frappe.get_all(
        "Program Fees",
        filters={"parent": program},
        fields=["pgm_feecategory"],
    )
    print(program_fees)
    return program_fees


@frappe.whitelist()
def add_scholarship(doc):
    print("Add Scholarship called")
    program_enrollment = doc.program_enrollment
    student = doc.student
    scholarship = doc.scholarship
    sch_payer = frappe.db.get_value(
        "Singles",
        {"doctype": "Seminary Settings", "field": "scholarship_cust"},
        "value",
    )
    if scholarship:
        scholarship_discs = frappe.db.sql(
            """select pgm_fee, discount_ from `tabScholarship Discounts` where parent = %s""",
            (scholarship),
        )
        student_fees = frappe.db.sql(
            """select  fee_category, pay_percent, payterm_payer, pep_event from `tabpgm_enroll_payers` where parent = %s and payer = %s""",
            (program_enrollment, student),
        )
        for fee in student_fees:
            for disc in scholarship_discs:

                if fee[0] == disc[0]:
                    stu_pay = fee[2]
                    discount = disc[1]
                    new_stu_pay = stu_pay - discount
                    print("category: " + fee[0] + ", new fee: " + str(new_stu_pay))
                    frappe.db.set_value(
                        "pgm_enroll_payers",
                        {"parent": program_enrollment, "fee_category": fee[0]},
                        "pay_percent",
                        new_stu_pay,
                    )
                    doc = frappe.new_doc("pgm_enroll_payers")
                    doc.parent = program_enrollment
                    doc.parentfield = "pf_payers"
                    doc.parenttype = "Payers Fee Category PE"
                    doc.fee_category = fee[0]
                    doc.payer = sch_payer
                    doc.payterm_payer = fee[2]
                    doc.pep_event = fee[3]
                    doc.pay_percent = discount
                    doc.insert()
                    doc.save()


@frappe.whitelist()
def get_fields(doctype, fields=None):
    if fields is None:
        fields = []
    meta = frappe.get_meta(doctype)
    fields.extend(meta.get_search_fields())

    if meta.title_field and meta.title_field.strip() not in fields:
        fields.insert(1, meta.title_field.strip())

    return unique(fields)


@frappe.whitelist()
def get_scholarships(doctype, txt, searchfield, start, page_len, filters):
    program_enrollment = frappe.db.sql(
        """select pf_pe from `tabPayers Fee Category PE` where name LIKE %s""",
        (f"%{txt}%",),
    )[0][0]
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    program = pe.program
    scholarships = frappe.db.sql(
        """select name from `tabScholarships` where program = %s""", (program,)
    )
    return scholarships


@frappe.whitelist()
def delete_lesson(lesson, chapter):
    # Delete Reference
    chapter = frappe.get_doc("Course Schedule Chapter", chapter)
    chapter.lessons = [row for row in chapter.lessons if row.lesson != lesson]
    chapter.save()

    # Delete progress
    frappe.db.delete("Course Schedule Progress", {"lesson": lesson})

    # Delete Lesson
    frappe.db.delete("Course Lesson", lesson)


@frappe.whitelist()
def delete_documents(doctype, documents):
    frappe.only_for(["Seminary Manager", "Academics User", "Instructor"])
    for doc in documents:
        frappe.delete_doc(doctype, doc)


@frappe.whitelist()
def get_announcements(cs):
    communications = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "Course Schedule",
            "reference_name": cs,
        },
        fields=[
            "subject",
            "content",
            "recipients",
            "cc",
            "communication_date",
            "sender",
            "sender_full_name",
        ],
        order_by="communication_date desc",
    )

    for communication in communications:
        communication.image = frappe.get_cached_value(
            "User", communication.sender, "user_image"
        )

    return communications


@frappe.whitelist()
def update_lesson_index(lesson, source_chapter, target_chapter, idx):
    """Update the order of a lesson inside or across chapters."""
    idx = cint(idx) or 1
    idx = max(idx, 1)

    lesson_doc = frappe.get_doc("Course Lesson", lesson)
    source_doc = frappe.get_doc("Course Schedule Chapter", source_chapter)
    target_doc = (
        source_doc
        if source_chapter == target_chapter
        else frappe.get_doc("Course Schedule Chapter", target_chapter)
    )

    if source_chapter == target_chapter:
        _reorder_lessons_within_chapter(target_doc, lesson_doc.name, idx)
    else:
        _move_lesson_between_chapters(lesson_doc, source_doc, target_doc, idx)

    frappe.db.commit()
    return {"message": _("Lesson index updated successfully.")}


def _clone_reference_rows(chapter_doc, exclude_lesson=None):
    rows = []
    for row in chapter_doc.lessons:
        if exclude_lesson and row.lesson == exclude_lesson:
            continue
        rows.append({"lesson": row.lesson})
    return rows


def _save_chapter_lessons(chapter_doc, lessons):
    chapter_doc.set("lessons", [])
    for row in lessons:
        chapter_doc.append("lessons", {"lesson": row["lesson"]})
    chapter_doc.save(ignore_permissions=True)


def _reorder_lessons_within_chapter(chapter_doc, lesson_name, idx):
    rows = _clone_reference_rows(chapter_doc, exclude_lesson=lesson_name)
    if len(rows) == len(chapter_doc.lessons):
        frappe.throw(
            _("Lesson {0} not found in chapter {1}").format(
                lesson_name, chapter_doc.name
            )
        )

    idx = min(idx, len(rows) + 1)
    rows.insert(idx - 1, {"lesson": lesson_name})
    _save_chapter_lessons(chapter_doc, rows)


def _move_lesson_between_chapters(lesson_doc, source_doc, target_doc, idx):
    source_rows = _clone_reference_rows(source_doc, exclude_lesson=lesson_doc.name)
    if len(source_rows) == len(source_doc.lessons):
        frappe.throw(
            _("Lesson {0} not linked to source chapter {1}").format(
                lesson_doc.name, source_doc.name
            )
        )
    _save_chapter_lessons(source_doc, source_rows)

    target_rows = _clone_reference_rows(target_doc)
    idx = min(idx, len(target_rows) + 1)
    target_rows.insert(idx - 1, {"lesson": lesson_doc.name})
    _save_chapter_lessons(target_doc, target_rows)

    lesson_doc.chapter = target_doc.name
    lesson_doc.save(ignore_permissions=True)
