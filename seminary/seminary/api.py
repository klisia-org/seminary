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
import defusedxml.ElementTree as ET
from defusedxml.minidom import parseString
from seminary.seminary.doctype.course_lesson.course_lesson import save_progress
import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "u",
    "ol",
    "ul",
    "li",
    "blockquote",
    "a",
    "h1",
    "h2",
    "h3",
    "span",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "target", "rel"],
    "span": ["class"],
}


@frappe.whitelist()
def sanitize_html(html):
    if not html:
        return html
    return bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )


@frappe.whitelist()
def sanitize_submission(doc, method):
    if doc.original_post:
        doc.original_post = sanitize_html(doc.original_post)


@frappe.whitelist()
def sanitize_reply(doc, method):
    if doc.reply:
        doc.reply = sanitize_html(doc.reply)


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
    course_name: str | None = None,
    discussion_id: str | None = None,
    member: str | None = None,
):
    """Fetch submissions for a discussion activity within a course."""
    if not course_name or not discussion_id:
        raise frappe.ValidationError(_("Course and discussion are required."))

    filters = {
        "coursesc": course_name,
        "disc_activity": discussion_id,
    }

    if member:
        filters["member"] = ["!=", member]

    submissions = frappe.get_all(
        "Discussion Submission",
        filters=filters,
        fields=[
            "name",
            "member",
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
def get_discussion_submission_summary(
    course_name: str,
    discussion_id: str,
):
    """Per-student summary for the discussion submissions list view.

    Returns one row per student in the roster with:
    - submission info (name, creation, grade, status) or None if not submitted
    - reply_count: number of replies BY the student on other students' posts
    - student_group info
    """
    if not course_name or not discussion_id:
        frappe.throw(_("Course and discussion are required."))

    # 1. All students in roster
    roster_rows = frappe.db.sql(
        """
        SELECT r.stuemail_rc AS member, r.stuname_roster AS student_name, r.student
        FROM `tabScheduled Course Roster` r
        WHERE r.course_sc = %s
        """,
        course_name,
        as_dict=True,
    )

    # Build student-to-group mapping from get_student_groups
    group_data = get_student_groups(course_name)
    student_to_group = {}
    for g in group_data:
        student_to_group[g["student"]] = g["student_group"]

    roster = []
    for r in roster_rows:
        r["student_group"] = student_to_group.get(r["student"], "")
        roster.append(r)

    # 2. Submissions for this discussion + course schedule
    submissions = frappe.get_all(
        "Discussion Submission",
        filters={"coursesc": course_name, "disc_activity": discussion_id},
        fields=[
            "name",
            "member",
            "student_name",
            "creation",
            "grade",
            "percentage",
            "status",
            "extra_credit",
            "fudge_points",
            "late",
        ],
    )
    sub_by_member = {s["member"]: s for s in submissions}

    # 3. Qualifying reply counts BY each student: distinct *other-student*
    # Submissions on which this student has at least one reply row.
    # Self-replies (member == parent submission's author) never count.
    reply_counts = frappe.db.sql(
        """
        SELECT r.member, COUNT(DISTINCT r.parent) AS reply_count
        FROM `tabDiscussion Submission Replies` r
        JOIN `tabDiscussion Submission` s ON s.name = r.parent
        WHERE s.coursesc = %s
          AND s.disc_activity = %s
          AND s.member <> r.member
        GROUP BY r.member
        """,
        (course_name, discussion_id),
        as_dict=True,
    )
    replies_by_member = {rc["member"]: rc["reply_count"] for rc in reply_counts}

    min_replies_required = (
        frappe.db.get_value(
            "Discussion Activity", discussion_id, "min_replies_required"
        )
        or 0
    )

    # 4. Merge into one row per student
    result = []
    for student in roster:
        member = student["member"]
        sub = sub_by_member.get(member)
        result.append(
            {
                "member": member,
                "student_name": student["student_name"],
                "student_group": student["student_group"],
                "submission_name": sub["name"] if sub else None,
                "original_post_date": sub["creation"] if sub else None,
                "grade": sub["grade"] if sub else None,
                "percentage": sub["percentage"] if sub else None,
                "status": sub["status"] if sub else "Not Submitted",
                "extra_credit": sub.get("extra_credit") if sub else None,
                "fudge_points": sub.get("fudge_points") if sub else None,
                "late": sub.get("late") if sub else None,
                "reply_count": replies_by_member.get(member, 0),
                "min_replies_required": min_replies_required,
            }
        )

    # Sort: submitted first (by date desc), then not submitted (alphabetical)
    result.sort(key=lambda x: (x["original_post_date"] is None, x["student_name"]))
    return result


@frappe.whitelist()
def save_discussion_submission_grade(submission_name: str, grade: float):
    """Save grade for a discussion submission."""
    if not submission_name:
        raise frappe.ValidationError(_("Submission name is required."))

    submission = frappe.get_doc("Discussion Submission", submission_name)
    submission.grade = float(grade)
    submission.status = "Graded"

    # Compute score_out_of from the grading scale max
    max_grade = frappe.db.get_value(
        "Course Schedule", submission.coursesc, "maxnumgrade"
    )
    if max_grade:
        submission.score_out_of = float(max_grade)
        fudge = float(submission.fudge_points or 0)
        submission.percentage = round(
            (float(grade) / float(max_grade)) * 100 + fudge, 2
        )

    submission.save()
    return {"status": "success", "message": "Grade saved successfully."}


@frappe.whitelist()
def add_grading_comment(submission_name: str, comment: str):
    """Add a grading comment to a discussion submission."""
    if not submission_name or not comment:
        frappe.throw(_("Submission name and comment are required."))

    submission = frappe.get_doc("Discussion Submission", submission_name)

    # Permission: must be the submission owner OR an instructor/moderator/evaluator
    user = frappe.session.user
    user_doc = frappe.get_doc("User", user)
    is_owner = submission.member == user
    is_staff = any(
        r.role in ("Instructor", "Course Moderator", "Evaluator", "System Manager")
        for r in user_doc.roles
    )
    if not is_owner and not is_staff:
        frappe.throw(_("You do not have permission to comment on this submission."))

    author_name = frappe.db.get_value("User", user, "full_name") or user
    submission.append(
        "grading_comments",
        {
            "author": user,
            "author_name": author_name,
            "comment": comment,
            "comment_dt": frappe.utils.now_datetime(),
        },
    )
    submission.save(ignore_permissions=True)
    return submission.grading_comments[-1].as_dict()


@frappe.whitelist()
def get_grading_comments(submission_name: str):
    """Get all grading comments for a discussion submission."""
    if not submission_name:
        frappe.throw(_("Submission name is required."))

    comments = frappe.get_all(
        "Grading Comment",
        filters={"parent": submission_name},
        fields=["author", "author_name", "comment", "comment_dt", "name"],
        order_by="comment_dt asc",
    )
    return comments


@frappe.whitelist()
def get_discussion_dashboard(course_name: str, discussion_id: str):
    """Mini dashboard stats for instructor view of a discussion activity.

    Only counts submissions and replies by students in the course roster
    (excludes instructor/moderator posts).
    """
    if not course_name or not discussion_id:
        frappe.throw(_("Course and discussion are required."))

    # Get student emails from roster to filter out instructor posts
    roster_emails = frappe.db.sql_list(
        """
        SELECT r.stuemail_rc
        FROM `tabScheduled Course Roster` r
        WHERE r.course_sc = %s
        """,
        course_name,
    )

    if not roster_emails:
        return {"submission_count": 0, "avg_replies": 0}

    submission_count = frappe.db.count(
        "Discussion Submission",
        filters={
            "coursesc": course_name,
            "disc_activity": discussion_id,
            "member": ["in", roster_emails],
        },
    )

    reply_count = 0
    if submission_count:
        placeholders = ", ".join(["%s"] * len(roster_emails))
        reply_count = (
            frappe.db.sql(
                f"""
            SELECT COUNT(*) FROM `tabDiscussion Submission Replies` r
            JOIN `tabDiscussion Submission` s ON s.name = r.parent
            WHERE s.coursesc = %s AND s.disc_activity = %s
            AND r.member IN ({placeholders})
            """,
                [course_name, discussion_id] + roster_emails,
            )[0][0]
            or 0
        )

    avg_replies = round(reply_count / submission_count, 1) if submission_count else 0

    return {
        "submission_count": submission_count,
        "avg_replies": avg_replies,
    }


@frappe.whitelist(allow_guest=True)
def get_translations():
    if frappe.session.user != "Guest":
        language = frappe.db.get_value("User", frappe.session.user, "language")
    else:
        language = frappe.db.get_single_value("System Settings", "language")
    return get_all_translations(language)


@frappe.whitelist()
def get_enabled_languages():
    """Return all enabled languages and the current user's language preference."""
    languages = frappe.get_all(
        "Language",
        filters={"enabled": 1},
        fields=["name as language_code", "language_name"],
        order_by="language_name asc",
    )
    current = frappe.db.get_value("User", frappe.session.user, "language") or ""
    return {"languages": languages, "current": current}


@frappe.whitelist()
def set_user_language(language):
    """Set the current user's UI language preference."""
    frappe.db.set_value("User", frappe.session.user, "language", language)
    return {"success": True}


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
            (
                course_data["course_image"]["file_url"]
                if course_data["course_image"]
                else None
            ),
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
    user.is_alumni = "Alumni" in user.roles
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
            "prof_email",
            "phone_message",
        ],
        as_dict=1,
    )
    if instructor:
        from seminary.seminary.utils import get_instructor_messaging_apps

        instructor["messaging_apps"] = get_instructor_messaging_apps(instructor.name)
        # Also return all available messaging apps for the edit form
        instructor["available_messaging_apps"] = frappe.get_all(
            "Messaging App",
            fields=["app_name", "svg_icon", "url_prefix"],
            order_by="app_name",
        )
    return instructor


@frappe.whitelist()
def save_student_profile(
    mobile, address_line_1, address_line_2, city, pincode, state, country, image=None
):
    student_name = frappe.db.get_value("Student", {"user": frappe.session.user}, "name")
    if not student_name:
        frappe.throw("Student record not found")

    update_fields = {
        "student_mobile_number": mobile,
        "address_line_1": address_line_1,
        "address_line_2": address_line_2,
        "city": city,
        "pincode": pincode,
        "state": state,
        "country": country,
    }
    if image:
        update_fields["image"] = image

    frappe.db.set_value("Student", student_name, update_fields)
    return frappe.db.get_value(
        "Student", student_name, list(update_fields.keys()), as_dict=1
    )


@frappe.whitelist()
def save_instructor_profile(
    instructor_name,
    shortbio,
    bio,
    prof_email=None,
    phone_message=None,
    messaging_apps=None,
):
    doc = frappe.get_doc("Instructor", {"user": frappe.session.user})
    doc.instructor_name = instructor_name
    doc.shortbio = shortbio
    doc.bio = bio
    if prof_email is not None:
        doc.prof_email = prof_email
    if phone_message is not None:
        doc.phone_message = phone_message
    if messaging_apps is not None:
        import json

        if isinstance(messaging_apps, str):
            messaging_apps = json.loads(messaging_apps)
        doc.messaging_apps = []
        for app_name in messaging_apps:
            doc.append("messaging_apps", {"messaging_app": app_name})
    doc.save(ignore_permissions=False)
    return {
        "instructor_name": doc.instructor_name,
        "shortbio": doc.shortbio,
        "bio": doc.bio,
        "prof_email": doc.prof_email,
        "phone_message": doc.phone_message,
    }


@frappe.whitelist(allow_guest=True)
def get_school_abbr_logo():
    abbr = frappe.db.get_single_value("Website Settings", "app_name")
    logo = frappe.db.get_single_value("Seminary Settings", "logo_portal")
    logo_dark = frappe.db.get_single_value("Seminary Settings", "logo_dark")
    support_user = frappe.db.get_single_value("Seminary Settings", "support_user")
    date_format = (
        frappe.db.get_single_value("System Settings", "date_format") or "yyyy-mm-dd"
    )
    allow_portal_enroll = (
        frappe.db.get_single_value("Seminary Settings", "allow_portal_enroll") or 0
    )
    return {
        "name": abbr,
        "logo": logo,
        "logo_dark": logo_dark,
        "support_user": support_user,
        "date_format": date_format,
        "allow_portal_enroll": allow_portal_enroll,
    }


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
    """Return list of programs for a particular student, with their grades and PE summary.
    :param student: Student
    """
    grades = frappe.db.sql(
        """SELECT pe.program, pe.name AS program_enrollment, pe.pgmenrol_active,
            pe.student, pe.totalcredits,
            pec.course_name, pec.academic_term, pec.credits,
            pec.pec_finalgradecode, pec.pec_finalgradenum, pec.status
        FROM `tabProgram Enrollment` pe
        INNER JOIN `tabProgram Enrollment Course` pec ON pe.name = pec.parent
        WHERE pe.student = %s""",
        (student),
        as_dict=1,
    )

    # Enrich with program-level data (credits_complete) and emphasis summary per PE
    pe_summary = {}
    for row in grades:
        pe_name = row.program_enrollment
        if pe_name not in pe_summary:
            credits_complete = (
                frappe.db.get_value("Program", row.program, "credits_complete") or 0
            )
            emphases = frappe.get_all(
                "Program Enrollment Emphasis",
                filters={"parent": pe_name, "status": ["in", ["Active", "Completed"]]},
                fields=["emphasis_track", "trackcredits"],
            )
            emphasis_summary = []
            for emph in emphases:
                track_name = frappe.db.get_value(
                    "Program Track", emph.emphasis_track, "track_name"
                )
                addcredits = (
                    frappe.db.get_value(
                        "Program Track", emph.emphasis_track, "addcredits"
                    )
                    or 0
                )
                emphasis_summary.append(
                    {
                        "track_name": track_name,
                        "trackcredits": emph.trackcredits or 0,
                        "credits_required": addcredits,
                    }
                )
            pe_summary[pe_name] = {
                "credits_complete": credits_complete,
                "emphases": emphasis_summary,
            }

        row["credits_complete"] = pe_summary[pe_name]["credits_complete"]
        row["emphases"] = pe_summary[pe_name]["emphases"]

    return grades


@frappe.whitelist()
def first_term(doc):
    # Set the first term as the current term if no term is set as current
    # currentterm = frappe.db.sql("""select name from `tabAcademic Term` where iscurrent_acterm = 1""")
    # print("Current term is: ", currentterm)
    print("Self.name is: ", doc)
    # if not currentterm:
    # 	frappe.db.set_value("Academic Term", doc, "iscurrent_acterm", 1)
    # 	print("The current term has been set to this term.")
    # else:
    # 	return print("There is already a current term. Terms will roll automatically according to their dates.")
    academic_terms = frappe.get_all(
        "Academic Term", filters={}, fields=["name", "term_start_date", "term_end_date"]
    )
    today = getdate()
    currentterm = frappe.db.sql(
        """select name from `tabAcademic Term` where iscurrent_acterm = 1"""
    )

    for term in academic_terms:
        if term.term_start_date <= today <= term.term_end_date:
            if term.name != currentterm[0][0]:
                frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 1)
                frappe.db.set_value("Academic Term", term.name, "open", 1)
            else:
                break

        else:
            frappe.db.set_value("Academic Term", term.name, "iscurrent_acterm", 0)
    return "Active term updated successfully"


@frappe.whitelist()
def roll_students(academic_term=None):
    # Student-advancement only. Invoice generation lives in tasks.daily() now
    # (see generate_nat_invoices / generate_nay_invoices / generate_monthly_invoices).
    roll_pe()
    return "Students advanced"


@frappe.whitelist()
def regenerate_current_term_invoices():
    """Manual recovery: clear invoiced_nat_on on the current Academic Term and
    re-run the NAT generator. Safety-net seminary_trigger check still prevents
    duplicates for invoices that already exist."""
    current = frappe.db.get_value("Academic Term", {"iscurrent_acterm": 1}, "name")
    if not current:
        frappe.throw(_("No current Academic Term set."))
    frappe.db.set_value("Academic Term", current, "invoiced_nat_on", None)
    return generate_nat_invoices(current)


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
        filters={
            "academic_term": currentterm,
            "workflow_state": "Open for Enrollment",
        },
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
    """Enroll student in a course schedule. Creates a draft CEI document."""
    student = frappe.get_value("Program Enrollment", pe_name, "student")
    if not student:
        frappe.throw(_("Invalid Program Enrollment"))

    # Validate the Course Schedule exists and is open for enrollment
    cs = frappe.db.get_value(
        "Course Schedule", course, ["name", "workflow_state"], as_dict=True
    )
    if not cs:
        frappe.throw(_("Course Schedule not found"))
    if cs.workflow_state != "Open for Enrollment":
        frappe.throw(_("This course is not open for enrollment"))

    doc = frappe.new_doc("Course Enrollment Individual")
    doc.program_ce = pe_name
    doc.student_ce = student
    doc.coursesc_ce = cs.name
    doc.docstatus = 0

    # Populate fetch_from fields so get_credits() can resolve them
    doc.program_data = frappe.db.get_value("Program Enrollment", pe_name, "program")
    doc.course_data = frappe.db.get_value("Course Schedule", cs.name, "course")

    doc.credits = doc.get_credits()
    doc.insert()

    # Without registrar gating (per-Program flag), advance the draft
    # immediately. submit() raises docstatus and fires on_submit (which
    # creates the Sales Invoice); workflow_state is then nudged via
    # db_set, which skips validate_workflow's role check (the student
    # fails it even with ignore_permissions). Program conditions decide
    # the target state.
    if not doc.registrar_block_cei:
        target_state = (
            "Submitted"
            if (doc.is_free or not doc.require_pay_submit)
            else "Awaiting Payment"
        )
        doc.flags.ignore_permissions = True
        doc.submit()
        doc.db_set("workflow_state", target_state, update_modified=False)

    return {
        "name": doc.name,
        "course_data": doc.course_data,
        "academic_term": doc.academic_term,
        "credits": doc.credits,
    }


@frappe.whitelist()
def get_student_enrollments_for_term(program_enrollment):
    """Return the student's CEIs for the current academic term."""
    student = frappe.db.get_value("Program Enrollment", program_enrollment, "student")
    if not student:
        return []

    current_terms = frappe.get_all(
        "Academic Term", filters={"iscurrent_acterm": 1}, pluck="name"
    )
    if not current_terms:
        return []

    ceis = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "student_ce": student,
            "program_ce": program_enrollment,
            "academic_term": ["in", current_terms],
            "docstatus": ["!=", 2],
            "course_cancelled": 0,
        },
        fields=[
            "name",
            "course_data",
            "academic_term",
            "coursesc_ce",
            "docstatus",
            "audit",
            "withdrawn",
            "credits",
            "workflow_state",
            "paid_percent",
        ],
        order_by="docstatus asc, course_data asc",
    )

    # Map CEI workflow_state to a student-facing status. The workflow is
    # the canonical source post-ADR 016 — `withdrawn` and docstatus alone
    # can't distinguish Awaiting Payment (invoiced, not on roster) from
    # Submitted (fully enrolled).
    for cei in ceis:
        cei["start_date"] = frappe.db.get_value(
            "Course Schedule", cei.coursesc_ce, "c_datestart"
        )

        if cei.docstatus == 0:
            cei["status"] = "Draft"
        elif cei.workflow_state == "Awaiting Payment":
            cei["status"] = "Awaiting Payment"
        elif cei.workflow_state == "Withdrawn" or cei.withdrawn:
            cei["status"] = "Withdrawn"
        else:
            cei["status"] = "Enrolled"

        # For Awaiting Payment, surface the unpaid invoice so the student
        # can click through to pay.
        cei["sales_invoice"] = None
        if cei["status"] == "Awaiting Payment":
            si_rows = frappe.get_all(
                "Sales Invoice",
                filters={
                    "custom_cei": cei.name,
                    "docstatus": 1,
                    "is_return": 0,
                },
                fields=["name", "grand_total", "outstanding_amount"],
                order_by="creation desc",
                limit=1,
            )
            if si_rows:
                cei["sales_invoice"] = si_rows[0]

    return ceis


@frappe.whitelist()
def cancel_draft_enrollment(cei_name):
    """Cancel (delete) a draft CEI. Only works on draft documents."""
    doc = frappe.get_doc("Course Enrollment Individual", cei_name)
    if doc.docstatus != 0:
        frappe.throw(_("Only draft enrollments can be cancelled"))
    if doc.student_ce != frappe.db.get_value(
        "Student", {"user": frappe.session.user}, "name"
    ):
        frappe.throw(_("You can only cancel your own enrollments"))
    doc.delete()
    return {"success": True}


@frappe.whitelist()
def credits_pe_track():
    """Recalculate track credits for all active program enrollments.
    Iterates over each emphasis in the Program Enrollment Emphasis child table,
    sums passed credits from matching track courses, and applies the credit ceiling.
    """
    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"pgmenrol_active": 1},
        fields=["name", "program"],
    )

    for pe in enrollments:
        emphases = frappe.get_all(
            "Program Enrollment Emphasis",
            filters={"parent": pe.name, "status": ["in", ["Active", "Completed"]]},
            fields=["name", "emphasis_track"],
        )

        for emphasis in emphases:
            credits = frappe.db.sql(
                """SELECT COALESCE(SUM(pec.credits), 0)
                FROM `tabProgram Enrollment Course` pec
                INNER JOIN `tabProgram Track Courses` ptc
                    ON ptc.program_track_course = pec.course_name
                    AND ptc.parent = %s
                    AND ptc.program_track = %s
                WHERE pec.parent = %s
                    AND pec.status = 'Pass'""",
                (pe.program, emphasis.emphasis_track, pe.name),
            )[0][0]

            # Apply credit ceiling if set
            max_credits = frappe.db.get_value(
                "Program Track", emphasis.emphasis_track, "max_credits"
            )
            if max_credits and max_credits > 0 and credits > max_credits:
                credits = max_credits

            frappe.db.set_value(
                "Program Enrollment Emphasis",
                emphasis.name,
                "trackcredits",
                int(credits),
            )


@frappe.whitelist()
def get_program_audit(program_enrollment):
    """Return comprehensive program progress data for a given Program Enrollment.

    Includes credit progress, emphasis status, mandatory course completion,
    and graduation eligibility.
    """
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    program = frappe.get_cached_doc("Program", pe.program)

    result = {
        "program": pe.program,
        "program_enrollment": pe.name,
        "student": pe.student,
        "student_name": pe.student_name,
        "program_type": program.program_type,
        "credits_required": program.credits_complete or 0,
        "credits_earned": pe.totalcredits or 0,
        "terms_required": program.terms_complete or 0,
        "current_term": pe.current_std_term or 0,
        "emphasis_overlap_policy": program.emphasis_overlap_policy
        or "Shared Credit Pool",
        "active": pe.pgmenrol_active,
    }

    # Get all program courses with their mandatory/required status
    program_courses = {
        pc.course: {
            "course": pc.course,
            "course_name": pc.course_name,
            "credits": pc.pgmcourse_credits or 0,
            "course_term": pc.course_term or 0,
            "required": pc.required,
        }
        for pc in program.courses
    }

    # Get student's completed/in-progress courses
    student_courses = {}
    for pec in pe.courses:
        student_courses[pec.course_name] = {
            "course_schedule": pec.course,
            "course": pec.course_name,
            "academic_term": pec.academic_term,
            "credits": pec.credits or 0,
            "grade_code": pec.pec_finalgradecode,
            "grade_num": pec.pec_finalgradenum,
            "status": pec.status,
        }

    # Also check in-progress enrollments (Course Enrollment Individual, not yet graded)
    in_progress = frappe.get_all(
        "Course Enrollment Individual",
        filters={
            "program_ce": pe.name,
            "docstatus": 1,
            "withdrawn": 0,
            "course_cancelled": 0,
        },
        fields=["course_data", "coursesc_ce"],
    )
    in_progress_courses = {cei.course_data for cei in in_progress}

    # Build emphases data FIRST so we can deduplicate the program mandatory list
    emphases_data = []
    active_emphases = [
        e for e in (pe.emphases or []) if e.status in ("Active", "Completed")
    ]
    courses_in_emphases = (
        set()
    )  # courses shown under an emphasis — exclude from program list

    for emphasis in active_emphases:
        track = frappe.db.get_value(
            "Program Track",
            emphasis.emphasis_track,
            ["track_name", "addcredits", "max_credits", "advisory_only"],
            as_dict=True,
        )
        if not track:
            continue

        # Get mandatory track courses
        track_courses = frappe.get_all(
            "Program Track Courses",
            filters={
                "parent": pe.program,
                "program_track": emphasis.emphasis_track,
                "pgm_track_course_mandatory": 1,
            },
            fields=["program_track_course"],
        )

        mandatory_remaining = []
        track_mandatory_courses = []
        for tc in track_courses:
            sc = student_courses.get(tc.program_track_course)
            course_name_display = tc.program_track_course
            # Try to get a readable name from Program Course table
            pc_info = program_courses.get(tc.program_track_course)
            if pc_info:
                course_name_display = pc_info["course_name"] or tc.program_track_course

            if sc and sc["status"] == "Pass":
                status = "Completed"
            elif tc.program_track_course in in_progress_courses or (
                sc and not sc["status"]
            ):
                status = "In Progress"
            else:
                status = "Not Started"
                mandatory_remaining.append(tc.program_track_course)

            course_term = pc_info["course_term"] if pc_info else 0
            track_mandatory_courses.append(
                {
                    "course": tc.program_track_course,
                    "course_name": course_name_display,
                    "credits": pc_info["credits"] if pc_info else 0,
                    "course_term": course_term,
                    "status": status,
                    "grade_code": sc["grade_code"] if sc else None,
                }
            )
            courses_in_emphases.add(tc.program_track_course)

        # Sort track courses by term, then name
        track_mandatory_courses.sort(key=lambda x: (x["course_term"], x["course_name"]))

        credits_earned = emphasis.trackcredits or 0
        credits_capped = credits_earned
        if (
            track.max_credits
            and track.max_credits > 0
            and credits_earned > track.max_credits
        ):
            credits_capped = track.max_credits

        emphases_data.append(
            {
                "track_name": track.track_name,
                "emphasis_track": emphasis.emphasis_track,
                "credits_required": track.addcredits or 0,
                "credits_earned": credits_earned,
                "credits_capped": credits_capped,
                "max_credits": track.max_credits or 0,
                "mandatory_remaining": mandatory_remaining,
                "mandatory_courses": track_mandatory_courses,
                "advisory_only": track.advisory_only,
                "status": emphasis.status,
            }
        )

    result["emphases"] = emphases_data

    # Build program mandatory courses list, EXCLUDING courses already shown under an emphasis
    mandatory_courses = []
    for course_name, pc in program_courses.items():
        if not pc["required"]:
            continue
        if course_name in courses_in_emphases:
            continue
        sc = student_courses.get(course_name)
        if sc and sc["status"] == "Pass":
            status = "Completed"
        elif course_name in in_progress_courses or (sc and not sc["status"]):
            status = "In Progress"
        else:
            status = "Not Started"

        mandatory_courses.append(
            {
                "course": course_name,
                "course_name": pc["course_name"],
                "credits": pc["credits"],
                "course_term": pc["course_term"],
                "status": status,
                "grade_code": sc["grade_code"] if sc else None,
                "grade_num": sc["grade_num"] if sc else None,
            }
        )

    # Sort by course_term, then course_name
    mandatory_courses.sort(key=lambda x: (x["course_term"], x["course_name"]))
    result["mandatory_courses"] = mandatory_courses

    # Add disclaimer
    result["disclaimer"] = (
        "This audit reflects the declared emphasis at the time of generation."
    )

    # Calculate effective total required based on overlap policy
    effective_total = program.credits_complete or 0
    if (
        program.emphasis_overlap_policy == "Additional Credits Required"
        and len(active_emphases) > 1
    ):
        for emph in emphases_data[1:]:
            effective_total += emph["credits_required"]
    result["effective_credits_required"] = effective_total

    # Elective credits calculation
    # Committed credits = program mandatory credits + emphasis track required credits (addcredits)
    # The emphasis carve-out is the full track credit requirement, not just the few mandatory courses
    program_mandatory_credits = sum(mc["credits"] for mc in mandatory_courses)
    emphasis_committed_credits = sum(emph["credits_required"] for emph in emphases_data)
    committed_total = program_mandatory_credits + emphasis_committed_credits

    mandatory_credits_earned = sum(
        mc["credits"] for mc in mandatory_courses if mc["status"] == "Completed"
    )
    emphasis_credits_earned = sum(emph["credits_earned"] for emph in emphases_data)

    result["elective_credits_earned"] = max(
        0, (pe.totalcredits or 0) - mandatory_credits_earned - emphasis_credits_earned
    )
    result["elective_credits_needed"] = (
        max(0, effective_total - committed_total)
        if program.program_type == "Credits-based"
        else 0
    )

    # Ongoing programs have no graduation concept — short-circuit the eligibility
    # block and return `graduation_eligible=None` so frontends can distinguish
    # "not applicable" from "blocked".
    if program.is_ongoing:
        result["graduation_requirements"] = []
        result["graduation_policy"] = pe.graduation_policy
        result["expected_graduation_date"] = pe.expected_graduation_date
        result["graduation_eligible"] = None
        return result

    # Graduation eligibility check
    graduation_eligible = True

    if program.program_type == "Credits-based":
        if (pe.totalcredits or 0) < effective_total:
            graduation_eligible = False
    elif program.program_type == "Time-based":
        if (pe.current_std_term or 0) < (program.terms_complete or 0):
            graduation_eligible = False

    # All mandatory program courses passed?
    if any(mc["status"] != "Completed" for mc in mandatory_courses):
        graduation_eligible = False

    # All emphasis requirements met?
    for emph in emphases_data:
        if emph["advisory_only"]:
            continue
        if emph["credits_capped"] < emph["credits_required"]:
            graduation_eligible = False
        if emph["mandatory_remaining"]:
            graduation_eligible = False

    # Fallback emphasis check
    if not active_emphases and program.fallback_emphasis:
        fallback_track = frappe.db.get_value(
            "Program Track",
            program.fallback_emphasis,
            ["addcredits", "max_credits", "advisory_only"],
            as_dict=True,
        )
        if fallback_track and not fallback_track.advisory_only:
            # Check fallback track credits
            fallback_credits = frappe.db.sql(
                """SELECT COALESCE(SUM(pec.credits), 0)
                FROM `tabProgram Enrollment Course` pec
                INNER JOIN `tabProgram Track Courses` ptc
                    ON ptc.program_track_course = pec.course_name
                    AND ptc.parent = %s
                    AND ptc.program_track = %s
                WHERE pec.parent = %s AND pec.status = 'Pass'""",
                (pe.program, program.fallback_emphasis, pe.name),
            )[0][0]
            if fallback_track.max_credits and fallback_track.max_credits > 0:
                fallback_credits = min(fallback_credits, fallback_track.max_credits)
            if fallback_credits < (fallback_track.addcredits or 0):
                graduation_eligible = False

    # Graduation requirements (non-course evidence: letters, theses, manual
    # verifications, etc.) — see seminary/seminary/graduation.py
    from seminary.seminary.graduation import evaluate_activation

    grad_requirements = []
    grad_requirements_blocking = False
    for sgr in pe.graduation_requirements or []:
        active = evaluate_activation(sgr, pe)
        satisfied = sgr.status in ("Fulfilled", "Waived")
        if sgr.mandatory and active and not satisfied:
            grad_requirements_blocking = True
        grad_requirements.append(
            {
                "name": sgr.name,
                "requirement_name": sgr.requirement_name,
                "requirement_type": sgr.requirement_type,
                "mandatory": bool(sgr.mandatory),
                "slot_index": sgr.slot_index or 1,
                "status": sgr.status,
                "active": active,
                "due_date": sgr.due_date,
                "fulfilled_on": sgr.fulfilled_on,
                "link_doctype": sgr.link_doctype,
                "linked_doc": sgr.linked_doc,
                "student_evidence_attachment": sgr.student_evidence_attachment,
                "staff_evidence_attachment": sgr.staff_evidence_attachment,
                "verified_by": sgr.verified_by,
                "verified_on": sgr.verified_on,
                "waived": bool(sgr.waived),
                "waiver_reason": sgr.waiver_reason,
                "notes": sgr.notes,
                "grad_requirement_item": sgr.grad_requirement_item,
            }
        )

    result["graduation_requirements"] = grad_requirements
    result["graduation_policy"] = pe.graduation_policy
    result["expected_graduation_date"] = pe.expected_graduation_date

    if grad_requirements_blocking:
        graduation_eligible = False

    result["graduation_eligible"] = graduation_eligible

    # Graduation Request CTA inputs (consumed by ProgramAudit.vue).
    result["students_can_request_graduation"] = bool(
        getattr(program, "students_can_request_graduation", 0)
    )
    result["graduation_request_trigger"] = (
        getattr(program, "graduation_request_trigger", None) or None
    )
    result["grad_candidate"] = bool(pe.grad_candidate)
    result["graduation_request"] = _active_graduation_request_summary(pe.name)
    result["student_phonetic_name"] = (
        frappe.db.get_value("Student", pe.student, "phonetic_name") or ""
    )

    return result


def _active_graduation_request_summary(pe_name):
    """Return the most recent non-cancelled Graduation Request for this PE,
    or None. Frontend uses this to render the CTA state."""
    rows = frappe.get_all(
        "Graduation Request",
        filters={"program_enrollment": pe_name, "docstatus": ("!=", 2)},
        fields=[
            "name",
            "workflow_state",
            "paid_percent",
            "request_date",
            "is_free",
        ],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        return None
    gr = rows[0]
    sales_invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "custom_graduation_request": gr.name,
            "docstatus": 1,
            "is_return": 0,
        },
        fields=["name", "grand_total", "outstanding_amount"],
    )
    return {
        **gr,
        "sales_invoices": sales_invoices,
    }


@frappe.whitelist()
def create_graduation_request(
    program_enrollment, legal_name_at_graduation, phonetic_name=None
):
    """Create + submit a Graduation Request for the given Program Enrollment.

    Permission model:
      - Caller is the student linked to the PE (portal flow), OR
      - Caller has the Academics User role (registrar acting on behalf).

    Captures the legal name (required) and phonetic spelling (optional) for
    the diploma. The phonetic name is also persisted on the Student record so
    it's reusable beyond graduation. Validates trigger / candidacy at the
    controller level (`before_submit`). Returns a summary suitable for
    refreshing the audit page CTA.
    """
    legal_name_at_graduation = (legal_name_at_graduation or "").strip()
    if not legal_name_at_graduation:
        frappe.throw(_("Legal name is required."))
    phonetic_name = (phonetic_name or "").strip() or None

    pe = frappe.db.get_value(
        "Program Enrollment",
        program_enrollment,
        [
            "name",
            "student",
            "program",
            "expected_graduation_date",
            "grad_candidate",
            "docstatus",
            "pgmenrol_active",
        ],
        as_dict=True,
    )
    if not pe:
        frappe.throw(_("Program Enrollment {0} not found.").format(program_enrollment))

    # Permission gate
    user = frappe.session.user
    user_roles = set(frappe.get_roles(user))
    is_staff = bool(
        user_roles & {"Academics User", "Seminary Manager", "System Manager"}
    )
    is_owner = False
    if not is_staff:
        student_for_user = frappe.db.get_value(
            "Student", {"student_email_id": user}, "name"
        )
        is_owner = bool(student_for_user and student_for_user == pe.student)
    if not (is_staff or is_owner):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    # Quick guards (controller re-validates with full context)
    if pe.docstatus != 1 or not pe.pgmenrol_active:
        frappe.throw(_("Program Enrollment is not active."))
    program_flags = frappe.db.get_value(
        "Program",
        pe.program,
        ["students_can_request_graduation", "graduation_request_trigger"],
        as_dict=True,
    )
    if not program_flags or not program_flags.students_can_request_graduation:
        frappe.throw(_("This program does not allow Graduation Requests."))
    if not program_flags.graduation_request_trigger:
        frappe.throw(_("This program has no graduation request trigger configured."))
    if not pe.grad_candidate:
        frappe.throw(_("Not yet a graduation candidate."))

    if phonetic_name:
        frappe.db.set_value(
            "Student",
            pe.student,
            "phonetic_name",
            phonetic_name,
            update_modified=False,
        )

    gr = frappe.get_doc(
        {
            "doctype": "Graduation Request",
            "student": pe.student,
            "program_enrollment": pe.name,
            "program": pe.program,
            "expected_graduation_date": pe.expected_graduation_date,
            "legal_name_at_graduation": legal_name_at_graduation,
            "phonetic_name_snapshot": phonetic_name,
        }
    )
    gr.insert(ignore_permissions=is_owner)
    gr.submit()

    return _active_graduation_request_summary(pe.name)


@frappe.whitelist()
def get_pe_unpaid_invoices(program_enrollment):
    """Aggregate every unpaid Sales Invoice tied to this Program Enrollment,
    grouped by payer (Customer). Covers three linkage paths:

    - Course Enrollment Individual via Sales Invoice.custom_cei
    - Graduation Request via Sales Invoice.custom_graduation_request
    - Trigger invoices (NAT/NAY/Monthly/etc.) via the seminary_trigger
      tag's last segment, which is the pgm_enroll_payers row name.

    Returns a list grouped by customer:
        [{
            "customer": "Cust A",
            "invoices": [{name, grand_total, outstanding_amount, source}],
            "total_unpaid": 123.45,
        }, ...]

    Sorted by total_unpaid desc.
    """
    if not program_enrollment:
        return []

    rows = frappe.db.sql(
        """
        SELECT * FROM (
            SELECT si.name, si.customer, si.grand_total, si.outstanding_amount,
                   'Course Enrollment' AS source
            FROM `tabSales Invoice` si
            INNER JOIN `tabCourse Enrollment Individual` cei ON cei.name = si.custom_cei
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.outstanding_amount > 0
              AND cei.program_ce = %(pe)s

            UNION ALL

            SELECT si.name, si.customer, si.grand_total, si.outstanding_amount,
                   'Graduation Request' AS source
            FROM `tabSales Invoice` si
            INNER JOIN `tabGraduation Request` gr ON gr.name = si.custom_graduation_request
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.outstanding_amount > 0
              AND gr.program_enrollment = %(pe)s

            UNION ALL

            SELECT si.name, si.customer, si.grand_total, si.outstanding_amount,
                   'Recurring Fee' AS source
            FROM `tabSales Invoice` si
            INNER JOIN `tabpgm_enroll_payers` pep
                ON pep.name = SUBSTRING_INDEX(si.seminary_trigger, ':', -1)
            INNER JOIN `tabPayers Fee Category PE` pfc ON pfc.name = pep.parent
            WHERE si.docstatus = 1
              AND si.is_return = 0
              AND si.outstanding_amount > 0
              AND si.seminary_trigger IS NOT NULL
              AND si.seminary_trigger != ''
              AND pfc.pf_pe = %(pe)s
        ) AS u
        ORDER BY u.customer, u.name
        """,
        {"pe": program_enrollment},
        as_dict=True,
    )

    # Group by customer
    by_customer = {}
    for r in rows:
        bucket = by_customer.setdefault(
            r.customer, {"customer": r.customer, "invoices": [], "total_unpaid": 0.0}
        )
        bucket["invoices"].append(
            {
                "name": r.name,
                "grand_total": float(r.grand_total or 0),
                "outstanding_amount": float(r.outstanding_amount or 0),
                "source": r.source,
            }
        )
        bucket["total_unpaid"] += float(r.outstanding_amount or 0)

    return sorted(by_customer.values(), key=lambda b: b["total_unpaid"], reverse=True)


@frappe.whitelist()
def get_available_courses_categorized(program_enrollment):
    """Return available courses for enrollment with category metadata.

    Each course includes its categories (Program Mandatory, Track Mandatory, Elective)
    and available course schedules.
    """
    pe = frappe.get_doc("Program Enrollment", program_enrollment)
    program = frappe.get_cached_doc("Program", pe.program)

    # Get all available courses using existing logic
    available_courses = courses_for_student(program_enrollment)

    if not available_courses:
        return []

    # Build lookup maps
    program_course_map = {}
    for pc in program.courses:
        program_course_map[pc.course] = {
            "required": pc.required,
            "credits": pc.pgmcourse_credits or 0,
            "course_name": pc.course_name,
        }

    # Track course lookup: course -> list of tracks
    track_course_map = {}
    active_emphasis_tracks = set()
    for emphasis in pe.emphases or []:
        if emphasis.status == "Active":
            active_emphasis_tracks.add(emphasis.emphasis_track)

    track_courses = frappe.get_all(
        "Program Track Courses",
        filters={"parent": pe.program},
        fields=["program_track", "program_track_course", "pgm_track_course_mandatory"],
    )
    for tc in track_courses:
        if tc.program_track not in active_emphasis_tracks:
            continue
        if tc.program_track_course not in track_course_map:
            track_course_map[tc.program_track_course] = []
        track_name = frappe.db.get_value(
            "Program Track", tc.program_track, "track_name"
        )
        track_course_map[tc.program_track_course].append(
            {
                "track": tc.program_track,
                "track_name": track_name,
                "mandatory": tc.pgm_track_course_mandatory,
            }
        )

    # Get course schedules for available courses in current term
    course_schedules = frappe.get_all(
        "Course Schedule",
        filters={
            "course": ["in", available_courses],
            "workflow_state": "Open for Enrollment",
        },
        fields=[
            "name",
            "course",
            "academic_term",
            "section",
            "modality",
            "c_datestart",
            "c_dateend",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "from_time",
            "to_time",
        ],
    )
    schedule_map = {}
    for cs in course_schedules:
        # Build day initials for presential/hybrid
        days = ""
        if cs.modality in ("Presential", "Hybrid"):
            day_map = [
                (cs.monday, "M"),
                (cs.tuesday, "T"),
                (cs.wednesday, "W"),
                (cs.thursday, "Th"),
                (cs.friday, "F"),
                (cs.saturday, "Sa"),
                (cs.sunday, "Su"),
            ]
            days = "".join(abbr for checked, abbr in day_map if checked)

        # Format time range for presential/hybrid
        time_range = ""
        if cs.modality in ("Presential", "Hybrid") and cs.from_time:
            from_t = frappe.utils.format_time(cs.from_time, "h:mm a")
            if cs.to_time:
                to_t = frappe.utils.format_time(cs.to_time, "h:mm a")
                time_range = f"{from_t} – {to_t}"
            else:
                time_range = from_t

        # Get instructors
        instructors = frappe.get_all(
            "Course Schedule Instructors",
            filters={"parent": cs.name},
            fields=["instructor"],
        )
        instructor_names = ", ".join(i.instructor for i in instructors if i.instructor)

        # Format dates as short form
        date_range = ""
        if cs.c_datestart and cs.c_dateend:
            date_range = f"{frappe.utils.formatdate(cs.c_datestart, 'MMM d')} – {frappe.utils.formatdate(cs.c_dateend, 'MMM d, yyyy')}"
        elif cs.c_datestart:
            date_range = frappe.utils.formatdate(cs.c_datestart, "MMM d, yyyy")

        if cs.course not in schedule_map:
            schedule_map[cs.course] = []
        schedule_map[cs.course].append(
            {
                "name": cs.name,
                "academic_term": cs.academic_term,
                "section": cs.section or "",
                "modality": cs.modality or "",
                "instructors": instructor_names,
                "date_range": date_range,
                "days": days,
                "time_range": time_range,
            }
        )

    # Build categorized result
    result = []
    for course in available_courses:
        pc = program_course_map.get(course, {})
        course_name = pc.get("course_name") or frappe.db.get_value(
            "Course", course, "course_name"
        )
        credits = pc.get("credits", 0)

        categories = []

        # Check if program mandatory
        if pc.get("required"):
            categories.append({"type": "Program Mandatory"})

        # Check track categories
        if course in track_course_map:
            for track_info in track_course_map[course]:
                cat_type = (
                    "Track Mandatory" if track_info["mandatory"] else "Track Elective"
                )
                categories.append(
                    {
                        "type": cat_type,
                        "track": track_info["track"],
                        "track_name": track_info["track_name"],
                    }
                )

        # If no specific category, it's a general elective
        if not categories:
            categories.append({"type": "Elective"})

        result.append(
            {
                "course": course,
                "course_name": course_name,
                "categories": categories,
                "credits": credits,
                "course_schedules": schedule_map.get(course, []),
            }
        )

    # Sort: Program Mandatory first, then Track Mandatory, then Elective
    priority = {
        "Program Mandatory": 0,
        "Track Mandatory": 1,
        "Track Elective": 2,
        "Elective": 3,
    }
    result.sort(key=lambda x: min(priority.get(c["type"], 99) for c in x["categories"]))

    return result


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
    # Discussion Submission uses 'coursesc' for Course Schedule; others use 'course'
    course_schedule = getattr(doc, "coursesc", None) or doc.course
    max_grade = frappe.db.get_value("Course Schedule", course_schedule, "maxnumgrade")
    # Fetch the corresponding Course Assess Results Detail record
    cardname = frappe.db.get_value(
        "Course Assess Results Detail",
        {"assessment_criteria": doc.course_assess, "student_card": doc.student},
        "name",
    )
    if not cardname:
        frappe.log_error(
            (
                f"No Course Assess Results Detail found for "
                f"{doc.doctype} {doc.name}: assessment_criteria={doc.course_assess!r}, "
                f"student={doc.student!r}, course={course_schedule!r}. "
                f"Grade was not propagated to the gradebook."
            ),
            "quizresult_to_card: missing CARD row",
        )
        return
    card = frappe.get_doc("Course Assess Results Detail", cardname)

    # Update the raw score and extra credit points
    card.rawscore_card = doc.percentage if not doc.extra_credit else ""
    card.actualextrapt_card = (
        (doc.percentage / max_grade) * card.maxextrapoints_card
        if doc.extra_credit
        else ""
    )
    # Mark the cell as carrying a real grade (vs. the Float column's NOT NULL
    # default 0). Cleared if the prof unsets the submission grade.
    card.graded_card = 1 if doc.percentage not in (None, "") else 0
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
            print("Creating new doc with data:", doc.as_dict())
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
def get_student_invoices(student=None):
    # If the caller is a student user, always scope to their own Student
    # record — ignore any client-supplied `student` parameter to prevent a
    # student from querying someone else's invoices.
    from seminary.seminary.sales_invoice_permissions import (
        _current_student,
        _should_restrict,
    )

    if _should_restrict(frappe.session.user):
        student = _current_student(frappe.session.user)
        if not student:
            return []

    if not student:
        frappe.throw("student is required")

    # Only show invoices where the student is the customer (not church/scholarship)
    student_customer = frappe.db.get_value("Student", student, "customer")

    si_filters = {"custom_student": student, "docstatus": 1}
    if student_customer:
        si_filters["customer"] = student_customer

    sales_invoice_list = frappe.get_all(
        "Sales Invoice",
        filters=si_filters,
        fields=[
            "name",
            "customer",
            "posting_date",
            "due_date",
            "total",
            "outstanding_amount",
            "status",
            "is_return",
            "return_against",
            "custom_cei",
            "seminary_summary",
        ],
    )
    for invoice in sales_invoice_list:
        invoice["name"] = frappe.get_value("Sales Invoice", invoice["name"], "name")
        invoice["customer"] = frappe.get_value(
            "Customer", invoice["customer"], "customer_name"
        )
        # Prefer the explicit seminary_summary; fall back to the legacy CEI course
        # label so invoices that pre-date the summary field still get a label.
        summary = invoice.get("seminary_summary")
        if not summary and invoice.get("custom_cei"):
            course = frappe.db.get_value(
                "Course Enrollment Individual", invoice["custom_cei"], "course_data"
            )
            summary = _("Course: {0}").format(course) if course else None
        invoice["summary"] = summary
        invoice["course"] = summary  # back-compat for Fees.vue field name
        invoice["posting_date"] = frappe.utils.formatdate(invoice["posting_date"])
        invoice["outstanding_raw"] = invoice["outstanding_amount"]
        invoice["total_raw"] = invoice["total"]
        if invoice["is_return"]:
            invoice["status"] = "Return"
        invoice["total"] = "{:,.2f}".format(invoice["total"])
        invoice["outstanding_amount"] = "{:,.2f}".format(invoice["outstanding_amount"])
    sales_invoice_list = sorted(
        sales_invoice_list, key=lambda x: (x["status"], x["posting_date"]), reverse=True
    )

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
    # Get available scheduled courses for the student based on program enrollment,
    # emphasis tracks (from child table), academic term, and prerequisites

    courses = frappe.db.sql(
        """SELECT cs.course
        FROM `tabCourse Schedule` cs
        INNER JOIN `tabAcademic Term` aterm ON aterm.name = cs.academic_term
        WHERE cs.workflow_state = 'Open for Enrollment'
            AND aterm.iscurrent_acterm = '1'
            AND cs.course IN (
                (SELECT pc.course
                FROM `tabProgram Enrollment` pe
                INNER JOIN `tabProgram Course` pc ON pe.program = pc.parent
                WHERE pe.name = %s)
                UNION
                (SELECT ptc.program_track_course
                FROM `tabProgram Enrollment` pe
                INNER JOIN `tabProgram Enrollment Emphasis` pee ON pee.parent = pe.name
                INNER JOIN `tabProgram Track Courses` ptc
                    ON ptc.parent = pe.program
                    AND ptc.program_track = pee.emphasis_track
                WHERE pe.pgmenrol_active = '1'
                    AND pee.status = 'Active'
                    AND pe.name = %s)
            )
            AND cs.course NOT IN (
                SELECT c.name
                FROM `tabCourse` c
                INNER JOIN `tabCourse_prerequisite` cp ON cp.parent = c.name
                WHERE cp.prereq_mandatory = 'Mandatory'
                    AND c.name NOT IN (
                        SELECT pec.course
                        FROM `tabCourse_prerequisite` cp2
                        INNER JOIN `tabProgram Enrollment Course` pec ON cp2.parent = pec.course
                        WHERE pec.parent = %s
                            AND pec.pec_finalgradecode IS NOT NULL
                    )
            )
            AND cs.course NOT IN (
                SELECT pc.course
                FROM `tabProgram` p
                INNER JOIN `tabProgram Course` pc ON p.name = pc.parent
                INNER JOIN `tabProgram Enrollment` pe ON p.name = pe.program
                WHERE pe.name = %s
                    AND p.program_type = 'Time-based'
                    AND pc.course_term > pe.current_std_term
            )
            AND cs.course NOT IN (
                SELECT ptc.program_track_course
                FROM `tabProgram` p
                INNER JOIN `tabProgram Track Courses` ptc ON p.name = ptc.parent
                INNER JOIN `tabProgram Enrollment` pe ON p.name = pe.program
                WHERE pe.name = %s
                    AND p.program_type = 'Time-based'
                    AND ptc.term > pe.current_std_term
            )
            AND cs.course NOT IN (
                SELECT course_data
                FROM `tabCourse Enrollment Individual`
                WHERE audit = 0
                    AND docstatus != '2'
                    AND course_cancelled = 0
                    AND program_ce = %s
            )""",
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


def _billing_context():
    company = frappe.db.get_single_value("Seminary Settings", "company")
    return {
        "today": frappe.utils.today(),
        "company": company,
        "currency": erpnext.get_company_currency(company),
        "receivable_account": frappe.db.get_single_value(
            "Seminary Settings", "receivable_account"
        ),
        "income_account": frappe.db.get_value(
            "Company", company, "default_income_account"
        ),
        "cost_center": frappe.db.get_single_value("Seminary Settings", "cost_center")
        or None,
        "auto_submit": bool(
            frappe.db.get_single_value("Seminary Settings", "auto_submit_sales_invoice")
        ),
    }


def _empty_invoice_result(reason=""):
    return {"created": 0, "skipped": 0, "failed": 0, "reason": reason}


def _create_trigger_invoice(row, tag, ctx, counts, summary=""):
    # Safety net: an SI with this tag already exists — partial prior run or flag cleared.
    if frappe.db.exists(
        "Sales Invoice", {"seminary_trigger": tag, "docstatus": ["<", 2]}
    ):
        counts["skipped"] += 1
        return
    try:
        items = [
            {
                "doctype": "Sales Invoice Item",
                "item_code": row.item,
                "qty": (row.pay_percent or 0) / 100,
                "rate": 0,
                "description": summary or f"Fee for {row.fee_category}",
                "income_account": ctx["income_account"],
                "cost_center": ctx["cost_center"],
                "base_rate": 0,
                "price_list_rate": row.price_list_rate,
            }
        ]
        si = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "naming_series": "ACC-SINV-.YYYY.-",
                "posting_date": ctx["today"],
                "company": ctx["company"],
                "currency": ctx["currency"],
                "debit_to": ctx["receivable_account"],
                "income_account": ctx["income_account"],
                "conversion_rate": 1,
                "custom_student": row.student,
                "customer": row.customer,
                "selling_price_list": row.default_price_list,
                "base_grand_total": row.price_list_rate,
                "payment_terms_template": row.payterm_payer,
                "seminary_trigger": tag,
                "seminary_summary": summary,
                "items": items,
            }
        )
        si.run_method("set_missing_values")
        si.insert(ignore_permissions=True)
        if ctx["auto_submit"]:
            si.submit()
        counts["created"] += 1
    except Exception:
        counts["failed"] += 1
        frappe.log_error(frappe.get_traceback(), f"seminary billing tag {tag}")


@frappe.whitelist()
def generate_nat_invoices(academic_term):
    """Generate 'New Academic Term' Sales Invoices for the given term.

    Idempotent: fast-path exits if the term's invoiced_nat_on flag is set;
    per-row safety net checks seminary_trigger before each insert."""
    if not academic_term:
        return _empty_invoice_result("no term")
    if frappe.db.get_value("Academic Term", academic_term, "invoiced_nat_on"):
        return _empty_invoice_result("already invoiced")

    rows = frappe.db.sql(
        """
        SELECT pep.name AS pep_name, pfc.stu_link AS student,
               pep.fee_category, pep.payer AS customer,
               pep.pay_percent, pep.payterm_payer,
               fc.item,
               cg.default_price_list, ip.price_list_rate
        FROM `tabpgm_enroll_payers` pep
        INNER JOIN `tabPayers Fee Category PE` pfc ON pep.parent = pfc.name
        INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
        INNER JOIN `tabCustomer Group` cg ON pfc.pf_custgroup = cg.customer_group_name
        INNER JOIN `tabItem Price` ip
                ON cg.default_price_list = ip.price_list AND ip.item_code = fc.item
        INNER JOIN `tabProgram Enrollment` pe ON pe.name = pfc.pf_pe
        INNER JOIN `tabProgram` pgm ON pgm.name = pe.program
        WHERE pfc.pf_active = 1
          AND fc.docstatus = 1
          AND pep.pep_event = 'New Academic Term'
          AND COALESCE(pgm.is_free, 0) = 0
        """,
        as_dict=True,
    )
    ctx = _billing_context()
    counts = {"created": 0, "skipped": 0, "failed": 0}
    term_label = (
        frappe.db.get_value("Academic Term", academic_term, "term_name")
        or academic_term
    )
    for r in rows:
        summary = _("New Academic Term \u2014 {0} ({1})").format(
            term_label, r.fee_category
        )
        _create_trigger_invoice(
            r, f"NAT:{academic_term}:{r.pep_name}", ctx, counts, summary=summary
        )
    frappe.db.set_value("Academic Term", academic_term, "invoiced_nat_on", getdate())
    frappe.logger().info(f"generate_nat_invoices({academic_term}): {counts}")
    return counts


@frappe.whitelist()
def generate_nay_invoices(academic_year):
    """Generate 'New Academic Year' Sales Invoices for the given year.

    Idempotent via invoiced_nay_on flag + seminary_trigger safety net."""
    if not academic_year:
        return _empty_invoice_result("no year")
    if frappe.db.get_value("Academic Year", academic_year, "invoiced_nay_on"):
        return _empty_invoice_result("already invoiced")

    rows = frappe.db.sql(
        """
        SELECT pep.name AS pep_name, pfc.stu_link AS student,
               pep.fee_category, pep.payer AS customer,
               pep.pay_percent, pep.payterm_payer,
               fc.item,
               cg.default_price_list, ip.price_list_rate
        FROM `tabpgm_enroll_payers` pep
        INNER JOIN `tabPayers Fee Category PE` pfc ON pep.parent = pfc.name
        INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
        INNER JOIN `tabCustomer Group` cg ON pfc.pf_custgroup = cg.customer_group_name
        INNER JOIN `tabItem Price` ip
                ON cg.default_price_list = ip.price_list AND ip.item_code = fc.item
        INNER JOIN `tabProgram Enrollment` pe ON pe.name = pfc.pf_pe
        INNER JOIN `tabProgram` pgm ON pgm.name = pe.program
        WHERE pfc.pf_active = 1
          AND fc.docstatus = 1
          AND pep.pep_event = 'New Academic Year'
          AND COALESCE(pgm.is_free, 0) = 0
        """,
        as_dict=True,
    )
    ctx = _billing_context()
    counts = {"created": 0, "skipped": 0, "failed": 0}
    for r in rows:
        summary = _("New Academic Year \u2014 {0} ({1})").format(
            academic_year, r.fee_category
        )
        _create_trigger_invoice(
            r, f"NAY:{academic_year}:{r.pep_name}", ctx, counts, summary=summary
        )
    frappe.db.set_value("Academic Year", academic_year, "invoiced_nay_on", getdate())
    frappe.logger().info(f"generate_nay_invoices({academic_year}): {counts}")
    return counts


def _ensure_applicant_customer(applicant):
    """Return the Customer for a Student Applicant, creating one if missing.

    Strategy: prefer the link already on the applicant, then a Customer
    matching the applicant's email, then create a fresh Customer using the
    applicant's title and customer_group (defaulting to "Individual").
    """
    if applicant.customer and frappe.db.exists("Customer", applicant.customer):
        return applicant.customer

    if applicant.student_email_id:
        existing = frappe.db.get_value(
            "Customer",
            {"email_id": applicant.student_email_id},
            "name",
        )
        if existing:
            applicant.db_set("customer", existing, update_modified=False)
            return existing

    customer_group = applicant.customer_group or "Individual"
    if not frappe.db.exists("Customer Group", customer_group):
        frappe.throw(
            _(
                "Customer Group {0} does not exist; set a valid Customer Group on the applicant before submitting."
            ).format(customer_group)
        )

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": applicant.title or applicant.name,
            "customer_type": "Individual",
            "customer_group": customer_group,
            "email_id": applicant.student_email_id,
        }
    )
    customer.flags.ignore_permissions = True
    customer.insert(ignore_permissions=True)
    applicant.db_set("customer", customer.name, update_modified=False)
    return customer.name


def generate_application_invoices(applicant_name):
    """Generate Application-fee Sales Invoices for a Student Applicant.

    Walks `Program.pgm_pgmfees` rows where `pgm_feeevent = 'Application'`
    and creates one Sales Invoice per submitted Fee Category that has an
    Item Price under the resolved Customer Group's default price list.

    Idempotent: per-row safety net via `seminary_trigger = APP:<applicant>:<pf_row>`.
    Free programs and applicants whose Program has no Application fee
    configured are no-ops.
    """
    if not applicant_name:
        return _empty_invoice_result("no applicant")
    applicant = frappe.get_doc("Student Applicant", applicant_name)
    if not applicant.program:
        return _empty_invoice_result("no program")
    program = frappe.get_doc("Program", applicant.program)
    if program.is_free:
        return _empty_invoice_result("free program")

    application_rows = [
        row
        for row in (program.pgm_pgmfees or [])
        if row.pgm_feeevent == "Application" and row.pgm_feecategory
    ]
    if not application_rows:
        return _empty_invoice_result("no Application fee configured on program")

    customer = _ensure_applicant_customer(applicant)
    customer_group = frappe.db.get_value("Customer", customer, "customer_group")
    default_price_list = frappe.db.get_value(
        "Customer Group", customer_group, "default_price_list"
    )
    if not default_price_list:
        frappe.throw(
            _(
                "Customer Group {0} has no default Price List; cannot price the Application fee."
            ).format(customer_group)
        )

    ctx = _billing_context()
    counts = {"created": 0, "skipped": 0, "failed": 0}

    for pf_row in application_rows:
        tag = f"APP:{applicant_name}:{pf_row.name}"
        if frappe.db.exists(
            "Sales Invoice", {"seminary_trigger": tag, "docstatus": ["<", 2]}
        ):
            counts["skipped"] += 1
            continue

        fc = frappe.db.get_value(
            "Fee Category",
            pf_row.pgm_feecategory,
            ["item", "payment_term_template", "docstatus"],
            as_dict=True,
        )
        if not fc or fc.docstatus != 1 or not fc.item:
            counts["skipped"] += 1
            continue

        price_list_rate = frappe.db.get_value(
            "Item Price",
            {"price_list": default_price_list, "item_code": fc.item},
            "price_list_rate",
        )
        if price_list_rate is None:
            counts["skipped"] += 1
            frappe.log_error(
                f"No Item Price for {fc.item} on {default_price_list}; "
                f"skipped Application fee for {applicant_name}.",
                "generate_application_invoices",
            )
            continue

        summary = _("Application — {0}").format(pf_row.pgm_feecategory)
        try:
            si = frappe.get_doc(
                {
                    "doctype": "Sales Invoice",
                    "naming_series": "ACC-SINV-.YYYY.-",
                    "posting_date": ctx["today"],
                    "company": ctx["company"],
                    "currency": ctx["currency"],
                    "debit_to": ctx["receivable_account"],
                    "income_account": ctx["income_account"],
                    "conversion_rate": 1,
                    "customer": customer,
                    "selling_price_list": default_price_list,
                    "base_grand_total": price_list_rate,
                    "payment_terms_template": fc.payment_term_template,
                    "remarks": summary,
                    "seminary_trigger": tag,
                    "seminary_summary": summary,
                    "items": [
                        {
                            "doctype": "Sales Invoice Item",
                            "item_code": fc.item,
                            "qty": 1,
                            "rate": 0,
                            "description": _("Application fee for program {0}").format(
                                applicant.program
                            ),
                            "income_account": ctx["income_account"],
                            "cost_center": ctx["cost_center"],
                            "base_rate": 0,
                            "price_list_rate": price_list_rate,
                        }
                    ],
                    "cost_center": ctx["cost_center"],
                }
            )
            si.flags.ignore_permissions = True
            si.run_method("set_missing_values")
            si.insert(ignore_permissions=True)
            if ctx["auto_submit"]:
                si.submit()
            counts["created"] += 1
        except Exception:
            counts["failed"] += 1
            frappe.log_error(
                frappe.get_traceback(), f"seminary application billing tag {tag}"
            )

    frappe.logger().info(f"generate_application_invoices({applicant_name}): {counts}")
    return counts


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
            "discussion": criteria.get("discussion"),
            "extracredit_scac": criteria.get("extracredit_scac"),
            "fudgepoints_scac": criteria.get("fudgepoints_scac"),
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def generate_monthly_invoices(as_of=None):
    """Generate 'Monthly' Sales Invoices on the 1st of the month for every
    active Program Enrollment whose linked Fee Categories use fc_event='Monthly'.

    Idempotent: skips PEs whose last_monthly_invoiced_on is already >= the
    first of the current month; safety-net tag check prevents duplicates."""
    from frappe.utils import get_first_day

    as_of = getdate(as_of) if as_of else getdate()
    first_of_month = get_first_day(as_of)
    month_tag = as_of.strftime("%Y-%m")

    active_pes = frappe.db.sql(
        """
        SELECT DISTINCT pfc.pf_pe AS pe_name
        FROM `tabPayers Fee Category PE` pfc
        INNER JOIN `tabpgm_enroll_payers` pep ON pep.parent = pfc.name
        INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
        INNER JOIN `tabProgram Enrollment` pe ON pe.name = pfc.pf_pe
        INNER JOIN `tabProgram` pgm ON pgm.name = pe.program
        WHERE pfc.pf_active = 1
          AND fc.docstatus = 1
          AND pep.pep_event = 'Monthly'
          AND pe.pgmenrol_active = 1
          AND COALESCE(pgm.is_free, 0) = 0
          AND (pe.last_monthly_invoiced_on IS NULL OR pe.last_monthly_invoiced_on < %s)
          AND (fc.effective_from IS NULL OR pe.enrollment_date > fc.effective_from)
        """,
        (first_of_month,),
        as_dict=True,
    )

    ctx = _billing_context()
    counts = {"created": 0, "skipped": 0, "failed": 0}
    month_label = as_of.strftime("%B %Y")
    for pe_row in active_pes:
        pe_name = pe_row.pe_name
        rows = frappe.db.sql(
            """
            SELECT pep.name AS pep_name, pfc.stu_link AS student,
                   pep.fee_category, pep.payer AS customer,
                   pep.pay_percent, pep.payterm_payer,
                   fc.item,
                   cg.default_price_list, ip.price_list_rate
            FROM `tabpgm_enroll_payers` pep
            INNER JOIN `tabPayers Fee Category PE` pfc ON pep.parent = pfc.name
            INNER JOIN `tabFee Category` fc ON pep.fee_category = fc.name
            INNER JOIN `tabCustomer Group` cg ON pfc.pf_custgroup = cg.customer_group_name
            INNER JOIN `tabItem Price` ip
                    ON cg.default_price_list = ip.price_list AND ip.item_code = fc.item
            INNER JOIN `tabProgram Enrollment` pe ON pe.name = pfc.pf_pe
            WHERE pfc.pf_active = 1
              AND fc.docstatus = 1
              AND pep.pep_event = 'Monthly'
              AND pfc.pf_pe = %s
              AND (fc.effective_from IS NULL OR pe.enrollment_date > fc.effective_from)
            """,
            (pe_name,),
            as_dict=True,
        )
        for r in rows:
            summary = _("Monthly \u2014 {0} ({1})").format(month_label, r.fee_category)
            _create_trigger_invoice(
                r,
                f"MONTHLY:{month_tag}:{r.pep_name}",
                ctx,
                counts,
                summary=summary,
            )
        frappe.db.set_value(
            "Program Enrollment", pe_name, "last_monthly_invoiced_on", first_of_month
        )
    frappe.logger().info(f"generate_monthly_invoices({as_of}): {counts}")
    return counts


@frappe.whitelist()
def get_pgmenrollments(name):
    program_enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": name, "docstatus": 1},
        fields=[
            "name",
            "program",
            "pgmenrol_active",
            "enrollment_date",
            "date_of_conclusion",
        ],
        order_by="pgmenrol_active desc, enrollment_date desc",
    )
    return program_enrollments or []


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
                row.grade = get_grade(grading_scale.name, score)
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
        fgrade = get_grade(grading_scale.name, fscore)
        frappe.db.set_value("Scheduled Course Roster", name, "fgrade", fgrade)
        fgradepass = get_gradepass(grading_scale.name, fscore)
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

    state = frappe.db.get_value("Course Schedule", docname, "workflow_state")
    if state == "Closed":
        return "All grades sent"
    if state != "Grading":
        frappe.throw(
            _(
                "Send Grades is only available while the course is in the "
                "Grading state. Current state: {0}."
            ).format(state or _("(none)"))
        )

    missing = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT scr.name)
        FROM `tabCourse Assess Results Detail` card
        JOIN `tabScheduled Course Roster` scr ON card.parent = scr.name
        LEFT JOIN `tabCourse Enrollment Individual` cei
            ON cei.coursesc_ce = scr.course_sc
           AND cei.student_ce = scr.student
           AND cei.docstatus = 1
        WHERE scr.course_sc = %s
          AND scr.active = 1
          AND scr.audit_bool = 0
          AND COALESCE(cei.course_cancelled, 0) = 0
          AND COALESCE(card.graded_card, 0) = 0
        """,
        (docname,),
    )
    missing_count = missing[0][0] if missing else 0
    if missing_count:
        frappe.throw(
            _(
                "Cannot send grades: {0} student(s) still have ungraded "
                "assessments. Fill in all grades (or 0 explicitly) before sending."
            ).format(missing_count)
        )

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
            frappe.db.set_value("Scheduled Course Roster", named, "active", 0)
        else:
            continue

    # System-driven transition: bypass the workflow validator (the "Send
    # Grades" transition is intentionally absent from the workflow fixture
    # so the Desk Action menu can't bypass the grade computation and PEC
    # update above). Mirrors the cancel_course pattern.
    frappe.db.set_value("Course Schedule", docname, "workflow_state", "Closed")

    # After grades are sent, recalculate track credits and check auto-grant emphases
    affected_pes = set()
    for record in records:
        if record.audit_bool == 0 and record.active == 1:
            pe_name = frappe.db.get_value(
                "Program Enrollment",
                {"student": record.student, "program": record.program_std_scr},
                "name",
            )
            if pe_name:
                affected_pes.add(pe_name)

    from seminary.seminary.gpa import recompute_program_enrollment_gpa

    for pe_name in affected_pes:
        _recalculate_emphasis_credits(pe_name)
        _check_auto_grant_emphases(pe_name)
        recompute_program_enrollment_gpa(pe_name)

    return "All grades sent"


def _recalculate_emphasis_credits(pe_name):
    """Recalculate track credits for all emphases on a single Program Enrollment."""
    pe = frappe.get_doc("Program Enrollment", pe_name)
    program_name = pe.program

    for emphasis in pe.emphases or []:
        if emphasis.status not in ("Active", "Completed"):
            continue

        credits = frappe.db.sql(
            """SELECT COALESCE(SUM(pec.credits), 0)
            FROM `tabProgram Enrollment Course` pec
            INNER JOIN `tabProgram Track Courses` ptc
                ON ptc.program_track_course = pec.course_name
                AND ptc.parent = %s
                AND ptc.program_track = %s
            WHERE pec.parent = %s AND pec.status = 'Pass'""",
            (program_name, emphasis.emphasis_track, pe_name),
        )[0][0]

        max_credits = frappe.db.get_value(
            "Program Track", emphasis.emphasis_track, "max_credits"
        )
        if max_credits and max_credits > 0 and credits > max_credits:
            credits = max_credits

        frappe.db.set_value(
            "Program Enrollment Emphasis", emphasis.name, "trackcredits", int(credits)
        )


def _check_auto_grant_emphases(pe_name):
    """Check if any auto-grant emphases should be awarded for this PE."""
    pe = frappe.get_doc("Program Enrollment", pe_name)
    program = frappe.get_cached_doc("Program", pe.program)

    existing_tracks = {e.emphasis_track for e in (pe.emphases or [])}

    for track in program.pgm_pgmtracks:
        if not track.is_emphasis or track.emphasis_declaration != "Auto-grant":
            continue
        if track.name in existing_tracks:
            continue

        # Check if student meets requirements: all mandatory track courses passed
        mandatory_track_courses = frappe.get_all(
            "Program Track Courses",
            filters={
                "parent": pe.program,
                "program_track": track.name,
                "pgm_track_course_mandatory": 1,
            },
            fields=["program_track_course"],
        )

        all_mandatory_passed = True
        for tc in mandatory_track_courses:
            passed = frappe.db.exists(
                "Program Enrollment Course",
                {
                    "parent": pe_name,
                    "course_name": tc.program_track_course,
                    "status": "Pass",
                },
            )
            if not passed:
                all_mandatory_passed = False
                break

        if not all_mandatory_passed:
            continue

        # Check track credit requirement
        track_credits = frappe.db.sql(
            """SELECT COALESCE(SUM(pec.credits), 0)
            FROM `tabProgram Enrollment Course` pec
            INNER JOIN `tabProgram Track Courses` ptc
                ON ptc.program_track_course = pec.course_name
                AND ptc.parent = %s
                AND ptc.program_track = %s
            WHERE pec.parent = %s AND pec.status = 'Pass'""",
            (pe.program, track.name, pe_name),
        )[0][0]

        if track_credits >= (track.addcredits or 0):
            # Auto-grant this emphasis
            pe.reload()
            pe.append(
                "emphases",
                {
                    "emphasis_track": track.name,
                    "declared_date": frappe.utils.today(),
                    "status": "Completed",
                    "trackcredits": int(track_credits),
                },
            )
            pe.flags.ignore_validate = True
            pe.save(ignore_permissions=True)
            frappe.msgprint(
                f"Emphasis '{track.track_name}' auto-granted for {pe.student_name}",
                alert=True,
            )


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
    """Return the current admission Doctrinal Statement for the web form.

    Picks the most recently created submitted DS that is both `active` and
    flagged `use_in_student_admission`. Returns `{name, title, body}` or
    None if none configured. The body is the HTML stored in the DS's
    `doctrinal_statement` field, ready for direct injection.
    """
    row = frappe.db.get_value(
        "Doctrinal Statement",
        {
            "active": 1,
            "use_in_student_admission": 1,
            "docstatus": 1,
        },
        ["name", "ds_title", "doctrinal_statement"],
        as_dict=True,
        order_by="creation desc",
    )
    if not row:
        return None
    return {"name": row.name, "title": row.ds_title, "body": row.doctrinal_statement}


@frappe.whitelist(allow_guest=True)
def get_application_payment_url(applicant_name):
    """Return a payment URL for a Student Applicant's outstanding Application
    Sales Invoice, plus any alternative payment instructions configured on
    Seminary Settings. Used by the public Student Applicant web form to let
    applicants pay immediately after submitting.

    Returns a dict:
        payment_url: gateway URL (None if no gateway / no SI / already paid)
        amount: outstanding amount on the invoice
        currency: invoice currency
        alternative_instructions: HTML from Seminary Settings (if configured)
    Returns None if applicant doesn't exist.
    """
    if not applicant_name or not frappe.db.exists("Student Applicant", applicant_name):
        return None

    settings = frappe.get_single("Seminary Settings")
    alternative_instructions = settings.get("alternative_payment_instructions") or None

    invoice = frappe.db.sql(
        """
        SELECT name, currency, outstanding_amount
        FROM `tabSales Invoice`
        WHERE seminary_trigger LIKE %(prefix)s
          AND docstatus < 2
          AND outstanding_amount > 0
        ORDER BY creation DESC
        LIMIT 1
        """,
        {"prefix": f"APP:{applicant_name}:%"},
        as_dict=True,
    )

    if not invoice:
        return {
            "payment_url": None,
            "amount": None,
            "currency": None,
            "alternative_instructions": alternative_instructions,
        }

    inv = invoice[0]
    payment_url = None
    if settings.portal_payment_enable and settings.payment_gateway:
        try:
            payment_url = _create_application_payment_url(inv.name, settings)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"get_application_payment_url({applicant_name})",
            )

    return {
        "payment_url": payment_url,
        "amount": inv.outstanding_amount,
        "currency": inv.currency,
        "alternative_instructions": alternative_instructions,
    }


def _create_application_payment_url(invoice_name, settings):
    """Create a Payment Request for an Application SI and return the URL.
    Mirrors get_invoice_payment_url but skips the student-permission gate
    (applicant payments come from the guest web form context — they need
    to pay before they have a Student record)."""
    gateway_account = frappe.db.get_value(
        "Payment Gateway Account",
        {"payment_gateway": settings.payment_gateway},
        "name",
    )
    if not gateway_account:
        return None

    from erpnext.accounts.doctype.payment_request.payment_request import (
        cancel_old_payment_requests,
        get_amount,
        get_gateway_details,
    )

    ref_doc = frappe.get_doc("Sales Invoice", invoice_name)
    gateway = (
        get_gateway_details(
            frappe._dict(
                {
                    "payment_gateway_account": gateway_account,
                    "company": ref_doc.company,
                }
            )
        )
        or frappe._dict()
    )

    grand_total = get_amount(ref_doc, gateway.get("payment_account"))
    if not grand_total:
        return None

    cancel_old_payment_requests("Sales Invoice", invoice_name)

    pr = frappe.new_doc("Payment Request")
    pr.update(
        {
            "payment_gateway_account": gateway.get("name"),
            "payment_gateway": gateway.get("payment_gateway"),
            "payment_account": gateway.get("payment_account"),
            "payment_channel": gateway.get("payment_channel"),
            "payment_request_type": "Inward",
            "currency": ref_doc.currency,
            "grand_total": grand_total,
            "email_to": ref_doc.owner,
            "subject": _("Application Payment for {0}").format(ref_doc.customer),
            "message": gateway.get("message") or "",
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice_name,
            "company": ref_doc.company,
            "party_type": "Customer",
            "party": ref_doc.customer,
            "mute_email": 1,
        }
    )
    pr.flags.ignore_permissions = True
    pr.insert(ignore_permissions=True)
    pr.submit()
    return pr.get_payment_url()


@frappe.whitelist(allow_guest=True)
def get_default_phone_country():
    """Return the configured Seminary company's country as a full name
    string (e.g. "United States"). Frappe's Phone control reads
    `frappe.sys_defaults.country` and matches by name; web forms set this
    on load to override the hard-coded "India" default."""
    company = frappe.db.get_single_value("Seminary Settings", "company")
    if not company:
        return None
    return frappe.db.get_value("Company", company, "country")


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
    pe_query = frappe.db.sql(
        """select pf_pe from `tabPayers Fee Category PE` where name LIKE %s""",
        (f"%{txt}%",),
    )
    # Adding check to ensure pe_query has results before accessing [0][0]
    if not pe_query or not pe_query[0][0]:
        return []
    program_enrollment = pe_query[0][0]
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


@frappe.whitelist()
def GradeableDiscussion(courseName, discussionID):
    count = frappe.db.sql(
        """select count(c.name)
from `tabScheduled Course Assess Criteria` c,
`tabCourse Schedule` cs
where cs.name = %s and
cs.name = c.parent and
c.discussion = %s""",
        (courseName, discussionID),
    )
    return count[0][0] > 0 if count else False


@frappe.whitelist()
def get_invoice_payment_url(invoice_name):
    """Create a Payment Request for a Sales Invoice and return the payment URL.

    Students can only request payment for their own invoices (validated via
    custom_student on the Sales Invoice).
    """
    from seminary.seminary.sales_invoice_permissions import (
        _current_student,
        _should_restrict,
    )

    # Validate that the student owns this invoice
    if _should_restrict(frappe.session.user):
        student = _current_student(frappe.session.user)
        invoice_student = frappe.db.get_value(
            "Sales Invoice", invoice_name, "custom_student"
        )
        if not student or invoice_student != student:
            frappe.throw(_("You do not have permission to pay this invoice."))

    settings = frappe.get_single("Seminary Settings")
    if not settings.portal_payment_enable or not settings.payment_gateway:
        frappe.throw(
            _("Online payments are not enabled. Please contact the administration.")
        )

    gateway_account = frappe.db.get_value(
        "Payment Gateway Account",
        {"payment_gateway": settings.payment_gateway},
        "name",
    )
    if not gateway_account:
        frappe.throw(
            _("No Payment Gateway Account configured for {0}.").format(
                settings.payment_gateway
            )
        )

    from erpnext.accounts.doctype.payment_request.payment_request import (
        cancel_old_payment_requests,
        get_gateway_details,
        get_amount,
    )

    ref_doc = frappe.get_doc("Sales Invoice", invoice_name)
    gateway = (
        get_gateway_details(
            frappe._dict(
                {
                    "payment_gateway_account": gateway_account,
                    "company": ref_doc.company,
                }
            )
        )
        or frappe._dict()
    )

    grand_total = get_amount(ref_doc, gateway.get("payment_account"))
    if not grand_total:
        frappe.throw(_("This invoice has already been paid."))

    # Cancel any incomplete Payment Requests (submitted but not paid),
    # following the webshop pattern for re-payment attempts.
    cancel_old_payment_requests("Sales Invoice", invoice_name)

    pr = frappe.new_doc("Payment Request")
    pr.update(
        {
            "payment_gateway_account": gateway.get("name"),
            "payment_gateway": gateway.get("payment_gateway"),
            "payment_account": gateway.get("payment_account"),
            "payment_channel": gateway.get("payment_channel"),
            "payment_request_type": "Inward",
            "currency": ref_doc.currency,
            "grand_total": grand_total,
            "email_to": ref_doc.owner,
            "subject": _("Payment Request for {0}").format(invoice_name),
            "message": gateway.get("message") or "",
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice_name,
            "company": ref_doc.company,
            "party_type": "Customer",
            "party": ref_doc.customer,
            "mute_email": 1,
        }
    )
    pr.insert(ignore_permissions=True)
    pr.submit()

    return {"payment_url": pr.get_payment_url()}


@frappe.whitelist()
def get_student_balance_payment_url():
    """Pay the full outstanding on the student's open Student Balance."""
    from seminary.seminary.sales_invoice_permissions import (
        _current_student,
        _should_restrict,
    )

    if not _should_restrict(frappe.session.user):
        frappe.throw(_("This action is only available for students."))

    student = _current_student(frappe.session.user)
    if not student:
        frappe.throw(_("Student record not found."))

    settings = frappe.get_single("Seminary Settings")
    if not settings.portal_payment_enable or not settings.payment_gateway:
        frappe.throw(_("Online payments are not enabled."))

    sb = _get_open_student_balance(student)

    if flt(sb.net_outstanding) <= 0:
        frappe.throw(_("No outstanding balance to pay."))

    # Set allocated_amount = outstanding_amount on each non-return row
    for row in sb.invoices:
        if not row.is_return and flt(row.outstanding_amount) > 0:
            row.allocated_amount = row.outstanding_amount
        else:
            row.allocated_amount = 0
    sb.save(ignore_permissions=True)

    pr = _create_balance_payment_request(sb, sb.net_outstanding, settings)
    return {"payment_url": pr.get_payment_url(), "student_balance": sb.name}


@frappe.whitelist()
def get_student_partial_balance_payment_url(amount=None, invoices=None):
    """Pay a partial amount against the student's open Student Balance.

    Args:
        amount: Fixed amount to pay (allocated by due date order).
        invoices: JSON list of {"sales_invoice": name, "amount": value} dicts.
    """
    from seminary.seminary.sales_invoice_permissions import (
        _current_student,
        _should_restrict,
    )

    if not _should_restrict(frappe.session.user):
        frappe.throw(_("This action is only available for students."))

    student = _current_student(frappe.session.user)
    if not student:
        frappe.throw(_("Student record not found."))

    settings = frappe.get_single("Seminary Settings")
    if not settings.portal_payment_enable or not settings.payment_gateway:
        frappe.throw(_("Online payments are not enabled."))

    sb = _get_open_student_balance(student)

    if flt(sb.net_outstanding) <= 0:
        frappe.throw(_("No outstanding balance to pay."))

    # Reset all allocations
    for row in sb.invoices:
        row.allocated_amount = 0

    if invoices:
        # Parse if string
        if isinstance(invoices, str):
            invoices = json.loads(invoices)
        invoice_map = {item["sales_invoice"]: flt(item["amount"]) for item in invoices}
        for row in sb.invoices:
            if row.sales_invoice in invoice_map:
                alloc = min(invoice_map[row.sales_invoice], flt(row.outstanding_amount))
                row.allocated_amount = alloc
    elif amount:
        amount = flt(amount)
        if amount <= 0 or amount > flt(sb.net_outstanding):
            frappe.throw(_("Invalid payment amount."))
        # Allocate by due date
        remaining = amount
        sorted_rows = sorted(sb.invoices, key=lambda r: r.due_date or "9999-12-31")
        for row in sorted_rows:
            if row.is_return or flt(row.outstanding_amount) <= 0:
                continue
            alloc = min(flt(row.outstanding_amount), remaining)
            row.allocated_amount = alloc
            remaining -= alloc
            if remaining <= 0:
                break
    else:
        frappe.throw(_("Please specify an amount or select invoices to pay."))

    total_allocated = sum(
        flt(row.allocated_amount)
        for row in sb.invoices
        if not row.is_return and flt(row.allocated_amount) > 0
    )
    if total_allocated <= 0:
        frappe.throw(_("No amount allocated for payment."))

    sb.save(ignore_permissions=True)

    pr = _create_balance_payment_request(sb, total_allocated, settings)
    return {"payment_url": pr.get_payment_url(), "student_balance": sb.name}


def _get_open_student_balance(student):
    """Get the open Student Balance for a student, or throw."""
    sb_name = frappe.db.get_value(
        "Student Balance", {"student": student, "is_open": 1}, "name"
    )
    if not sb_name:
        frappe.throw(_("No open balance found for this student."))
    return frappe.get_doc("Student Balance", sb_name)


def _create_balance_payment_request(sb, amount, settings):
    """Create and submit a Payment Request against a Student Balance."""
    from erpnext.accounts.doctype.payment_request.payment_request import (
        cancel_old_payment_requests,
    )

    gateway_account = frappe.db.get_value(
        "Payment Gateway Account",
        {"payment_gateway": settings.payment_gateway},
        ["name", "payment_gateway", "payment_account", "payment_channel", "message"],
        as_dict=True,
    )
    if not gateway_account:
        frappe.throw(
            _("No Payment Gateway Account configured for {0}.").format(
                settings.payment_gateway
            )
        )

    cancel_old_payment_requests("Student Balance", sb.name)

    pr = frappe.new_doc("Payment Request")
    pr.update(
        {
            "payment_gateway_account": gateway_account.name,
            "payment_gateway": gateway_account.payment_gateway,
            "payment_account": gateway_account.payment_account,
            "payment_channel": gateway_account.payment_channel,
            "payment_request_type": "Inward",
            "currency": sb.currency,
            "grand_total": amount,
            "email_to": frappe.session.user,
            "subject": _("Payment for Student Balance {0}").format(sb.name),
            "message": gateway_account.message or "",
            "reference_doctype": "Student Balance",
            "reference_name": sb.name,
            "company": sb.company,
            "party_type": "Customer",
            "party": sb.customer,
            "mute_email": 1,
        }
    )
    # Add a payment_reference row so that validate_payment_request_amount
    # is skipped — it only knows standard doctypes like Sales Invoice.
    pr.append(
        "payment_reference",
        {
            "amount": amount,
            "description": _("Student Balance {0}").format(sb.name),
        },
    )
    pr.insert(ignore_permissions=True)
    pr.submit()

    sb.db_set("payment_request", pr.name)
    return pr


@frappe.whitelist()
def get_my_announcements(limit=100):
    """Return announcements sent to the current user.

    Joined via Seminary Announcement Recipient matched by user or email.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.AuthenticationError)

    return frappe.db.sql(
        """
        SELECT
            sa.name,
            sa.subject,
            sa.message,
            sa.sent_datetime,
            sa.academic_term
        FROM `tabSeminary Announcement Recipient` r
        JOIN `tabSeminary Announcement` sa ON r.parent = sa.name
        WHERE sa.docstatus = 1
          AND sa.status = 'Sent'
          AND r.delivery_status = 'Sent'
          AND (r.user = %(user)s OR r.email = %(user)s)
        ORDER BY sa.sent_datetime DESC
        LIMIT %(limit)s
        """,
        {"user": frappe.session.user, "limit": cint(limit)},
        as_dict=True,
    )


@frappe.whitelist()
def preview_announcement_recipients(name):
    """Resolve the recipient list for a draft Seminary Announcement without sending.

    Returns {total, sample} where sample is the first 50 resolved rows.
    """
    from seminary.seminary.doctype.seminary_announcement.announcement_recipients import (
        resolve_recipients,
    )

    doc = frappe.get_doc("Seminary Announcement", name)
    if doc.docstatus != 0:
        frappe.throw(_("Preview is only available on draft announcements."))

    resolved = resolve_recipients(doc)
    return {
        "total": len(resolved),
        "sample": resolved[:50],
    }


_PROGRAM_PRICING_TEMPLATE = """
<style>
.program-pricing { font-size: 13px; margin-left: 6px; }
.program-pricing h2 { margin-top: 1.5rem; padding-bottom: 0.25rem; border-bottom: 2px solid #333; }
.program-pricing h2 .currency { font-weight: normal; color: #555; font-size: 0.85em; }
.program-pricing .customer-groups { margin: 0.5rem 0 1rem; color: #444; }
.program-pricing .program-block { margin: 1rem 0 1.5rem; padding: 0.75rem 1rem; border: 1px solid #ddd; border-radius: 4px; page-break-inside: avoid; }
.program-pricing .program-block h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.program-pricing .program-meta { list-style: none; padding: 0; margin: 0 0 0.75rem; display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; color: #333; }
.program-pricing .program-meta li { margin: 0; }
.program-pricing .fees-table { width: 100%; border-collapse: collapse; }
.program-pricing .fees-table th, .program-pricing .fees-table td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; vertical-align: top; }
.program-pricing .fees-table th { background: #f5f5f5; font-weight: 600; }
.program-pricing .fees-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.program-pricing .not-priced { color: #c0392b; font-weight: 600; }
.program-pricing .check { color: #2e7d32; font-weight: 700; }
.program-pricing .no-fees { color: #777; font-style: italic; margin: 0; }
@media print {
  .program-pricing h2 { page-break-after: avoid; }
}
</style>
<div class="program-pricing">
{% for pl in price_lists %}
  <section class="price-list-section">
    <h2>{{ _("Price List") }}: {{ pl.name }}{% if pl.currency %} <span class="currency">— {{ _("Currency") }}: {{ pl.currency }}</span>{% endif %}</h2>
    <p class="customer-groups">
      <strong>{{ _("This price list affects the following customer groups:") }}</strong>
      {% if pl.customer_groups %}{{ pl.customer_groups | join(", ") }}{% else %}<em>{{ _("None") }}</em>{% endif %}
    </p>
    {% for program in programs %}
      <article class="program-block">
        <h3>{{ program.program_name or program.name }}</h3>
        <ul class="program-meta">
          <li><strong>{{ _("Free Program") }}:</strong> {% if program.is_free %}<span class="check">✓</span>{% else %}—{% endif %}</li>
          <li><strong>{{ _("Require Payment Before Enrollment") }}:</strong> {% if program.require_pay_submit %}<span class="check">✓</span>{% else %}—{% endif %}</li>
          <li><strong>{{ _("Minimum Payment %") }}:</strong> {{ (program.percent_to_pay or 0) }}%</li>
        </ul>
        {% if program.fees %}
        <table class="fees-table">
          <thead>
            <tr>
              <th>{{ _("Fee Category") }}</th>
              <th>{{ _("Event to charge") }}</th>
              <th>{{ _("Item") }}</th>
              <th>{{ _("Academic Credit") }}</th>
              <th>{{ _("Audit") }}</th>
              <th>{{ _("Payment Term") }}</th>
              <th>{{ _("Item Price") }}</th>
              <th>{{ _("Price last modified on") }}</th>
            </tr>
          </thead>
          <tbody>
            {% for fee in program.fees %}
              {% set price = pl.prices.get(fee.item) if fee.item else None %}
              <tr>
                <td>{{ fee.fee_category or "—" }}</td>
                <td>{{ fee.event or "—" }}</td>
                <td>{{ fee.item or "—" }}</td>
                <td>{% if fee.is_credit %}<span class="check">✓</span>{% else %}—{% endif %}</td>
                <td>{% if fee.is_audit %}<span class="check">✓</span>{% else %}—{% endif %}</td>
                <td>{{ fee.payment_term_template or "—" }}</td>
                {% if price %}
                  <td class="num">{{ "{:,.2f}".format(price.rate or 0) }}</td>
                  <td>{{ price.modified_display or "—" }}</td>
                {% else %}
                  <td class="not-priced">{{ _("Not priced") }}</td>
                  <td class="not-priced">—</td>
                {% endif %}
              </tr>
            {% endfor %}
          </tbody>
        </table>
        {% else %}
        <p class="no-fees">{{ _("No fees configured.") }}</p>
        {% endif %}
      </article>
    {% endfor %}
  </section>
{% else %}
  <p>{{ _("No selling price lists found.") }}</p>
{% endfor %}
</div>
"""


@frappe.whitelist()
def get_program_pricing_html():
    """Render the Program Pricing report (one block per selling Price List).

    Resolves: customer groups whose default_price_list = the price list,
    every Program with its Program Fees rows, the Fee Category lookups
    (item, is_credit, is_audit, payment_term_template), and the matching
    Item Price for the chosen Price List.
    """
    price_lists = frappe.get_all(
        "Price List",
        filters={"selling": 1, "enabled": 1},
        fields=["name", "currency"],
        order_by="name asc",
    )

    programs_raw = frappe.get_all(
        "Program",
        fields=[
            "name",
            "program_name",
            "is_free",
            "require_pay_submit",
            "percent_to_pay",
        ],
        order_by="program_name asc",
    )
    program_names = [p["name"] for p in programs_raw]

    fee_rows = []
    if program_names:
        fee_rows = frappe.get_all(
            "Program Fees",
            filters={"parenttype": "Program", "parent": ["in", program_names]},
            fields=["parent", "pgm_feecategory", "pgm_feeevent", "idx"],
            order_by="parent asc, idx asc",
        )

    fee_category_names = sorted(
        {r["pgm_feecategory"] for r in fee_rows if r.get("pgm_feecategory")}
    )
    fee_categories = {}
    if fee_category_names:
        for fc in frappe.get_all(
            "Fee Category",
            filters={"name": ["in", fee_category_names]},
            fields=[
                "name",
                "category_name",
                "item",
                "is_credit",
                "is_audit",
                "payment_term_template",
            ],
        ):
            fee_categories[fc["name"]] = fc

    fees_by_program = {}
    referenced_items = set()
    for r in fee_rows:
        fc = fee_categories.get(r.get("pgm_feecategory")) or {}
        item = fc.get("item")
        if item:
            referenced_items.add(item)
        fees_by_program.setdefault(r["parent"], []).append(
            {
                "fee_category": fc.get("category_name") or r.get("pgm_feecategory"),
                "event": r.get("pgm_feeevent"),
                "item": item,
                "is_credit": fc.get("is_credit"),
                "is_audit": fc.get("is_audit"),
                "payment_term_template": fc.get("payment_term_template"),
            }
        )

    programs = []
    for p in programs_raw:
        programs.append({**p, "fees": fees_by_program.get(p["name"], [])})

    enriched_price_lists = []
    for pl in price_lists:
        customer_groups = [
            cg["name"]
            for cg in frappe.get_all(
                "Customer Group",
                filters={"default_price_list": pl["name"]},
                fields=["name"],
                order_by="name asc",
            )
        ]

        prices = {}
        if referenced_items:
            for ip in frappe.get_all(
                "Item Price",
                filters={
                    "price_list": pl["name"],
                    "item_code": ["in", list(referenced_items)],
                },
                fields=["item_code", "price_list_rate", "modified"],
                order_by="modified desc",
            ):
                if ip["item_code"] in prices:
                    continue
                prices[ip["item_code"]] = {
                    "rate": ip.get("price_list_rate"),
                    "modified_display": frappe.utils.format_datetime(
                        ip.get("modified"), "yyyy-MM-dd HH:mm"
                    ),
                }

        enriched_price_lists.append(
            {
                "name": pl["name"],
                "currency": pl.get("currency"),
                "customer_groups": customer_groups,
                "prices": prices,
            }
        )

    return frappe.render_template(
        _PROGRAM_PRICING_TEMPLATE,
        {"price_lists": enriched_price_lists, "programs": programs},
    )
