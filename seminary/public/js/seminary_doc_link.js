// seminary_doc_link.js — form-view "Documentation Link" Help icon
//
// Frappe gap (see docs/frappe-workarounds.md #5): a DocType's built-in
// `documentation` property (label "Documentation Link") is rendered by Frappe
// ONLY in the list-view empty-state ("Need Help?"). Nothing in form/ surfaces
// it. This shared fix reads `frm.meta.documentation` and, when set, adds a Help
// icon to the form header that opens the URL in a new tab.
//
// Fully generic: no backend call, no Seminary Help Entry dependency. The doc
// link lives natively on the doctype (set its "Documentation Link" in the
// DocType editor / JSON), so no per-doctype setup is needed beyond that.
//
// Bound to the `form-refresh` event rather than wrapping Form.prototype.refresh:
// render_form() runs its steps via frappe.run_serially(), and refresh_header()
// (which calls page.clear_icons()) runs one step BEFORE the form-refresh
// trigger. Adding the icon during the refresh wrap would race ahead of
// clear_icons() and get wiped; the event fires after it, so the icon survives.
//
// Remove when Frappe renders `meta.documentation` in form view: delete this
// file and its `app_include_js` entry in hooks.py, then `bench build`.

$(document).on('form-refresh', function (e, frm) {
	seminary_add_doc_link_icon(frm);
});

function seminary_add_doc_link_icon(frm) {
	const url = frm.meta && frm.meta.documentation;

	// form-refresh can fire repeatedly — drop any prior icon before re-adding.
	frm.page.wrapper.find('.seminary-doc-help').remove();

	if (!url) {
		return;
	}

	// es-line-question is in the desk (espresso) icon sprite; lucide names
	// (e.g. circle-help) are not loaded in Desk and render an empty button.
	frm.page.add_action_icon(
		'es-line-question',
		function () {
			window.open(url, '_blank');
		},
		'seminary-doc-help',
		__('Documentation')
	);
}
