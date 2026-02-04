from ics import Calendar, Event
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
    calendar = Calendar()

    for meeting in meeting_dates:
        event = ics.Event()
        event.begin = datetime.combine(meeting.cs_meetdate, meeting.cs_fromtime)
        event.end = datetime.combine(meeting.cs_meetdate, meeting.cs_totime)
        event.name = f"{course_schedule_doc.course_name} Session"
        event.description = f"Course Schedule: {course_schedule_doc.name}"
        calendar.events.add(event)

    calendar_data = str(calendar)
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
