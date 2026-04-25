import frappe


def update_website_context(context):
    try:
        context.show_student_application = frappe.db.get_single_value(
            "Seminary Settings", "show_student_application_on_login"
        )
    except Exception:
        context.show_student_application = 0

    if context.show_student_application:
        # Inject via head script that runs on login page only
        script = """
        <script>
        document.addEventListener("DOMContentLoaded", function () {
            if (window.location.pathname === "/login") {
                var loginContainer = document.querySelector(".page-card");
                if (loginContainer) {
                    var div = document.createElement("div");
                    div.className = "text-center";
                    div.style.marginTop = "20px";
                    div.innerHTML = '<p>%s</p>' +
                        '<a href="/student-applicant/new" class="btn btn-primary btn-md">%s</a>';
                    loginContainer.appendChild(div);
                }
            }
        });
        </script>
        """ % (
            frappe._("Want to join us?"),
            frappe._("Apply to be our Student"),
        )

        # Guard against `context["head_html"]` being explicitly None
        # (Builder pages initialise it that way). `setdefault` leaves an
        # existing None value alone, which would TypeError on the +=.
        context["head_html"] = (context.get("head_html") or "") + script
