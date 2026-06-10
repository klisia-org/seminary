// Desk inbox v1 (ADR 044): the Communication Log list with status indicators.
// Filter by person/channel/category/direction from the standard sidebar.

frappe.listview_settings["Communication Log"] = {
	add_fields: ["status", "direction", "channel"],
	get_indicator(doc) {
		const colors = {
			Queued: "orange",
			Sending: "orange",
			Sent: "blue",
			Delivered: "green",
			Read: "green",
			Failed: "red",
			Bounced: "red",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
