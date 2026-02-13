

const original_setup = frappe.ui.form.Form.prototype.setup;
frappe.ui.form.Form.prototype.setup = function() {
    original_setup.call(this);
    
    const frm = this;
    (frm.meta.fields || []).forEach(df => {
        if (df.fieldtype === 'Link' && df.options === 'Gender') {
            frm.set_query(df.fieldname, () => ({
                filters: { 'name': ['in', [_('Male'), _('Female')]] }
            }));
        }
    });
};