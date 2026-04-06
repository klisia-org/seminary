// seminary_help.js — Global help button for Desk forms
// Adds a "Help Docs" button when a Seminary Help Entry exists for the current doctype

$(document).ready(function () {
	const _origRefresh = frappe.ui.form.Form.prototype.refresh;
	frappe.ui.form.Form.prototype.refresh = function (...args) {
		const result = _origRefresh.apply(this, args);
		seminary_add_help_button(this);
		return result;
	};
});

function seminary_add_help_button(form) {
	// Avoid duplicate buttons on re-refresh
	form.page.remove_inner_button(__('Help Docs'));

	frappe.call({
		method: 'seminary.seminary.doctype.seminary_help_entry.seminary_help_entry.get_help_entry',
		args: { document_type: form.doctype },
		async: true,
		callback: function (r) {
			if (r.message) {
				form.page.add_inner_button(__('Help Docs'), function () {
					window.open(r.message.mkdocs_url, '_blank');
				});
			}
		},
	});
}
