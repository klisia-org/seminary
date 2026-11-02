// Copyright (c) 2026, Murilo R. Melo and contributors
// For license information, please see license.txt

// The Setup Progress page (privatedocs p024). One page per group: each app's own Page creates it
// with its group's name, so every task force sees only its steps, plus one tile per group for the
// whole school's progress.

frappe.provide("seminary");

seminary.SetupProgress = class SetupProgress {
	constructor(wrapper, group, title) {
		this.group = group;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title, single_column: true });
		this.page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
		this.$body = $('<div class="setup-progress"></div>').appendTo(this.page.main);
		this.load();
	}

	load() {
		frappe
			.xcall("seminary.setup_progress.get_progress", { group: this.group })
			.then((data) => this.render(data));
	}

	render(data) {
		const esc = frappe.utils.escape_html;
		const html = data.tiers
			.map(
				(tier) => `
			<section class="setup-tier">
				<h4 class="setup-tier-title">${esc(tier.label)}</h4>
				<div class="setup-tiles">${tier.tiles.map((t) => this.tile(t)).join("")}</div>
				${
					tier.steps.length
						? `<div class="setup-steps">${tier.steps.map((s) => this.step(s)).join("")}</div>`
						: `<p class="text-muted">${__("Nothing for {0} in this stage.", [esc(data.label)])}</p>`
				}
			</section>`
			)
			.join("");
		this.$body.html(html);
	}

	tile(t) {
		const esc = frappe.utils.escape_html;
		const pct = t.total ? Math.round((100 * t.done) / t.total) : 0;
		const mine = t.group === this.group;
		const body = `
			<div class="setup-tile-label">${esc(t.label)}</div>
			<div class="setup-tile-count">${__("{0} of {1} done", [t.done, t.total])}</div>
			<div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>`;
		const cls = `setup-tile ${mine ? "is-current" : ""} ${t.done === t.total ? "is-done" : ""}`;
		return t.page && !mine
			? `<a class="${cls}" href="/desk/${encodeURIComponent(t.page)}">${body}</a>`
			: `<div class="${cls}">${body}</div>`;
	}

	step(s) {
		const esc = frappe.utils.escape_html;
		const icon = s.done
			? `<span class="setup-step-icon is-done">${frappe.utils.icon("check", "sm")}</span>`
			: `<span class="setup-step-icon"></span>`;
		const count = s.count ? `<span class="setup-step-count">${s.count[0]}/${s.count[1]}</span>` : "";
		const flag = s.flag ? `<span class="indicator-pill orange">${esc(s.flag)}</span>` : "";
		const failed = s.failed
			? `<span class="indicator-pill red">${__("Could not check")}</span>`
			: "";
		const roles = (s.roles || []).map((r) => `<span class="setup-role">${esc(r)}</span>`).join("");
		const manual = s.manual
			? `<a class="setup-manual" href="${esc(s.manual)}">${__("Manual")}</a>`
			: "";
		const title = s.route
			? `<a href="${esc(s.route)}">${esc(s.title)}</a>`
			: esc(s.title);
		return `
			<div class="setup-step ${s.done ? "is-done" : ""}">
				${icon}
				<div class="setup-step-main">
					<div class="setup-step-title">${title} ${count} ${flag} ${failed}</div>
					${s.description ? `<div class="setup-step-description">${esc(s.description)}</div>` : ""}
					<div class="setup-step-meta">${roles} ${manual}</div>
				</div>
			</div>`;
	}
};

frappe.dom.set_style(`
.setup-progress { max-width: 960px; padding: var(--padding-md, 1rem) var(--padding-lg, 1.25rem); }
.setup-tier { margin-bottom: var(--margin-xl, 2rem); }
.setup-tier-title { margin-bottom: var(--margin-sm, .5rem); }
.setup-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--margin-sm, .5rem); margin-bottom: var(--margin-md, 1rem); }
.setup-tile { display: block; padding: var(--padding-sm, .5rem) var(--padding-md, .75rem); border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 8px); background: var(--card-bg); color: var(--text-color); }
a.setup-tile:hover { text-decoration: none; border-color: var(--primary); }
.setup-tile.is-current { border-color: var(--primary); }
.setup-tile-label { font-weight: 600; }
.setup-tile-count { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: 4px; }
.setup-tile .progress { height: 4px; margin: 0; }
.setup-tile.is-done .progress-bar { background: var(--green-500); }
.setup-steps { border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 8px); background: var(--card-bg); }
.setup-step { display: flex; gap: var(--margin-sm, .5rem); padding: var(--padding-sm, .5rem) var(--padding-md, .75rem); border-top: 1px solid var(--border-color); }
.setup-step:first-child { border-top: none; }
.setup-step-icon { flex: none; width: 18px; height: 18px; margin-top: 2px; border: 1.5px solid var(--gray-400); border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
.setup-step-icon.is-done { border-color: var(--green-500); background: var(--green-500); color: #fff; }
.setup-step-icon.is-done svg { stroke: currentColor; width: 12px; height: 12px; }
.setup-step.is-done .setup-step-title a { color: var(--text-muted); }
.setup-step-main { flex: 1; min-width: 0; }
.setup-step-count { color: var(--text-muted); font-size: var(--text-sm); margin-left: 4px; }
.setup-step-description { color: var(--text-muted); font-size: var(--text-sm); }
.setup-step-meta { font-size: var(--text-xs, 11px); color: var(--text-muted); margin-top: 2px; }
.setup-role { display: inline-block; padding: 0 6px; margin-right: 4px; border-radius: 10px; background: var(--control-bg); }
.setup-manual { margin-left: 4px; }
`);
