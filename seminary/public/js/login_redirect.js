$(document).ready(function () {
	var roles = (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
	if (roles.includes("Student") && window.location.pathname.startsWith("/desk")) {
		window.location.href = "/seminary/courses";
	}
});