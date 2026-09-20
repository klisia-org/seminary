"""p008a G6: call every endpoint still in PENDING_CLASSIFICATION and record what
a Student, a staff user and a Guest actually get.

The whitelist walk already does this for STAFF_ONLY (call it, expect
PermissionError for a student, no PermissionError for a chair). This runs the
same probe over the untriaged set so the classification is made from behaviour,
not from reading a gate and hoping.

Dummy arguments only ("ZZT-no-such"), so an endpoint that reaches its body
fails on a missing record. Endpoints that would do real work with no arguments
are skipped by name -- see SKIP.

    bench --site testable.localhost execute \
        seminary.scripts.p008a_validation.probe_pending.main

or, from a bench console:  from ... import main; main()
"""

import ast
import inspect
import io
import os
import traceback
from contextlib import redirect_stdout

import frappe

HERE = os.path.dirname(os.path.abspath(__file__))
WALK = os.path.join(
    HERE, "..", "..", "seminary", "seminary", "tests", "test_p007_whitelist_walk.py"
)

# Destructive or side-effecting with no arguments to stop them: never probed.
SKIP = {
    "seminary.demo.install_demo",
    "seminary.demo.remove_demo",
    "seminary.storage.api.selftest",
    "seminary.seminary.doctype.seminary_settings.seminary_settings.check_payments_app",
    "seminary.seminary.doctype.address_geocoding_settings.address_geocoding_settings.test_connection",
    "seminary.seminary.integrations.bible.test_connection",
    "seminary.seminary.integrations.pexels.test_connection",
    "seminary.seminary.doctype.partner_seminary_course_equivalence."
    "partner_seminary_course_equivalence.create_legacy_integration",
    "seminary.utils.create_student_groups",
    # reach an external API or send a real message; the gate, not the call, is
    # what is under test and reading it is cheaper than a network round trip
    "seminary.seminary.integrations.bible.lookup",
    "seminary.seminary.integrations.bible.passage_text",
    "seminary.seminary.integrations.bible.get_bible_name",
    "seminary.seminary.integrations.bible.list_bibles",
    "seminary.seminary.integrations.bible.get_available_bibles_for_user",
    "seminary.seminary.integrations.pexels.search_photos",
    "seminary.seminary.integrations.pexels.download_photo",
    "seminary.seminary.integrations.geocoding.geocode_now",
    "seminary.seminary.address_verification.request_verification",
    "seminary.seminary.telegram_adapter.register_webhook",
    "seminary.seminary.comms.send_portal_message",
    "seminary.seminary.comms.reply_portal_message",
    "seminary.seminary.comms.contact_instructor",
    "seminary.seminary.discipleship.api.broadcast_to_leaders",
    "seminary.seminary.discipleship.api.resend_invite",
    "seminary.alumni.api.send_directory_message",
}

KWARG_OVERRIDES = {}


def pending():
    tree = ast.parse(open(WALK).read())
    for n in tree.body:
        if (
            isinstance(n, ast.Assign)
            and getattr(n.targets[0], "id", "") == "PENDING_CLASSIFICATION"
        ):
            return set(ast.literal_eval(n.value))
    return set()


def _import_all():
    import importlib
    import pkgutil

    import seminary

    for info in pkgutil.walk_packages(seminary.__path__, prefix="seminary."):
        name = info.name
        leaf = name.rsplit(".", 1)[-1]
        if ".tests" in name or leaf.startswith("test_"):
            continue
        try:
            importlib.import_module(name)
        except Exception:  # noqa: BLE001
            pass


def _walk():
    _import_all()
    out = {}
    for fn in frappe.whitelisted:
        mod = getattr(fn, "__module__", "") or ""
        if mod.startswith("seminary."):
            out[f"{mod}.{fn.__name__}"] = fn
    return out


def _kwargs(fn, dotted):
    kw = {}
    for name, p in inspect.signature(fn).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.default is inspect.Parameter.empty:
            kw[name] = "ZZT-no-such"
    kw.update(KWARG_OVERRIDES.get(dotted, {}))
    return kw


def _user(role, tag):
    email = f"zzt-g6-{tag}@example.com"
    if not frappe.db.exists("User", email):
        u = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "G6",
                "last_name": tag,
                "send_welcome_email": 0,
            }
        )
        u.flags.ignore_permissions = True
        u.insert(ignore_permissions=True)
    doc = frappe.get_doc("User", email)
    for r in role:
        if not any(x.role == r for x in doc.roles):
            doc.add_roles(r)
    return email


def probe(fn, dotted, who):
    frappe.set_user(who)
    try:
        with redirect_stdout(io.StringIO()):
            fn(**_kwargs(fn, dotted))
        return "OK"
    except frappe.PermissionError:
        return "PermissionError"
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__
        if name in ("DoesNotExistError", "LinkValidationError", "ValidationError"):
            return name
        return f"{name}: {str(e)[:60]}"
    finally:
        frappe.set_user("Administrator")


def main():
    student = _user(["Student"], "student")
    staff = _user(["Program Chair", "Registrar", "Seminary Manager"], "staff")
    found = _walk()
    frappe.db.commit()

    rows = []
    for dotted in sorted(pending()):
        fn = found.get(dotted)
        if fn is None:
            rows.append((dotted, "-", "NOT-WHITELISTED", "-"))
            continue
        if dotted in SKIP:
            rows.append((dotted, "-", "SKIPPED", "-"))
            continue
        guest = "guest-ok" if fn in frappe.guest_methods else ""
        try:
            s = probe(fn, dotted, student)
        except Exception as e:  # noqa: BLE001
            s = "PROBE-FAILED: " + type(e).__name__
        try:
            c = probe(fn, dotted, staff)
        except Exception as e:  # noqa: BLE001
            c = "PROBE-FAILED: " + type(e).__name__
        rows.append((dotted, guest, s, c))
        frappe.db.rollback()

    print("dotted\tguest\tstudent\tstaff")
    for r in rows:
        print("\t".join(r))
    print("\n-- traceback sink --")
    return rows


if __name__ == "__main__":
    traceback  # noqa: B018
