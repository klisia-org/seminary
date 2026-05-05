frappe.pages['program-pricing'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Program Pricing'),
		single_column: true,
	});

	const $body = $(page.body).addClass('program-pricing-page');
	$body.html(`<div class="text-muted" style="padding: 1rem;">${__('Loading…')}</div>`);

	let cachedHtml = '';

	page.set_primary_action(__('Print'), () => printReport(cachedHtml), 'octicon octicon-printer');

	frappe.call({
		method: 'seminary.seminary.api.get_program_pricing_html',
		callback: (r) => {
			cachedHtml = r.message || '';
			$body.html(cachedHtml || `<div class="text-muted">${__('No pricing data.')}</div>`);
		},
	});
};

function printReport(html) {
	if (!html) {
		frappe.show_alert({ message: __('Nothing to print yet.'), indicator: 'orange' });
		return;
	}
	const w = window.open('', '_blank');
	if (!w) {
		frappe.show_alert({ message: __('Popup blocked — allow popups to print.'), indicator: 'red' });
		return;
	}
	w.document.write(
		`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${__('Program Pricing')}</title>` +
		`<style>body{font-family:sans-serif;margin:1rem;}</style>` +
		`</head><body>${html}</body></html>`
	);
	w.document.close();
	w.focus();
	w.onload = () => { w.print(); };
}
