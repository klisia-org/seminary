# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

# import frappe
# from frappe import _
# from seminary.seminary.doctype.instructor.instructor import get_timeline_data

# def get_data():
#     print("get_data function called")  # Debugging statement
#     instructor_name = frappe.form_dict.name
#     print("Instructor Name:", instructor_name)  # Debugging statement

#     timeline_data = get_timeline_data("Instructor", instructor_name)
#     print("Timeline Data:", timeline_data)  # Debugging statement

#     return {
#         "heatmap": True,
#         "heatmap_message": _("This is based on the course schedules of this Instructor"),
#         "fieldname": "instructor_name",
#         "timeline_data": timeline_data,
#         "transactions": [
#             {
#                 "label": _("Courses"),
#                 "items": ["Course Schedule"],
#             },
#         ],
#     }
