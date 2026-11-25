// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt

// The reviewer's form (decisions/112 §3-4): a rubric grid saved as Rubric
// Scores, then Submit Review or Recuse. Other reviews appear once this one is
// submitted, so nobody reads the others before forming their own view.
frappe.ui.form.on("Application Review", {
	refresh(frm) {
		frm.disable_save();
		if (frm.is_new()) return;
		frappe
			.call("seminary.seminary.admissions.review_panel", { review: frm.doc.name })
			.then((r) => {
				const data = r.message || {};
				draw_scores(frm, data);
				draw_others(frm, data.others);
				if (data.can_edit) add_actions(frm);
			});
	},
});

function add_actions(frm) {
	frm.add_custom_button(__("Submit Review"), () => {
		if (!frm.doc.recommendation) {
			frappe.msgprint(__("Choose a recommendation first."));
			return;
		}
		frappe
			.call("seminary.seminary.admissions.submit_review", {
				review: frm.doc.name,
				recommendation: frm.doc.recommendation,
				comments: frm.doc.comments || "",
			})
			.then(() => frm.reload_doc());
	}).addClass("btn-primary");
	frm.add_custom_button(__("Recuse"), () => {
		frappe.prompt(
			{
				fieldname: "note",
				fieldtype: "Small Text",
				label: __("What is the conflict of interest?"),
				reqd: 1,
			},
			(values) =>
				frappe
					.call("seminary.seminary.admissions.recuse", {
						review: frm.doc.name,
						note: values.note,
					})
					.then(() => frm.reload_doc()),
			__("Recuse from this review"),
			__("Recuse")
		);
	});
}

function draw_scores(frm, data) {
	const $wrap = frm.get_field("scores_html").$wrapper.empty();
	const rubric = data.rubric;
	if (!rubric) {
		$wrap.html(
			`<p class="text-muted">${__("This program reviews by recommendation alone.")}</p>`
		);
		return;
	}
	const scores = {};
	(data.scores || []).forEach((s) => (scores[s.criterion_code] = s));
	const cells = {};
	(rubric.cells || []).forEach((c) => (cells[`${c.criterion_code}|${c.level}`] = c.descriptor));
	const esc = frappe.utils.escape_html;
	const head = rubric.levels
		.map(
			(l) =>
				`<th scope="col">${esc(l.label)} <span class="text-muted">(${
					l.percent
				}%)</span></th>`
		)
		.join("");
	const rows = rubric.criteria
		.map((c) => {
			const picked = scores[c.criterion_code] && scores[c.criterion_code].level;
			const levels = rubric.levels
				.map((l) => {
					const id = `rs-${c.criterion_code}-${l.label}`.replace(/[^A-Za-z0-9_-]/g, "_");
					const text = cells[`${c.criterion_code}|${l.label}`] || l.description || "";
					return `<td><label for="${id}" style="display:block;cursor:pointer;">
						<input type="radio" id="${id}" name="rs-${esc(c.criterion_code)}" value="${esc(l.label)}"
							data-code="${esc(c.criterion_code)}" ${picked === l.label ? "checked" : ""}
							${data.can_edit ? "" : "disabled"}>
						<span class="small">${esc(text)}</span></label></td>`;
				})
				.join("");
			return `<tr><th scope="row">${esc(c.title)}<div class="text-muted small">${
				c.share
			}%</div></th>${levels}</tr>`;
		})
		.join("");
	const total =
		data.overall_percent !== null && data.overall_percent !== undefined
			? `<p><strong>${__("Overall score")}:</strong> <span class="overall">${
					data.overall_percent
			  }%</span></p>`
			: `<p class="text-muted overall-note">${__(
					"Score every criterion to see the overall score."
			  )}</p>`;
	$wrap.html(`<div class="table-responsive"><table class="table table-bordered">
		<caption>${__("Rubric")}</caption><thead><tr><th scope="col">${__(
		"Criterion"
	)}</th>${head}</tr></thead>
		<tbody>${rows}</tbody></table></div>${total}`);
	if (!data.can_edit) return;
	$wrap.find("input[type=radio]").on("change", function () {
		frappe
			.call("seminary.seminary.admissions.save_review_scores", {
				review: frm.doc.name,
				scores: [{ criterion_code: $(this).data("code"), level: $(this).val() }],
			})
			.then((r) => {
				const pct = r.message && r.message.overall_percent;
				if (pct !== null && pct !== undefined) {
					frm.doc.overall_percent = pct;
					frm.refresh_field("overall_percent");
				}
			});
	});
}

function draw_others(frm, others) {
	const $wrap = frm.get_field("others_html").$wrapper.empty();
	if (others === null || others === undefined) {
		$wrap.html(
			`<p class="text-muted">${__(
				"The other reviews are shown once you submit yours or recuse."
			)}</p>`
		);
		return;
	}
	if (!others.length) {
		$wrap.html(`<p class="text-muted">${__("No other reviews yet.")}</p>`);
		return;
	}
	const esc = frappe.utils.escape_html;
	$wrap.html(
		others
			.map(
				(o) => `<div class="mb-3"><strong>${esc(o.reviewer_name || "")}</strong> · ${esc(
					__(o.status)
				)}
				${o.recommendation ? " · " + esc(__(o.recommendation)) : ""}
				${
					o.overall_percent !== null && o.overall_percent !== undefined
						? " · " + o.overall_percent + "%"
						: ""
				}
				<div class="text-muted">${esc(o.comments || o.conflict_note || "")}</div></div>`
			)
			.join("")
	);
}
