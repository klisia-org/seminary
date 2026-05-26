// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bible API Settings", {
    refresh: function (frm) {
        frm.add_custom_button(__("Test Connection"), () => test_connection());
        frm.add_custom_button(__("Browse Bibles"), () => open_bible_browser());
    },
});

frappe.ui.form.on("Bible API Language Default", {
    bible_id: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.bible_id) {
            frappe.model.set_value(cdt, cdn, "bible_name", "");
            return;
        }
        frappe.call({
            method: "seminary.seminary.integrations.bible.get_bible_name",
            args: { bible_id: row.bible_id },
            callback: (r) => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "bible_name", r.message);
                }
            },
        });
    },
});

function test_connection() {
    frappe.call({
        method: "seminary.seminary.integrations.bible.test_connection",
        freeze: true,
        freeze_message: __("Testing Bible API connection..."),
        callback: (r) => {
            const res = r.message || {};
            if (res.ok) {
                frappe.show_alert({ message: res.message, indicator: "green" });
            } else {
                frappe.msgprint({
                    title: __("Bible API Connection Failed"),
                    message: res.message || __("Unknown error"),
                    indicator: "red",
                });
            }
        },
    });
}

function open_bible_browser() {
    const d = new frappe.ui.Dialog({
        title: __("Browse Bibles"),
        size: "large",
        fields: [
            {
                fieldtype: "Data",
                fieldname: "language",
                label: __("Language code (optional)"),
                description: __("e.g. eng, por, spa. Leave blank for all available Bibles."),
            },
            { fieldtype: "Button", fieldname: "fetch", label: __("Fetch") },
            { fieldtype: "HTML", fieldname: "results" },
        ],
    });

    const fetch = () => {
        const lang = d.get_value("language");
        const args = lang ? { language: lang } : {};
        d.fields_dict.results.$wrapper.html(
            `<p class="text-muted">${__("Loading…")}</p>`
        );
        frappe.call({
            method: "seminary.seminary.integrations.bible.list_bibles",
            args: args,
            callback: (r) => render_results(d, r.message),
            error: () => {
                d.fields_dict.results.$wrapper.html(
                    `<p class="text-danger">${__("Request failed. Check the connection.")}</p>`
                );
            },
        });
    };

    d.fields_dict.fetch.input.onclick = fetch;
    d.show();
    fetch();
}

function render_results(d, data) {
    const bibles = (data && data.data) || [];
    if (!bibles.length) {
        d.fields_dict.results.$wrapper.html(
            `<p class="text-muted">${__("No Bibles returned for this filter.")}</p>`
        );
        return;
    }
    const esc = (s) => frappe.utils.escape_html(s || "");
    const rows = bibles
        .map((b) => `
            <tr>
                <td>${esc(b.abbreviation)}</td>
                <td>${esc(b.name)}</td>
                <td>${esc(b.language && b.language.name)}</td>
                <td><code class="bible-id-cell" data-id="${esc(b.id)}" style="cursor:pointer">${esc(b.id)}</code></td>
            </tr>`)
        .join("");
    const html = `
        <div class="text-muted small mb-2">
            ${__("Click an ID to copy it. Paste into Default Bible ID or a Per-Language row.")}
        </div>
        <div style="max-height: 400px; overflow-y: auto;">
            <table class="table table-bordered table-hover">
                <thead><tr>
                    <th>${__("Abbr")}</th>
                    <th>${__("Name")}</th>
                    <th>${__("Language")}</th>
                    <th>${__("ID")}</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    d.fields_dict.results.$wrapper.html(html);
    d.fields_dict.results.$wrapper.find(".bible-id-cell").on("click", function () {
        const id = $(this).data("id");
        navigator.clipboard
            .writeText(id)
            .then(() =>
                frappe.show_alert({
                    message: __("Copied Bible ID: {0}", [id]),
                    indicator: "green",
                })
            )
            .catch(() =>
                frappe.show_alert({
                    message: __("Could not copy to clipboard"),
                    indicator: "red",
                })
            );
    });
}
