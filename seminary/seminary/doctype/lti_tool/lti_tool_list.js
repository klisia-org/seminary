// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// Dynamic Registration (decisions/110 §1): the tool registers itself in the
// window this opens, and the new tool appears here when it is done.
frappe.listview_settings["LTI Tool"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Register by URL"), () => {
			frappe.prompt(
				{
					fieldname: "registration_url",
					fieldtype: "Data",
					options: "URL",
					label: __("The tool's registration URL"),
					reqd: 1,
				},
				({ registration_url }) => {
					const win = window.open("", "_blank");
					frappe
						.call({
							method: "seminary.lti.registration.start_registration",
							args: { registration_url },
						})
						.then((r) => {
							if (win) win.location = r.message.url;
							const done = (e) => {
								if (e.data && e.data.subject === "org.imsglobal.lti.close") {
									window.removeEventListener("message", done);
									listview.refresh();
								}
							};
							window.addEventListener("message", done);
						})
						.catch(() => win && win.close());
				},
				__("Register an LTI tool")
			);
		});
	},
};
