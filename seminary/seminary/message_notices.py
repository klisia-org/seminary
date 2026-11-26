"""Email notices for unread portal messages (decisions/121 §1, §2).

A person-to-person In-App message is marked ``notify_if_unread``. When the oldest
unannounced unread one a person has is 15 minutes old, one email tells them
about all of their unannounced unread messages, and each message records that
notice in ``unread_notice``. A message read first is never announced, and the
notice never carries what the messages say.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, get_url, now_datetime

from seminary.seminary.web_push import INBOX_PATH

TEMPLATE = "portal-message-notice"
WINDOW_MINUTES = 15
MAX_NAMED_SENDERS = 3


def _pending():
	return frappe.db.sql(
		"""
        SELECT name, person, triggered_by, creation
        FROM `tabCommunication Log`
        WHERE notify_if_unread = 1
          AND channel = 'In-App'
          AND direction = 'Outbound'
          AND read_at IS NULL
          AND IFNULL(unread_notice, '') = ''
          AND status IN ('Sent', 'Delivered')
          AND person IS NOT NULL
        ORDER BY creation ASC
        """,
		as_dict=True,
	)


def _senders(users):
	names = []
	for user in dict.fromkeys(u for u in users if u):
		names.append(frappe.db.get_value("User", user, "full_name") or user)
	if len(names) > MAX_NAMED_SENDERS:
		shown = ", ".join(names[:MAX_NAMED_SENDERS])
		return _("{0} and {1} others").format(shown, len(names) - MAX_NAMED_SENDERS)
	return ", ".join(names)


def send_unread_notices():
	"""Cron: one email per person whose oldest unannounced unread message has
	waited the full window."""
	from seminary.seminary import comms

	if not frappe.db.exists("Communication Template", TEMPLATE):
		return
	cutoff = add_to_date(now_datetime(), minutes=-WINDOW_MINUTES)
	by_person = {}
	for row in _pending():
		by_person.setdefault(row.person, []).append(row)

	for person, rows in by_person.items():
		if rows[0].creation > cutoff:
			continue  # the window has not closed yet
		key = f"unread-notice::{rows[0].name}"
		try:
			notice = comms.send(
				person,
				TEMPLATE,
				channel=comms.EMAIL_CHANNEL,
				category="Community",
				context={
					"count": len(rows),
					"senders": _senders(r.triggered_by for r in rows),
					"url": get_url(INBOX_PATH),
				},
				triggered_by="Administrator",
				dedupe_key=key,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Unread message notice for {person} failed")
			continue
		# A consent-blocked notice is still a notice: the person chose not to
		# get it, and asking again every five minutes would not change that.
		notice = notice or frappe.db.get_value("Communication Log", {"idempotency_key": key}, "name")
		if not notice:
			continue
		frappe.db.set_value(
			"Communication Log",
			{"name": ("in", [r.name for r in rows])},
			"unread_notice",
			notice,
			update_modified=False,
		)
