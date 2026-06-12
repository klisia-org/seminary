def get_notification_config():
    """Desk notification badges (navbar bell + sidebar count). Inbound
    communications awaiting staff triage drive the Communication Log badge — the
    desk counterpart of the portal inbox unread count (ADR 046)."""
    return {
        "for_doctype": {
            "Communication Log": {
                "direction": "Inbound",
                "read_at": ["is", "not set"],
            },
        },
    }
