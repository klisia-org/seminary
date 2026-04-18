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
