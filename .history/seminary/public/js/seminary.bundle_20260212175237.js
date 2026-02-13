src="https://kit.fontawesome.com/01787f5cbf.js", crossorigin="anonymous"

frappe.ui.form.on('Customer', {
	onload(frm) {
		frm.set_query('gender', () => ({
            filters: { name: ['in', ['Male', 'Female']] }// your code here
		}));
	}
})