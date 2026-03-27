frappe.ready(function () {
	if (frappe.user.has_role("Student") && window.location.pathname.startsWith("/login")) {
		window.location.href = "/seminary/courses";
	}
});