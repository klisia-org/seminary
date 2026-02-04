# Copyright (c) 2024, Klisia and Frappe and contributors
# For license information, please see license.txt

import frappe
import pandas as pd

# Execute the SQL query
data = frappe.db.sql(
    """
    SELECT sc.student, sc.stuname_roster as Student_Name, cd.assessment_criteria, COALESCE(rawscore_card, actualextrapt_card) AS grade
    FROM `tabScheduled Course Roster` sc, `tabCourse Assess Results Detail` cd
    WHERE cd.parent = sc.name AND sc.course_sc = "GNS631 - Liberian Realities-2023-2024 (2024SP)-0345"
    ORDER BY sc.stuname_roster, cd.assessment_criteria
""",
    as_dict=True,
)

# Convert the data into a pandas DataFrame
df = pd.DataFrame(data)

# Display the DataFrame
df = df.pivot(
    index=["student", "Student_Name"], columns="assessment_criteria", values="grade"
)
result = df


""" def execute(filters=None):
	columns, data = [], []
	return columns, data
 """
