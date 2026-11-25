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


// The tax ID on the public application form (ADR 071). The applicant is asked
// for a number whose format depends on where they are from, so the field
// relabels and re-masks itself when they pick a nationality — a Brazilian sees
// "CPF" and a mask, and everyone else sees a plain box.
//
// Shared with the Desk forms: public/js/tax_id.bundle.js.
frappe.ready(() => {
	const country_of = () => {
		for (const fieldname of ["nationality", "country"]) {
			const el = document.querySelector(
				`[data-fieldname="${fieldname}"] input, [data-fieldname="${fieldname}"] select`
			);
			if (el && el.value) return el.value;
		}
		return "";
	};

	const bind = () => {
		const input = document.querySelector('[data-fieldname="tax_id"] input');
		if (!input || !window.seminary?.bindTaxIdInput) return false;

		const refresh = window.seminary.bindTaxIdInput(input, country_of, {
			subject: "person",
		});
		if (!refresh) return true;

		// Re-fetch the rule when the country they answered for changes.
		["nationality", "country"].forEach((fieldname) => {
			const el = document.querySelector(
				`[data-fieldname="${fieldname}"] input, [data-fieldname="${fieldname}"] select`
			);
			if (el) {
				el.addEventListener("change", () =>
					window.seminary.bindTaxIdInput(input, country_of, { subject: "person" })
				);
			}
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


// Documents the chosen program asks for on the application (decisions/091 §10).
//
// The `documents` table carries one row per Document Type the program marks
// "Ask on Application"; the applicant attaches a file to each. The rows follow
// the program: changing it keeps the files already attached to a type the new
// program also asks for. On a form without the table this does nothing.
frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;
    var wf = frappe.web_form;
    if (!wf.fields_dict || !wf.fields_dict.documents) return;

    function setRows(program) {
        if (!program) {
            apply([]);
            return;
        }
        frappe.call({
            method: "seminary.seminary.requirements.application_documents",
            args: { program: program },
        }).then(function (r) {
            apply((r && r.message) || []);
        });
    }

    function apply(types) {
        var current = (wf.doc && wf.doc.documents) || [];
        var byType = {};
        current.forEach(function (row) {
            if (row && row.document_type) byType[row.document_type] = row;
        });
        var rows = types.map(function (t, i) {
            var old = byType[t.document_type];
            return {
                doctype: "Student Applicant Document",
                idx: i + 1,
                document_type: t.document_type,
                file: old ? old.file : "",
            };
        });
        var help = types
            .filter(function (t) { return t.description || (t.allowed_extensions || []).length; })
            .map(function (t) {
                var exts = (t.allowed_extensions || []).join(", ");
                return frappe.utils.escape_html(t.document_type) + ": " +
                    frappe.utils.escape_html(t.description || "") +
                    (exts ? " (" + frappe.utils.escape_html(exts) + ")" : "");
            })
            .join("<br>");
        wf.doc.documents = rows;
        try {
            wf.set_value("documents", rows);
        } catch (e) {
            var grid = wf.fields_dict.documents.grid;
            if (grid) {
                grid.df.data = rows;
                grid.refresh();
            }
        }
        wf.set_df_property("documents", "description", help);
        wf.set_df_property("documents", "hidden", rows.length ? 0 : 1);
    }

    if (wf.on) {
        wf.on("program", function (field, value) {
            setRows(value);
        });
    }
    setRows(wf.doc && wf.doc.program);
});

// Every field named for assistive technology (decision 102 §9, WCAG 1.3.1/4.1.2):
// Frappe's web form draws a field's label beside its control without tying the two
// together for some field types (Select among them). Name any control left without
// a label from the field's own label.
frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;
    function nameControls() {
        var fields = frappe.web_form.fields_dict || {};
        Object.keys(fields).forEach(function (key) {
            var field = fields[key];
            var label = field && field.df && field.df.label;
            if (!label || !field.$wrapper) return;
            field.$wrapper.find("input, select, textarea").each(function () {
                var has = (this.labels && this.labels.length) || this.getAttribute("aria-label") || this.getAttribute("aria-labelledby");
                if (!has) this.setAttribute("aria-label", __(label));
            });
        });
    }
    nameControls();
    // Fields drawn later (a section shown, a page turned) are named on the next change.
    var timer = null;
    new MutationObserver(function () {
        clearTimeout(timer);
        timer = setTimeout(nameControls, 200);
    }).observe(document.body, { childList: true, subtree: true });
});

// Landmarks told apart (WCAG 1.3.1): the web form is one form, named by its title.
// Frappe lays out each column of fields in a <form> of its own; those are layout, not
// further forms, so they leave the landmark list. Each date field's calendar has a
// <nav> for its month arrows; it is named after its field.
frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;
    function nameLandmarks() {
        var title = frappe.web_form_doc && frappe.web_form_doc.title;
        var main = document.querySelector("form.web-form");
        if (main && title && !main.getAttribute("aria-label")) main.setAttribute("aria-label", __(title));
        document.querySelectorAll("form.web-form form:not([role])").forEach(function (column) {
            column.setAttribute("role", "none");
        });
        var fields = frappe.web_form.fields_dict || {};
        Object.keys(fields).forEach(function (key) {
            var field = fields[key];
            var label = field && field.df && field.df.label;
            var picker = field && field.datepicker && field.datepicker.$datepicker;
            if (!label || !picker) return;
            picker.find("nav").attr("aria-label", __("{0} calendar", [__(label)]));
        });
    }
    nameLandmarks();
    // Fields drawn later (a section shown, a page turned) are handled on the next change.
    var timer = null;
    new MutationObserver(function () {
        clearTimeout(timer);
        timer = setTimeout(nameLandmarks, 200);
    }).observe(document.body, { childList: true, subtree: true });
});

// The chosen program's own questions and agreements (decisions/111).
//
// Questions come from the school's shared pool; the program picks which ones
// its form asks. They are drawn above the hidden `answers` table and written
// into it as the applicant types, one row per question. Three pool entries are
// tables (education, emergency contacts, references): those are shown only
// when the program asks for them. Agreements are drawn above the hidden
// `agreements` table: the applicant reads each one, ticks I agree, types their
// name and signs. The server checks all of it again on save.
frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;
    var wf = frappe.web_form;
    var fields = wf.fields_dict || {};
    if (!fields.answers && !fields.agreements) return;

    var TABLES = ["education", "contacts", "references"];
    var TYPES = {
        "Short text": { fieldtype: "Data" },
        "Long text": { fieldtype: "Small Text" },
        "Select": { fieldtype: "Select" },
        "Check": { fieldtype: "Check" },
        "Date": { fieldtype: "Date" },
        "Number": { fieldtype: "Float" },
        "Phone": { fieldtype: "Data", options: "Phone" },
        "Email": { fieldtype: "Data", options: "Email" },
    };

    function setTable(fieldname, rows) {
        wf.doc[fieldname] = rows;
        try {
            wf.set_value(fieldname, rows);
        } catch (e) {
            var grid = fields[fieldname] && fields[fieldname].grid;
            if (grid) {
                grid.df.data = rows;
                grid.refresh();
            }
        }
    }

    function holder(fieldname, id) {
        var field = fields[fieldname];
        if (!field || !field.$wrapper) return null;
        field.$wrapper.hide();
        var $box = $("#" + id);
        if (!$box.length) {
            $box = $('<div id="' + id + '" class="seminary-application-block"></div>');
            field.$wrapper.before($box);
        }
        return $box.empty();
    }

    // ---- questions --------------------------------------------------------
    var questions = [];
    var answers = {};

    function writeAnswers() {
        var rows = questions.map(function (q, i) {
            var v = answers[q.question];
            if (q.answer_type === "Check") v = v ? "1" : "0";
            return {
                doctype: "Student Applicant Answer",
                idx: i + 1,
                question: q.question,
                answer: v === undefined || v === null ? "" : String(v),
            };
        });
        setTable("answers", rows);
    }

    function drawQuestions() {
        var $box = holder("answers", "seminary-application-questions");
        if (!$box) return;
        if (!questions.length) {
            $('<p class="text-muted"></p>').text(__("This program has no further questions.")).appendTo($box);
            writeAnswers();
            return;
        }
        var group = null;
        questions.forEach(function (q) {
            if (q.group && q.group !== group) {
                group = q.group;
                $('<h4 class="mt-4 mb-2"></h4>').text(q.group).appendTo($box);
            }
            var spec = TYPES[q.answer_type] || TYPES["Short text"];
            var df = {
                fieldname: "q_" + q.question.replace(/[^A-Za-z0-9]/g, "_"),
                fieldtype: spec.fieldtype,
                label: q.label,
                reqd: q.required ? 1 : 0,
                description: q.help || "",
                options: spec.options || "",
                change: function () {
                    answers[q.question] = control.get_value();
                    writeAnswers();
                },
            };
            if (q.answer_type === "Select") {
                df.options = [{ value: "", label: "" }].concat(q.choices || []);
            }
            var $slot = $("<div></div>").appendTo($box);
            var control = frappe.ui.form.make_control({ df: df, parent: $slot, render_input: true });
            control.refresh();
            if (answers[q.question] !== undefined) control.set_value(answers[q.question]);
        });
        writeAnswers();
    }

    function applyTables(tables) {
        TABLES.forEach(function (fieldname) {
            if (!fields[fieldname]) return;
            var t = tables[fieldname];
            wf.set_df_property(fieldname, "hidden", t ? 0 : 1);
            if (!t) {
                setTable(fieldname, []);
                return;
            }
            wf.set_df_property(fieldname, "label", t.label);
            wf.set_df_property(fieldname, "reqd", t.required ? 1 : 0);
            wf.set_df_property(
                fieldname,
                "description",
                [t.help, t.required ? __("Add at least one row.") : ""].filter(Boolean).join(" ")
            );
        });
    }

    // ---- agreements -------------------------------------------------------
    var agreements = [];
    var signed = {};

    function writeAgreements() {
        setTable(
            "agreements",
            agreements.map(function (a, i) {
                var s = signed[a.agreement_template] || {};
                return {
                    doctype: "Student Applicant Agreement",
                    idx: i + 1,
                    agreement_template: a.agreement_template,
                    agreed: s.agreed ? 1 : 0,
                    signer_name: s.signer_name || "",
                    signature: s.signature || "",
                };
            })
        );
    }

    function drawAgreements() {
        var $box = holder("agreements", "seminary-application-agreements");
        if (!$box) return;
        if (!agreements.length) {
            $('<p class="text-muted"></p>').text(__("This program has no agreements to sign.")).appendTo($box);
            writeAgreements();
            return;
        }
        agreements.forEach(function (a) {
            var s = (signed[a.agreement_template] = signed[a.agreement_template] || {});
            var $card = $('<section class="mb-5"></section>').appendTo($box);
            $('<h4 class="mb-2"></h4>').text(a.title).appendTo($card);
            if (a.instructions) $('<p class="text-muted"></p>').text(a.instructions).appendTo($card);
            $(
                '<div tabindex="0" style="padding:1rem;border:1px solid var(--border-color, #e0e0e0);' +
                    'border-radius:6px;max-height:320px;overflow:auto;margin-bottom:1rem;"></div>'
            )
                .attr("aria-label", a.title)
                .html(a.html)
                .appendTo($card);
            var parts = [
                { fieldname: "agreed", fieldtype: "Check", label: __("I have read this agreement and I agree") },
                { fieldname: "signer_name", fieldtype: "Data", label: __("Your full name"), reqd: 1 },
                { fieldname: "signature", fieldtype: "Signature", label: __("Signature"), reqd: 1 },
            ];
            parts.forEach(function (df) {
                var $slot = $("<div></div>").appendTo($card);
                var control = frappe.ui.form.make_control({
                    df: Object.assign({}, df, {
                        fieldname: df.fieldname + "_" + a.agreement_template.replace(/[^A-Za-z0-9]/g, "_"),
                        change: function () {
                            s[df.fieldname] = control.get_value();
                            writeAgreements();
                        },
                    }),
                    parent: $slot,
                    render_input: true,
                });
                control.refresh();
                if (s[df.fieldname]) control.set_value(s[df.fieldname]);
            });
        });
        writeAgreements();
    }

    function load(program) {
        if (!program) {
            questions = [];
            agreements = [];
            applyTables({});
            drawQuestions();
            drawAgreements();
            return;
        }
        if (fields.answers) {
            frappe
                .call({
                    method: "seminary.seminary.application_form.application_questions",
                    args: { program: program },
                })
                .then(function (r) {
                    var data = (r && r.message) || {};
                    questions = data.questions || [];
                    applyTables(data.tables || {});
                    drawQuestions();
                });
        }
        if (fields.agreements) {
            frappe
                .call({
                    method: "seminary.seminary.requirements.application_agreements",
                    args: { program: program },
                })
                .then(function (r) {
                    agreements = (r && r.message) || [];
                    drawAgreements();
                });
        }
    }

    if (wf.on) {
        wf.on("program", function (field, value) {
            load(value);
        });
    }
    load(wf.doc && wf.doc.program);
});

// The application fee (decisions/113): the fee code and the waiver request
// are shown only for a program that charges a fee, and the request only when
// the program accepts them. The server checks both again on save.
frappe.ready(function () {
    if (!window.frappe || !frappe.web_form) return;
    var wf = frappe.web_form;
    var fields = wf.fields_dict || {};
    if (!fields.fee_waiver_code && !fields.fee_waiver_requested) return;

    function hide(fieldname, hidden) {
        if (!fields[fieldname]) return;
        try {
            wf.set_df_property(fieldname, "hidden", hidden ? 1 : 0);
        } catch (e) {
            fields[fieldname].$wrapper && fields[fieldname].$wrapper.toggle(!hidden);
        }
    }

    function note(text) {
        var field = fields.fee_waiver_code || fields.fee_waiver_requested;
        if (!field || !field.$wrapper) return;
        var $note = field.$wrapper.prev(".seminary-fee-window");
        if (!$note.length) {
            $note = $('<p class="seminary-fee-window text-muted"></p>');
            field.$wrapper.before($note);
        }
        $note.text(text || "").toggle(!!text);
    }

    function apply(options) {
        var hasFee = !!(options && options.has_fee);
        var requests = hasFee && !!options.allow_requests;
        hide("fee_tab", !hasFee);
        hide("fee_waiver_code", !hasFee);
        hide("fee_waiver_requested", !requests);
        hide("fee_waiver_reason", !requests || !wf.doc.fee_waiver_requested);
        if (!requests && wf.doc.fee_waiver_requested) wf.set_value("fee_waiver_requested", 0);
        note(hasFee ? options.window : "");
    }

    function load(program) {
        if (!program) return apply(null);
        frappe
            .call({
                method: "seminary.seminary.application_fee.form_options",
                args: { program: program },
            })
            .then(function (r) {
                apply(r && r.message);
            });
    }

    if (wf.on) {
        wf.on("program", function (field, value) {
            load(value);
        });
        wf.on("fee_waiver_requested", function (field, value) {
            hide("fee_waiver_reason", !value);
        });
    }
    apply(null);
    load(wf.doc && wf.doc.program);
});
