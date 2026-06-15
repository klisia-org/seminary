frappe.listview_settings["Partner Job Opening"] = {
	// A posting is "Awaiting Approval" until staff publish it (publish=1), per the
	// partner portal approval flow (ADR 053).
	get_indicator(doc) {
		if (doc.status === "Closed") {
			return [__("Closed"), "gray", "status,=,Closed"];
		}
		if (!doc.publish) {
			return [__("Awaiting Approval"), "orange", "publish,=,0"];
		}
		return [__("Published"), "green", "publish,=,1"];
	},
};
