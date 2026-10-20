// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Signed Agreement', {
	refresh(frm) {
		// Shown sandboxed: the text is the school's template filled with the
		// signer's data, and nothing in it should run on the desk.
		const frame = document.createElement('iframe');
		frame.setAttribute('sandbox', '');
		frame.style.cssText = 'width:100%;height:480px;border:1px solid var(--border-color);border-radius:6px;background:#fff';
		frame.srcdoc = frm.doc.rendered_html || '';
		frm.get_field('text_preview').$wrapper.empty().append(frame);
		const pdf = frm.doc.final_pdf || frm.doc.pdf;
		if (pdf) {
			frm.add_custom_button(__('Open PDF'), () => window.open(pdf, '_blank'));
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Awaiting Countersignature') {
			frm.add_custom_button(__('Countersign'), () => {
				frappe.prompt(
					[
						{ fieldname: 'text', fieldtype: 'HTML',
						  options: `<div class="text-muted small mb-3">${__('Read the signed text below the form before countersigning.')}</div>` },
						{ fieldname: 'signer_name', fieldtype: 'Data', label: __('Your full name'), reqd: 1,
						  default: frappe.session.user_fullname },
						{ fieldname: 'signature', fieldtype: 'Signature', label: __('Draw your signature (optional)') },
					],
					(v) => frappe.call({
						method: 'seminary.seminary.requirements.countersign',
						args: { signed_agreement: frm.doc.name, signer_name: v.signer_name, signature: v.signature || null },
						freeze: true,
					}).then(() => frm.reload_doc()),
					__('Countersign agreement'),
					__('Countersign'),
				);
			}).addClass('btn-primary');
		}
	},
});
