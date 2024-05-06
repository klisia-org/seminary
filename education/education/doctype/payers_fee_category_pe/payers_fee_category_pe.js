// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payers Fee Category PE", {
refresh(frm) {
    if (!frm.doc.si_created) {
       
        frm.add_custom_button("Create Sales Invoice(s)", function() {
            frm.call('get_inv_data_pe')
                .then(r => {
                    frm.set_value("si_created", 1);
                    frm.save();
                    frm.refresh();
                })
                .catch(e => {
                    frappe.msgprint("Error creating Sales Invoice(s)!");
                });
        }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});}; 
    console.log("Sales Invoice button added")   
    },      
    

after_save(frm) {
    frm.call('check_percentages')
         console.log("Percentages checked")
        .then(r => {
            if (r.message) {
                frappe.msgprint(r.message);
            }
        });
    }  
});          