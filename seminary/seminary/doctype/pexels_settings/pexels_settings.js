// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pexels Settings", {
    refresh: function (frm) {
        frm.add_custom_button(__("Test Connection"), () => test_connection());
    },
});

function test_connection() {
    frappe.call({
        method: "seminary.seminary.integrations.pexels.test_connection",
        freeze: true,
        freeze_message: __("Testing Pexels connection..."),
        callback: (r) => {
            const res = r.message || {};
            if (res.ok) {
                frappe.show_alert({ message: res.message, indicator: "green" });
            } else {
                frappe.msgprint({
                    title: __("Pexels Connection Failed"),
                    message: res.message || __("Unknown error"),
                    indicator: "red",
                });
            }
        },
    });
}
