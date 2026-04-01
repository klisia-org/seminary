$(document).ready(function () {
	var roles = (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
	var path = window.location.pathname;
	var isStudent = roles.includes("Student");
	var isStaff = roles.includes("Instructor") || roles.includes("System Manager")
		|| roles.includes("Administrator") || roles.includes("Seminary Manager")
		|| roles.includes("Course Moderator") || roles.includes("Evaluator");
	if (isStudent && !isStaff && (path === "/desk" || path === "/desk/" || path.startsWith("/desk/seminary"))) {
		window.location.href = "/seminary/courses";
	}
});