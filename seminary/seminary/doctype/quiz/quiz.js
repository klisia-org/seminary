// Copyright (c) 2021, FOSS United and contributors
// For license information, please see license.txt

frappe.ui.form.on("Quiz", {
	// refresh: function(frm) {
	// }
});

frappe.ui.form.on("Quiz Question", {
	points: function (frm) {
		total_points = 0;
		frm.doc.questions.forEach((question) => {
			total_points += question.points;
		});
		frm.doc.total_points = total_points;
	},
});