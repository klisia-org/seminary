// Copyright (c) 2025, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarships", {
    onload: function(frm) {
        // Default the cost center from Seminary Settings; the registrar can override
        // to budget this scholarship separately (see ERPNext Budget on the cost center).
        if (frm.is_new() && !frm.doc.cost_center) {
            frappe.db.get_single_value("Seminary Settings", "scholarship_cc").then((cc) => {
                if (cc && !frm.doc.cost_center) {
                    frm.set_value("cost_center", cc);
                }
            });
        }
    },
    program: function(frm) {
        // Populate the child table sch_discounts with the Programs fees of the selected Program
        frappe.call({
            method: "seminary.seminary.api.get_program_fees",
            args: {
                program: frm.doc.program
            },
            callback: function(r) {
                if (r.message) {
                    frm.clear_table("sch_discounts");
                    r.message.forEach(fee => {
                        let row = frm.add_child("sch_discounts");
                        row.pgm_fee = fee.pgm_feecategory || fee;
                        row.mode = "Percent";
                    });
                    frm.refresh_field("sch_discounts");
                }
            }
        });
    }
});