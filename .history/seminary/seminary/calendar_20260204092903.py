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


def convert_to_ics_datetime(dt: datetime):
    """Convert a datetime object to ICS format with timezone."""
    if not dt:
        return None
    dt = frappe.utils.get_datetime(dt)
    dt_utc = dt.astimezone(pytz.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")


@frappe.whitelist()
def course_ics(course_schedule: str | None = None, token: str | None = None):
    print("Generating ICS for Course Schedule:", course_schedule)
    """Generate ICS calendar data for a given course schedule."""
    if not course_schedule or not token:
        raise frappe.ValidationError(_("Course Schedule and token are required."))

    # Validate the token
    validate_token(course_schedule, token)
    course_schedule_doc = frappe.get_doc("Course Schedule", course_schedule)
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
    assignments = frappe.db.sql(
        """
		select assignment, parent, due_date from `tabScheduled Course Assess Criteria` where parent = %s
        """,
        (course_schedule,),
        as_dict=True,
    )

    calendar = Calendar()

    for meeting in meeting_dates:
        event = Event()
        event.begin = convert_to_ics_datetime(
            datetime.combine(meeting.cs_meetdate, meeting.cs_fromtime)
        )
        event.end = convert_to_ics_datetime(
            datetime.combine(meeting.cs_meetdate, meeting.cs_totime)
        )
        event.name = f"{course_schedule_doc.course_name} (_( Class Session))"
        event.description = f"Course Schedule: {course_schedule_doc.name}"
        if meeting.room:
            event.location = meeting.room
        calendar.events.add(event)
    for assignment in assignments:
        event = Event()
        event.begin = convert_to_ics_datetime(assignment.due_date - timedelta(hours=1))
        event.end = convert_to_ics_datetime(assignment.due_date)
        event.name = f"{course_schedule_doc.course_name} - {assignment.assignment} (_( Assignment Due))"
        event.description = f"Course Schedule: {course_schedule_doc.name}\nAssignment: {assignment.assignment}\nDue Date: {assignment.due_date}"
        calendar.events.add(event)

    calendar_data = str(calendar)
    print("Generated ICS data: ", calendar_data)
    return calendar_data


@frappe.whitelist()
def get_calendar_instructions():
    """Fetch calendar instructions from Seminary Settings."""
    instructions = frappe.db.get_single_value(
        "Seminary Settings", "calendar_instructions"
    )
    print("Fetched calendar instructions: ", instructions)
    return instructions
