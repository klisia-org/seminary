"""decisions/106 §4: a Question's four fixed option slots and four accepted-answer
slots move into the Choices and Accepted Answers tables.

The old columns stay in tabQuestion after the fields leave the schema, so this
reads them with SQL. A question that already has rows is left alone, so the
patch can run twice."""

import frappe

OLD = [f"{k}_{n}" for n in range(1, 5) for k in ("option", "is_correct", "explanation", "possibility")]


def execute():
	columns = set(frappe.db.get_table_columns("Question"))
	if "option_1" not in columns:
		return
	have = {
		r.parent
		for r in frappe.get_all(
			"Question Option", filters={"parenttype": "Question"}, fields=["parent"], distinct=True
		)
	}
	have |= {
		r.parent
		for r in frappe.get_all(
			"Question Accepted Answer", filters={"parenttype": "Question"}, fields=["parent"], distinct=True
		)
	}
	table = frappe.qb.DocType("Question")
	rows = (
		frappe.qb.from_(table).select(table.name, *[table[c] for c in OLD if c in columns]).run(as_dict=True)
	)
	for q in rows:
		if q.name in have:
			continue
		doc = frappe.get_doc("Question", q.name)
		for n in range(1, 5):
			# Text kept as stored: past submissions recorded the option text itself.
			option = q.get(f"option_{n}")
			if option and option.strip():
				doc.append(
					"choices",
					{
						"option": option,
						"is_correct": 1 if q.get(f"is_correct_{n}") else 0,
						"explanation": q.get(f"explanation_{n}") or None,
					},
				)
			answer = q.get(f"possibility_{n}")
			if answer and answer.strip():
				doc.append("accepted_answers", {"answer": answer})
		for child in doc.choices + doc.accepted_answers:
			child.db_insert()
