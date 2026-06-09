// Guard for an upstream Frappe bug in Script/Query Reports that declare a
// `ref_doctype`.
//
// QueryReport.update_masked_fields_in_columns (frappe query_report.js) reads
//   frappe.get_meta(this.report_doc?.ref_doctype).masked_fields
// and calls `.includes()` on it WITHOUT the `|| []` guard that every other
// call site in frappe uses (layout.js, list_view.js, form.js, formatters.js …).
// The lightweight client meta from frappe.get_meta does not carry
// `masked_fields` (only the full FormMeta does), so on sessions where that
// doctype's form/list wasn't opened it is `undefined`, and the report blanks
// with: "Uncaught (in promise) TypeError: Cannot read properties of undefined
// (reading 'includes')".
//
// We wrap the method once, app-wide, to backfill `masked_fields = []` on the
// cached meta before delegating to the original. Idempotent and harmless if
// frappe later ships the `|| []` fix.
// Upstream: https://github.com/frappe/frappe/issues/39813
// Registry: docs/frappe-workarounds.md (#1); rationale: project_frappe_quirks.md.
//
// report.bundle.js is lazy-loaded (only when a report opens), so we intercept
// the assignment of `frappe.views.QueryReport` via a property setter rather
// than polling for the class to appear.

(function () {
	function applyPatch(QueryReport) {
		if (!QueryReport || !QueryReport.prototype) return;
		const proto = QueryReport.prototype;
		if (proto.__seminary_masked_guard) return;

		const original = proto.update_masked_fields_in_columns;
		if (typeof original !== "function") return;

		proto.update_masked_fields_in_columns = function () {
			try {
				const ref = this.report_doc && this.report_doc.ref_doctype;
				const meta = ref && frappe.get_meta(ref);
				if (meta && meta.masked_fields === undefined) {
					meta.masked_fields = [];
				}
			} catch (e) {
				// Never let the guard itself break report rendering.
			}
			return original.apply(this, arguments);
		};
		proto.__seminary_masked_guard = true;
	}

	frappe.provide("frappe.views");

	if (frappe.views.QueryReport) {
		// Bundle already loaded (e.g. landed directly on a report route).
		applyPatch(frappe.views.QueryReport);
	} else {
		// Patch the moment frappe assigns the class when report.bundle loads.
		let _value;
		Object.defineProperty(frappe.views, "QueryReport", {
			configurable: true,
			enumerable: true,
			get: function () {
				return _value;
			},
			set: function (v) {
				_value = v;
				applyPatch(v);
			},
		});
	}
})();
