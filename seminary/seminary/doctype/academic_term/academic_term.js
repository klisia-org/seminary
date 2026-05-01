// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Academic Term', {

    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Configure Withdrawal Dates'), function() {
                frappe.set_route('List', 'Term Withdrawal Rules', {
                    academic_term: frm.doc.name
                });
            }, __('Actions'));
        }

        render_year_context(frm);
    },

    academic_year: function(frm) {
        render_year_context(frm);
    },

    after_save: function(frm) {
        frappe.call({
            method: "seminary.seminary.api.first_term",
            args: {
                doc: frm.doc.name
            },
            callback: function() {
                frm.reload_doc();
            }
        });
    }

});

function render_year_context(frm) {
    if (!frm.doc) {
        return;
    }
    const field = frm.get_field("year_context_html");
    if (!field) {
        return;
    }

    if (!frm.doc.academic_year) {
        field.html(`<div class="text-muted">${__("Select an Academic Year to see its date range and other terms.")}</div>`);
        return;
    }

    field.html(`<div class="text-muted">${__("Loading...")}</div>`);

    frappe.call({
        method: "seminary.seminary.doctype.academic_term.academic_term.get_academic_year_context",
        args: {
            academic_year: frm.doc.academic_year,
            exclude_term: frm.is_new() ? null : frm.doc.name
        },
        callback: function(r) {
            if (!r.message || !r.message.year) {
                field.html(`<div class="text-muted">${__("No data available.")}</div>`);
                return;
            }
            const { year, terms } = r.message;
            const fmt = frappe.datetime.str_to_user;

            let html = `<div>
                <strong>${__("Academic Year")}:</strong>
                ${fmt(year.year_start_date)} &mdash; ${fmt(year.year_end_date)}
            </div>`;

            if (terms && terms.length) {
                const rows = terms.map(t => `
                    <tr>
                        <td>${frappe.utils.escape_html(t.term_name || t.name)}</td>
                        <td>${t.term_start_date ? fmt(t.term_start_date) : ""}</td>
                        <td>${t.term_end_date ? fmt(t.term_end_date) : ""}</td>
                    </tr>
                `).join("");

                html += `
                    <div style="margin-top: 8px;">
                        <strong>${__("Other Terms in this Year")}:</strong>
                        <table class="table table-sm" style="margin-top: 4px;">
                            <thead>
                                <tr>
                                    <th>${__("Term")}</th>
                                    <th>${__("Start")}</th>
                                    <th>${__("End")}</th>
                                </tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                `;
            } else {
                html += `<div style="margin-top: 4px;" class="text-muted">
                    ${__("No other terms exist for this academic year yet.")}
                </div>`;
            }

            field.html(html);
        }
    });
}
