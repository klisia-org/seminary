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


// Make the multi-page progress dots navigable.
//
// Frappe renders one `.slide-step` per page with a `data-step-id`, marks the
// visited ones with a tick, and binds no click handler — so they look like
// navigation and are not. On a form this long that is a trap: an applicant who
// hits a validation error on the last page can only walk back through every
// page with Previous, and then walk forward again to reach Submit.
//
// Deliberately not gated on validating the page being left. The whole point is
// to go *back* and fix something, and jumping forward is safe because Submit
// validates the entire document regardless of which page you are standing on.
frappe.ready(() => {
	// Delegated: `toggle_section()` re-renders the dots on every page change,
	// so anything bound to the elements themselves is discarded on first use.
	$(document).on("click", ".slides-progress .slide-step", function () {
		const form = window.frappe && frappe.web_form;
		if (!form || !form.is_multi_step_form) return;

		const target = parseInt($(this).attr("data-step-id"), 10);
		if (isNaN(target) || target === form.current_section) return;

		form.current_section = target;
		form.toggle_section();
		// The page changes above the fold; without this the applicant is left
		// looking at the footer of a page they did not ask for. Plain
		// `scrollTo` rather than `frappe.utils.scroll_to`, which is a Desk
		// helper and is not guaranteed to be in the portal bundle.
		window.scrollTo(0, 0);
	});

	// The dots carry no affordance of their own.
	$("<style>.slides-progress .slide-step { cursor: pointer; }</style>").appendTo("head");
});


// Address autocomplete on the public application form (ADR 068 §7), proxied
// through the server so no API key sits in the page — which matters most here,
// on the one page served to anyone on the internet. This is also where a badly
// typed address does the most damage: the applicant never sees the Person
// record their address ends up on, and a misspelt street is what makes a
// mentor-distance rule quietly useless.
frappe.ready(() => {
	const bind = () => {
		const input = document.querySelector('[data-fieldname="address_line_1"] input');
		if (!input || !window.seminary?.attachAddressAutocomplete) return false;
		window.seminary.attachAddressAutocomplete(input, (address) => {
			const set = (fieldname, value) => {
				if (!value) return;
				const el = document.querySelector(`[data-fieldname="${fieldname}"] input, [data-fieldname="${fieldname}"] select`);
				if (!el) return;
				el.value = value;
				el.dispatchEvent(new Event("change", { bubbles: true }));
			};
			set("address_line_1", address.address_line_1);
			set("address_line_2", address.address_line_2);
			set("city", address.city);
			set("state", address.state);
			set("pincode", address.pincode);
			set("country", address.country);
		});
		return true;
	};

	// Web form fields render after ready; poll briefly rather than guess.
	if (bind()) return;
	let tries = 0;
	const timer = setInterval(() => {
		if (bind() || ++tries > 40) clearInterval(timer);
	}, 150);
});
