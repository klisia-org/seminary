frappe.pages['registrar-hub'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Registrar Hub',
		single_column: true
	});

	page.set_primary_action(__('Advance Students'), () => advance_students(), 'octicon octicon-arrow-right');
	function advance_students() {
		frappe.confirm(
			__("Advance all active students to the next term? Confirm that grades for the ending term are finalized first."),
			() => {
				frappe.call({
					method: 'seminary.seminary.api.roll_students',
					freeze: true,
					freeze_message: __('Advancing students...'),
					callback: (r) => {
						frappe.show_alert({ message: r.message || __('Done'), indicator: 'green' });
					}
				});
			}
		);
	}

	page.set_secondary_action(__('Regenerate Current-Term Invoices'), () => regen_nat(), 'octicon octicon-sync');
	function regen_nat() {
		frappe.confirm(
			__("Clear the current term's billing flag and regenerate its New-Academic-Term invoices? Duplicates are prevented by the seminary_trigger check."),
			() => {
				frappe.call({
					method: 'seminary.seminary.api.regenerate_current_term_invoices',
					freeze: true,
					freeze_message: __('Regenerating invoices...'),
					callback: (r) => {
						const res = r.message || {};
						frappe.show_alert({
							message: __('Created {0}, skipped {1}, failed {2}.', [
								res.created || 0, res.skipped || 0, res.failed || 0
							]),
							indicator: res.failed ? 'orange' : 'green',
						});
					}
				});
			}
		);
	}
};
