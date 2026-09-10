// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

// The tax-ID field on any record that carries one (ADR 071): Person, Student
// Applicant and Partner Organization, on the Desk and on the public
// application form.
//
// Nothing in this file knows what a CPF is. It fetches the rule for whatever
// country the record names and applies it — label, mask, shape — so adding a
// country is an entry in `tax_ids.py` and no change here at all. Check digits
// are an algorithm rather than a pattern, so they stay on the server and the
// blur handler asks; the shape check is instant and offline, which is what
// catches the common mistake while someone is still typing.

(function () {
	const seminary = (window.seminary = window.seminary || {});

	//: One fetch per country/subject for the life of the page.
	const CACHE = {};

	function ruleFor(country, subject) {
		const key = (country || "") + "|" + (subject || "both");
		if (!CACHE[key]) {
			CACHE[key] = frappe
				.call({
					method: "seminary.seminary.tax_ids.get_tax_id_rule",
					args: { country: country || "", subject: subject || "both" },
				})
				.then((r) => r.message || { configured: false })
				.catch(() => ({ configured: false }));
		}
		return CACHE[key];
	}

	function clean(value, rule) {
		if (!value) return "";
		if (!rule || !rule.configured) return String(value).trim();
		return String(value).replace(new RegExp(rule.clean, "g"), "");
	}

	/**
	 * The form a part-typed value is heading towards: the shortest one that
	 * could still hold it, so a Brazilian number masks as a CPF until the
	 * twelfth digit and as a CNPJ after it.
	 */
	function formFor(cleaned, rule) {
		if (!rule || !rule.configured || !rule.forms.length) return null;
		const byLength = rule.forms
			.slice()
			.sort((a, b) => (a.mask || "").length - (b.mask || "").length);
		return (
			byLength.find((f) => (f.mask || "").split("#").length - 1 >= cleaned.length) ||
			byLength[byLength.length - 1]
		);
	}

	function mask(cleaned, form) {
		if (!form || !form.mask) return cleaned;
		let out = "";
		let i = 0;
		for (const char of form.mask) {
			if (char === "#") {
				if (i >= cleaned.length) break;
				out += cleaned[i++];
			} else if (i < cleaned.length) {
				out += char;
			}
		}
		return out;
	}

	/** Does the cleaned value match any form the country accepts? */
	function matches(cleaned, rule) {
		if (!rule || !rule.configured) return true;
		return rule.forms.some((f) => new RegExp(f.pattern).test(cleaned));
	}

	seminary.formatTaxId = function (value, rule) {
		const cleaned = clean(value, rule);
		return mask(cleaned, formFor(cleaned, rule));
	};

	/**
	 * Ask the server whether the check digits hold. Resolves to null when the
	 * value is fine, or to a sentence saying what is wrong.
	 */
	function checkOnServer(value, country, subject) {
		return frappe
			.call({
				method: "seminary.seminary.tax_ids.check_tax_id",
				args: { value: value, country: country || "", subject: subject || "both" },
			})
			.then((r) => ((r.message || {}).ok ? null : (r.message || {}).message))
			// An unreachable endpoint must not block typing; `validate()` on the
			// server is still the thing that refuses a save.
			.catch(() => null);
	}

	/**
	 * Wire a Desk form's tax-ID field.
	 *
	 * @param {object} frm
	 * @param {object} [opts]
	 * @param {string} [opts.fieldname]        defaults to `tax_id`
	 * @param {string[]} [opts.country_fields] which Link fields decide the rule,
	 *   most authoritative first: `["nationality", "mailing_country"]` on a
	 *   Person, `["country"]` on an organization. Mirrors `COUNTRY_FIELDS`.
	 * @param {string} [opts.subject]          `person` or `organization`
	 */
	seminary.bindTaxIdField = function (frm, opts) {
		opts = opts || {};
		const fieldname = opts.fieldname || "tax_id";
		const country_fields = opts.country_fields || ["country"];
		const field = frm.get_field(fieldname);
		if (!field || !field.$input) return;

		const country = country_fields.map((f) => frm.doc[f]).find(Boolean) || "";

		ruleFor(country, opts.subject).then((rule) => {
			// The field calls itself whatever this country calls it, so nobody
			// has to guess which of their numbers is wanted.
			if (rule.configured) {
				frm.set_df_property(fieldname, "label", rule.label);
				if (rule.note) frm.set_df_property(fieldname, "description", rule.note);
				const form = rule.forms[0];
				if (form && form.example) {
					field.$input.attr("placeholder", form.example);
				}
			}

			const input = field.$input;
			input.off(".taxid");

			input.on("input.taxid", function () {
				if (!rule.configured) return;
				const cleaned = clean(this.value, rule);
				this.value = mask(cleaned, formFor(cleaned, rule));
			});

			input.on("blur.taxid", function () {
				const value = this.value;
				if (!value || !rule.configured) return;
				const cleaned = clean(value, rule);
				if (!matches(cleaned, rule)) {
					const names = rule.forms.map((f) => f.name).join(" / ");
					const examples = rule.forms.map((f) => f.example).join(__(" or "));
					frappe.show_alert({
						message: __("That does not look like a {0}. For example: {1}.", [
							names,
							examples,
						]),
						indicator: "orange",
					});
					return;
				}
				checkOnServer(value, country, opts.subject).then((problem) => {
					if (problem) frappe.show_alert({ message: problem, indicator: "orange" });
				});
			});
		});
	};

	/**
	 * Wire a plain input — the public application form, which renders after
	 * `frappe.ready` and has no `frm`.
	 *
	 * @param {HTMLElement} input
	 * @param {function(): string} getCountry  read the country at the moment of
	 *   use, not at bind time: the applicant picks their nationality after this
	 *   runs.
	 * @param {object} [opts]
	 */
	seminary.bindTaxIdInput = function (input, getCountry, opts) {
		opts = opts || {};
		if (!input) return null;
		// Binding twice must re-read the country rather than do nothing: the
		// caller re-invokes this when the applicant changes their nationality.
		if (input._taxIdRefresh) return input._taxIdRefresh();

		let current = { configured: false };

		function refresh() {
			return ruleFor(getCountry(), opts.subject).then((rule) => {
				current = rule;
				input.setCustomValidity("");
				if (rule.configured) {
					const form = rule.forms[0];
					if (form && form.example) input.placeholder = form.example;
					if (rule.max_length) input.setAttribute("maxlength", rule.max_length);
					// Re-mask whatever is already typed under the new country.
					if (input.value) input.value = seminary.formatTaxId(input.value, rule);
				} else {
					input.placeholder = "";
					input.removeAttribute("maxlength");
				}
				return rule;
			});
		}

		input._taxIdRefresh = refresh;

		input.addEventListener("input", function () {
			if (!current.configured) return;
			const cleaned = clean(input.value, current);
			input.value = mask(cleaned, formFor(cleaned, current));
			input.setCustomValidity("");
		});

		input.addEventListener("blur", function () {
			if (!input.value || !current.configured) return;
			const cleaned = clean(input.value, current);
			if (!matches(cleaned, current)) {
				const names = current.forms.map((f) => f.name).join(" / ");
				input.setCustomValidity(
					__("That does not look like a {0}.", [names])
				);
				input.reportValidity();
				return;
			}
			checkOnServer(input.value, getCountry(), opts.subject).then((problem) => {
				input.setCustomValidity(problem || "");
				if (problem) input.reportValidity();
			});
		});

		return refresh();
	};
})();
