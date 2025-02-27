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
                        frm.save();
                        frm.refresh();
                    })
                    .catch(e => {
                        frappe.msgprint("Error creating Sales Invoice(s)!");
                    });
            }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"}); 
            console.log("Sales Invoice button added");
        }

        frm.add_custom_button("Add Scholarship", function() {
            console.log("Calling add_scholarship");
            frm.call('add_scholarship')
                .then(r => {
                    console.log("Add scholarship called");
                })
                .catch(e => {
                    console.log("Error calling add_scholarship:", e);
                });
        }).css({"color":"white", "background": "#0d3049", "font-weight": "700", "border-radius": "5px", "padding": "5px 10px", "margin-right": "10px"});
        console.log("Add Scholarship button added");
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
        console.log("Calling seminary.seminary.api.add_scholarship with doc name:", frm.doc.name);
        frm.call('add_scholarship', frm.doc.name)
            .then(r => {
                console.log("add_scholarship called successfully");
            })
            .catch(e => {
                console.log("Error calling add_scholarship:", e);
            });
    },

    onload(frm) {
        frm.set_query("scholarship", "seminary.seminary.api.get_scholarships");
     
                
           
        
                    
    }
               
      
    
});