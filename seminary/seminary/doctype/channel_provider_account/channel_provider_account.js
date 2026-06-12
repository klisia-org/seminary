frappe.ui.form.on("Channel Provider Account", {
    refresh(frm) {
        if (frm.doc.provider === "telegram" && !frm.is_new()) {
            frm.add_custom_button(__("Register Telegram Webhook"), () => {
                frappe.prompt(
                    [
                        {
                            fieldname: "base_url",
                            fieldtype: "Data",
                            label: __("Public Base URL (optional)"),
                            description: __(
                                "Leave blank to use this site's URL. On dev, pass a public HTTPS tunnel (e.g. https://abc.ngrok.io)."
                            ),
                        },
                    ],
                    (values) => {
                        frappe.call({
                            method: "seminary.seminary.telegram_adapter.register_webhook",
                            args: { account: frm.doc.name, base_url: values.base_url },
                            freeze: true,
                            freeze_message: __("Registering with Telegram..."),
                            callback: (r) => {
                                if (r.message) {
                                    frappe.msgprint({
                                        title: __("Webhook registered"),
                                        message: r.message,
                                        indicator: "green",
                                    });
                                    frm.reload_doc();
                                }
                            },
                        });
                    },
                    __("Register Telegram Webhook"),
                    __("Register")
                );
            });
        }
    },
});
