frappe.ui.form.on('Customer', {
	onload(frm) {
		frm.set_query('gender', () => ({
            filters: { custom_enabled: 1 }// your code here
		}));
	}
})