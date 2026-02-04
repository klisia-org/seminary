# from ics import Calendar, Event
import frappe
from datetime import datetime
import re
from frappe import _
from seminary.seminary.doctype.course_schedule import course_schedule
from seminary.seminary.doctype.course_schedule import course_schedule


@frappe.whitelist()
def validate_token(course_schedule: str | None = None, token: str | None = None):
    """Validate calendar token for a given course schedule."""
    if not course_schedule or not token:
        raise frappe.ValidationError(_("Course Schedule and token are required."))

    stored_token = frappe.db.get_value(
        "Course Schedule", course_schedule, "calendar_token"
    )
    if not stored_token or stored_token != token:
        raise frappe.ValidationError(_("Invalid calendar token provided."))

    return True


@frappe.whitelist()
def course_ics(course_schedule: str | None = None, token: str | None = None):
    """Generate ICS calendar data for a given course schedule."""
    if not course_schedule or not token:
        raise frappe.ValidationError(_("Course Schedule and token are required."))

    # Validate the token
    validate_token(course_schedule, token)
    course_schedule_doc = frappe.get_doc("Course Schedule", course_schedule)
    meeting_dates = frappe.db.sql(
        """
        SELECT cs_meetdate, cs_fromtime, cs_totime
        FROM `tabCourse Schedule Meeting Dates`
        WHERE parent = %s
        """,
        (course_schedule,),
        as_dict=True,
    )
    calendar_data = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//SeminaryERP//Course Schedule//EN\n"
    )

    for meeting in meeting_dates:
        calendar_data += "BEGIN:VEVENT\n"
        start_datetime = datetime.combine(meeting.cs_meetdate, meeting.cs_fromtime)
        end_datetime = datetime.combine(meeting.cs_meetdate, meeting.cs_totime)
        calendar_data += f"DTSTART:{start_datetime.strftime('%Y%m%dT%H%M%S')}\n"
        calendar_data += f"DTEND:{end_datetime.strftime('%Y%m%dT%H%M%S')}\n"
        calendar_data += f"SUMMARY:{course_schedule_doc.course}\n"
        if course_schedule_doc.room:
            calendar_data += f"LOCATION:{course_schedule_doc.room}\n"
        if course_schedule_doc.course_description_for_lms:
            description = re.sub(
                r"\s+", " ", course_schedule_doc.course_description_for_lms
            )
            calendar_data += f"DESCRIPTION:{description}\n"
        calendar_data += "END:VEVENT\n"

    calendar_data += "END:VCALENDAR"

    print("Generated ICS data: ", calendar_data)
    return calendar_data


@frappe.whitelist()
def get_calendar_instructions():
    """Fetch calendar instructions from Seminary Settings."""
    instructions = frappe.db.get_single_value(
        "SeminarySettings", "calendar_instructions"
    )
    print("Fetched calendar instructions: ", instructions)
    return instructions
