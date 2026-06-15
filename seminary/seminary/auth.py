import frappe

# Non-staff portal users are redirected to their portal home after login, in
# priority order. A user with a staff role keeps the Desk default.
PORTAL_HOME = (
    ("Student", "/seminary/courses"),
    ("Partner", "/seminary/partner"),
    ("Alumni", "/seminary/alumni"),
)
STAFF_ROLES = {
    "Instructor",
    "Program Chair",
    "Registrar",
    "Seminary Manager",
    "System Manager",
    "Administrator",
}


def redirect_student_on_login(login_manager):
    """Redirect portal users (students, partners, alumni) to their portal home
    instead of Desk after login.

    on_login fires before set_user_info(), which would overwrite home_page to
    /desk for any System User. Writing to the redirect_after_login cache key is
    the correct mechanism: set_user_info() reads it and emits it as `redirect_to`
    in the response, which the login page JS prioritises over `home_page`.
    """
    roles = set(frappe.get_roles(login_manager.user))
    if roles & STAFF_ROLES:
        return
    for role, home in PORTAL_HOME:
        if role in roles:
            frappe.cache.hset("redirect_after_login", login_manager.user, home)
            return
