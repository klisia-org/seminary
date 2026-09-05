// Copyright (c) 2026, Klisia / SeminaryERP and contributors
// For license information, please see license.txt
//
// The Cohort Planner (ADR 067 section 6).
//
// Setup -> Match Students and Mentors -> review and drag -> Create Cohorts.
// Nothing is written before the last button. The proposal lives in this page
// and nowhere else: it is a pure function of the setup, so a lost tab costs a
// re-run rather than data, and there is no draft record for a second chair to
// collide with mid-review.
//
// Dragging never asks the server. The payload carries each student's ranked
// shortlist of the *opened groups*, so moving somebody recomputes the counts
// and their notes locally -- a round trip per drag would make the interaction
// unusable at 200 students.

//: The unplaced list is a drop target like any group, so it needs a key that no
//: Person can collide with.
const UNPLACED = "__unplaced__";

frappe.pages["cohort-planner"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cohort Planner"),
		single_column: true,
	});
	new CohortPlanner(page);
};

class CohortPlanner {
	constructor(page) {
		this.page = page;
		this.setup = null; // planner_setup payload for the chosen type
		this.plan = null; // the current proposal, as edited
		this.excluded = new Set(); // mentors withdrawn for this run only
		this.chosen_criteria = null; // null = use the type's own rules
		this.injectStyles();
		this.render();
		this.loadTypes();
	}

	// ------------------------------------------------------------------ chrome

	injectStyles() {
		if (document.getElementById("cohort-planner-styles")) return;
		const style = document.createElement("style");
		style.id = "cohort-planner-styles";
		style.textContent = `
			.cp-wrap { padding: 0 15px 40px; }
			.cp-card { background: var(--card-bg); border: 1px solid var(--border-color);
				border-radius: var(--border-radius-md); padding: 12px 15px; margin-bottom: 12px; }
			.cp-card h5 { margin: 0 0 8px; font-size: var(--text-md); }
			.cp-muted { color: var(--text-muted); font-size: var(--text-sm); }
			.cp-label { display: block; margin-bottom: 3px; font-size: var(--text-sm);
				color: var(--text-muted); font-weight: 500; }
			.cp-groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
				gap: 12px; align-items: start; }
			.cp-group { background: var(--card-bg); border: 1px solid var(--border-color);
				border-radius: var(--border-radius-md); overflow: hidden; }
			.cp-group.cp-flag { border-color: var(--yellow-400); }
			.cp-group-head { padding: 10px 12px; border-bottom: 1px solid var(--border-color); }
			.cp-group-head input { border: none; background: transparent; font-weight: 600;
				width: 100%; padding: 0; color: var(--text-color); }
			.cp-group-head input:focus { outline: 1px solid var(--border-color); border-radius: 4px; }
			.cp-members { list-style: none; margin: 0; padding: 6px; min-height: 46px; }
			.cp-member { border: 1px solid var(--border-color); border-radius: var(--border-radius-sm);
				padding: 6px 8px; margin-bottom: 6px; background: var(--bg-color); cursor: grab; }
			.cp-member:last-child { margin-bottom: 0; }
			.cp-member .cp-name { font-weight: 500; }
			.cp-note { display: block; color: var(--text-muted); font-size: var(--text-xs); }
			.cp-note-warn { color: var(--text-on-yellow); }
			.cp-drop-hint { color: var(--text-muted); font-size: var(--text-xs);
				text-align: center; padding: 12px 0; }
			.cp-badge { font-size: var(--text-xs); }
			.cp-unplaced .cp-members { display: grid;
				grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 6px; }
			.cp-readiness td { padding: 2px 10px 2px 0; font-size: var(--text-sm); }
		`;
		document.head.appendChild(style);
	}

	render() {
		// The two choices that define a run live in the page body, not in the
		// toolbar's field row: `page.add_field` renders with `only_input`, so a
		// select there has no visible label — three unlabelled dropdowns in a
		// row, and the first decision of the flow is the easiest to miss.
		this.page.main.html(`
			<div class="cp-wrap">
				<div class="cp-setup"></div>
				<div class="cp-plan"></div>
			</div>
		`);
		this.$setup = this.page.main.find(".cp-setup");
		this.$plan = this.page.main.find(".cp-plan");
	}

	// ------------------------------------------------------------------- setup

	loadTypes() {
		frappe.call("seminary.seminary.discipleship.planner.plannable_types").then((r) => {
			this.types = r.message || [];
			if (!this.types.length) {
				this.$setup.html(
					`<div class="cp-card">${__(
						"No Cohort Type is set up for bulk planning yet. Open a Cohort Type, tick <b>May Be Planned in Bulk</b> and give it a Mentor Unit."
					)}</div>`
				);
				return;
			}
			this.loadSetup(this.types[0].name);
		});
	}

	loadSetup(cohort_type) {
		if (!cohort_type) return;
		this.cohort_type = cohort_type;
		(this.sortables || []).forEach((s) => s.destroy());
		this.sortables = [];
		this.plan = null;
		this.excluded = new Set();
		this.chosen_criteria = null;
		this.scope_value = "all";
		this.$plan.empty();
		frappe
			.call("seminary.seminary.discipleship.planner.planner_setup", { cohort_type })
			.then((r) => {
				this.setup = r.message;
				this.renderSetup();
			});
	}

	scope() {
		return this.scope_value || "all";
	}

	typeRow() {
		return (this.types || []).find((t) => t.name === this.cohort_type) || {};
	}

	whatToPlanHtml() {
		const bound = this.typeRow().program || this.typeRow().program_level;
		const options = this.types
			.map(
				(t) =>
					`<option value="${frappe.utils.escape_html(t.name)}" ${
						t.name === this.cohort_type ? "selected" : ""
					}>${frappe.utils.escape_html(t.name)}</option>`
			)
			.join("");

		// The counts go in the option labels: which slice of students to work
		// on is a decision about how many there are.
		const scopes = [
			["all", __("All")],
			["never", __("Never in this cohort type")],
			["former", __("No longer in this cohort type")],
		]
			.map(
				([value, label]) =>
					`<option value="${value}" ${value === this.scope() ? "selected" : ""}>${label} (${
						this.setup.scopes[value] || 0
					})</option>`
			)
			.join("");

		return `<div class="cp-card">
			<h5>${__("What to Plan")}</h5>
			<div class="row">
				<div class="col-md-6">
					<label class="cp-label">${__("Cohort Type")}</label>
					<select class="form-control cp-type">${options}</select>
					<div class="cp-muted mt-1">${
						bound
							? __("For {0}", [frappe.utils.escape_html(bound)])
							: __("Not bound to a program")
					}</div>
				</div>
				<div class="col-md-6">
					<label class="cp-label">${__("Students")}</label>
					<select class="form-control cp-scope">${scopes}</select>
					<div class="cp-muted mt-1">${__(
						"Anyone already in an active cohort of this type is never offered."
					)}</div>
				</div>
			</div>
		</div>`;
	}

	activeCriteria() {
		if (this.chosen_criteria) return this.chosen_criteria;
		return (this.setup.criteria || []).map((c) => c.handler);
	}

	renderSetup() {
		const s = this.setup;
		if (!s) return;
		const active = this.activeCriteria();
		const students = s.scopes[this.scope()] || 0;
		const mentors = s.mentors.filter((m) => !this.excluded.has(m.instructor));

		const criteria = (s.criteria || []).length
			? s.criteria
					.map(
						(c) => `
				<label class="mr-3">
					<input type="checkbox" class="cp-criterion" value="${frappe.utils.escape_html(c.handler)}"
						${active.includes(c.handler) ? "checked" : ""}>
					${frappe.utils.escape_html(__(c.label))}
					<span class="cp-muted">(${frappe.utils.escape_html(__(c.kind))})</span>
				</label>`
					)
					.join("")
			: `<span class="cp-muted">${__(
					"This type has no matching rules, so the planner will balance group sizes only."
			  )}</span>`;

		const mentorRows = s.mentors
			.map(
				(m) => `
			<label class="mr-3">
				<input type="checkbox" class="cp-mentor" value="${frappe.utils.escape_html(m.instructor)}"
					${this.excluded.has(m.instructor) ? "" : "checked"}>
				${frappe.utils.escape_html(m.full_name || m.instructor)}
				<span class="cp-muted">${
					m.remaining === null
						? __("no ceiling")
						: __("{0} free", [m.remaining])
				}</span>
			</label>`
			)
			.join("");

		this.$setup.html(`
			${this.whatToPlanHtml()}
			<div class="cp-card">
				<h5>${__("Mentor Unit")}</h5>
				<div>${frappe.utils.escape_html(s.unit_name || s.unit)}
					<span class="cp-muted">— ${__("{0} students to place, {1} mentors available", [
						students,
						mentors.length,
					])}</span></div>
			</div>
			<div class="cp-card">
				<h5>${__("Matching Rules for This Run")}</h5>
				<div>${criteria}</div>
				<div class="cp-muted mt-2">${__(
					"Changing these affects this run only. The Cohort Type is not modified."
				)}</div>
			</div>
			<div class="cp-card">
				<h5>${__("Mentors")}</h5>
				<div>${mentorRows || `<span class="cp-muted">${__("Nobody in this unit is wired to mentor cohorts with capacity to spare.")}</span>`}</div>
			</div>
			${this.readinessHtml()}
		`);

		this.$setup.find(".cp-type").on("change", (e) => this.loadSetup(e.target.value));
		this.$setup.find(".cp-scope").on("change", (e) => {
			this.scope_value = e.target.value;
			this.renderSetup();
		});
		this.$setup.find(".cp-criterion").on("change", () => {
			this.chosen_criteria = this.$setup
				.find(".cp-criterion:checked")
				.map((_i, el) => el.value)
				.get();
			this.renderSetup();
		});
		this.$setup.find(".cp-mentor").on("change", (e) => {
			if (e.target.checked) this.excluded.delete(e.target.value);
			else this.excluded.add(e.target.value);
			this.renderSetup();
		});
		this.$setup.find(".cp-gap").on("click", (e) => {
			e.preventDefault();
			this.showGap(e.currentTarget.dataset.criterion, e.currentTarget.dataset.side);
		});

		this.page.set_primary_action(
			__("Match Students and Mentors"),
			() => this.match(),
			"sitemap"
		);
		this.page.clear_secondary_action();
	}

	readinessHtml() {
		const rows = (this.setup.readiness || []).filter(
			(r) =>
				this.activeCriteria().includes(r.criterion) &&
				(r.mentors_missing || r.students_missing)
		);
		if (!rows.length) return "";
		// Mentor gaps and student gaps are different failures: one student
		// without gender makes that student unplaced, but a mentor pool without
		// gender makes the rule inoperable. So they are never summed.
		// The counts are buttons, not text. Finding the same people by hand
		// means filtering a list view on "is not set" — which is neither
		// obvious nor reachable from where the question was asked.
		const gap = (r, side, count, total, cls) =>
			count
				? `<a href="#" class="cp-gap ${cls}" data-criterion="${frappe.utils.escape_html(
						r.criterion
				  )}" data-side="${side}">${__("{0} of {1} {2} have no {3}", [
						count,
						total,
						side === "mentors" ? __("mentors") : __("students"),
						frappe.utils.escape_html(r.reads_label || r.reads),
				  ])}</a>`
				: "";

		const body = rows
			.map(
				(r) => `
			<tr>
				<td>${frappe.utils.escape_html(__(r.label))}</td>
				<td>${gap(r, "mentors", r.mentors_missing, r.mentors_total, "text-danger")}</td>
				<td>${gap(r, "students", r.students_missing, r.students_total, "text-warning")}</td>
			</tr>`
			)
			.join("");
		return `<div class="cp-card">
			<h5>${__("Before You Run")}</h5>
			<table class="cp-readiness"><tbody>${body}</tbody></table>
			<div class="cp-muted mt-2">${__(
				"A mentor missing a detail makes the rule unusable for everyone; a student missing one leaves that student unplaced."
			)}</div>
		</div>`;
	}

	showGap(criterion, side) {
		frappe
			.call("seminary.seminary.discipleship.planner.readiness_detail", {
				cohort_type: this.setup.cohort_type,
				criterion,
				side,
			})
			.then((r) => {
				const d = r.message;
				if (!d || !d.people.length) return;

				const rows = d.people
					.map(
						(p) => `<tr>
							<td><a href="${frappe.utils.get_form_link(
								"Person",
								p.person
							)}" target="_blank">${frappe.utils.escape_html(p.full_name)}</a></td>
							<td class="cp-muted">${
								p.role
									? `<a href="${frappe.utils.get_form_link(
											p.role_doctype,
											p.role
									  )}" target="_blank">${frappe.utils.escape_html(
											__(p.role_doctype)
									  )}</a>`
									: ""
							}</td>
						</tr>`
					)
					.join("");

				const where = d.can_edit_person
					? __("{0} is recorded on each person's record — the links below open it.", [
							d.reads_label,
					  ])
					: __(
							"{0} is recorded on each person's record, which a Registrar or Seminary Manager can edit.",
							[d.reads_label]
					  );

				const more = d.truncated
					? `<div class="cp-muted mt-2">${__(
							"Showing the first {0} of {1}. At this many, an import is a better answer than a form.",
							[d.people.length, d.total]
					  )}</div>`
					: "";

				new frappe.ui.Dialog({
					title:
						side === "mentors"
							? __("Mentors with no {0}", [d.reads_label])
							: __("Students with no {0}", [d.reads_label]),
					size: "small",
					fields: [
						{
							fieldtype: "HTML",
							options: `
								<p class="cp-muted">${frappe.utils.escape_html(where)}</p>
								<table class="table table-sm"><tbody>${rows}</tbody></table>
								${more}`,
						},
					],
				}).show();
			});
	}

	// ------------------------------------------------------------------ match

	match() {
		const run = () => {
			frappe
				.call("seminary.seminary.discipleship.planner.build_proposal", {
					cohort_type: this.setup.cohort_type,
					scope: this.scope(),
					exclude_mentors: JSON.stringify([...this.excluded]),
					criteria: JSON.stringify(this.activeCriteria()),
				})
				.then((r) => {
					this.adopt(r.message);
				});
		};
		// Re-running discards the review. Cheap to redo, annoying to lose by
		// accident, so it is confirmed once anything has been moved.
		if (this.plan && this.touched) {
			frappe.confirm(
				__("Matching again will discard the changes you have made to this plan. Continue?"),
				run
			);
		} else {
			run();
		}
	}

	// ------------------------------------------------------------------- plan

	group(key) {
		return this.plan.groups.find((g) => g.key === key);
	}

	/** A group, or the unplaced list dressed as one, so a drag between them is
	 *  the same operation rather than three special cases. */
	bucket(key) {
		if (key === UNPLACED) return { key: UNPLACED, members: this.plan.unplaced };
		return this.group(key);
	}

	mentorLabel(person) {
		const g = this.group(person);
		if (g) return g.mentor_name || person;
		const m = (this.setup.mentors || []).find((x) => x.person === person);
		return (m && m.full_name) || person;
	}

	/** The notes a member carries in the group they are currently in.
	 *
	 * Recomputed on every drag from the shortlist in the payload, because a
	 * note that says "next nearest mentor 34 km" stops being true the moment
	 * somebody is moved -- and a stale decision aid is worse than none.
	 */
	notesFor(member, group) {
		// The shortlist ranks every mentor the rules allow for this student,
		// pool-wide. Eligibility is asked of that; "where else could they go"
		// is asked of the groups currently on screen, which is a smaller and
		// changing set — a mentor leading no cohort is not a destination.
		const shortlist = this.plan.shortlists[member.person] || [];
		if (!shortlist.includes(group.key)) {
			// Overridden on purpose, so say so — and still show the quantity.
			// A chair who broke a filter to put somebody near a local mentor
			// wants the distance most of all.
			const notes = [
				{
					text: __("{0} does not match this student under the rules you chose.", [
						this.mentorLabel(group.key),
					]),
					warn: true,
				},
			];
			const km = this.distance(member.person, group.key);
			if (km !== null) {
				notes.push({ text: __("{0} away.", [this.formatDistance(km)]), warn: false });
			}
			return notes;
		}
		// The server's notes were computed for the group it proposed. They stay
		// accurate only while the member has not moved.
		if (member._home === group.key) {
			return (member.notes || []).map((text) => ({ text, warn: false }));
		}

		// Cohorts on screen that the rules also allow for this student, in
		// preference order — the only places they could be moved to next.
		const open = shortlist.filter((key) => key !== group.key && this.group(key));
		const rank = shortlist.filter((key) => this.group(key)).indexOf(group.key);

		const distance = this.distance(member.person, group.key);
		if (distance !== null) {
			// Measured against the cohorts now on screen, so the comparison is
			// re-earned by every drag rather than inherited from the proposal.
			const nearer = open
				.map((key) => this.distance(member.person, key))
				.filter((d) => d !== null)
				.sort((a, b) => a - b)[0];
			return [
				{
					text:
						nearer === undefined
							? __("{0} away; no other cohort here has a mentor we could locate.", [
									this.formatDistance(distance),
							  ])
							: __("{0} away; next nearest cohort {1}.", [
									this.formatDistance(distance),
									this.formatDistance(nearer),
							  ]),
					warn: false,
				},
			];
		}

		return [
			{
				text: open.length
					? __("Choice {0} of {1} here; next best is {2}.", [
							rank + 1,
							open.length + 1,
							this.mentorLabel(open[0]),
					  ])
					: __("The only cohort here matching this student."),
				warn: false,
			},
		];
	}

	/** The quantity a ranking published for this pairing, or null.
	 *
	 * Already in the school's unit — the server converts, because the page is
	 * never told where anybody lives. */
	distance(person, groupKey) {
		const row = (this.plan.pair_values || {})[person];
		if (!row || row[groupKey] === undefined) return null;
		return row[groupKey];
	}

	formatDistance(value) {
		return `${value} ${this.plan.pair_suffix || ""}`.trim();
	}

	/** Mentors in the pool who are not already leading one of these cohorts. */
	spareMentors() {
		const leading = new Set(this.plan.groups.map((g) => g.mentor_person));
		return (this.setup.mentors || []).filter(
			(m) => !leading.has(m.person) && !this.excluded.has(m.instructor)
		);
	}

	/** Open an empty cohort under a mentor the matcher did not choose.
	 *
	 * The rules balance and rank; they do not know that three students share a
	 * timezone with one particular mentor, or that a congregation would rather
	 * keep its own people together. This is the seam for that judgement, and it
	 * is why the shortlist covers the whole pool: an added cohort has to know
	 * whether the rules allow each student dragged into it.
	 */
	addCohort() {
		const spare = this.spareMentors();
		if (!spare.length) {
			frappe.msgprint(
				__("Every mentor with capacity in this unit is already leading one of these cohorts.")
			);
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Add a Cohort"),
			fields: [
				{
					fieldname: "mentor",
					fieldtype: "Select",
					label: __("Mentor"),
					reqd: 1,
					options: spare.map((m) => ({
						label: `${m.full_name || m.instructor}${
							m.remaining === null ? "" : __(" ({0} free)", [m.remaining])
						}`,
						value: m.instructor,
					})),
				},
				{
					fieldname: "cohort_name",
					fieldtype: "Data",
					label: __("Name"),
					description: __("Students will see this. Left empty, it is named after the mentor."),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				const m = spare.find((x) => x.instructor === values.mentor);
				this.plan.groups.push({
					key: m.person,
					mentor: m.instructor,
					mentor_person: m.person,
					mentor_name: m.full_name,
					remaining: m.remaining,
					suggested_name:
						values.cohort_name ||
						`${this.plan.cohort_type} — ${m.full_name || m.instructor}`,
					members: [],
					size: 0,
					below_minimum: false,
				});
				this.touched = true;
				dialog.hide();
				this.renderPlan();
			},
		});
		dialog.show();
	}

	/** Remember where the matcher put each student.
	 *
	 * Stamped once, when a proposal arrives — NOT on every render. Doing it in
	 * `renderPlan` re-stamped a member the instant they were dragged, so they
	 * looked to be at home in their new group and kept the server's original
	 * note: the distances never moved, which is exactly the symptom.
	 */
	adopt(plan) {
		this.plan = plan;
		this.touched = false;
		plan.groups.forEach((g) =>
			g.members.forEach((m) => {
				m._home = g.key;
			})
		);
		this.renderPlan();
	}

	renderPlan() {
		const plan = this.plan;
		const cards = plan.groups.map((g) => this.groupHtml(g)).join("");
		// A drop target as well as a list. Dragging out of it is how a chair
		// overrides a filter for one person; dragging into it is how a student
		// is left for next time.
		const unplaced = `<div class="cp-card cp-unplaced">
				<h5>${__("Not Placed ({0})", [plan.unplaced.length])}</h5>
				<div class="cp-muted mb-2">${__(
					"Leaving these students unplaced is a legitimate end to a run — they stay in the pool for next time. Or drag one into a cohort, which overrides the rules for that person only."
				)}</div>
				<ul class="cp-members" data-group="${UNPLACED}">
					${
						plan.unplaced
							.map(
								(u) => `<li class="cp-member" data-person="${frappe.utils.escape_html(
									u.person
								)}">
									<span class="cp-name">${frappe.utils.escape_html(u.student_name || u.person)}</span>
									<span class="cp-note">${frappe.utils.escape_html(u.reason || "")}</span>
								</li>`
							)
							.join("") ||
						`<div class="cp-drop-hint">${__("Everybody has a cohort")}</div>`
					}
				</ul>
			</div>`;

		this.$plan.html(`
			<div class="cp-card">
				<h5>${__("Proposed Cohorts")}</h5>
				<div class="cp-muted">${__(
					"Nothing has been created yet. Drag students between cohorts, rename them, then press Create Cohorts."
				)}</div>
				<button class="btn btn-default btn-xs mt-2 cp-add">${__(
					"Add a Cohort"
				)}</button>
				<span class="cp-muted ml-2">${__(
					"Open one under a mentor the rules did not pick, and drag students in. An empty one is simply not created."
				)}</span>
			</div>
			<div class="cp-groups">${cards}</div>
			${unplaced}
		`);

		this.$plan.find(".cp-add").on("click", () => this.addCohort());
		this.wireDrag();
		this.$plan.find(".cp-group-head input").on("change", (e) => {
			const g = this.group(e.target.dataset.group);
			if (g) g.suggested_name = e.target.value;
		});

		this.page.set_primary_action(__("Create Cohorts"), () => this.create(), "check");
		this.page.set_secondary_action(__("Match Again"), () => this.match());
	}

	groupHtml(g) {
		const min = this.plan.min_size;
		const max = this.plan.max_size;
		const over = max && g.members.length > max;
		const under = min && g.members.length && g.members.length < min;
		const overCapacity =
			g.remaining !== null && g.members.length > g.remaining;

		const badges = [];
		if (under)
			badges.push(
				`<span class="badge badge-warning cp-badge">${__("Below minimum ({0} of {1})", [
					g.members.length,
					min,
				])}</span>`
			);
		if (over)
			badges.push(
				`<span class="badge badge-warning cp-badge">${__("Over the size limit ({0} of {1})", [
					g.members.length,
					max,
				])}</span>`
			);
		if (overCapacity)
			badges.push(
				`<span class="badge badge-danger cp-badge">${__(
					"Past this mentor's capacity — confirm with them"
				)}</span>`
			);

		const members = g.members
			.map((m) => {
				const notes = this.notesFor(m, g)
					.map(
						(n) =>
							`<span class="cp-note ${n.warn ? "cp-note-warn" : ""}">${frappe.utils.escape_html(
								n.text
							)}</span>`
					)
					.join("");
				return `<li class="cp-member" data-person="${frappe.utils.escape_html(m.person)}">
					<span class="cp-name">${frappe.utils.escape_html(m.student_name || m.person)}</span>
					${notes}
				</li>`;
			})
			.join("");

		return `<div class="cp-group ${under || over || overCapacity ? "cp-flag" : ""}"
				data-group="${frappe.utils.escape_html(g.key)}">
			<div class="cp-group-head">
				<input type="text" data-group="${frappe.utils.escape_html(g.key)}"
					value="${frappe.utils.escape_html(g.suggested_name || "")}">
				<div class="cp-muted">${frappe.utils.escape_html(g.mentor_name || g.mentor)} —
					${__("{0} students", [g.members.length])}${
						g.remaining === null ? "" : __(", {0} free", [g.remaining])
					}</div>
				<div class="mt-1">${badges.join(" ")}</div>
			</div>
			<ul class="cp-members" data-group="${frappe.utils.escape_html(g.key)}">
				${members || `<div class="cp-drop-hint">${__("Drag a student here")}</div>`}
			</ul>
		</div>`;
	}

	wireDrag() {
		// `Sortable` is a frappe global (libs.bundle.js sets window.Sortable) --
		// the kanban board drags cards between columns with it, which is this
		// page's exact gesture.
		//
		// Destroy the previous instances first. Every drag re-renders the board,
		// and a Sortable whose element has been replaced keeps its listeners and
		// its observers alive against detached DOM. At sixteen groups plus the
		// unplaced list that is seventeen leaked instances *per drag* — invisible
		// on a small plan and steadily worse on a real intake, which is exactly
		// where it would first be met.
		(this.sortables || []).forEach((s) => s.destroy());
		this.sortables = [];
		this.$plan.find(".cp-members").each((_i, el) => {
			this.sortables.push(
				new Sortable(el, {
					group: "cohort-planner",
					animation: 120,
					onEnd: (evt) => this.moved(evt),
				})
			);
		});
	}

	moved(evt) {
		const person = evt.item.dataset.person;
		const from = this.bucket(evt.from.dataset.group);
		const to = this.bucket(evt.to.dataset.group);
		if (!person || !from || !to || from === to) return;

		const idx = from.members.findIndex((m) => m.person === person);
		if (idx === -1) return;
		const [member] = from.members.splice(idx, 1);

		// A drag that breaks a Filter warns and proceeds: overriding the
		// school's rule in one case is exactly the control being retained. What
		// it must not do is keep claiming a rule chose this.
		if (
			to.key !== UNPLACED &&
			!(this.plan.shortlists[person] || []).includes(to.key)
		) {
			frappe.show_alert({
				message: __("{0} does not match {1} under the rules you chose.", [
					member.student_name || person,
					to.mentor_name || to.mentor,
				]),
				indicator: "orange",
			});
		}
		delete member.placed_by_rule;
		delete member._home;
		if (to.key === UNPLACED) {
			member.reason = __("Set aside by hand.");
		} else {
			delete member.reason;
		}
		to.members.push(member);
		this.touched = true;
		this.renderPlan();
	}

	// ------------------------------------------------------------------ create

	create() {
		const groups = this.plan.groups
			.filter((g) => g.members.length)
			.map((g) => ({
				name: g.suggested_name,
				mentor: g.mentor,
				members: g.members.map((m) => ({
					person: m.person,
					placed_by_rule: m.placed_by_rule,
				})),
			}));
		if (!groups.length) {
			frappe.msgprint(__("Every proposed cohort is empty, so there is nothing to create."));
			return;
		}
		const students = groups.reduce((n, g) => n + g.members.length, 0);

		frappe.confirm(
			__("Create {0} cohorts and place {1} students? Members are added straight away, not invited.", [
				groups.length,
				students,
			]),
			() => {
				frappe
					.call({
						method: "seminary.seminary.discipleship.planner.create_cohorts",
						args: {
							cohort_type: this.plan.cohort_type,
							groups: JSON.stringify(groups),
						},
						freeze: true,
						freeze_message: __("Creating cohorts..."),
					})
					.then((r) => this.created(r.message));
			}
		);
	}

	created(result) {
		if (!result) return;
		// The exceptions come from what was actually written, not from what this
		// page thought it was sending.
		const over = result.over_capacity || [];
		let message = __("{0} cohorts created.", [result.created.length]);
		if (over.length) {
			message +=
				"<br><br>" +
				__("These mentors are now past the capacity recorded for them. Confirm the exception with each of them, or raise their capacity in the Academic Unit:") +
				"<ul>" +
				over
					.map(
						(o) =>
							`<li>${frappe.utils.escape_html(o.mentor_name)} — ${__("{0} of {1}", [
								o.current_students,
								o.max_students,
							])}</li>`
					)
					.join("") +
				"</ul>";
		}
		frappe.msgprint({ title: __("Cohorts Created"), message, indicator: "green" });
		this.plan = null;
		this.$plan.empty();
		this.loadSetup(this.setup.cohort_type);
	}
}
