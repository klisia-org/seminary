import frappe


def execute():
    """File every assessment on its chapter's competency.

    Activities placed in a lesson after their assessment existed were never
    filed, so the row kept no competency: it could not be graded, and its result
    card blocked Send Grades.
    """
    from seminary.seminary.doctype.course_schedule.course_schedule import (
        refile_chapter_competencies,
    )

    for cs in frappe.get_all(
        "Course Schedule Chapter",
        filters={"course_competency": ("is", "set")},
        pluck="coursesc",
        distinct=True,
    ):
        refile_chapter_competencies(cs)
