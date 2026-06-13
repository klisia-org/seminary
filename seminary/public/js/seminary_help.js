// seminary_help.js — inline "Local Notes" panel on Desk forms
//
// Surfaces a Seminary Help Entry's `local_notes` (institution-specific "how we
// do it here" guidance) as a collapsible panel at the top of the matching
// doctype's form. The external documentation link is handled separately by
// seminary_doc_link.js (it reads the doctype's own `documentation` meta), so
// this file is purely about local notes.
//
// We mount into `.form-layout` (above `.form-page` and the tab bar) rather than
// the dashboard: on tabbed forms the dashboard is prepended inside a tab wrapper
// (form.js make_form), which is display:none unless that tab is active — so a
// dashboard section renders with zero height on every doctype without an active
// dashboard tab. `.form-layout` is always visible. Styling lives in seminary.css.
//
// `local_notes` is admin-authored Text Editor HTML, rendered as-is — same trust
// level as any client script in this app.

// Per-doctype cache (incl. negative results) so we hit the backend at most once
// per doctype per session instead of on every form refresh.
// Future optimization: preload a {doctype: has_entry} map via extend_bootinfo
// to drop the call entirely.
const _seminary_help_cache = {};

$(document).ready(function () {
	const _origRefresh = frappe.ui.form.Form.prototype.refresh;
	frappe.ui.form.Form.prototype.refresh = function (...args) {
		const result = _origRefresh.apply(this, args);
		seminary_render_local_notes(this);
		return result;
	};
});

function seminary_render_local_notes(frm) {
	const doctype = frm.doctype;

	if (Object.prototype.hasOwnProperty.call(_seminary_help_cache, doctype)) {
		seminary_show_notes_section(frm, _seminary_help_cache[doctype]);
		return;
	}

	frappe.call({
		method: 'seminary.seminary.doctype.seminary_help_entry.seminary_help_entry.get_help_entry',
		args: { document_type: doctype },
		async: true,
		callback: function (r) {
			_seminary_help_cache[doctype] = r.message || null;
			seminary_show_notes_section(frm, _seminary_help_cache[doctype]);
		},
	});
}

function seminary_show_notes_section(frm, entry) {
	// Refresh fires repeatedly — drop any prior panel before re-adding.
	frm.layout.wrapper.find('.seminary-local-notes-panel').remove();

	if (!entry || !entry.local_notes) {
		return;
	}

	const $panel = $(`
		<div class="seminary-local-notes-panel">
			<div class="seminary-ln-head">
				<span class="seminary-ln-title">
					${frappe.utils.icon('es-line-book', 'sm')} ${__('Local Notes')}
				</span>
				<span class="seminary-ln-caret">${frappe.utils.icon('es-line-down', 'sm')}</span>
			</div>
			<div class="seminary-ln-body"></div>
		</div>
	`);
	// Set notes via .html() rather than template interpolation so the markup is
	// not re-parsed/escaped oddly inside the template literal.
	$panel.find('.seminary-ln-body').html(entry.local_notes);
	$panel.find('.seminary-ln-head').on('click', () => $panel.toggleClass('collapsed'));

	frm.layout.wrapper.prepend($panel);
}
