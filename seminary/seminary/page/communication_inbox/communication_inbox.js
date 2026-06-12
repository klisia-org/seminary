frappe.pages["communication-inbox"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Communication Inbox"),
		single_column: true,
	});
	new CommunicationInbox(page);
};

class CommunicationInbox {
	constructor(page) {
		this.page = page;
		this.scope = "all";
		this.active = null; // active person
		this.inReplyTo = null; // latest inbound log in the open thread
		this.injectStyles();
		this.render();
		this.loadConversations();

		this.page.set_primary_action(__("New Message"), () => this.compose(), "add");
		this.page.set_secondary_action(__("Refresh"), () => this.loadConversations());
		this.scopeField = this.page.add_select(__("Show"), [
			{ label: __("All"), value: "all" },
			{ label: __("Unread"), value: "unread" },
		]);
		this.scopeField.val("all").on("change", (e) => {
			this.scope = e.target.value;
			this.loadConversations();
		});
	}

	compose(person) {
		const dialog = new frappe.ui.Dialog({
			title: __("New Message"),
			fields: [
				{
					fieldname: "person",
					fieldtype: "Link",
					options: "Person",
					label: __("To (Person)"),
					reqd: 1,
					default: person || undefined,
				},
				{
					fieldname: "channel",
					fieldtype: "Select",
					label: __("Channel"),
					options: ["In-App", "Email", "SMS", "WhatsApp", "Telegram"].join("\n"),
					default: "In-App",
					reqd: 1,
				},
				{ fieldname: "subject", fieldtype: "Data", label: __("Subject") },
				{
					fieldname: "message",
					fieldtype: "Text Editor",
					label: __("Message"),
					reqd: 1,
				},
			],
			primary_action_label: __("Send"),
			primary_action: (values) => {
				frappe.call({
					method: "seminary.seminary.comms.compose_communication",
					args: {
						person: values.person,
						channel: values.channel,
						subject: values.subject,
						message: values.message,
					},
					freeze: true,
					freeze_message: __("Sending…"),
					callback: () => {
						dialog.hide();
						frappe.show_alert({
							message: __("Message sent."),
							indicator: "green",
						});
						this.loadConversations();
						this.openConversation(values.person);
					},
				});
			},
		});
		dialog.show();
	}

	render() {
		this.page.main.html(`
			<div class="ci-wrap">
				<div class="ci-list"><div class="ci-empty">${__("Loading…")}</div></div>
				<div class="ci-thread">
					<div class="ci-thread-empty text-muted">${__("Select a conversation.")}</div>
				</div>
			</div>
		`);
		this.$list = this.page.main.find(".ci-list");
		this.$thread = this.page.main.find(".ci-thread");
	}

	loadConversations() {
		frappe.call({
			method: "seminary.seminary.comms.get_inbox_conversations",
			args: { scope: this.scope },
			callback: (r) => this.renderConversations(r.message || []),
		});
	}

	renderConversations(rows) {
		if (!rows.length) {
			this.$list.html(`<div class="ci-empty text-muted">${__("Nothing here.")}</div>`);
			return;
		}
		this.$list.empty();
		rows.forEach((c) => {
			const unread = c.unread
				? `<span class="ci-badge">${c.unread}</span>`
				: "";
			const item = $(`
				<div class="ci-item ${c.person === this.active ? "active" : ""}" data-person="${frappe.utils.escape_html(c.person)}">
					<div class="ci-item-top">
						<span class="ci-name">${frappe.utils.escape_html(c.person_name)}</span>
						${unread}
					</div>
					<div class="ci-snippet text-muted">
						${c.last_mine ? "" : "↩ "}${frappe.utils.escape_html(c.snippet || "")}
					</div>
					<div class="ci-meta text-muted">${c.last_channel || ""} · ${frappe.datetime.comment_when(c.last_at)}</div>
				</div>
			`);
			item.on("click", () => this.openConversation(c.person));
			this.$list.append(item);
		});
	}

	openConversation(person) {
		this.active = person;
		this.$list.find(".ci-item").removeClass("active");
		this.$list.find(`.ci-item[data-person="${CSS.escape(person)}"]`).addClass("active");
		frappe.call({
			method: "seminary.seminary.comms.get_conversation",
			args: { person },
			callback: (r) => {
				this.renderThread(r.message);
				// opening triages the inbound messages
				frappe.call({
					method: "seminary.seminary.comms.mark_conversation_read",
					args: { person },
					callback: () => this.loadConversations(),
				});
			},
		});
	}

	renderThread(data) {
		const msgs = data.messages || [];
		this.inReplyTo = null;
		for (let i = msgs.length - 1; i >= 0; i--) {
			if (!msgs[i].mine) {
				this.inReplyTo = msgs[i].name;
				break;
			}
		}
		const bubbles = msgs
			.map((m) => {
				const meta = `${m.channel} · ${frappe.datetime.str_to_user(m.creation)}${
					m.status ? " · " + m.status : ""
				}`;
				return `
				<div class="ci-row ${m.mine ? "out" : "in"}">
					<div class="ci-bubble">
						${m.subject ? `<div class="ci-subj">${frappe.utils.escape_html(m.subject)}</div>` : ""}
						<div class="ci-body">${m.message || ""}</div>
						<div class="ci-bmeta text-muted">${frappe.utils.escape_html(meta)}</div>
					</div>
				</div>`;
			})
			.join("");
		this.$thread.html(`
			<div class="ci-thead">${frappe.utils.escape_html(data.person_name)}</div>
			<div class="ci-msgs">${bubbles || `<div class="text-muted">${__("No messages.")}</div>`}</div>
			<div class="ci-reply">
				<textarea class="form-control ci-reply-text" rows="2" placeholder="${__("Write a reply…")}"></textarea>
				<button class="btn btn-primary btn-sm ci-reply-send">${__("Reply")}</button>
			</div>
		`);
		const $msgs = this.$thread.find(".ci-msgs");
		$msgs.scrollTop($msgs[0].scrollHeight);
		this.$thread.find(".ci-reply-send").on("click", () => this.sendReply(data.person));
	}

	sendReply(person) {
		const $text = this.$thread.find(".ci-reply-text");
		const message = ($text.val() || "").trim();
		if (!message) return;
		this.$thread.find(".ci-reply-send").prop("disabled", true);
		frappe.call({
			method: "seminary.seminary.comms.reply_in_conversation",
			args: { person, message, in_reply_to: this.inReplyTo },
			callback: (r) => {
				$text.val("");
				this.openConversation(person);
				if (r.message && r.message.channel) {
					frappe.show_alert({
						message: __("Reply sent via {0}.", [r.message.channel]),
						indicator: "green",
					});
				}
			},
			always: () => this.$thread.find(".ci-reply-send").prop("disabled", false),
		});
	}

	injectStyles() {
		if (document.getElementById("ci-styles")) return;
		$(`<style id="ci-styles">
			.ci-wrap { display: flex; height: calc(100vh - 160px); border: 1px solid var(--border-color); border-radius: var(--border-radius-md); overflow: hidden; }
			.ci-list { width: 300px; border-right: 1px solid var(--border-color); overflow-y: auto; background: var(--fg-color); }
			.ci-thread { flex: 1; display: flex; flex-direction: column; min-width: 0; }
			.ci-item { padding: 10px 12px; border-bottom: 1px solid var(--border-color); cursor: pointer; }
			.ci-item:hover { background: var(--bg-color); }
			.ci-item.active { background: var(--bg-light-gray); }
			.ci-item-top { display: flex; justify-content: space-between; align-items: center; }
			.ci-name { font-weight: 600; }
			.ci-badge { background: var(--red-500, #e24c4c); color: #fff; border-radius: 10px; padding: 0 7px; font-size: 11px; font-weight: 600; }
			.ci-snippet, .ci-meta { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
			.ci-meta { margin-top: 2px; font-size: 11px; }
			.ci-empty { padding: 16px; }
			.ci-thead { padding: 10px 14px; border-bottom: 1px solid var(--border-color); font-weight: 600; }
			.ci-msgs { flex: 1; overflow-y: auto; padding: 14px; background: var(--bg-color); }
			.ci-row { display: flex; margin-bottom: 10px; }
			.ci-row.in { justify-content: flex-start; }
			.ci-row.out { justify-content: flex-end; }
			.ci-bubble { max-width: 70%; padding: 8px 12px; border-radius: 10px; background: var(--fg-color); border: 1px solid var(--border-color); }
			.ci-row.out .ci-bubble { background: var(--bg-blue, #e7f0ff); }
			.ci-subj { font-weight: 600; margin-bottom: 3px; }
			.ci-body img { max-width: 100%; height: auto; }
			.ci-bmeta { font-size: 11px; margin-top: 4px; }
			.ci-reply { padding: 10px; border-top: 1px solid var(--border-color); display: flex; gap: 8px; align-items: flex-end; }
			.ci-reply-text { flex: 1; }
		</style>`).appendTo(document.head);
	}
}
