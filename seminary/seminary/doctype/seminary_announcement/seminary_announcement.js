frappe.ui.form.on("Seminary Announcement", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Preview Recipients"), () => preview_recipients(frm));
        }
        render_status_indicator(frm);
    },

    onload(frm) {
        if (frm.is_new() && !frm.doc.academic_term) {
            frappe.db.get_list("Academic Term", {
                filters: { iscurrent_acterm: 1 },
                fields: ["name"],
                limit: 1,
            }).then((rows) => {
                if (rows && rows.length) {
                    frm.set_value("academic_term", rows[0].name);
                }
            });
        }
    },

    custom_filter_doctype(frm) {
        if (!frm.doc.custom_filter_doctype) {
            frm.set_value("custom_filters", "");
            frm.set_value("custom_email_field", "");
        } else if (!frm.doc.custom_email_field) {
            frm.set_value("custom_email_field", "email");
        }
    },
});

function preview_recipients(frm) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the draft first, then preview."));
        return;
    }
    frappe.call({
        method: "seminary.seminary.api.preview_announcement_recipients",
        args: { name: frm.doc.name },
        freeze: true,
        freeze_message: __("Resolving recipients..."),
        callback: (r) => {
            if (!r.message) return;
            const { total, sample } = r.message;
            const rows = sample
                .map((row) => `<tr><td>${frappe.utils.escape_html(row.party_type)}</td>`
                    + `<td>${frappe.utils.escape_html(row.party_name || "")}</td>`
                    + `<td>${frappe.utils.escape_html(row.email)}</td></tr>`)
                .join("");
            const msg = `
                <p><strong>${total}</strong> ${__("recipient(s) will receive this announcement.")}</p>
                <table class="table table-bordered" style="margin-top:10px;">
                    <thead><tr>
                        <th>${__("Type")}</th><th>${__("Name")}</th><th>${__("Email")}</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
                ${total > sample.length
                    ? `<p class="text-muted">${__("Showing first {0} of {1}.", [sample.length, total])}</p>`
                    : ""}
            `;
            frappe.msgprint({ title: __("Preview"), message: msg, indicator: "blue" });
        },
    });
}

function render_status_indicator(frm) {
    const map = {
        Draft: ["gray", __("Draft")],
        Queued: ["orange", __("Queued")],
        Sending: ["blue", __("Sending")],
        Sent: ["green", __("Sent")],
        Failed: ["red", __("Failed")],
    };
    const entry = map[frm.doc.status];
    if (entry) frm.page.set_indicator(entry[1], entry[0]);
}
