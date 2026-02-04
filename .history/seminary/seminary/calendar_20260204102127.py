import frappe
from datetime import datetime
from datetime import timedelta
import re
from frappe import _
from ics import Calendar, Event
import pytz


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


def convert_to_ics_datetime(dt):
    """Convert a datetime object to ICS format with timezone."""
    if not dt:
        return None
    dt = frappe.utils.get_datetime(dt)
    dt_utc = dt.astimezone(pytz.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")


@frappe.whitelist()
def course_ics(course_schedule, token):
    """Generate ICS calendar data for a given course schedule."""
    if not course_schedule or not token:
        raise frappe.ValidationError(_("Course Schedule and token are required."))

    # Validate the token
    validate_token(course_schedule, token)
    meeting_dates = frappe.db.sql(
        """
        select mt.cs_fromtime, mt.cs_totime, mt.cs_meetdate, cs.room
        from `tabCourse Schedule Meeting Dates` mt, `tabCourse Schedule` cs
        where mt.parent = %s and
        mt.parent = cs.name
        """,
        (course_schedule,),
        as_dict=True,
    )
    print("Fetched meeting dates: ", meeting_dates)
    assignments = frappe.db.sql(
        """
        select assignment, parent, due_date from `tabScheduled Course Assess Criteria` where parent = %s
        """,
        (course_schedule,),
        as_dict=True,
    )
    current
    calendar = Calendar()

    for meeting in meeting_dates:
        event = Event()
        event.begin = convert_to_ics_datetime(
            datetime.combine(
                meeting.cs_meetdate, (datetime.min + meeting.cs_fromtime).time()
            )
        )
        event.end = convert_to_ics_datetime(
            datetime.combine(
                meeting.cs_meetdate, (datetime.min + meeting.cs_totime).time()
            )
        )
        event.name = f"{course_schedule} (_( Class Session))"
        event.description = f"Course Schedule: {course_schedule}\nMeeting Date: {meeting.cs_meetdate}\nFrom: {meeting.cs_fromtime}\nTo: {meeting.cs_totime}"
        if meeting.room:
            event.location = meeting.room
        # Add DTSTAMP property to the event
        event.dtstamp = convert_to_ics_datetime(datetime.utcnow())
        calendar.events.add(event)
    for assignment in assignments:
        event = Event()
        event.begin = convert_to_ics_datetime(assignment.due_date - timedelta(hours=1))
        event.end = convert_to_ics_datetime(assignment.due_date)
        event.name = f"{course_schedule} - {assignment.assignment} (_( Assignment Due))"
        event.description = f"Course Schedule: {course_schedule}\nAssignment: {assignment.assignment}\nDue Date: {assignment.due_date}"
        calendar.events.add(event)

    # Use serialize() to generate the ICS representation
    calendar_data = calendar.serialize()

    # Ensure proper line length for ICS format
    calendar_data = "\r\n".join(
        line[:75] + ("\r\n " + line[75:] if len(line) > 75 else "")
        for line in calendar_data.splitlines()
    )

    # Directly set the response headers and body
    frappe.local.response.filename = f"{course_schedule}.ics"
    frappe.local.response.filecontent = calendar_data
    frappe.local.response.type = "binary"

    # Ensure frappe.local.response.headers is initialized
    if not frappe.local.response.headers:
        frappe.local.response.headers = {}

    # Set the Content-Type header
    frappe.local.response.headers["Content-Type"] = "text/calendar; charset=utf-8"

    print("Generated ICS data: ", calendar_data)
    return


@frappe.whitelist()
def get_calendar_instructions():
    """Fetch calendar instructions from Seminary Settings."""
    instructions = frappe.db.get_single_value(
        "Seminary Settings", "calendar_instructions"
    )
    print("Fetched calendar instructions: ", instructions)
    return instructions
