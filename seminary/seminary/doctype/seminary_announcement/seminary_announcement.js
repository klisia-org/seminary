const RICH_CHANNELS = ["Email", "In-App", "Print"];
const SHORT_LIMIT = 4096;

frappe.ui.form.on("Seminary Announcement", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Preview Recipients"), () => preview_recipients(frm));
        }
        render_status_indicator(frm);
        apply_channel_field_logic(frm);
        bind_short_message_counter(frm);

        if (frm.doc.docstatus !== 2 && selected_channels(frm).includes("Print")) {
            if (frm.doc.docstatus === 1) {
                // Submitted: the official, all-recipient letters to print and mail.
                frm.add_custom_button(__("Print Letters (PDF)"), () => generate_letters(frm));
            } else {
                // Draft: a quick single-recipient preview.
                frm.add_custom_button(__("Letter Preview (PDF)"), () => generate_letter(frm));
            }
            if (frm.doc.print_mailing_labels) {
                frm.add_custom_button(__("Mailing Labels (PDF)"), () => generate_labels(frm));
            }
        }
    },

    onload(frm) {
        // Only offer channels with an enabled provider account. `channels` is a
        // Table MultiSelect whose control extends ControlLink and sits on the
        // parent form, so it has no `.grid` — use the parent-field set_query
        // signature (the child-table signature crashes on `.grid.get_field`).
        frm.set_query("channels", () => ({ filters: { enabled: 1 } }));

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

    channels(frm) {
        apply_channel_field_logic(frm);
    },

    short_message(frm) {
        update_short_counter(frm);
    },

    print_mailing_labels(frm) {
        frm.refresh();
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

function selected_channels(frm) {
    // Mirror the server default: no channels selected = Email + In-App.
    const chosen = (frm.doc.channels || []).map((r) => r.channel).filter(Boolean);
    return chosen.length ? chosen : ["Email", "In-App"];
}

function apply_channel_field_logic(frm) {
    const sel = selected_channels(frm);
    const has_rich = sel.some((c) => RICH_CHANNELS.includes(c));
    const has_short = sel.some((c) => !RICH_CHANNELS.includes(c));
    frm.toggle_display("message", has_rich);
    frm.toggle_reqd("message", has_rich);
    frm.toggle_display("short_message", has_short);
    // Short Message is only mandatory when there is no rich Message to derive it from.
    frm.toggle_reqd("short_message", has_short && !has_rich);
    frm.toggle_display("print_options_section", sel.includes("Print"));
    frm.toggle_display("voice_audio", sel.includes("Voice"));
    update_short_counter(frm);
}

function generate_letter(frm) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save first, then preview the letter."));
        return;
    }
    frappe.call({
        method: "seminary.seminary.api.preview_announcement_letter",
        args: { name: frm.doc.name },
        freeze: true,
        freeze_message: __("Rendering letter..."),
        callback: (r) => {
            if (r.message && r.message.file_url) window.open(r.message.file_url, "_blank");
        },
    });
}

function generate_letters(frm) {
    frappe.call({
        method: "seminary.seminary.api.announcement_letters_pdf",
        args: { name: frm.doc.name },
        freeze: true,
        freeze_message: __("Building letters..."),
        callback: (r) => {
            if (r.message && r.message.file_url) {
                window.open(r.message.file_url, "_blank");
                frm.reload_doc();
            }
        },
    });
}

function generate_labels(frm) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save first, then generate labels."));
        return;
    }
    frappe.call({
        method: "seminary.seminary.api.generate_announcement_labels",
        args: { name: frm.doc.name },
        freeze: true,
        freeze_message: __("Building labels..."),
        callback: (r) => {
            if (!r.message) return;
            const { file_url, placed, omitted } = r.message;
            window.open(file_url, "_blank");
            let msg = __("{0} label(s) generated.", [placed]);
            if (omitted && omitted.length) {
                msg += "<br>" + __("No postal address for {0}:", [omitted.length])
                    + " " + frappe.utils.escape_html(omitted.slice(0, 20).join(", "))
                    + (omitted.length > 20 ? "…" : "");
            }
            frappe.msgprint({ title: __("Mailing Labels"), message: msg, indicator: "blue" });
        },
    });
}

function update_short_counter(frm) {
    const field = frm.fields_dict.short_message;
    if (!field) return;
    const len = (frm.doc.short_message || "").length;
    const over = len > SHORT_LIMIT;
    const note = over
        ? ` — ${__("over the {0} limit; longer text is split (SMS) or truncated (Telegram)", [SHORT_LIMIT])}`
        : "";
    frm.set_df_property(
        "short_message",
        "description",
        `${len}/${SHORT_LIMIT}${note}`
    );
}

function bind_short_message_counter(frm) {
    const field = frm.fields_dict.short_message;
    if (!field || !field.$input || field._counter_bound) return;
    field.$input.on("input", () => update_short_counter(frm));
    field._counter_bound = true;
}

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
            frappe.msgprint({
                title: __("Preview"),
                message: render_preview(r.message),
                indicator: r.message.unreachable ? "orange" : "blue",
            });
        },
    });
}

function render_preview(data) {
    const {
        total, reachable, unreachable, channels, channel_counts,
        fallback, fallback_count, sample,
    } = data;

    const channel_bits = (channels || [])
        .map((c) => `${frappe.utils.escape_html(c)} ${channel_counts[c] || 0}`)
        .join(" · ");
    const summary = `
        <p>
            <strong>${total}</strong> ${__("intended")} ·
            <span style="color:#2e7d32;font-weight:600;">${reachable} ${__("reachable")}</span>
            ${unreachable
                ? ` · <span style="color:#c0392b;font-weight:600;">${unreachable} ${__("unreachable")}</span>`
                : ""}
        </p>
        <p class="text-muted" style="margin-top:-6px;">
            ${__("On selected channels")}: ${channel_bits || __("none")}
            ${fallback && fallback_count
                ? ` &nbsp;·&nbsp; ${__("via Email/In-App fallback")}: ${fallback_count}`
                : ""}
        </p>`;

    const cell = (row) => {
        if (row.reachable && row.via_fallback) {
            return `<span style="color:#2e7d32;" title="${__("Falls back to Email/In-App")}">✓ ${__("fallback")}</span>`;
        }
        if (row.reachable) {
            return `<span style="color:#2e7d32;">✓</span>`;
        }
        const why = row.reason === "opted_out"
            ? __("opted out")
            : row.reason === "no_address"
                ? __("no address")
                : "";
        return `<span style="color:#c0392b;" title="${why}">✗ ${why}</span>`;
    };

    const rows = (sample || [])
        .map((row) => `<tr>`
            + `<td>${frappe.utils.escape_html(row.party_type)}</td>`
            + `<td>${frappe.utils.escape_html(row.party_name || "")}</td>`
            + `<td>${frappe.utils.escape_html(row.email)}</td>`
            + `<td>${cell(row)}</td></tr>`)
        .join("");

    return `
        ${summary}
        <table class="table table-bordered" style="margin-top:10px;">
            <thead><tr>
                <th>${__("Type")}</th><th>${__("Name")}</th>
                <th>${__("Email")}</th><th>${__("Reachable")}</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>
        ${total > (sample || []).length
            ? `<p class="text-muted">${__("Showing first {0} of {1}.", [sample.length, total])}</p>`
            : ""}`;
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
