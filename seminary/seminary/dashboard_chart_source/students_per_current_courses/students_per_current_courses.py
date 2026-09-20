import frappe
from frappe import _


@frappe.whitelist()
def get(
    chart_name=None,
    chart=None,
    no_cache=None,
    filters=None,
    from_date=None,
    to_date=None,
    timespan=None,
    time_interval=None,
    heatmap_year=None,
    to_timezone=None,
):
    # p008a G6: this is a Desk dashboard chart source, and it was whitelisted
    # with no check of any kind -- any signed-in session, a Student's included,
    # got every current section with its active enrolment headcount. Frappe's own
    # chart route checks the chart's permissions; a source called directly does
    # not, so the check belongs here.
    frappe.only_for(
        ("Program Chair", "Registrar", "Seminary Manager", "System Manager")
    )
    rows = frappe.db.sql(
        """
        SELECT cs.title AS label,
               cs.name AS schedule_name,
               COUNT(scr.name) AS value
        FROM `tabCourse Schedule` cs
        INNER JOIN `tabAcademic Term` aterm
            ON aterm.name = cs.academic_term
        LEFT JOIN `tabScheduled Course Roster` scr
            ON scr.course_sc = cs.name
            AND scr.active = 1
        WHERE aterm.iscurrent_acterm = 1
        GROUP BY cs.name
        HAVING value > 0
        ORDER BY cs.title
        """,
        as_dict=True,
    )

    labels = [r.label or r.schedule_name for r in rows]
    values = [r.value for r in rows]

    return {
        "labels": labels,
        "datasets": [
            {
                "name": _("Students Enrolled"),
                "values": values,
            }
        ],
    }
