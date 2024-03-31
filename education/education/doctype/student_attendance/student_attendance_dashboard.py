from frappe import _


def get_data():
	return {
		"reports": [
			{
				"label": _("Reports"),
				"items": ["Student Monthly Attendance Sheet"],
			}
		]
	}
