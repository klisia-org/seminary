// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Academic Term'].refresh = function(listview) {
	listview.page.add_menu_item(__("Roll Term"));
	listview.page.add_action_item(__('Roll Term'), function() {
		
		frappe.call("education.education.api.set_iscurrent_acterm")
				.then(r =>  {
				console.log(r)
				})});};
