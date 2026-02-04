import frappe


@frappe.whitelist()
def create_student_groups(course_name, groups):
    """
    Create student groups and their associations.

    Args:
        course_name (str): The name of the course.
        groups (list): A list of dictionaries containing group details.

    Returns:
        dict: Success or error message.
    """
    from frappe.model.document import Document

    try:
        for group in groups:
            # Create Student Group
            student_group = frappe.get_doc(
                {
                    "doctype": "Student Group",
                    "group_name": group["group_name"],
                    "course": course_name,
                    "reuse": False,
                    "active": False,
                }
            )
            student_group.insert()

            # Add Student Group Members
            for student in group["students"]:
                student_group.append(
                    "members",
                    {
                        "student": student,
                    },
                )

            # Link to Course Schedule
            for schedule in group["schedules"]:
                student_group.append(
                    "course_schedule_links",
                    {
                        "course_schedule": schedule,
                    },
                )

            student_group.save()

        return {"status": "success", "message": "Student groups created successfully."}

    except Exception as e:
        return {"status": "error", "message": str(e)}
