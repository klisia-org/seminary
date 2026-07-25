frappe.ui.form.on("Person Import Batch", {
	refresh(frm) {
		add_workflow_buttons(frm);
		render_image_match(frm);

		if (!frm.__pib_realtime_bound) {
			frm.__pib_realtime_bound = true;
			frappe.realtime.on("person_import_complete", (data) => {
				if (!data || data.batch !== frm.doc.name) return;
				frappe.msgprint({
					title: __("Import Complete"),
					indicator: "green",
					message: data.summary,
				});
				frm.reload_doc();
			});
		}
	},
	source_file(frm) {
		// A freshly attached file clears any prior match summary until reloaded.
		render_image_match(frm);
	},
});

function add_workflow_buttons(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 0) return;

	frm.add_custom_button(__("Download Template CSV"), () => {
		frm.call("download_template").then((r) => {
			const csv = (r && r.message) || "";
			const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "person_import_template.csv";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		});
	});

	frm.add_custom_button(__("Load Rows from File"), () => {
		if (!frm.doc.source_file) {
			frappe.msgprint(__("Attach a Source CSV first."));
			return;
		}
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save your changes first, then click Load Rows from File."));
			return;
		}
		frm.call("load_from_csv", {}, null, {
			freeze: true,
			freeze_message: __("Parsing CSV..."),
		}).then((r) => {
			const n = (r && r.message && r.message.rows) || 0;
			frappe.show_alert({
				message: __("Loaded {0} row(s).", [n]),
				indicator: "green",
			});
			frm.reload_doc();
		});
	});

	if (has_image_rows(frm)) {
		frm.add_custom_button(__("Upload Images"), () => {
			if (frm.is_new()) {
				frappe.msgprint(__("Save the batch first, then upload images."));
				return;
			}
			new frappe.ui.FileUploader({
				doctype: frm.doctype,
				docname: frm.docname,
				allow_multiple: true,
				make_attachments_public: false,
				restrictions: { allowed_file_types: ["image/*"] },
				on_success() {
					frm.reload_doc();
				},
			});
		});
	}

	frm.add_custom_button(__("Run Dry-Run"), () => {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save your changes first, then click Run Dry-Run."));
			return;
		}
		frm.call("dry_run", {}, null, {
			freeze: true,
			freeze_message: __("Validating rows..."),
		}).then((r) => {
			const msg = (r && r.message) || {};
			frappe.show_alert({
				message: msg.clean
					? __("Dry-run clean. You may submit the batch.")
					: __(
							"Dry-run found {0} error(s) and {1} warning(s). Review the Messages column; add Override Notes to accept warnings.",
							[msg.errors || 0, msg.warnings || 0]
					  ),
				indicator: msg.clean ? "green" : "orange",
			});
			frm.reload_doc();
		});
	}).addClass(
		frm.doc.batch_status === "Dry-Run Clean" ? "btn-default" : "btn-primary"
	);
}

function has_image_rows(frm) {
	return (frm.doc.rows || []).some((row) => (row.image_filename || "").trim());
}

async function render_image_match(frm) {
	const wrapper = frm.fields_dict.image_match_html;
	if (!wrapper || !wrapper.$wrapper) return;

	const wanted = (frm.doc.rows || [])
		.map((row) => (row.image_filename || "").trim())
		.filter(Boolean);

	if (!wanted.length || frm.is_new()) {
		wrapper.$wrapper.empty();
		return;
	}

	const attachments = await frappe.db.get_list("File", {
		filters: { attached_to_doctype: frm.doctype, attached_to_name: frm.docname },
		fields: ["file_name"],
		limit: 0,
	});
	const have = new Set(
		(attachments || []).map((f) => (f.file_name || "").toLowerCase())
	);
	const missing = wanted.filter((name) => !have.has(name.toLowerCase()));
	const matched = wanted.length - missing.length;

	const indicator = missing.length ? "orange" : "green";
	let html = `<div class="text-muted" style="padding:4px 0;">
		<span class="indicator ${indicator}">${__("Images: {0} of {1} filenames matched", [
		matched,
		wanted.length,
	])}</span></div>`;
	if (missing.length) {
		html += `<div class="small text-muted">${__("Missing")}: ${frappe.utils.escape_html(
			missing.join(", ")
		)}</div>`;
	}
	wrapper.$wrapper.html(html);
}
