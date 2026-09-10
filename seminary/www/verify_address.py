import frappe

from seminary.seminary.address_verification import apply_token


def get_context(context):
    """Confirm a channel address from the link in its confirmation mail
    (ADR 070).

    Guest-reachable on purpose. The mail is opened in a mail client with no
    portal session, often on a different device, and the address being
    confirmed is frequently not the person's login email — so requiring a
    session would be both a dead end and a leak, since Frappe's login redirect
    would carry the token through `redirect-to`. The token is the
    authorization, and it names one address on one Person.
    """
    context.no_cache = 1
    context.title = frappe._("Confirm your address")

    result = apply_token((frappe.form_dict.get("t") or "").strip())
    context.state = result["state"]
    context.address = result.get("value")
    context.channel = result.get("channel")

    # Every outcome is a plain sentence: a second click is not an error, and a
    # token for an address that has since been removed is not one either.
    context.headline, context.detail = {
        "confirmed": (
            frappe._("Address confirmed"),
            frappe._(
                "Thank you. We can now use this address, and you can choose to "
                "show it in the alumni directory from your portal preferences."
            ),
        ),
        "already": (
            frappe._("Already confirmed"),
            frappe._("This address was confirmed earlier. There is nothing to do."),
        ),
        "expired": (
            frappe._("This link has expired"),
            frappe._(
                "Confirmation links are valid for a short time. Open Preferences "
                "in the portal and send yourself a new one."
            ),
        ),
        "gone": (
            frappe._("That address is no longer on file"),
            frappe._(
                "It looks like this address was changed or removed after the "
                "confirmation was sent. You can add it again from Preferences."
            ),
        ),
        "invalid": (
            frappe._("This link is not valid"),
            frappe._(
                "The link may have been broken by your mail program. Try copying "
                "the whole address from the message, or send yourself a new "
                "confirmation from Preferences."
            ),
        ),
    }[result["state"]]

    return context
