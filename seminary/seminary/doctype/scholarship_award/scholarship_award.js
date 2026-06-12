// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Award", {
    scholarship: function (frm) {
        // Pull the template's discounts onto the award as a snapshot the first time.
        if (!frm.doc.scholarship || (frm.doc.award_terms || []).length) {
            return;
        }
        frappe.db.get_doc("Scholarships", frm.doc.scholarship).then((sch) => {
            frm.clear_table("award_terms");
            (sch.sch_discounts || []).forEach((d) => {
                if (!d.pgm_fee) return;
                const row = frm.add_child("award_terms");
                row.fee_category = d.pgm_fee;
                row.mode = d.mode || "Percent";
                row.value = d.value || d.discount_ || 0;
            });
            frm.refresh_field("award_terms");
        });
    },
});
