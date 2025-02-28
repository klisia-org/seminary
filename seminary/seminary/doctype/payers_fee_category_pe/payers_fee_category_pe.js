// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payers Fee Category PE", {
    refresh(frm) {
        if (!frm.doc.si_created) {
            frm.add_custom_button("Create Sales Invoice(s)", function() {
                console.log("Calling get_inv_data_pe");
                frm.call('get_inv_data_pe')
                    .then(r => {
                        frm.set_value("si_created", 1);
                        frm.save()
                            .then(() => {
                                frm.refresh();
                            });
                    })
                    .catch(e => {
                        frappe.msgprint("Error creating Sales Invoice(s)!");
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

        console.log("Calling add_scholarship automatically after save");
        frm.call('add_scholarship')
            .then(r => {
                console.log("add_scholarship called successfully");
                frm.save()
                    .then(() => {
                        frm.reload_doc(); // Reload the form after saving
                    }); 
            })
            .catch(e => {
                console.log("Error calling add_scholarship:", e);
            });
    },

    onload(frm) {
        frm.set_query("scholarship", function (doc, cdt, cdn) {
            let row = frappe.get_doc(cdt, cdn);
            return {
                query: "seminary.seminary.api.get_scholarships"
            };      
        });
    }
});