frappe.pages['registrar-hub'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Registrar Hub',
		single_column: true
	});
	let $btn = page.set_primary_action('Roll Ac. Term', () => roll_at(), 'octicon octicon-plus');
	function roll_at() {
		frappe.call('seminary.seminary.api.get_inv_data_nat').then(r => {
			if (r.message) {
				if (r.message === 'done') {
					frappe.msgprint('Invoices for New Academic Term were created');
				} else {
					frappe.msgprint('Rolling Academic Term is failed')};
				} else {
				frappe.msgprint('Rolling Academic Term is failed');
				}
			});
	};
	let $btn2 = page.set_secondary_action('Yearly Invoices', () => year_inv(), 'octicon octicon-sync');
	function year_inv() {
		frappe.call('seminary.seminary.api.get_inv_data_nayear').then(r => {
			if (r.message) {
				if (r.message === 'done') {
					frappe.msgprint('Invoices for New Academic Year were created');
				} else {
					frappe.msgprint('Yearly Invoices is failed')};
				} else {
				frappe.msgprint('Yearly Invoices is failed');
				}
			});
	};
	

}