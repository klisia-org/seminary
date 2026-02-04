import frappe
from datetime import datetime
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

    timezone = pytz.timezone(
        frappe.db.get_single_value("System Settings", "time_zone") or "UTC"
    )
    localized_dt = timezone.localize(dt)
    return localized_dt


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
        event.begin = datetime.combine(meeting.cs_meetdate, meeting.cs_fromtime)
        event.end = datetime.combine(meeting.cs_meetdate, meeting.cs_totime)
        event.name = f"{course_schedule_doc.course_name} (_( Class Session))"
        event.description = f"Course Schedule: {course_schedule_doc.name}"
        if meeting.room:
            event.location = meeting.room
        calendar.events.add(event)
    for assignment in assignments:
        event = Event()
        event.begin = datetime.combine(assignment.due_date, datetime.min.time())
        event.end = datetime.combine(assignment.due_date, datetime.max.time())
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
