from frappe import _


def get_data():
    return {
        "fieldname": "program_enrollment",
        "transactions": [
            {"label": _("Requirements"), "items": ["Requirement Exception"]},
        ],
        "reports": [{"label": _("Report"), "items": ["Student Program Progress"]}],
    }
