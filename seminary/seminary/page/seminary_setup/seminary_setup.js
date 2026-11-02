// Copyright (c) 2026, Murilo R. Melo and contributors
// For license information, please see license.txt

frappe.pages["seminary-setup"].on_page_load = (wrapper) => {
	frappe.require("setup_progress.bundle.js", () => {
		new seminary.SetupProgress(wrapper, "Seminary", __("Seminary Setup"));
	});
};
