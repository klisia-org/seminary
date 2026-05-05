frappe.ready(function () {
    frappe.call("seminary.seminary.api.get_default_phone_country").then((r) => {
        const country = r.message;
        if (!country) return;
        frappe.sys_defaults = frappe.sys_defaults || {};
        frappe.sys_defaults.country = country;
        applyPhoneCountry(country);
    });

    frappe.call("seminary.seminary.api.active_term").then((r) => {
        if (r.message) {
            frappe.web_form.set_value("academic_term", r.message.academic_term);
            frappe.web_form.set_value("academic_year", r.message.academic_year);
        }
    });

    frappe.call("seminary.seminary.api.get_doctrinal_statement").then((r) => {
        const ds = r.message;
        if (!ds || !ds.body) return;
        whenFieldsReady(["ds2"], (fields) => {
            const f = fields[0];
            if (f && f.set_value) f.set_value(ds.body);
            else $('[data-fieldname="ds2"]').html(ds.body);
        });
    });

    // Shim handle_success so we can redirect using the saved doc's `data.name`.
    // The `after_save` event fires AFTER handle_success but doesn't carry data,
    // and `frappe.web_form.doc.name` is undefined for new docs (autoname runs
    // server-side). handle_success is the only hook that receives the response.
    if (frappe.web_form && typeof frappe.web_form.handle_success === "function") {
        const orig = frappe.web_form.handle_success.bind(frappe.web_form);
        frappe.web_form.handle_success = function (data) {
            if (frappe.web_form.is_new && data && data.name) {
                window.location.href =
                    "/applicant-payment?applicant=" + encodeURIComponent(data.name);
                return;
            }
            return orig(data);
        };
    }
});

function applyPhoneCountry(country) {
    const phoneFields = collectPhoneFieldNames();
    if (!phoneFields.length) return;
    whenFieldsReady(phoneFields, (fields) => {
        fields.forEach((field) => {
            if (field.country_code_picker && field.country_codes && field.country_codes[country]) {
                field.country_code_picker.on_change(country, false);
            }
        });
    });
}

function collectPhoneFieldNames() {
    const dict = (frappe.web_form && frappe.web_form.fields_dict) || {};
    return Object.keys(dict).filter((fn) => dict[fn] && dict[fn].df && dict[fn].df.fieldtype === "Phone");
}

function whenFieldsReady(fieldnames, callback) {
    let tries = 0;
    const interval = setInterval(() => {
        tries += 1;
        const dict = (frappe.web_form && frappe.web_form.fields_dict) || {};
        const fields = fieldnames.map((fn) => dict[fn]).filter(Boolean);
        if (fields.length === fieldnames.length) {
            clearInterval(interval);
            callback(fields);
        } else if (tries > 30) {
            clearInterval(interval);
        }
    }, 200);
}
