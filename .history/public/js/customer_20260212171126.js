console.log("Customer custom js called");

frappe.ui.form.on('Customer', {
    refresh: function(frm) {
        console.log('>>> SEMINARY ITEM JS LOADED <<<');
        frappe.show_alert({message: 'Seminary JS loaded!', indicator: 'green'});
    }
});
