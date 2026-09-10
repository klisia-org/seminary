// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

// The Location surface of any record that carries an address (ADR 068 §7):
// the summary of what the last lookup concluded, the on-demand "Geocode Now"
// button, and the address typeahead wired into the form's fields.
//
// Shared rather than copied because two doctypes hold an address — Person and
// Partner Organization — and the half that differs between them is one field
// name (`mailing_country` vs `country`). A geocode is deliberately silent at
// save time, so this is the only place its outcome becomes visible; a second
// copy of it drifting out of step would mean one form quietly explaining a
// failure the other does not.

(function () {
	const seminary = (window.seminary = window.seminary || {});

	const STATE = () => ({
		Resolved: ["green", __("Located")],
		Unresolvable: ["orange", __("No such place")],
		Failed: ["red", __("Lookup failed")],
	});

	/**
	 * Render the Location summary into the form's `geo_html` field and add the
	 * on-demand lookup button.
	 *
	 * @param {object} frm
	 */
	seminary.renderLocationSummary = function (frm) {
		const field = frm.get_field("geo_html");
		if (!field) return; // permlevel: not everyone can see this section
		const wrapper = field.$wrapper;
		const esc = frappe.utils.escape_html;
		const d = frm.doc;

		const [colour, label] = STATE()[d.geo_status] || ["gray", __("Not looked up")];
		const when = d.geocoded_on ? frappe.datetime.str_to_user(d.geocoded_on) : null;
		const parts = [`<span class="indicator-pill ${colour}">${label}</span>`];

		if (d.geo_status === "Resolved") {
			const map = `https://www.openstreetmap.org/?mlat=${d.latitude}&mlon=${d.longitude}#map=16/${d.latitude}/${d.longitude}`;
			parts.push(
				`<a href="${map}" target="_blank" rel="noopener" style="margin-left:8px">
					${d.latitude}, ${d.longitude}</a>`,
				// A rooftop and a city centroid are not the same answer, and a
				// distance ranking built on the latter is noise.
				d.geocode_precision
					? `<span class="text-muted small" style="margin-left:8px">${esc(d.geocode_precision)}</span>`
					: ""
			);
		} else if (d.geo_status === "Unresolvable") {
			parts.push(
				`<span class="text-muted small" style="margin-left:8px">${__(
					"The provider knows of no such address. Correct the address above; it is not retried on its own."
				)}</span>`
			);
		} else if (d.geo_status === "Failed") {
			parts.push(
				`<span class="text-muted small" style="margin-left:8px">${__(
					"The provider could not be reached. The daily sweeper will try again."
				)}</span>`
			);
		}

		if (when) {
			parts.push(
				`<div class="text-muted small" style="margin-top:6px">${__("Last checked")}: ${esc(when)}</div>`
			);
		}

		wrapper.html(`<div style="padding:4px 0">${parts.join("")}</div>`);

		if (!frm.is_new()) {
			frm.add_custom_button(__("Geocode Now"), () => geocodeNow(frm), __("Location"));
		}
	};

	function geocodeNow(frm) {
		frappe.dom.freeze(__("Looking up the address..."));
		frappe
			.call("seminary.seminary.integrations.geocoding.geocode_now", {
				doctype: frm.doc.doctype,
				name: frm.doc.name,
			})
			.then((r) => {
				frappe.dom.unfreeze();
				const res = r.message || {};
				if (!res.ok) {
					frappe.msgprint({
						title: __("Not located"),
						indicator: "orange",
						message: frappe.utils.escape_html(res.message || ""),
					});
				}
				frm.reload_doc();
			})
			.catch(() => frappe.dom.unfreeze());
	}

	/**
	 * Wire the proxied address typeahead into a form's address fields.
	 *
	 * A typed address is what the geocoder has to work with, so normalising it
	 * at entry is cheaper than chasing Unresolvable statuses afterwards — and a
	 * picked address arrives already located, so it needs no separate geocode.
	 *
	 * @param {object} frm
	 * @param {object} [opts]
	 * @param {string} [opts.country_field]  which Link field holds the postal
	 *   country: `mailing_country` on a Person, `country` on an organization.
	 */
	seminary.bindFormAddressAutocomplete = function (frm, opts) {
		const country_field = (opts || {}).country_field || "country";
		const field = frm.get_field("address_line_1");
		if (!field || !field.$input || !seminary.attachAddressAutocomplete) return;

		seminary.attachAddressAutocomplete(field.$input.get(0), (address) => {
			const map = {
				address_line_1: address.address_line_1,
				address_line_2: address.address_line_2,
				city: address.city,
				state: address.state,
				pincode: address.pincode,
			};
			Object.entries(map).forEach(([fieldname, value]) => {
				if (value) frm.set_value(fieldname, value);
			});
			// Place Details returns the point, so the address is located the
			// moment it is chosen rather than on the next queued lookup.
			if (address.latitude) {
				frm.set_value("latitude", address.latitude);
				frm.set_value("longitude", address.longitude);
			}
			// Country is a Link, so only set it when Google's name is one we
			// hold — otherwise the field silently rejects it on save.
			if (address.country) {
				frappe.db.exists("Country", address.country).then((exists) => {
					if (exists) frm.set_value(country_field, address.country);
				});
			}
		});
	};
})();
