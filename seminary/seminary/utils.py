# Copyright (c) 2015, Frappe Technologies and contributors

import frappe
from frappe import _
import re
import string
import hashlib
import json
import requests


from frappe.desk.doctype.dashboard_chart.dashboard_chart import get_result
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.desk.search import get_user_groups
from frappe.desk.notifications import extract_mentions
from frappe.utils import (
    add_months,
    cint,
    cstr,
    ceil,
    flt,
    fmt_money,
    format_date,
    get_datetime,
    getdate,
    validate_phone_number,
    get_fullname,
    pretty_date,
    get_time_str,
    nowtime,
    format_datetime,
)
from frappe.utils.dateutils import get_period
from seminary.seminary.md import find_macros, markdown_to_html


class OverlapError(frappe.ValidationError):
    pass


RE_SLUG_NOTALLOWED = re.compile("[^a-z0-9]+")


def slugify(title, used_slugs=None):
    """Converts title to a slug.

    If a list of used slugs is specified, it will make sure the generated slug
    is not one of them.

        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Hello World!", ['hello-world'])
        'hello-world-2'
        >>> slugify("Hello World!", ['hello-world', 'hello-world-2'])
        'hello-world-3'
    """
    if not used_slugs:
        used_slugs = []

    slug = RE_SLUG_NOTALLOWED.sub("-", title.lower()).strip("-")
    used_slugs = set(used_slugs)

    if slug not in used_slugs:
        return slug

    count = 2
    while True:
        new_slug = f"{slug}-{count}"
        if new_slug not in used_slugs:
            return new_slug
        count = count + 1


def generate_slug(title, doctype):
    result = frappe.get_all(doctype, fields=["name"])
    slugs = {row["name"] for row in result}
    return slugify(title, used_slugs=slugs)


def validate_duplicate_student(students):
    unique_students = []
    for stud in students:
        if stud.student in unique_students:
            frappe.throw(
                _("Student {0} - {1} appears Multiple times in row {2} & {3}").format(
                    stud.student,
                    stud.student_name,
                    unique_students.index(stud.student) + 1,
                    stud.idx,
                )
            )
        else:
            unique_students.append(stud.student)


def user_is_enrolled_in_course(course: str | None, user: str | None = None) -> bool:
    """Return True if the given user is enrolled in (or otherwise allowed to access) the course."""
    if not course:
        return False
    user = user or frappe.session.user
    if not user or user in {"Guest"}:
        return False
    if has_super_access(user):
        return True
    student = frappe.db.get_value("Student", {"user": user, "enabled": 1}, "name")
    if not student:
        student = frappe.db.get_value("Student", {"student_email_id": user}, "name")
    if not student:
        return False
    schedule_names = frappe.get_all(
        "Course Schedule",
        filters={"course": course},
        pluck="name",
    )
    if not schedule_names:
        return False
    return bool(
        frappe.get_all(
            "Scheduled Course Roster",
            filters={
                "student": student,
                "course_sc": ["in", schedule_names],
                "active": 1,
            },
            limit=1,
        )
    )

    return None


def validate_overlap_for(doc, doctype, fieldname, value=None):
    """Checks overlap for specified field.

    :param fieldname: Checks Overlap for this field
    """

    existing = get_overlap_for(doc, doctype, fieldname, value)
    if existing:
        frappe.throw(
            _("This {0} conflicts with {1} for {2} {3}").format(
                doc.doctype,
                existing.name,
                doc.meta.get_label(fieldname) if not value else fieldname,
                value or doc.get(fieldname),
            ),
            OverlapError,
        )


def get_overlap_for(doc, doctype, fieldname, value=None):
    """Returns overlaping document for specified field.

    :param fieldname: Checks Overlap for this field
    """

    existing = frappe.db.sql(
        """select name, from_time, to_time from `tab{0}`
		where `{1}`=%(val)s and schedule_date = %(schedule_date)s and
		(
			(from_time > %(from_time)s and from_time < %(to_time)s) or
			(to_time > %(from_time)s and to_time < %(to_time)s) or
			(%(from_time)s > from_time and %(from_time)s < to_time) or
			(%(from_time)s = from_time and %(to_time)s = to_time))
		and name!=%(name)s and docstatus!=2""".format(
            doctype, fieldname
        ),
        {
            "schedule_date": doc.schedule_date,
            "val": value or doc.get(fieldname),
            "from_time": doc.from_time,
            "to_time": doc.to_time,
            "name": doc.name or "No Name",
        },
        as_dict=True,
    )

    return existing[0] if existing else None


def get_telemetry_boot_info():
    POSTHOG_PROJECT_FIELD = "posthog_project_id"
    POSTHOG_HOST_FIELD = "posthog_host"

    if not frappe.conf.get(POSTHOG_HOST_FIELD) or not frappe.conf.get(
        POSTHOG_PROJECT_FIELD
    ):
        return {}

    return {
        "posthog_host": frappe.conf.get(POSTHOG_HOST_FIELD),
        "posthog_project_id": frappe.conf.get(POSTHOG_PROJECT_FIELD),
        "enable_telemetry": 1,
    }


# Seminary Utils (Frontend)


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
    return user


@frappe.whitelist()
def get_all_users():
    frappe.only_for(["Academics User", "Instructor", "Seminary Manager"])
    users = frappe.get_all(
        "User",
        {
            "enabled": 1,
        },
        ["name", "full_name", "user_image"],
    )
    return {user.name: user for user in users}


@frappe.whitelist(allow_guest=True)
def has_course_moderator_role(member=None):
    return frappe.db.get_value(
        "Has Role",
        {"parent": member or frappe.session.user, "role": "Seminary Manager"},
        "name",
    )


@frappe.whitelist(allow_guest=True)
def has_course_instructor_role(member=None):
    return frappe.db.get_value(
        "Has Role",
        {"parent": member or frappe.session.user, "role": "Academics User"},
        "name",
    )


@frappe.whitelist(allow_guest=True)
def has_course_evaluator_role(member=None):
    return frappe.db.get_value(
        "Has Role",
        {"parent": member or frappe.session.user, "role": "Instructor"},
        "name",
    )


@frappe.whitelist(allow_guest=True)
def has_student_role(member=None):
    return frappe.db.get_value(
        "Has Role",
        {"parent": member or frappe.session.user, "role": "Student"},
        "name",
    )


@frappe.whitelist(allow_guest=True)
def get_courses_for_student(student):
    courses = frappe.db.sql(
        """select cei.coursesc_ce as name, cei.course_data as course, cs.course_image, cs.course_description_for_lms, cs.short_introduction, cs. academic_term
from `tabCourse Enrollment Individual` cei, `tabCourse Schedule` cs
where cs.name = cei.coursesc_ce and cs.published = 1
and cei.stu_user = %s""",
        student,
        as_dict=True,
    )

    return courses


@frappe.whitelist(allow_guest=True)
def get_courses(filters=None, start=0, page_length=20):
    """Returns the list of courses."""

    if not filters:
        filters = {}

    fields = get_course_fields()

    courses = frappe.get_all(
        "Course Schedule",
        filters=filters,
        fields=fields,
        start=start,
        page_length=page_length,
    )
    courses = get_enrollment_details(courses)
    courses = get_course_card_details(courses)

    return courses


def get_course_card_details(courses):
    for course in courses:
        course.instructors = get_instructors(course.name)
    return courses


@frappe.whitelist(allow_guest=True)
def get_instructors(course):
    instructor_details = []
    instructors = frappe.get_all(
        "Course Schedule Instructors",
        {"parent": course},
        order_by="idx",
        pluck="instructor",
    )

    for instructor in instructors:
        details = frappe.db.get_value(
            "Instructor",
            instructor,
            [
                "instructor_name",
                "user",
                "profileimage",
                "shortbio",
                "bio",
                "prof_email",
                "phone_message",
            ],
            as_dict=True,
        )
        details["messaging_apps"] = get_instructor_messaging_apps(instructor)
        instructor_details.append(details)
    return instructor_details


@frappe.whitelist(allow_guest=True)
def get_instructor(instructorName):
    instructor = frappe.db.get_value(
        "Instructor",
        instructorName,
        [
            "instructor_name",
            "user",
            "profileimage",
            "shortbio",
            "bio",
            "prof_email",
            "phone_message",
        ],
        as_dict=True,
    )
    if not instructor:
        frappe.throw(f"Instructor {instructorName} not found", frappe.DoesNotExistError)
    instructor["messaging_apps"] = get_instructor_messaging_apps(instructorName)
    return instructor


def get_instructor_messaging_apps(instructor_name):
    apps = frappe.get_all(
        "Instructor Messaging App",
        filters={"parent": instructor_name, "parenttype": "Instructor"},
        fields=["messaging_app"],
    )
    result = []
    for app in apps:
        app_details = frappe.db.get_value(
            "Messaging App",
            app.messaging_app,
            ["app_name", "svg_icon", "url_prefix"],
            as_dict=True,
        )
        if app_details:
            result.append(app_details)
    return result


def get_course_or_filters(filters):
    or_filters = {}
    or_filters.update({"title": filters.get("title")})
    or_filters.update({"course_description_for_lms": filters.get("title")})
    return or_filters


@frappe.whitelist(allow_guest=True)
def get_course_outline(course, progress=False):
    """Returns the course outline."""
    outline = []

    chapters = frappe.get_all(
        "Course Schedule Chapter Reference",
        {"parent": course},
        ["chapter", "idx"],
        order_by="idx",
    )
    for chapter in chapters:
        chapter_details = frappe.db.get_value(
            "Course Schedule Chapter",
            chapter.chapter,
            [
                "name",
                "chapter_title",
                "is_scorm_package",
                "launch_file",
                "scorm_package",
            ],
            as_dict=True,
        )
        chapter_details["idx"] = chapter.idx

        chapter_details.lessons = get_lessons(
            course, chapter_details, progress=progress
        )

        if chapter_details.is_scorm_package:
            chapter_details.scorm_package = frappe.db.get_value(
                "File",
                chapter_details.scorm_package,
                ["file_name", "file_size", "file_url"],
                as_dict=1,
            )

        outline.append(chapter_details)
    return outline


@frappe.whitelist(allow_guest=True)
def get_course_title(course):
    return frappe.db.get_value("Course Schedule", course, "course")


def get_enrollment_details(courses):
    for course in courses:
        filters = {
            "course_sc": course.name,
            "stuemail_rc": frappe.session.user,
            "active": 1,
        }

        course.membership = frappe.db.get_value(
            "Scheduled Course Roster",
            filters,
            [
                "stuname_roster",
                "stuimage",
                "audit_bool",
                "course_sc",
                "current_lesson",
                "progress",
                "stuemail_rc",
            ],
            as_dict=1,
        )

    return courses


def get_course_fields():
    return [
        "name",
        "course",
        "course_image",
        "short_introduction",
        "course_description_for_lms",
        "published",
        "syllabus",
        "modality",
        "academic_term",
        "c_datestart",
        "c_dateend",
    ]


@frappe.whitelist(allow_guest=True)
def get_course_details(course):
    course_details = frappe.db.get_value(
        "Course Schedule",
        course,
        [
            "name",
            "course",
            "course_image",
            "short_introduction",
            "course_description_for_lms",
            "published",
            "syllabus",
            "modality",
            "academic_term",
            "c_datestart",
            "c_dateend",
            "enrollments",
            "lessons",
            "calendar_token",
        ],
        as_dict=1,
    )

    course_details.instructors = get_instructors(course_details.name)

    if frappe.session.user == "Guest":
        course_details.membership = None
        course_details.is_instructor = False
    else:
        course_details.membership = frappe.db.get_value(
            "Scheduled Course Roster",
            {"stuemail_rc": frappe.session.user, "course_sc": course_details.name},
            ["name", "course_sc", "current_lesson", "progress", "stuemail_rc"],
            as_dict=1,
        )

    if course_details.membership and course_details.membership.current_lesson:
        course_details.current_lesson = get_lesson_index(
            course_details.membership.current_lesson
        )

    return course_details


@frappe.whitelist()
def get_roster(course):
    """Returns the course roster."""
    roster = frappe.get_all(
        "Scheduled Course Roster",
        {"course_sc": course},
        [
            "name",
            "stuname_roster",
            "stuemail_rc",
            "audit_bool",
            "active",
            "stuimage",
            "student",
        ],
        order_by="stuname_roster",
    )
    return roster


def get_lesson_index(lesson_name):
    """Returns the {chapter_index}.{lesson_index} for the lesson."""
    lesson = frappe.db.get_value(
        "Course Schedule Lesson Reference",
        {"lesson": lesson_name},
        ["idx", "parent"],
        as_dict=True,
    )
    if not lesson:
        return "1-1"

    chapter = frappe.db.get_value(
        "Course Schedule Chapter Reference",
        {"chapter": lesson.parent},
        ["idx"],
        as_dict=True,
    )
    if not chapter:
        return "1-1"

    return f"{chapter.idx}-{lesson.idx}"


def get_lesson_url(course, lesson_number):
    if not lesson_number:
        return
    return f"/courses/{course}/learn/{lesson_number}"


def get_membership(course, member=None):
    if not member:
        member = frappe.session.user

    filters = {"member": member, "course": course}

    if frappe.db.exists("Scheduled Course Roster", filters):
        membership = frappe.db.get_value(
            "Scheduled Course Roster",
            filters,
            [
                "stuname_roster",
                "current_lesson",
                "progress",
                "student",
                "program",
            ],
            as_dict=True,
        )
        return membership

    return False


def get_chapters(course):
    """Returns all chapters of this course."""
    if not course:
        return []
    chapters = frappe.get_all(
        "Course Schedule Chapter Reference",
        {"parent": course},
        ["idx", "chapter"],
        order_by="idx",
    )
    for chapter in chapters:
        chapter_details = frappe.db.get_value(
            "Course Schedule Chapter",
            {"name": chapter.chapter},
            ["name", "chapter_title"],
            as_dict=True,
        )
        chapter.update(chapter_details)
    return chapters


@frappe.whitelist()
def get_lesson(course, chapter, lesson):
    chapter_name = frappe.db.get_value(
        "Course Schedule Chapter Reference",
        {"parent": course, "idx": chapter},
        "chapter",
    )
    print(f"Chapter Name: {chapter_name}")  # Debug print

    lesson_name = frappe.db.get_value(
        "Course Schedule Lesson Reference",
        {"parent": chapter_name, "idx": lesson},
        "lesson",
    )
    print(f"Lesson Name: {lesson_name}")  # Debug print

    if not lesson_name:
        return {}

    if not (has_super_access() or has_course_moderator_role() or is_instructor(course)):
        if not frappe.db.exists(
            "Scheduled Course Roster",
            {"stuemail_rc": frappe.session.user, "course_sc": course},
        ):
            return {}

    lesson_details = frappe.db.get_value(
        "Course Lesson",
        lesson_name,
        [
            "name",
            "allow_discuss",
            "lesson_title",
            "preview",
            "body",
            "creation",
            "youtube",
            "quiz_id",
            "exam",
            "assessment_criteria_quiz",
            "assessment_criteria_assignment",
            "assessment_criteria_exam",
            "assignment_id",
            "discussion_id",
            "course_sc",
            "content",
            "instructor_content",
            "instructor_notes",
        ],
        as_dict=True,
    )

    if frappe.session.user == "Guest":
        progress = 0
    else:
        progress = get_progress(course, lesson_details.name)

    lesson_details.rendered_content = render_html(lesson_details)
    neighbours = get_neighbour_lesson(course, chapter, lesson)
    lesson_details.next = neighbours["next"]
    lesson_details.progress = progress
    lesson_details.prev = neighbours["prev"]
    lesson_details.instructors = get_instructors(course)
    lesson_details.due_date = get_lesson_due_date(lesson_details.name)
    lesson_details.course_title = frappe.db.get_value(
        "Course Schedule", course, "course"
    )
    # print(f"Lesson Details (third): {lesson_details}")  # Debug print

    if frappe.session.user == "Guest":
        lesson_details.membership = None
    else:
        lesson_details.membership = frappe.db.get_value(
            "Scheduled Course Roster",
            {"stuemail_rc": frappe.session.user, "course_sc": course},
            ["name", "course_sc", "current_lesson", "progress", "stuemail_rc"],
            as_dict=1,
        )

    lesson_details.chapter_name = chapter_name

    return lesson_details


def get_course_progress(course, member=None):
    """Returns the course progress of the session user"""
    lesson_count = get_lessons(course, get_details=False)
    if not lesson_count:
        return 0
    completed_lessons = frappe.db.count(
        "Course Schedule Progress",
        {
            "course": course,
            "member": member or frappe.session.user,
            "status": "Complete",
        },
    )
    precision = cint(frappe.db.get_default("float_precision")) or 3
    return flt(((completed_lessons / lesson_count) * 100), precision)


def get_progress(course, lesson, member=None):
    if not member:
        member = frappe.session.user

    return frappe.db.exists(
        "Course Schedule Progress",
        {"course": course, "member": member, "lesson": lesson},
        ["status"],
    )


def get_lessons(course, chapter=None, get_details=True, progress=False):
    """If chapter is passed, returns lessons of only that chapter.
    Else returns lessons of all chapters of the course"""
    lessons = []
    lesson_count = 0
    if chapter:
        if get_details:
            return get_lesson_details(chapter, progress=progress)
        else:
            return frappe.db.count(
                "Course Schedule Lesson Reference", {"parent": chapter.name}
            )

    for chapter in get_chapters(course):
        if get_details:
            lessons += get_lesson_details(chapter, progress=progress)
        else:
            lesson_count += frappe.db.count(
                "Course Schedule Lesson Reference", {"parent": chapter.name}
            )

    return lessons if get_details else lesson_count


def get_lesson_details(chapter, progress=False):
    lessons = []
    lesson_list = frappe.get_all(
        "Course Schedule Lesson Reference",
        {"parent": chapter.name},
        ["lesson", "idx"],
        order_by="idx",
    )
    for row in lesson_list:
        lesson_details = frappe.db.get_value(
            "Course Lesson",
            row.lesson,
            [
                "name",
                "lesson_title",
                "preview",
                "content",
                "body",
                "creation",
                "youtube",
                "assessment_criteria_quiz",
                "assessment_criteria_assignment",
                "assessment_criteria_exam",
                "quiz_id",
                "assignment_id",
                "exam",
                "instructor_content",
                "course_sc",
            ],
            as_dict=True,
        )
        lesson_details.number = f"{chapter.idx}.{row.idx}"
        lesson_details.icon = get_lesson_icon(
            lesson_details.body, lesson_details.content
        )
        lesson_details.due_date = get_lesson_due_date(lesson_details.name)
        lesson_details.assessments_submitted = _lesson_assessments_submitted(
            lesson_details
        )

        if progress:
            lesson_details.is_complete = get_progress(
                lesson_details.course_sc, lesson_details.name
            )

        lessons.append(lesson_details)
    return lessons


def get_lesson_icon(body, content):
    if content:
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            print("Invalid JSON content")
            return "icon-list"

        for block in content.get("blocks"):
            if block.get("type") == "upload" and block.get("data").get(
                "file_type"
            ).lower() in [
                "mp4",
                "webm",
                "ogg",
                "mov",
            ]:
                return "icon-youtube"

            if block.get("type") == "embed" and block.get("data").get("service") in [
                "youtube",
                "vimeo",
            ]:
                return "icon-youtube"

            if block.get("type") == "quiz":
                return "icon-quiz"
            if block.get("type") == "exam":
                return "icon-exam"
            if block.get("type") == "assignment":
                return "icon-assignment"
            if block.get("type") in (
                "discussion",
                "discussionActivity",
                "discussionactivity",
            ):
                return "icon-discussion"
            if block.get("type") == "folder":
                return "icon-folder"

        return "icon-list"

    macros = find_macros(body)
    for macro in macros:
        if macro[0] == "YouTubeVideo" or macro[0] == "Video":
            return "icon-youtube"
        elif macro[0] == "Quiz":
            return "icon-quiz"

    return "icon-list"


@frappe.whitelist()
def get_lesson_due_date(lesson):
    """Earliest SCAC due date among activities embedded in this lesson's
    content. Resolved on read against the live content + SCAC rows so it
    cannot drift like a denormalized field would."""
    lesson_doc = frappe.db.get_value(
        "Course Lesson", lesson, ["content", "course_sc"], as_dict=True
    )
    if not lesson_doc or not lesson_doc.content or not lesson_doc.course_sc:
        return None

    try:
        content = json.loads(lesson_doc.content)
    except (ValueError, TypeError):
        return None

    activities_by_type = {}
    for block in content.get("blocks", []) or []:
        block_type = block.get("type")
        block_data = block.get("data") or {}
        for scac_type, pairs in _LESSON_BLOCK_LOOKUP.items():
            for bt, bk in pairs:
                if block_type != bt:
                    continue
                activity = block_data.get(bk)
                if activity:
                    activities_by_type.setdefault(scac_type, []).append(activity)

    if not activities_by_type:
        return None

    scac_names = []
    for scac_type, activities in activities_by_type.items():
        scac_names.extend(
            frappe.get_all(
                "Scheduled Course Assess Criteria",
                filters={
                    "parent": lesson_doc.course_sc,
                    scac_type.lower(): ["in", activities],
                },
                pluck="name",
                ignore_permissions=True,
            )
        )

    if not scac_names:
        return None

    due_date = frappe.db.sql(
        """SELECT due_date FROM `tabScheduled Course Assess Criteria`
           WHERE name IN %(names)s AND due_date IS NOT NULL
           ORDER BY due_date ASC LIMIT 1""",
        {"names": scac_names},
        as_dict=True,
    )
    return due_date[0].due_date if due_date else None


def render_html(lesson):
    youtube = lesson.youtube
    quiz_id = lesson.quiz_id
    body = lesson.body

    if youtube and "/" in youtube:
        youtube = youtube.split("/")[-1]

    quiz_id = "{{ Quiz('" + quiz_id + "') }}" if quiz_id else ""
    youtube = "{{ YouTubeVideo('" + youtube + "') }}" if youtube else ""
    text = youtube + body + quiz_id

    if lesson.question:
        assignment = (
            "{{ Assignment('" + lesson.question + "-" + lesson.file_type + "') }}"
        )
        text = text + assignment

    return text


def get_neighbour_lesson(course, chapter, lesson):
    numbers = []
    current = f"{chapter}.{lesson}"
    chapters = frappe.get_all(
        "Course Schedule Chapter Reference", {"parent": course}, ["idx", "chapter"]
    )
    for chapter in chapters:
        lessons = frappe.get_all(
            "Course Schedule Lesson Reference", {"parent": chapter.chapter}, pluck="idx"
        )
        for lesson in lessons:
            numbers.append(f"{chapter.idx}.{lesson}")

    tuples_list = [tuple(int(x) for x in s.split(".")) for s in numbers]
    sorted_tuples = sorted(tuples_list)
    sorted_numbers = [".".join(str(num) for num in t) for t in sorted_tuples]
    index = sorted_numbers.index(current)

    return {
        "prev": sorted_numbers[index - 1] if index - 1 >= 0 else None,
        "next": sorted_numbers[index + 1] if index + 1 < len(sorted_numbers) else None,
    }


def is_instructor(course):
    return (
        len(
            list(
                filter(lambda x: x.name == frappe.session.user, get_instructors(course))
            )
        )
        > 0
    )


def get_current_student():
    """Returns current student from frappe.session.user

    Returns:
            object: Student Document
    """
    email = frappe.session.user
    if email in ("Administrator", "Guest"):
        return None
    try:
        student_id = frappe.get_all("Student", {"student_email_id": email}, ["name"])[
            0
        ].name
        return frappe.get_doc("Student", student_id)
    except (IndexError, frappe.DoesNotExistError):
        return None


def get_enrollment(master, document, student):
    """Gets enrollment for course or program

    Args:
            master (string): can either be program or course
            document (string): program or course name
            student (string): Student ID

    Returns:
            string: Enrollment Name if exists else returns empty string
    """
    if master == "program":
        enrollments = frappe.get_all(
            "Program Enrollment",
            filters={"student": student, "program": document, "docstatus": 1},
        )
    if master == "course":
        enrollments = frappe.get_all(
            "Course Enrollment", filters={"student": student, "course": document}
        )

    if enrollments:
        return enrollments[0].name
    else:
        return None


def get_lesson_count(course):
    lesson_count = 0
    chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["chapter"])
    for chapter in chapters:
        lesson_count += frappe.db.count("Lesson Reference", {"parent": chapter.chapter})

    return lesson_count


@frappe.whitelist()
def get_lesson_creation_details(course, chapter, lesson):
    chapter_name = frappe.db.get_value(
        "Course Schedule Chapter Reference",
        {"parent": course, "idx": chapter},
        "chapter",
    )
    lesson_name = frappe.db.get_value(
        "Course Schedule Lesson Reference",
        {"parent": chapter_name, "idx": lesson},
        "lesson",
    )

    if lesson_name:
        lesson_details = frappe.db.get_value(
            "Course Lesson",
            lesson_name,
            [
                "name",
                "lesson_title",
                "preview",
                "body",
                "content",
                "instructor_notes",
                "instructor_content",
                "assessment_criteria_quiz",
                "assessment_criteria_assignment",
                "assessment_criteria_exam",
                "youtube",
                "quiz_id",
                "assignment_id",
                "exam",
                "allow_discuss",
            ],
            as_dict=1,
        )

    return {
        "course_title": frappe.db.get_value("Course Schedule", course, "course"),
        "chapter": frappe.db.get_value(
            "Course Schedule Chapter",
            chapter_name,
            ["chapter_title", "name"],
            as_dict=True,
        ),
        "lesson": lesson_details if lesson_name else None,
    }


@frappe.whitelist()
def get_question_details(question):
    fields = ["question", "type", "multiple"]
    for i in range(1, 5):
        fields.append(f"option_{i}")
        fields.append(f"explanation_{i}")

    question_details = frappe.db.get_value("Question", question, fields, as_dict=1)
    return question_details


@frappe.whitelist()
def get_all_questions_details(questions):

    questions_str = "', '".join(questions)
    all_question_details = frappe.db.sql(
        f"""select distinct qq.name, qq.points, qq.question_detail, q.name as question, q.type, q.option_1, q.option_2, q.option_3, q.option_4, q.explanation_1, q.explanation_2, q.explanation_3, q.explanation_4
from `tabQuestion` q, `tabQuiz Question` qq
where q.name = qq.question and qq.name in ('{questions_str}')""",
        as_dict=1,
    )
    return all_question_details


@frappe.whitelist()
def get_open_question_details(question):
    fields = ["question", "explanation"]
    question_details = frappe.db.get_value("Open Question", question, fields, as_dict=1)
    return question_details


@frappe.whitelist()
def get_all_open_questions_details(questions):
    if not questions:
        frappe.throw(_("Questions parameter is required"))

        # Ensure questions is a list
    if isinstance(questions, str):
        questions = frappe.parse_json(questions)
    all_question_details = frappe.db.sql(
        f"""select distinct qq.name, qq.points, qq.question_detail, q.name as question_name, q.explanation
from `tabOpen Question` q, `tabExam Question` qq
where q.name = qq.question and qq.name in ({', '.join(frappe.db.escape(q) for q in questions)})""",
        as_dict=1,
    )
    print("All questions details: " + str(all_question_details))
    return all_question_details


@frappe.whitelist()
def get_assessments(course):
    assessments = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course},
        fields=["*"],
        order_by="due_date",
        ignore_permissions=True,
    )

    activity_to_lesson = _build_lesson_index_for_course(course)
    submitted_index = _build_user_submission_index(course)
    for a in assessments:
        key = _scac_activity_key(a)
        a["lesson"] = activity_to_lesson.get(key)
        a["submitted"] = bool(key and submitted_index.get(key))

    return assessments


@frappe.whitelist()
def get_assessment_due_date(course, activity_type, activity_id):
    """Return the due date for an SCAC row matching (course schedule,
    activity type, activity id), or None. Bypasses the child-table permission
    check that `frappe.client.get_value` enforces on Scheduled Course Assess
    Criteria so callers don't need explicit SCAC roles."""
    if not course or not activity_type or not activity_id:
        return None
    field = (activity_type or "").strip().lower()
    if field not in {"quiz", "assignment", "exam", "discussion"}:
        return None
    return frappe.db.get_value(
        "Scheduled Course Assess Criteria",
        {"parent": course, field: activity_id},
        "due_date",
    )


def _build_user_submission_index(course_sc, member=None):
    """{(scac_type, activity_name): True} for activities the user has
    submitted in this Course Schedule. For Discussion, "submitted" means
    the student has met any per-activity participation requirement (initial
    post plus the configured number of distinct other-student replies)."""
    member = member or frappe.session.user
    if member == "Guest":
        return {}
    index = {}
    for scac_type, (
        doctype,
        activity_field,
        course_field,
    ) in _LESSON_SUBMISSION_LOOKUP.items():
        rows = frappe.get_all(
            doctype,
            filters={"member": member, course_field: course_sc},
            pluck=activity_field,
        )
        for activity in rows:
            if not activity:
                continue
            if scac_type == "Discussion":
                if not _discussion_meets_participation(member, activity, course_sc):
                    continue
            index[(scac_type, activity)] = True
    return index


def _discussion_meets_participation(member, disc_activity, course_sc):
    """True iff `member` has (a) a Discussion Submission with a non-empty
    `original_post` for this discussion in this Course Schedule and (b) at
    least `min_replies_required` distinct *other* students whose Submissions
    have at least one reply row authored by `member`. Self-replies (the
    student replying on their own Submission) never count."""
    if not member or not disc_activity or not course_sc:
        return False

    submission = frappe.db.get_value(
        "Discussion Submission",
        {"disc_activity": disc_activity, "coursesc": course_sc, "member": member},
        ["name", "original_post"],
        as_dict=True,
    )
    if not submission or not (submission.original_post or "").strip():
        return False

    min_required = (
        frappe.db.get_value(
            "Discussion Activity", disc_activity, "min_replies_required"
        )
        or 0
    )
    if min_required <= 0:
        return True

    qualifying = frappe.db.sql(
        """SELECT COUNT(DISTINCT r.parent)
           FROM `tabDiscussion Submission Replies` r
           JOIN `tabDiscussion Submission` s ON s.name = r.parent
           WHERE s.disc_activity = %(disc)s
             AND s.coursesc = %(course_sc)s
             AND s.member <> %(member)s
             AND r.member = %(member)s""",
        {"disc": disc_activity, "course_sc": course_sc, "member": member},
    )
    count = (qualifying[0][0] if qualifying and qualifying[0] else 0) or 0
    return count >= min_required


# Maps SCAC.type → block-type/data-key pairs to scan in lesson content JSON.
# Discussion has two shapes because graded discussions and free-form
# discussions register different Editor.js tools.
_LESSON_BLOCK_LOOKUP = {
    "Quiz": [("quiz", "quiz")],
    "Assignment": [("assignment", "assignment")],
    "Exam": [("exam", "exam")],
    "Discussion": [
        ("discussion", "discussion"),
        ("discussionActivity", "discussionID"),
        ("discussionActivity", "discussion"),
    ],
}

# Maps SCAC.type → (Submission DocType, activity field, course-schedule field).
# Discussion Submission uses `coursesc` for the Course Schedule link
# because its `course` field stores the parent Course instead.
_LESSON_SUBMISSION_LOOKUP = {
    "Assignment": ("Assignment Submission", "assignment", "course"),
    "Exam": ("Exam Submission", "exam", "course"),
    "Quiz": ("Quiz Submission", "quiz", "course"),
    "Discussion": ("Discussion Submission", "disc_activity", "coursesc"),
}

# Reverse lookup keyed by Submission DocType, used by the controller-side
# backfill helper.
_SUBMISSION_BACKFILL_CONFIG = {
    config[0]: (scac_type, config[1], config[2])
    for scac_type, config in _LESSON_SUBMISSION_LOOKUP.items()
}


def backfill_submission_course_if_missing(submission):
    """Defensive validate-time guard: if a submission is being saved without
    its Course Schedule field set, infer it from the SCAC that owns the
    activity and the student's roster, then log so the gap can be diagnosed.
    Never throws — submissions still save in the worst case so users aren't
    blocked.
    """
    config = _SUBMISSION_BACKFILL_CONFIG.get(submission.doctype)
    if not config:
        return
    scac_type, activity_field, course_field = config

    if submission.get(course_field):
        return

    activity = submission.get(activity_field)
    member = submission.get("member")
    if not activity or not member:
        # Other validators will surface this; nothing for us to backfill from.
        return

    candidate_schedules = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={scac_type.lower(): activity},
        pluck="parent",
        ignore_permissions=True,
    )
    if not candidate_schedules:
        frappe.log_error(
            title=f"{submission.doctype} missing {course_field} (no SCAC)",
            message=(
                f"Submission for activity {activity!r} by {member!r} has "
                f"no {course_field} and no Scheduled Course Assess Criteria "
                f"references this {scac_type}. Cannot backfill."
            ),
        )
        return

    enrolled = frappe.get_all(
        "Scheduled Course Roster",
        filters={
            "stuemail_rc": member,
            "course_sc": ["in", list(set(candidate_schedules))],
        },
        pluck="course_sc",
    )

    if len(set(enrolled)) == 1:
        inferred = enrolled[0]
        submission.set(course_field, inferred)
        frappe.log_error(
            title=f"{submission.doctype} {course_field} backfilled",
            message=(
                f"Submission for activity {activity!r} by {member!r} was "
                f"saved without {course_field}; backfilled to {inferred!r} "
                f"based on the student's roster and the SCAC for this "
                f"{scac_type}. Investigate the create path that produced "
                f"the missing field."
            ),
        )
    else:
        frappe.log_error(
            title=f"{submission.doctype} {course_field} backfill ambiguous",
            message=(
                f"Submission for activity {activity!r} by {member!r} has "
                f"no {course_field}. Found {len(set(candidate_schedules))} "
                f"candidate Course Schedule(s) for this {scac_type}; "
                f"student is enrolled in {sorted(set(enrolled))!r}. "
                f"Not backfilling. Investigate manually."
            ),
        )


def _lesson_activities_by_type(content_json):
    """Parse a Course Lesson.content JSON and return
    {scac_type: set(activity_name)} for every gradable activity embedded."""
    activities = {}
    if not content_json:
        return activities
    try:
        content = json.loads(content_json)
    except (ValueError, TypeError):
        return activities
    for block in content.get("blocks", []) or []:
        block_type = block.get("type")
        block_data = block.get("data") or {}
        for scac_type, pairs in _LESSON_BLOCK_LOOKUP.items():
            for bt, bk in pairs:
                if block_type != bt:
                    continue
                activity = block_data.get(bk)
                if activity:
                    activities.setdefault(scac_type, set()).add(activity)
    return activities


def _lesson_assessments_submitted(lesson_row, member=None):
    """True iff the lesson contains at least one gradable activity AND the
    student has at least one submission for every one of them. Returns False
    for Guest, lessons with no gradable activities, and lessons missing a
    course schedule."""
    member = member or frappe.session.user
    if member == "Guest":
        return False
    if not lesson_row.get("content") or not lesson_row.get("course_sc"):
        return False

    activities_by_type = _lesson_activities_by_type(lesson_row.content)
    if not activities_by_type:
        return False

    for scac_type, activities in activities_by_type.items():
        if scac_type == "Discussion":
            for activity in activities:
                if not _discussion_meets_participation(
                    member, activity, lesson_row.course_sc
                ):
                    return False
            continue

        dt, activity_field, course_field = _LESSON_SUBMISSION_LOOKUP[scac_type]
        submitted = set(
            frappe.get_all(
                dt,
                filters={
                    course_field: lesson_row.course_sc,
                    "member": member,
                    activity_field: ["in", list(activities)],
                },
                pluck=activity_field,
            )
        )
        if not activities <= submitted:
            return False
    return True


def _scac_activity_key(scac_row):
    scac_type = scac_row.get("type")
    if not scac_type:
        return None
    activity = scac_row.get(scac_type.lower())
    if not activity:
        return None
    return (scac_type, activity)


def _build_lesson_index_for_course(course_sc):
    """Walk every Course Lesson under a Course Schedule once, return a
    {(type, activity_name) -> lesson_name} index built from the lessons'
    content JSON. First match wins per activity."""
    index = {}
    lessons = frappe.get_all(
        "Course Lesson",
        filters={"course_sc": course_sc},
        fields=["name", "content"],
    )
    for lesson in lessons:
        if not lesson.content:
            continue
        try:
            content = json.loads(lesson.content)
        except (ValueError, TypeError):
            continue
        for block in content.get("blocks", []) or []:
            block_type = block.get("type")
            block_data = block.get("data") or {}
            for scac_type, pairs in _LESSON_BLOCK_LOOKUP.items():
                for bt, bk in pairs:
                    if block_type != bt:
                        continue
                    activity = block_data.get(bk)
                    if activity:
                        index.setdefault((scac_type, activity), lesson.name)
    return index


@frappe.whitelist()
def get_gradebook(course):
    students = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course},
        fields=[
            "name",
            "stuname_roster",
            "stuemail_rc",
            "audit_bool",
            "active",
            "stuemail_rc",
            "program_std_scr",
            "progress",
        ],
    )
    for student in students:
        student["assessments"] = frappe.db.sql(
            f"""select r.name, r.rawscore_card, r.actualextrapt_card, r.graded_card, scar.weight_scac, scar.extracredit_scac, scar.fudgepoints_scac, r.assessment_criteria, scar.title, scar.type, scar.due_date, scar.quiz, scar.exam, scar.assignment, scar.discussion
	from  `tabCourse Assess Results Detail` r, `tabScheduled Course Assess Criteria` scar
	where r.assessment_criteria = scar.name and r.parent ='{student.name}'""",
            as_dict=1,
        )

    print(students)
    return students


@frappe.whitelist()
def get_student_course_status(course):
    """Returns the current student's course status including grades, progress, and class statistics."""
    import statistics

    user = frappe.session.user

    # Get student's roster record
    roster = frappe.db.get_value(
        "Scheduled Course Roster",
        {"course_sc": course, "stuemail_rc": user},
        [
            "name",
            "progress",
            "fscore",
            "fgrade",
            "fgradepass",
            "active",
            "audit_bool",
            "student",
            "stuname_roster",
        ],
        as_dict=True,
    )
    print("Roster of Course Status", roster)
    if not roster:
        frappe.throw("You are not enrolled in this course.", frappe.PermissionError)

    # Get all assessments for this course, LEFT JOIN with student's grades
    roster["assessments"] = frappe.db.sql(
        """select scar.name as assessment_criteria, scar.title, scar.type, scar.due_date,
            scar.weight_scac, scar.extracredit_scac, scar.fudgepoints_scac,
            r.name as grade_name, r.rawscore_card, r.actualextrapt_card
        from `tabScheduled Course Assess Criteria` scar
        left join `tabCourse Assess Results Detail` r
            on r.assessment_criteria = scar.name and r.parent = %s
        where scar.parent = %s
        order by scar.idx""",
        (roster.name, course),
        as_dict=1,
    )

    # Add status field per assessment
    for a in roster["assessments"]:
        if a.rawscore_card is None:
            a["status"] = "Not Submitted"
        elif a.rawscore_card == 0:
            a["status"] = "Not Graded"
        else:
            a["status"] = "Graded"

    # Get class statistics per assessment
    all_rosters = frappe.get_all(
        "Scheduled Course Roster",
        filters={"course_sc": course, "active": 1},
        pluck="name",
    )

    for assessment in roster["assessments"]:
        if not all_rosters:
            assessment["class_median"] = None
            assessment["percentile"] = None
            continue
        # Get all scores for this assessment across the class
        roster_placeholders = ", ".join(["%s"] * len(all_rosters))
        all_scores = frappe.db.sql(
            f"""select rawscore_card from `tabCourse Assess Results Detail`
            where assessment_criteria = %s and parent in ({roster_placeholders}) and rawscore_card > 0""",
            [assessment.assessment_criteria] + all_rosters,
            as_list=1,
        )
        scores = [s[0] for s in all_scores if s[0] is not None]

        if scores:
            assessment["class_median"] = round(statistics.median(scores), 1)
            student_score = assessment.rawscore_card or 0
            if student_score > 0:
                below_count = sum(1 for s in scores if s <= student_score)
                assessment["percentile"] = round(below_count / len(scores) * 100)
            else:
                assessment["percentile"] = None
        else:
            assessment["class_median"] = None
            assessment["percentile"] = None

    # Get CEI and PE for withdrawal form
    cei = frappe.db.get_value(
        "Course Enrollment Individual",
        {
            "coursesc_ce": course,
            "student_ce": roster.student,
            "docstatus": 1,
            "withdrawn": 0,
        },
        ["name", "program_ce"],
        as_dict=True,
    )
    roster["course_enrollment_individual"] = cei.name if cei else None
    roster["program_enrollment"] = cei.program_ce if cei else None

    # Check for active withdrawal request
    withdrawal = frappe.db.get_value(
        "Course Withdrawal Request",
        {
            "course_enrollment_individual": cei.name if cei else "",
            "docstatus": ("!=", 2),
        },
        ["name", "workflow_state"],
        as_dict=True,
    )
    roster["withdrawal_request"] = withdrawal

    # Get max grade for scale reference
    cs = frappe.db.get_value(
        "Course Schedule",
        course,
        ["gradesc_cs", "maxnumgrade", "academic_term"],
        as_dict=True,
    )
    roster["maxnumgrade"] = cs.maxnumgrade if cs else 100

    # Get grading scale intervals for frontend grade mapping
    if cs and cs.gradesc_cs:
        roster["grading_scale_intervals"] = frappe.get_all(
            "Grading Scale Interval",
            fields=["grade_code", "threshold", "grade_pass"],
            filters={"parent": cs.gradesc_cs},
            order_by="threshold desc",
        )
    else:
        roster["grading_scale_intervals"] = []

    # Get term withdrawal rules for the course's academic term
    if cs and cs.academic_term:
        roster["withdrawal_rules"] = frappe.get_all(
            "Term Withdrawal Rules",
            filters={"academic_term": cs.academic_term},
            fields=["withdrawal_rule", "applies_until"],
            order_by="applies_until asc",
        )
    else:
        roster["withdrawal_rules"] = []

    return roster


@frappe.whitelist()
def enroll_in_program(program_name, student=None):
    """Enroll student in program

    Args:
            program_name (string): Name of the program to be enrolled into
            student (string, optional): name of student who has to be enrolled, if not
                    provided, a student will be created from the current user

    Returns:
            string: name of the program enrollment document
    """
    if has_super_access():
        return

    if not student == None:
        student = frappe.get_doc("Student", student)
    else:
        # Check if self enrollment in allowed
        program = frappe.get_doc("Program", program_name)
        if not program.allow_self_enroll:
            return frappe.throw(_("You are not allowed to enroll for this course"))

        student = get_current_student()
        if not student:
            student = create_student_from_current_user()

    # Check if student is already enrolled in program
    enrollment = get_enrollment("program", program_name, student.name)
    if enrollment:
        return enrollment

    # Check if self enrollment in allowed
    program = frappe.get_doc("Program", program_name)
    if not program.allow_self_enroll:
        return frappe.throw(_("You are not allowed to enroll for this course"))

    # Enroll in program
    program_enrollment = student.enroll_in_program(program_name)
    return program_enrollment.name


def has_super_access(user: str | None = None):
    """Check if user has a role that allows full access to LMS

    Returns:
            bool: true if user has access to all lms content
    """
    user = user or frappe.session.user
    current_user = frappe.get_doc("User", user)
    roles = set([role.role for role in current_user.roles])
    return bool(
        roles
        & {
            "Administrator",
            "Instructor",
            "Seminary Manager",
            "System Manager",
            "Academic User",
        }
    )


def create_student_from_current_user():
    user = frappe.get_doc("User", frappe.session.user)

    student = frappe.get_doc(
        {
            "doctype": "Student",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "student_email_id": user.email,
            "user": frappe.session.user,
        }
    )

    student.save(ignore_permissions=True)
    return student


@frappe.whitelist()
def get_discussion_topics(doctype, docname, single_thread):
    if single_thread:
        filters = {
            "reference_doctype": doctype,
            "reference_docname": docname,
        }
        topic = frappe.db.exists("Discussion Topic", filters)
        if topic:
            return frappe.db.get_value("Discussion Topic", topic, ["name"], as_dict=1)
        else:
            return create_discussion_topic(doctype, docname)
    else:
        topics = frappe.get_all(
            "Discussion Topic",
            {
                "reference_doctype": doctype,
                "reference_docname": docname,
            },
            ["name", "title", "owner", "creation", "modified"],
            order_by="creation desc",
        )

    for topic in topics:
        topic.user = frappe.db.get_value(
            "User", topic.owner, ["full_name", "user_image"], as_dict=True
        )

    return topics


def create_discussion_topic(doctype, docname):
    doc = frappe.new_doc("Discussion Topic")
    doc.update(
        {
            "title": docname,
            "reference_doctype": doctype,
            "reference_docname": docname,
        }
    )
    doc.insert()
    return doc


@frappe.whitelist()
def get_discussion_replies(topic):
    print("Fetching replies for topic:", topic)  # Debugging log
    replies = frappe.get_all(
        "Discussion Reply",
        {
            "topic": topic,
        },
        ["name", "owner", "creation", "modified", "reply"],
        order_by="creation",
    )

    for reply in replies:
        reply.user = frappe.db.get_value(
            "User", reply.owner, ["full_name", "user_image"], as_dict=True
        )
    print("Replies: ", replies)

    return replies


@frappe.whitelist()
def ensure_single_topic(doctype, docname, title):
    print("Ensuring single topic for:", doctype, docname, title)
    existing_topic = frappe.get_all(
        "Discussion Topic",
        filters={"reference_doctype": doctype, "reference_docname": docname},
        fields=["name", "title"],
        limit=1,
    )

    if existing_topic:
        print("Existing topic found:", existing_topic)
        return existing_topic[0]

    # Create a new topic if none exists
    new_topic = frappe.get_doc(
        {
            "doctype": "Discussion Topic",
            "reference_doctype": doctype,
            "reference_docname": docname,
            "title": title,
        }
    )
    print("Creating new topic:", new_topic)
    new_topic.insert(ignore_permissions=True)
    return new_topic


@frappe.whitelist()
def missing_exams(course):
    students_missing_exam = frappe.db.sql(
        """
		select r.stuname_roster, r.stuemail_rc, r.stuimage, r.program_std_scr, c.exam
		from `tabScheduled Course Roster` r, `tabScheduled Course Assess Criteria` c
		where r.course_sc = c.parent and
		c.exam <> '' and
		r.course_sc = %(course)s and
		r.stuemail_rc not in (
			select member
			from `tabExam Submission`
			where course = %(course)s
		)
		""",
        {"course": course},
        as_dict=True,
    )
    return students_missing_exam


@frappe.whitelist()
def get_course_exams(course):
    exams = frappe.get_all(
        "Scheduled Course Assess Criteria",
        filters={"parent": course, "exam": ["!=", ""]},
        fields=["name", "title", "due_date", "exam"],
        ignore_permissions=True,
    )
    return exams


@frappe.whitelist()
def get_course_meetingdates(course):
    meetingdates = frappe.get_all(
        "Course Schedule Meeting Dates",
        fields=["name", "cs_meetdate", "cs_fromtime", "cs_totime", "attendance"],
        filters={"parent": course},
        order_by="cs_meetdate asc",
    )
    return meetingdates


@frappe.whitelist()
def get_missingassessments(course, member=None):
    # Default to the logged-in user when the caller omits `member`.
    # The frontend can't reliably pass it on first render because the
    # user resource resolves asynchronously.
    student_email = member or frappe.session.user
    course_name = course

    # Per-row correlated NOT EXISTS: an assessment is "missing" only when
    # *this* student has no submission for *that specific* activity. The
    # previous `not in (... where course=X)` form excluded the student from
    # every missing row the moment they submitted a single assessment of
    # that type anywhere in the course.
    missing_exams_query = """
		select r.stuname_roster, r.stuemail_rc, r.stuimage, r.program_std_scr, c.title, c.due_date
		from `tabScheduled Course Roster` r, `tabScheduled Course Assess Criteria` c
		where r.course_sc = c.parent and
		c.exam <> '' and
		c.due_date < NOW() and
		r.stuemail_rc = %(student_email)s and
		r.course_sc = %(course_name)s and
		not exists (
			select 1 from `tabExam Submission` es
			where es.course = c.parent
			and es.exam = c.exam
			and es.member = r.stuemail_rc
		)
	"""

    missing_quizzes_query = """
		select r.stuname_roster, r.stuemail_rc, r.stuimage, r.program_std_scr, c.title, c.due_date
		from `tabScheduled Course Roster` r, `tabScheduled Course Assess Criteria` c
		where r.course_sc = c.parent and
		c.quiz <> '' and
		c.due_date < NOW() and
		r.stuemail_rc = %(student_email)s and
		r.course_sc = %(course_name)s and
		not exists (
			select 1 from `tabQuiz Submission` qs
			where qs.course = c.parent
			and qs.quiz = c.quiz
			and qs.member = r.stuemail_rc
		)
	"""

    missing_assignments_query = """
		select r.stuname_roster, r.stuemail_rc, r.stuimage, r.program_std_scr, c.title, c.due_date
		from `tabScheduled Course Roster` r, `tabScheduled Course Assess Criteria` c
		where r.course_sc = c.parent and
		c.assignment <> '' and
		c.due_date < NOW() and
		r.stuemail_rc = %(student_email)s and
		r.course_sc = %(course_name)s and
		not exists (
			select 1 from `tabAssignment Submission` asub
			where asub.course = c.parent
			and asub.assignment = c.assignment
			and asub.member = r.stuemail_rc
		)
	"""

    result = frappe.db.sql(
        f"({missing_exams_query}) UNION ({missing_quizzes_query}) UNION ({missing_assignments_query})",
        {"student_email": student_email, "course_name": course_name},
        as_dict=True,
    )
    print("Missing assessments: ", result)  # Debugging log
    return result


@frappe.whitelist()
def get_assessments_tograde(course):
    print("Assessment to Grade from Course Name: ", course)  # Debugging log
    # Query to get all assignments and exams that are not graded for the course card ToDo. Quizzes are auto-graded.
    assignments_query = """
		select "Assignment" as Type, assignment as assessmentID, assignment_title as title, count(name)  as ToGrade
		from `tabAssignment Submission`
		where course = %(course)s and status = 'Not Graded'
		group by assignment, assignment_title"""
    exams_query = """select "Exam" as Type, exam as assessmentID, exam_title as title, count(name)  as ToGrade
		from `tabExam Submission`
		where course = %(course)s and status = 'Not Graded'
		group by exam, exam_title"""
    result = frappe.db.sql(
        f"({assignments_query}) UNION ({exams_query})",
        {"course": course},
        as_dict=True,
    )
    print("Assessments to grade: ", result)
    # Debugging log
    return result


# debugging frappe.client.insert dict error
@frappe.whitelist()
def insert_discussion_reply(reply, topic):
    print("Inserting reply:", reply)
    print("Topic:", topic)
    doc = frappe.new_doc("Discussion Reply")
    doc.update(
        {
            "reply": reply,
            "topic": topic,
            "owner": frappe.session.user,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


# Student Group Utils
@frappe.whitelist()
def get_student_groups(course):
    groups = frappe.db.sql(
        """select lk.student_group, lk.group_instructor, sgm.student, sgm.student_name, sg.group_name
from `tabCourse Schedule` cs, `tabStudent Group Link` lk, `tabStudent Group` sg, `tabStudent Group Members` sgm
where lk.parent = cs.name and
sg.name = lk.student_group and
sg.name = sgm.parent and cs.name = %s""",
        (course,),
        as_dict=True,
    )
    return groups


@frappe.whitelist()
def create_student_group(course, group_name, group_instructor, members):
    course_doc = frappe.get_doc("Course Schedule", course)
    student_group = frappe.new_doc("Student Group")
    student_group.group_name = group_name
    student_group.mentor = group_instructor
    student_group.insert(ignore_permissions=True)

    course_doc.append("stu_groups_course", {})
    course_doc.stu_groups_course[-1].student_group = student_group.name
    course_doc.stu_groups_course[-1].group_instructor = group_instructor
    course_doc.save(ignore_permissions=True)

    for member in members:
        # Extract the 'member' key if member is a dictionary
        if isinstance(member, dict):
            member = member.get("member", "")

        if not member:
            frappe.throw("Invalid member data: 'member' field is missing.")

        group_member = frappe.new_doc("Student Group Members")
        group_member.parent = student_group.name
        group_member.parentfield = "group_members"
        group_member.parenttype = "Student Group"
        group_member.student = member
        group_member.student_name = frappe.db.get_value(
            "Student", {"name": member}, "student_name"
        )
        group_member.insert(ignore_permissions=True)

    return student_group.name
