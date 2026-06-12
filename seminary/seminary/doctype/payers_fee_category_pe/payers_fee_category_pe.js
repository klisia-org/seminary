// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payers Fee Category PE", {
    refresh(frm) {
        if (!frm.doc.si_created) {
            frm.add_custom_button("Create Sales Invoice(s)", function() {
                frm.call('get_inv_data_pe')
                    .then(r => {
                        const res = r.message || {};
                        const created = res.created || 0;
                        const skipped = res.skipped || 0;
                        if (created === 0 && skipped === 0) {
                            // server should have thrown; defensive no-op
                            return;
                        }
                        frappe.show_alert({
                            message: __("Created {0}, skipped {1}.", [created, skipped]),
                            indicator: "green",
                        });
                        frm.set_value("si_created", 1);
                        frm.save().then(() => frm.refresh());
                    });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});
            console.log("Sales Invoice button added");
        }
    },

    after_save(frm) {
        console.log("Calling check_percentages");
        frm.call('check_percentages')
            .then(r => {
                console.log("Percentages checked");
                if (r.message) {
                    frappe.msgprint(r.message);
                }
            })
            .catch(e => {
                console.log("Error calling check_percentages:", e);
            });

    }
    // Scholarships are no longer baked into payer rows: they are granted as
    // Scholarship Awards and applied at invoice time (see billing.resolve_scholarship).
});