import frappe


def redirect_student_on_login(login_manager):
    """Redirect students to the Seminary portal instead of Desk after login.

    on_login fires before set_user_info(), which would overwrite home_page to /desk
    for any System User. Writing to the redirect_after_login cache key is the correct
    mechanism: set_user_info() reads it and emits it as `redirect_to` in the response,
    which the login page JS prioritises over `home_page`.
    """
    if "Student" in frappe.get_roles(login_manager.user):
        frappe.cache.hset(
            "redirect_after_login", login_manager.user, "/seminary/courses"
        )
