// Advance Students (ADR 083 §4). Opened from the Registrar workspace block.
// Students move one program step at a time (term N → N+1 out of a closing
// Academic Term), and only once every section they hold that term is Closed.
// The server checks every step again, so this dialog only has to explain.

frappe.provide("seminary");

seminary.advance_students = {
	open() {
		const d = new frappe.ui.Dialog({
			title: __("Advance Students"),
			size: "large",
			fields: [
				{
					fieldname: "academic_term",
					fieldtype: "Link",
					options: "Academic Term",
					label: __("Term being closed"),
					reqd: 1,
					onchange: () => load(),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "program",
					fieldtype: "Link",
					options: "Program",
					label: __("Program"),
					description: __("Leave blank for all programs."),
					onchange: () => load(),
				},
				{ fieldtype: "Section Break" },
				{ fieldname: "steps_html", fieldtype: "HTML" },
			],
			primary_action_label: __("Advance selected"),
			primary_action: () => confirm_and_advance(),
		});

		let state = { steps: [], next_term: null };

		const load = () => {
			const academic_term = d.get_value("academic_term");
			if (!academic_term) {
				render();
				return;
			}
			frappe
				.call({
					method: "seminary.seminary.advancement.get_steps",
					args: { academic_term, program: d.get_value("program") || null },
				})
				.then((r) => {
					state = r.message || { steps: [] };
					render();
				});
		};

		const status_cell = (s) => {
			if (s.status === "Ready")
				return `<span class="indicator-pill green">${__("Ready")}</span>`;
			if (s.status === "Blocked") {
				const links = s.sections
					.map(
						(cs) =>
							`<a href="/app/course-schedule/${encodeURIComponent(cs)}" target="_blank">${frappe.utils.escape_html(cs)}</a>`
					)
					.join(", ");
				return `<span class="indicator-pill red">${__("Waiting for grades")}</span> <span class="small">${links}</span>`;
			}
			if (s.status === "Done")
				return `<span class="indicator-pill gray">${__("Done on {0}", [
					frappe.datetime.str_to_user(s.done_on) || "",
				])}</span>`;
			return `<span class="indicator-pill gray">${__("Final term")}</span>`;
		};

		const render = () => {
			const wrap = d.fields_dict.steps_html.$wrapper;
			if (!state.steps.length) {
				wrap.html(
					`<p class="text-muted">${
						d.get_value("academic_term")
							? __("No active students to advance from this term.")
							: __("Choose the term being closed.")
					}</p>`
				);
				d.get_primary_btn().prop("disabled", true);
				return;
			}
			const rows = state.steps
				.map((s, i) => {
					const step =
						s.status === "Final"
							? __("Term {0}", [s.from_term])
							: __("Term {0} → {1}", [s.from_term, s.to_term]);
					const tick =
						s.status === "Ready"
							? `<input type="checkbox" class="adv-step" data-i="${i}" checked>`
							: `<input type="checkbox" disabled>`;
					return `<tr>
						<td>${tick}</td>
						<td>${frappe.utils.escape_html(s.program)}</td>
						<td>${step}</td>
						<td>${s.students}</td>
						<td>${status_cell(s)}</td>
					</tr>`;
				})
				.join("");
			wrap.html(`
				<table class="table table-bordered">
					<thead><tr>
						<th style="width:32px"></th><th>${__("Program")}</th><th>${__("Step")}</th>
						<th>${__("Students")}</th><th>${__("Status")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
				<p class="text-muted small">${__(
					"A step is ready when every section its students took this term has had its grades sent. Students can be advanced out of a term only once."
				)}</p>`);
			const sync = () =>
				d.get_primary_btn().prop("disabled", !wrap.find(".adv-step:checked").length);
			wrap.find(".adv-step").on("change", sync);
			sync();
		};

		const selected = () =>
			d.fields_dict.steps_html.$wrapper
				.find(".adv-step:checked")
				.map((_, el) => state.steps[$(el).data("i")])
				.get();

		const confirm_and_advance = () => {
			const steps = selected();
			if (!steps.length) return;
			const total = steps.reduce((n, s) => n + s.students, 0);
			const list = steps
				.map((s) =>
					__("{0} term {1} → {2} ({3})", [
						frappe.utils.escape_html(s.program),
						s.from_term,
						s.to_term,
						s.students,
					])
				)
				.join("<br>");
			frappe.confirm(
				`${__("Advance {0} students:", [total])}<br>${list}<br><br>${__(
					"This can't be undone."
				)}`,
				() => advance(steps)
			);
		};

		const advance = (steps) => {
			frappe
				.call({
					method: "seminary.seminary.advancement.advance",
					args: {
						academic_term: d.get_value("academic_term"),
						program: d.get_value("program") || null,
						steps: steps.map((s) => ({ program: s.program, from_term: s.from_term })),
					},
					freeze: true,
					freeze_message: __("Advancing students..."),
				})
				.then((r) => {
					d.hide();
					show_result(r.message || {});
				});
		};

		const show_result = (res) => {
			const colour = { Advanced: "green", Blocked: "red" };
			const lines = (res.messages || [])
				.map(
					(m) =>
						`<p><span class="indicator ${colour[m.status] || "gray"}"></span>${frappe.utils.escape_html(m.message)}</p>`
				)
				.join("");
			const result = new frappe.ui.Dialog({
				title: __("Advance Students"),
				fields: [{ fieldname: "out", fieldtype: "HTML", options: lines }],
			});
			// Only Time-based programs have courses planned per term to enroll in.
			const advanced = (res.advanced || []).filter((a) => a.time_based);
			if (advanced.length && res.next_term) {
				result.set_primary_action(__("Enroll them for {0}", [res.next_term]), () => {
					frappe
						.call({
							method: "seminary.seminary.doctype.bulk_course_enrollment.bulk_course_enrollment.new_run",
							args: {
								academic_term: res.next_term,
								programs: [...new Set(advanced.map((a) => a.program))],
								advanced_from: d.get_value("academic_term"),
							},
							freeze: true,
						})
						.then((r) => {
							result.hide();
							frappe.set_route("Form", "Bulk Course Enrollment", r.message);
						});
				});
			}
			result.show();
		};

		d.show();
		frappe
			.call({ method: "seminary.seminary.advancement.get_steps" })
			.then((r) => {
				const term = r.message && r.message.academic_term;
				if (term) d.set_value("academic_term", term);
				else render();
			});
	},
};
