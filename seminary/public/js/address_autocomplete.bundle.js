// Copyright (c) 2026, Klisia and contributors
// For license information, please see license.txt

// Address autocomplete, proxied through this server (ADR 068 §7).
//
// A free-text address box produces exactly the malformed addresses that come
// back `Unresolvable` from the geocoder, so normalising at entry is cheaper
// than chasing them afterwards.
//
// **No Google script is loaded and no API key reaches the browser.** The
// obvious implementation — Google's own `PlaceAutocompleteElement` — requires
// the key in page source. That is Google's documented model and referrer
// restrictions are the intended mitigation, but it cannot work here: the
// `Vendor proxy` mode exists so a hosted school holds no Google account, so
// there would be no key of theirs to expose and no honest way to expose ours.
// Predictions and place details come from whitelisted endpoints instead, which
// also means every call is logged and counted like the geocoder's.
//
// Frappe's own Geolocation Settings (Geoapify / Nomatim / HERE) is left alone:
// a second provider account for the same job, and its providers return address
// components without coordinates.

(function () {
	const seminary = (window.seminary = window.seminary || {});
	const DEBOUNCE_MS = 250;
	const MIN_CHARS = 3;

	// Groups the keystrokes and the details call that follows into one billable
	// session. Without it every keystroke is charged separately.
	function newSessionToken() {
		if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
		return "s-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
	}

	function buildDropdown(input) {
		const list = document.createElement("div");
		list.className = "seminary-address-suggestions";
		Object.assign(list.style, {
			position: "absolute",
			zIndex: "1000",
			background: "var(--fg-color, #fff)",
			border: "1px solid var(--border-color, #d1d8dd)",
			borderRadius: "6px",
			boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
			maxHeight: "240px",
			overflowY: "auto",
			display: "none",
			minWidth: input.offsetWidth + "px",
		});
		document.body.appendChild(list);
		return list;
	}

	function place(list, input) {
		const box = input.getBoundingClientRect();
		list.style.left = box.left + window.scrollX + "px";
		list.style.top = box.bottom + window.scrollY + 2 + "px";
		list.style.minWidth = box.width + "px";
	}

	/**
	 * Attach a proxied address typeahead to an input.
	 *
	 * @param {HTMLElement} input   the address-line-1 input
	 * @param {Function} onPlace    called with the resolved address object
	 */
	seminary.attachAddressAutocomplete = function (input, onPlace) {
		if (!input || input.dataset.seminaryAutocomplete) return;
		input.dataset.seminaryAutocomplete = "1";

		const list = buildDropdown(input);
		let session = newSessionToken();
		let timer = null;
		let active = -1;
		let items = [];

		const close = () => {
			list.style.display = "none";
			active = -1;
		};

		const render = () => {
			list.innerHTML = "";
			items.forEach((item, i) => {
				const row = document.createElement("div");
				row.textContent = item.label;
				Object.assign(row.style, {
					padding: "6px 10px",
					cursor: "pointer",
					background: i === active ? "var(--bg-light-gray, #f4f5f6)" : "transparent",
				});
				row.addEventListener("mousedown", (e) => {
					e.preventDefault(); // keep focus; blur would close the list first
					choose(item);
				});
				list.appendChild(row);
			});
			place(list, input);
			list.style.display = items.length ? "block" : "none";
		};

		const choose = (item) => {
			close();
			frappe
				.call("seminary.seminary.integrations.geocoding.resolve_address", {
					place_id: item.place_id,
					session_token: session,
				})
				.then((r) => {
					if (r.message) onPlace(r.message);
					// The session ends with the details call; the next address
					// typed starts a new one.
					session = newSessionToken();
				});
		};

		input.addEventListener("input", () => {
			clearTimeout(timer);
			const text = input.value.trim();
			if (text.length < MIN_CHARS) {
				items = [];
				close();
				return;
			}
			timer = setTimeout(() => {
				frappe
					.call("seminary.seminary.integrations.geocoding.suggest_addresses", {
						text,
						session_token: session,
					})
					.then((r) => {
						items = r.message || [];
						render();
					})
					// A typeahead that fails must leave a usable form: the field
					// is still a plain input and the address still saves.
					.catch(close);
			}, DEBOUNCE_MS);
		});

		input.addEventListener("keydown", (e) => {
			if (list.style.display === "none" || !items.length) return;
			if (e.key === "ArrowDown") {
				active = Math.min(active + 1, items.length - 1);
				render();
				e.preventDefault();
			} else if (e.key === "ArrowUp") {
				active = Math.max(active - 1, 0);
				render();
				e.preventDefault();
			} else if (e.key === "Enter" && active >= 0) {
				choose(items[active]);
				e.preventDefault();
			} else if (e.key === "Escape") {
				close();
			}
		});

		input.addEventListener("blur", () => setTimeout(close, 150));
		window.addEventListener("scroll", () => list.style.display !== "none" && place(list, input), true);
	};
})();
