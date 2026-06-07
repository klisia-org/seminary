// Shared behaviour for ALL Student Applicant web forms (the built-in
// `student-applicant` form and any custom, seminary-built ones).
//
// It is wired up via `webform_include_js` in hooks.py for standard forms, and
// injected into non-standard forms by SeminaryWebForm (see
// seminary/seminary/overrides/web_form.py). Keep it self-contained: on the
// standard form it is concatenated after that form's own script, so it must not
// rely on or collide with helpers defined there.
//
// Form-specific behaviour (e.g. the built-in form's post-submit payment
// redirect) stays in the individual form's own script, NOT here.

frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;

    // Render the active admission Doctrinal Statement as a read-only block
    // directly above the `signdoctrine` signature, so the applicant reads it
    // before signing. This works on any form that includes the signature field
    // — no `ds2` field and no per-form script required.
    frappe.call("seminary.seminary.api.get_doctrinal_statement").then(function (r) {
        var ds = r && r.message;
        if (!ds || !ds.body) return;

        var tries = 0;
        var timer = setInterval(function () {
            tries += 1;

            // Already injected (e.g. script ran twice) — stop.
            if (document.getElementById("seminary-doctrinal-statement")) {
                clearInterval(timer);
                return;
            }

            var $sign = $('[data-fieldname="signdoctrine"]').first();
            if ($sign.length) {
                clearInterval(timer);
                var heading = {{ _("Please read carefully and check if you agree with our doctrinal statement") | tojson }};
                var $wrap = $('<div id="seminary-doctrinal-statement" style="margin-bottom:1rem;"></div>');
                $('<p style="font-weight:600;margin-bottom:0.5rem;"></p>').text(heading).appendTo($wrap);
                $(
                    '<div style="padding:1rem;border:1px solid #e0e0e0;border-radius:6px;' +
                    'max-height:320px;overflow:auto;background:#fafafa;"></div>'
                ).html(ds.body).appendTo($wrap);
                $sign.before($wrap);
            } else if (tries > 40) {
                clearInterval(timer);
            }
        }, 150);
    });
});
