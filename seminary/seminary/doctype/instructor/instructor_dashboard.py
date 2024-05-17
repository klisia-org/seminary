# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from frappe import _


def get_data():
	return {
		"heatmap": True,
		"heatmap_message": _("This is based on the course schedules of this Instructor"),
		"fieldname": "instructor",
		
		"transactions": [
			{
				"label": _("Courses"),
				"items": ["Course Schedule"],
			},
			
		],
	}
