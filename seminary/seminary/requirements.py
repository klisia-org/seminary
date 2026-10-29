# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Agreements and required documents for students and instructors (ADR 091).

A Requirement Rule (on Program, or on Seminary Settings for instructors) says
what a role must sign or upload. A Person Requirement is one thing one person
owes, for one Program Enrollment or Instructor record. Its status is derived
from the record that satisfies it -- an Accepted Person Document of the right
type, or a Signed Agreement made for it -- and recomputed whenever that record
changes, never typed in.

Portal reads and writes go through the whitelisted functions below, which find
the caller's own Person and check the row is theirs before writing with
ignore_permissions.
"""

import hashlib
import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import (
    add_days,
    add_months,
    cint,
    escape_html,
    format_datetime,
    formatdate,
    get_datetime,
    getdate,
    now_datetime,
    today,
)

from seminary.seminary.guards import SCHOOL_ROLES, _deny, _roles, require_registrar

OPEN = ("Pending", "Submitted")
NOT_RENEWED = "Not needed"
SUBJECTS = ("Program Enrollment", "Instructor")
# Other apps' records a Person can owe requirements for (ADR 092).
SUBJECT_HOOK = "requirement_subjects"
RULE_FIELDS = (
    "kind",
    "agreement_template",
    "document_type",
    "blocking",
    "due_days",
    "renewal",
    "instructions",
)
# A drawn signature is a PNG data URL; anything bigger than this is not a signature.
MAX_SIGNATURE_BYTES = 300_000
_PNG_DATA_URL = re.compile(r"^data:image/png;base64,[A-Za-z0-9+/]+={0,2}$")
# Where `{{ signature }}` / `{{ countersignature }}` landed in the rendered text.
# The stored text keeps the empty lines the signer read; the PDFs fill them.
SLOTS = ("signature", "countersignature")


# --------------------------------------------------------------------------- #
# Who owes what
# --------------------------------------------------------------------------- #
def hooked_subjects():
    """{doctype: handler} from other apps' `requirement_subjects` hook. A handler
    has person(name), rules(name), label(name) and optionally active(). A doctype
    seminary handles itself, or one not installed, is skipped and logged."""
    subjects = {}
    for doctype, value in (frappe.get_hooks(SUBJECT_HOOK) or {}).items():
        path = value[-1] if isinstance(value, list) else value
        if doctype in SUBJECTS or not frappe.db.exists("DocType", doctype):
            frappe.logger("seminary").warning(
                f"requirement subject {doctype} ({path}) skipped"
            )
            continue
        subjects[doctype] = frappe.get_attr(path)
    return subjects


def _subject(reference_doctype):
    if reference_doctype in SUBJECTS:
        return None
    return hooked_subjects().get(reference_doctype)


def is_subject(reference_doctype):
    return reference_doctype in SUBJECTS or bool(_subject(reference_doctype))


def person_of(reference_doctype, reference_name):
    if reference_doctype == "Program Enrollment":
        student = frappe.db.get_value("Program Enrollment", reference_name, "student")
        return frappe.db.get_value("Student", student, "person") if student else None
    if reference_doctype == "Instructor":
        return frappe.db.get_value("Instructor", reference_name, "person")
    subject = _subject(reference_doctype)
    return subject.person(reference_name) if subject else None


def rules_for(reference_doctype, reference_name):
    """The rules that apply to a record now: the program's for an enrollment,
    Seminary Settings' for an instructor, the handler's for another app's record."""
    subject = _subject(reference_doctype)
    if subject:
        return subject.rules(reference_name) or []
    if reference_doctype == "Program Enrollment":
        program = frappe.db.get_value("Program Enrollment", reference_name, "program")
        if not program:
            return []
        parent, field = program, "enrollment_requirements"
        parenttype = "Program"
    else:
        parent, field, parenttype = (
            "Seminary Settings",
            "instructor_requirements",
            "Seminary Settings",
        )
    return frappe.get_all(
        "Requirement Rule",
        filters={"parent": parent, "parenttype": parenttype, "parentfield": field},
        fields=list(RULE_FIELDS),
        order_by="idx asc",
    )


def _current_period():
    """(term, year, term start, year start) for the current academic term."""
    from seminary.seminary.api import current_academic_term

    term = current_academic_term()
    if not term:
        return frappe._dict()
    t = frappe.db.get_value(
        "Academic Term",
        term,
        ["name", "academic_year", "term_start_date"],
        as_dict=True,
    )
    if not t:
        return frappe._dict()
    year_start = (
        frappe.db.get_value("Academic Year", t.academic_year, "year_start_date")
        if t.academic_year
        else None
    )
    return frappe._dict(
        term=t.name,
        year=t.academic_year,
        term_start=t.term_start_date,
        year_start=year_start,
    )


def _period_of(rule, period):
    """What a new row for `rule` covers: (academic_term, academic_year, start)."""
    if rule.renewal == "Every Academic Term" and period.get("term"):
        return period.term, period.year, period.term_start
    if rule.renewal == "Every Academic Year" and period.get("year"):
        return None, period.year, period.year_start
    return None, None, None


def _rule_key(rule):
    return {
        "kind": rule.kind,
        "agreement_template": (
            rule.agreement_template if rule.kind == "Agreement" else None
        ),
        "document_type": rule.document_type if rule.kind == "Document" else None,
    }


def ensure_requirements(reference_doctype, reference_name, rules=None, notify=True):
    """Add a row for each rule that has none yet for the current period.
    Returns the names of the rows created."""
    if not is_subject(reference_doctype):
        return []
    person = person_of(reference_doctype, reference_name)
    if not person:
        return []
    if rules is None:
        rules = rules_for(reference_doctype, reference_name)
    period = _current_period()
    created = []
    for rule in rules:
        rule = frappe._dict(rule)
        if not rule.kind or not (rule.agreement_template or rule.document_type):
            continue
        term, year, start = _period_of(rule, period)
        filters = {
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            **{k: v for k, v in _rule_key(rule).items() if v},
        }
        if rule.renewal == "Every Academic Term" and term:
            filters["academic_term"] = term
        elif rule.renewal == "Every Academic Year" and year:
            filters["academic_year"] = year
        if frappe.db.exists("Person Requirement", filters):
            continue
        start = getdate(start) if start else getdate(today())
        due_from = max(start, getdate(today()))
        doc = frappe.get_doc(
            {
                "doctype": "Person Requirement",
                "person": person,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                **{k: rule.get(k) for k in RULE_FIELDS},
                **_rule_key(rule),
                "renewal": rule.renewal or NOT_RENEWED,
                "start_date": start,
                "due_date": add_days(due_from, cint(rule.due_days)),
                "academic_term": (
                    term if rule.renewal == "Every Academic Term" else None
                ),
                "academic_year": year if rule.renewal != NOT_RENEWED else None,
            }
        )
        doc.insert(ignore_permissions=True)
        created.append(doc.name)
    if created and notify:
        _notify_opened(person, created)
    return created


def on_program_enrollment_submit(doc, method=None):
    # An imported enrollment is history: it opens nothing to chase (ADR 094 §1).
    if frappe.flags.in_import:
        return
    ensure_requirements("Program Enrollment", doc.name)


def on_instructor_update(doc, method=None):
    if doc.status == "Active" and doc.person:
        ensure_requirements("Instructor", doc.name)


@frappe.whitelist()
def add_missing_requirements(program):
    """Program button: give every active enrollment the program's rules it lacks."""
    require_registrar()
    rules = rules_for_program(program)
    count = 0
    for pe in frappe.get_all(
        "Program Enrollment",
        filters={"program": program, "docstatus": 1, "status": "Active"},
        pluck="name",
    ):
        count += len(ensure_requirements("Program Enrollment", pe, rules=rules))
    return count


def rules_for_program(program):
    return frappe.get_all(
        "Requirement Rule",
        filters={
            "parent": program,
            "parenttype": "Program",
            "parentfield": "enrollment_requirements",
        },
        fields=list(RULE_FIELDS),
        order_by="idx asc",
    )


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
def _satisfying_document(row, statuses):
    filters = {
        "person": row.person,
        "document_type": row.document_type,
        "status": ["in", statuses],
    }
    docs = frappe.get_all(
        "Person Document",
        filters=filters,
        fields=["name", "status", "valid_until", "submitted_on", "reviewed_on"],
        order_by="creation desc",
    )
    for d in docs:
        if (
            d.status == "Accepted"
            and d.valid_until
            and getdate(d.valid_until) < getdate(today())
        ):
            continue
        if row.renewal != NOT_RENEWED and row.start_date:
            when = d.reviewed_on if d.status == "Accepted" else d.submitted_on
            if not when or getdate(when) < getdate(row.start_date):
                continue
        return d
    return None


def compute_status(row):
    """(status, satisfied_by_doctype, satisfied_by) for a Person Requirement."""
    if row.status == "Waived":
        return "Waived", None, None
    if row.kind == "Agreement":
        sa = frappe.db.get_value(
            "Signed Agreement",
            {"person_requirement": row.name, "docstatus": 1},
            ["name", "status"],
            as_dict=True,
            order_by="creation desc",
        )
        if not sa:
            return "Pending", None, None
        if sa.status == "Complete":
            return "Satisfied", "Signed Agreement", sa.name
        return "Submitted", "Signed Agreement", sa.name
    doc = _satisfying_document(row, ["Accepted"])
    if doc:
        return "Satisfied", "Person Document", doc.name
    doc = _satisfying_document(row, ["Submitted"])
    if doc:
        return "Submitted", "Person Document", doc.name
    return "Pending", None, None


def recompute(name):
    row = frappe.get_doc("Person Requirement", name)
    status, by_type, by = compute_status(row)
    values = {"status": status, "satisfied_by_doctype": by_type, "satisfied_by": by}
    if any((row.get(k) or None) != (v or None) for k, v in values.items()):
        row.db_set(values, notify=True)
    return status


def recompute_documents(person, document_type):
    for name in frappe.get_all(
        "Person Requirement",
        filters={
            "person": person,
            "kind": "Document",
            "document_type": document_type,
            "status": ["!=", "Waived"],
        },
        pluck="name",
    ):
        recompute(name)


def is_overdue(row, on=None):
    return bool(
        row.status in OPEN
        and row.due_date
        and getdate(row.due_date) < getdate(on or today())
    )


def overdue_blocking(reference_doctype, reference_name, on=None):
    rows = frappe.get_all(
        "Person Requirement",
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "blocking": 1,
            "status": ["in", OPEN],
            "due_date": ["<", getdate(on or today())],
        },
        fields=[
            "name",
            "kind",
            "agreement_template",
            "document_type",
            "status",
            "due_date",
        ],
    )
    return rows


def label_of(row):
    return row.agreement_template if row.kind == "Agreement" else row.document_type


def assert_may_self_enroll(program_enrollment):
    """ADR 091 §9: an overdue blocking requirement stops course self-enrollment."""
    rows = overdue_blocking("Program Enrollment", program_enrollment)
    if rows:
        frappe.throw(
            _(
                "Before enrolling in courses, complete these overdue requirements on "
                "your Requirements page: {0}"
            ).format(", ".join(escape_html(label_of(r)) for r in rows)),
            title=_("Requirements overdue"),
        )


def overdue_labels(program_enrollment):
    return ", ".join(
        label_of(r) for r in overdue_blocking("Program Enrollment", program_enrollment)
    )


def warn_course_schedule_instructors(doc, method=None):
    """A warning, never a block, when an instructor with an overdue blocking
    requirement is put on a section (ADR 091 §9)."""
    before = doc.get_doc_before_save()
    had = {r.instructor for r in (before.get("instructor1") or [])} if before else set()
    added = [
        r.instructor
        for r in (doc.get("instructor1") or [])
        if r.instructor and r.instructor not in had
    ]
    lines = []
    for instructor in added:
        rows = overdue_blocking("Instructor", instructor)
        if rows:
            name = (
                frappe.db.get_value("Instructor", instructor, "instructor_name")
                or instructor
            )
            labels = ", ".join(escape_html(label_of(r)) for r in rows)
            lines.append(f"{escape_html(name)}: {labels}")
    if lines:
        frappe.msgprint(
            "<br>".join(lines),
            title=_("Instructor requirements overdue"),
            indicator="orange",
        )


@frappe.whitelist()
def waive_requirement(requirement, reason):
    require_registrar()
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("A waiver needs a reason."))
    row = frappe.get_doc("Person Requirement", requirement)
    row.db_set(
        {
            "status": "Waived",
            "waived_by": frappe.session.user,
            "waived_on": now_datetime(),
            "waiver_reason": reason,
            "satisfied_by_doctype": None,
            "satisfied_by": None,
        },
        notify=True,
    )
    return row.name


@frappe.whitelist()
def unwaive_requirement(requirement):
    require_registrar()
    row = frappe.get_doc("Person Requirement", requirement)
    if row.status != "Waived":
        return row.status
    row.db_set(
        {
            "status": "Pending",
            "waived_by": None,
            "waived_on": None,
            "waiver_reason": None,
        }
    )
    return recompute(row.name)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
def allowed_extensions(document_type):
    raw = (
        frappe.db.get_value("Document Type", document_type, "allowed_extensions") or ""
    )
    return [
        e.strip().lstrip(".").lower()
        for e in raw.replace(";", ",").split(",")
        if e.strip()
    ]


def check_extension(document_type, file_name):
    allowed = allowed_extensions(document_type)
    if not allowed:
        return
    ext = (
        (file_name or "").rsplit(".", 1)[-1].lower() if "." in (file_name or "") else ""
    )
    if ext not in allowed:
        frappe.throw(
            _("{0} must be one of these file types: {1}").format(
                escape_html(document_type), ", ".join(allowed)
            )
        )


def create_person_document(person, document_type, file_url, accepted=False, by=None):
    """A Person Document for `file_url`. Accepted at once when the type needs no
    review, or when `accepted` says the school already has it (the applicant patch)."""
    doc = frappe.get_doc(
        {
            "doctype": "Person Document",
            "person": person,
            "document_type": document_type,
            "file": file_url,
            "status": "Submitted",
            "submitted_on": now_datetime(),
        }
    )
    doc.insert(ignore_permissions=True)  # accepted here if the type needs no review
    if accepted:
        doc.accept(by=by or frappe.session.user)
    return doc


def _review_doc(person_document):
    require_registrar()
    return frappe.get_doc("Person Document", person_document)


@frappe.whitelist()
def accept_document(person_document, valid_until=None):
    doc = _review_doc(person_document)
    doc.accept(by=frappe.session.user, valid_until=valid_until)
    return doc.status


@frappe.whitelist()
def reject_document(person_document, reason):
    doc = _review_doc(person_document)
    doc.reject(reason, by=frappe.session.user)
    return doc.status


def expire_documents(on=None):
    on = getdate(on or today())
    for d in frappe.get_all(
        "Person Document",
        filters={"status": "Accepted", "valid_until": ["<", on]},
        fields=["name", "person", "document_type"],
    ):
        frappe.db.set_value("Person Document", d.name, "status", "Expired")
        recompute_documents(d.person, d.document_type)


# --------------------------------------------------------------------------- #
# Agreements
# --------------------------------------------------------------------------- #
def _escaped(value):
    if isinstance(value, str):
        return escape_html(value)
    if isinstance(value, dict):
        return frappe._dict({k: _escaped(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_escaped(v) for v in value]
    return value


def _as_dict(doctype, name, escape=True):
    """A record for the template. What a person typed is HTML-escaped, so a name
    cannot inject markup into the contract or the PDF renderer."""
    if not name or not frappe.db.exists(doctype, name):
        return frappe._dict()
    d = frappe._dict(frappe.get_doc(doctype, name).as_dict())
    return _escaped(d) if escape else d


def _doctrinal_statement(for_instructor):
    flag = "ds_instructor" if for_instructor else "use_in_student_admission"
    ds = frappe.db.get_value(
        "Doctrinal Statement",
        {"active": 1, "docstatus": 1, flag: 1},
        ["ds_title", "doctrinal_statement"],
        as_dict=True,
        order_by="creation desc",
    )
    if not ds:
        return frappe._dict(title="", body="")
    return frappe._dict(title=ds.ds_title, body=ds.doctrinal_statement)


def agreement_context(row):
    """What an Agreement Template's Jinja sees (ADR 091 §7)."""
    ctx = frappe._dict(
        person=_as_dict("Person", row.person),
        student=frappe._dict(),
        program=frappe._dict(),
        program_enrollment=frappe._dict(),
        instructor=frappe._dict(),
        school=frappe._dict(
            name=escape_html(
                frappe.db.get_single_value("Website Settings", "app_name")
                or frappe.db.get_single_value("System Settings", "app_name")
                or ""
            )
        ),
        today=formatdate(today()),
        format_date=formatdate,
        academic_term=row.academic_term or "",
        academic_year=row.academic_year or "",
    )
    if row.reference_doctype == "Program Enrollment":
        ctx.program_enrollment = _as_dict("Program Enrollment", row.reference_name)
        ctx.student = _as_dict(
            "Student",
            frappe.db.get_value("Program Enrollment", row.reference_name, "student"),
        )
        # Written by staff, and its rich-text fields are meant to render.
        ctx.program = _as_dict(
            "Program",
            frappe.db.get_value("Program Enrollment", row.reference_name, "program"),
            escape=False,
        )
    elif row.reference_doctype == "Instructor":
        ctx.instructor = _as_dict("Instructor", row.reference_name)
    # Another app's record gets none; its agreement_context adds the one it
    # wants (ADR 092 §4).
    ctx.doctrinal_statement = (
        _doctrinal_statement(row.reference_doctype == "Instructor")
        if row.reference_doctype in SUBJECTS
        else frappe._dict(title="", body="")
    )
    # Empty signature lines; the PDFs fill them (ADR 091 §8, amended).
    ctx.signature = _slot(
        "signature", frappe.db.get_value("Person", row.person, "full_name") or ""
    )
    ctx.countersignature = _slot("countersignature", ctx.school.name, escaped=True)
    # oikonomos / tamias add fees and payment plans here, so seminary never names
    # a billing doctype.
    for path in frappe.get_hooks("agreement_context"):
        frappe.get_attr(path)(ctx, row)
    return ctx


def _line(top, caption):
    return (
        "<span style='display:inline-block;min-width:260px;margin:12px 24px 0 0;"
        "vertical-align:bottom'>"
        f"{top}<span style='display:block;border-top:1px solid #333;padding-top:2px;"
        f"font-size:9pt'>{caption}</span></span>"
    )


def _slot(name, label, escaped=False):
    caption = label if escaped else escape_html(label or "")
    body = _line("<span style='display:block;height:60px'></span>", caption)
    return f"<!--slot:{name}-->{body}<!--/slot:{name}-->"


def _signed_line(name, when, image=None):
    if image and _PNG_DATA_URL.match(image):
        top = f"<img src='{image}' style='display:block;height:60px'>"
    else:
        top = "<span style='display:block;height:60px'></span>"
    caption = "{0}<br>{1}".format(
        escape_html(name or ""),
        escape_html(_("Signed electronically on {0}").format(format_datetime(when))),
    )
    return _line(top, caption)


def fill_slots(html, **filled):
    """Put each signer's line where the template asked for it."""
    for name, line in filled.items():
        html = re.sub(
            rf"<!--slot:{name}-->.*?<!--/slot:{name}-->",
            lambda _m, line=line: line,
            html,
            flags=re.S,
        )
    return html


def current_version(template):
    t = frappe.get_doc("Agreement Template", template)
    if not t.versions:
        frappe.throw(_("Agreement Template {0} has no text yet.").format(template))
    v = t.versions[-1]
    return t, v


def render_agreement(row):
    template, version = current_version(row.agreement_template)
    html = frappe.render_template(
        version.body or "", agreement_context(row), restrict_globals=True
    )
    return template, version, html


def _letterhead():
    name = frappe.db.get_single_value("Seminary Settings", "letterhead")
    if not name:
        return None
    return frappe.db.get_value("Letter Head", name, ["content", "footer"], as_dict=True)


def _evidence_html(rows):
    cells = "".join(
        f"<tr><th style='text-align:left;padding:2px 8px 2px 0'>{escape_html(k)}</th>"
        f"<td style='padding:2px 0'>{escape_html(str(v or ''))}</td></tr>"
        for k, v in rows
    )
    return f"<table style='font-size:9pt;border-collapse:collapse'>{cells}</table>"


def _pdf(title, html, evidence_blocks):
    from frappe.utils.pdf import get_pdf

    from seminary.seminary import comms
    from seminary.seminary.doctype.seminary_announcement.seminary_announcement import (
        _wrap_letterhead,
    )

    evidence = "".join(
        f"<div style='margin-top:16px;border-top:1px solid #999;padding-top:8px'>"
        f"<p style='font-size:9pt;margin:0 0 4px'><b>{escape_html(heading)}</b></p>"
        f"{_evidence_html(rows)}</div>"
        for heading, rows in evidence_blocks
    )
    page = f"<h2>{escape_html(title)}</h2>{html}{evidence}"
    return get_pdf(comms.pdf_html(_wrap_letterhead(_letterhead(), page)))


def _save_pdf(content, doc, fieldname, suffix):
    from frappe.utils.file_manager import save_file

    f = save_file(
        f"{doc.name}-{suffix}.pdf",
        content,
        doc.doctype,
        doc.name,
        is_private=1,
        df=fieldname,
    )
    return f.file_url


def _sha256(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def _request_evidence():
    request = getattr(frappe.local, "request", None)
    agent = request.headers.get("User-Agent") if request else None
    return getattr(frappe.local, "request_ip", None) or "", (agent or "")[:500]


def _signer_evidence(heading, name, user, when, ip, agent, extra=()):
    return (
        heading,
        [
            (_("Name typed"), name),
            (_("User"), user),
            (_("Date and time"), format_datetime(when)),
            (_("IP address"), ip),
            (_("Browser"), agent),
            *extra,
        ],
    )


def sign(row, signer_name, signature=None):
    """Make, file and submit the Signed Agreement for `row`."""
    template, version, html = render_agreement(row)
    ip, agent = _request_evidence()
    when = now_datetime()
    sa = frappe.get_doc(
        {
            "doctype": "Signed Agreement",
            "person_requirement": row.name,
            "person": row.person,
            "agreement_template": template.name,
            "template_version": version.version,
            "reference_doctype": row.reference_doctype,
            "reference_name": row.reference_name,
            "status": (
                "Awaiting Countersignature" if template.countersign_role else "Complete"
            ),
            "rendered_html": html,
            "html_sha256": _sha256(html),
            "signed_on": when,
            "signed_by": frappe.session.user,
            "signer_name": signer_name,
            "ip_address": ip,
            "user_agent": agent,
            "signature": signature or None,
        }
    )
    sa.insert(ignore_permissions=True)
    evidence = _signer_evidence(
        _("Signed electronically"),
        signer_name,
        frappe.session.user,
        when,
        ip,
        agent,
        extra=(
            (_("Agreement"), f"{template.title} v{version.version} ({sa.name})"),
            (_("Text SHA-256"), sa.html_sha256),
        ),
    )
    signed = fill_slots(html, signature=_signed_line(signer_name, when, signature))
    content = _pdf(template.title, signed, [evidence])
    sa.pdf = _save_pdf(content, sa, "pdf", "signed")
    sa.pdf_sha256 = _sha256(content)
    sa.flags.ignore_permissions = True
    sa.submit()
    return sa


def countersign_agreement(sa, signer_name, signature=None):
    template = frappe.get_doc("Agreement Template", sa.agreement_template)
    ip, agent = _request_evidence()
    when = now_datetime()
    first = _signer_evidence(
        _("Signed electronically"),
        sa.signer_name,
        sa.signed_by,
        get_datetime(sa.signed_on),
        sa.ip_address,
        sa.user_agent,
        extra=(
            (_("Agreement"), f"{template.title} v{sa.template_version} ({sa.name})"),
            (_("Text SHA-256"), sa.html_sha256),
            (_("Signed PDF SHA-256"), sa.pdf_sha256),
        ),
    )
    second = _signer_evidence(
        _("Countersigned electronically"),
        signer_name,
        frappe.session.user,
        when,
        ip,
        agent,
    )
    text = fill_slots(
        sa.rendered_html,
        signature=_signed_line(
            sa.signer_name, get_datetime(sa.signed_on), sa.signature
        ),
        countersignature=_signed_line(signer_name, when, signature),
    )
    content = _pdf(template.title, text, [first, second])
    sa.countersignature = signature or None
    sa.countersigned_on = when
    sa.countersigned_by = frappe.session.user
    sa.countersigner_name = signer_name
    sa.countersign_ip = ip
    sa.countersign_user_agent = agent
    sa.final_pdf = _save_pdf(content, sa, "final_pdf", "final")
    sa.final_pdf_sha256 = _sha256(content)
    sa.status = "Complete"
    sa.flags.ignore_permissions = True
    sa.save()
    return sa


@frappe.whitelist()
def countersign(signed_agreement, signer_name, signature=None):
    require_registrar()
    sa = frappe.get_doc("Signed Agreement", signed_agreement)
    if sa.docstatus != 1 or sa.status != "Awaiting Countersignature":
        frappe.throw(_("This agreement is not waiting for a countersignature."))
    role = frappe.db.get_value(
        "Agreement Template", sa.agreement_template, "countersign_role"
    )
    if role and role not in _roles() and "System Manager" not in _roles():
        _deny(
            _("Only someone with the {0} role can countersign this agreement.").format(
                _(role)
            ),
            "requirements.countersign",
        )
    signer_name = _clean_name(signer_name)
    _check_signature(signature)
    countersign_agreement(sa, signer_name, signature)
    return sa.status


def _check_signature(signature):
    if signature and (
        len(signature) > MAX_SIGNATURE_BYTES or not _PNG_DATA_URL.match(signature)
    ):
        frappe.throw(
            _("The drawn signature could not be read. Clear it and draw again.")
        )


def _clean_name(name):
    name = " ".join((name or "").split())
    if len(name) < 3:
        frappe.throw(_("Type your full name to sign."))
    return name[:140]


# --------------------------------------------------------------------------- #
# Notices
# --------------------------------------------------------------------------- #
def _notify(person, key, subject, message, reference_name=None):
    from seminary.seminary import comms

    p = frappe.db.get_value(
        "Person", person, ["name", "user", "primary_email"], as_dict=True
    )
    if not p:
        return
    common = {
        "subject": subject,
        "message": message,
        "person": p.name,
        "category": "Transactional",
        "reference_doctype": "Person Requirement" if reference_name else None,
        "reference_name": reference_name,
    }
    try:
        if p.user:
            comms.send_message(channel="In-App", dedupe_key=f"{key}-app", **common)
        if p.primary_email:
            comms.send_message(
                channel="Email",
                to_address=p.primary_email,
                dedupe_key=f"{key}-email",
                **common,
            )
    except Exception:  # noqa: BLE001 -- a notice must never undo the work it reports
        frappe.log_error(frappe.get_traceback(), "requirement notice failed")


def _page_link():
    return frappe.utils.get_url("/seminary/requirements")


def _notify_opened(person, names):
    rows = frappe.get_all(
        "Person Requirement",
        filters={"name": ["in", names]},
        fields=["name", "kind", "agreement_template", "document_type", "due_date"],
    )
    items = "".join(
        f"<li>{escape_html(label_of(r))} ({_('due {0}').format(formatdate(r.due_date))})</li>"
        for r in rows
    )
    _notify(
        person,
        f"req-open-{names[0]}",
        _("Documents to sign or upload"),
        _("Your school asks you to complete:")
        + f"<ul>{items}</ul>"
        + f'<a href="{_page_link()}">{_("Open your requirements")}</a>',
        reference_name=names[0],
    )


def notify_rejected(doc):
    _notify(
        doc.person,
        f"req-rejected-{doc.name}",
        _("Please upload {0} again").format(doc.document_type),
        _("Your school could not accept the {0} you uploaded: {1}").format(
            escape_html(doc.document_type), escape_html(doc.rejection_reason or "")
        )
        + f'<br><a href="{_page_link()}">{_("Upload it again")}</a>',
    )


def notify_due(on=None):
    """One notice on each open row's due date."""
    on = getdate(on or today())
    sent = 0
    for r in frappe.get_all(
        "Person Requirement",
        filters={"status": ["in", OPEN], "due_date": on},
        fields=[
            "name",
            "person",
            "kind",
            "agreement_template",
            "document_type",
            "status",
        ],
    ):
        if r.status == "Submitted":
            continue  # waiting on the school, not on the person
        _notify(
            r.person,
            f"req-due-{r.name}",
            _("{0} is due today").format(label_of(r)),
            _("{0} is due today.").format(escape_html(label_of(r)))
            + f' <a href="{_page_link()}">{_("Open your requirements")}</a>',
            reference_name=r.name,
        )
        sent += 1
    return sent


# --------------------------------------------------------------------------- #
# Daily
# --------------------------------------------------------------------------- #
def daily():
    expire_documents()
    sweep()
    notify_due()


def sweep():
    """Instructors read Seminary Settings every day, so a rule added later reaches
    them all. Enrollments renew from their own rows, so a program edit never
    changes what an existing enrollment owes (ADR 091 §4–5)."""
    rules = rules_for("Instructor", None)
    if rules:
        for name in frappe.get_all(
            "Instructor", filters={"status": "Active"}, pluck="name"
        ):
            try:
                ensure_requirements("Instructor", name, rules=rules)
            except Exception:  # noqa: BLE001
                frappe.log_error(
                    frappe.get_traceback(), "instructor requirement sweep failed"
                )

    renewing = frappe.db.sql(
        """
        select r.reference_name, r.kind, r.agreement_template, r.document_type,
               r.blocking, r.due_days, r.renewal, r.instructions
        from `tabPerson Requirement` r
        join `tabProgram Enrollment` pe on pe.name = r.reference_name
        where r.reference_doctype = 'Program Enrollment'
          and r.renewal != %s
          and pe.docstatus = 1 and pe.status = 'Active'
        order by r.creation asc
        """,
        NOT_RENEWED,
        as_dict=True,
    )
    by_pe = {}
    for r in renewing:
        key = (r.kind, r.agreement_template, r.document_type)
        by_pe.setdefault(r.reference_name, {})[key] = r  # the latest row wins
    for pe, rules in by_pe.items():
        try:
            ensure_requirements("Program Enrollment", pe, rules=list(rules.values()))
        except Exception:  # noqa: BLE001
            frappe.log_error(
                frappe.get_traceback(), "enrollment requirement sweep failed"
            )

    # Other apps' records read their handler's rules every day, like
    # instructors, when the handler lists which are active (ADR 092 §1).
    for doctype, subject in hooked_subjects().items():
        if not hasattr(subject, "active"):
            continue
        for name in subject.active() or []:
            try:
                ensure_requirements(doctype, name)
            except Exception:  # noqa: BLE001
                frappe.log_error(
                    frappe.get_traceback(), f"{doctype} requirement sweep failed"
                )


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
def _is_staff(user=None):
    return bool(_roles(user) & SCHOOL_ROLES)


def _person_condition(doctype, user):
    user = user or frappe.session.user
    if _is_staff(user):
        return ""
    return (
        f"`tab{doctype}`.person in (select name from `tabPerson` where user = "  # nosec B608 -- doctype is one of three literals; user is escaped
        f"{frappe.db.escape(user)})"
    )


def _person_has(doc, user):
    user = user or frappe.session.user
    if _is_staff(user):
        return True
    person = doc.get("person") if hasattr(doc, "get") else None
    return bool(person) and frappe.db.get_value("Person", person, "user") == user


def person_document_query(user=None):
    return _person_condition("Person Document", user)


def person_document_has(doc, ptype=None, user=None):
    return _person_has(doc, user)


def person_requirement_query(user=None):
    return _person_condition("Person Requirement", user)


def person_requirement_has(doc, ptype=None, user=None):
    return _person_has(doc, user)


def signed_agreement_query(user=None):
    return _person_condition("Signed Agreement", user)


def signed_agreement_has(doc, ptype=None, user=None):
    return _person_has(doc, user)


# --------------------------------------------------------------------------- #
# Portal
# --------------------------------------------------------------------------- #
def _my_person():
    if frappe.session.user in ("Guest", None):
        frappe.throw(_("Please log in."), frappe.PermissionError)
    return frappe.db.get_value("Person", {"user": frappe.session.user}, "name")


def _own_row(requirement, kind=None):
    person = _my_person()
    row = frappe.db.get_value(
        "Person Requirement",
        requirement,
        ["name", "person", "kind", "status"],
        as_dict=True,
    )
    if not row or not person or row.person != person:
        _deny(_("This requirement is not yours."), "requirements.own_row")
    if kind and row.kind != kind:
        frappe.throw(_("This requirement asks for something else."))
    return frappe.get_doc("Person Requirement", requirement)


def _for_label(row, cache):
    key = (row.reference_doctype, row.reference_name)
    if key not in cache:
        if row.reference_doctype == "Program Enrollment":
            program = frappe.db.get_value(
                "Program Enrollment", row.reference_name, "program"
            )
            cache[key] = program or row.reference_name
        elif row.reference_doctype == "Instructor":
            cache[key] = _("Instructor")
        else:
            # An uninstalled app's rows keep the bare record name.
            subject = _subject(row.reference_doctype)
            cache[key] = (
                subject.label(row.reference_name) if subject else None
            ) or row.reference_name
    return cache[key]


def _row_view(row, labels):
    view = {
        "name": row.name,
        "kind": row.kind,
        "label": label_of(row),
        "for": _for_label(row, labels),
        "status": row.status,
        "blocking": cint(row.blocking),
        "due_date": row.due_date,
        "overdue": is_overdue(row),
        "instructions": row.instructions or "",
        "period": row.academic_term or row.academic_year or "",
    }
    if row.kind == "Document":
        dt = (
            frappe.db.get_value(
                "Document Type",
                row.document_type,
                ["description", "allowed_extensions"],
                as_dict=True,
            )
            or {}
        )
        last = frappe.db.get_value(
            "Person Document",
            {"person": row.person, "document_type": row.document_type},
            ["name", "status", "rejection_reason", "file", "valid_until"],
            as_dict=True,
            order_by="creation desc",
        )
        view.update(
            description=dt.get("description") or "",
            allowed_extensions=allowed_extensions(row.document_type),
            last_document=last,
        )
    else:
        sa = (
            frappe.db.get_value(
                "Signed Agreement",
                row.satisfied_by,
                ["name", "status", "pdf", "final_pdf", "signed_on"],
                as_dict=True,
            )
            if row.satisfied_by_doctype == "Signed Agreement" and row.satisfied_by
            else None
        )
        view.update(signed=sa)
    return view


def open_count(user=None):
    person = frappe.db.get_value(
        "Person", {"user": user or frappe.session.user}, "name"
    )
    if not person:
        return 0
    return frappe.db.count(
        "Person Requirement", {"person": person, "status": "Pending"}
    )


@frappe.whitelist()
def my_requirements():
    person = _my_person()
    if not person:
        return {"open": [], "done": []}
    rows = frappe.get_all(
        "Person Requirement",
        filters={"person": person},
        fields=[
            "name",
            "person",
            "kind",
            "agreement_template",
            "document_type",
            "status",
            "blocking",
            "due_date",
            "instructions",
            "academic_term",
            "academic_year",
            "reference_doctype",
            "reference_name",
            "satisfied_by_doctype",
            "satisfied_by",
        ],
        order_by="due_date asc, creation asc",
    )
    labels = {}
    views = [_row_view(frappe._dict(r), labels) for r in rows]
    return {
        "open": [v for v in views if v["status"] in OPEN],
        "done": [v for v in views if v["status"] not in OPEN],
    }


@frappe.whitelist()
def agreement_preview(requirement):
    row = _own_row(requirement, kind="Agreement")
    template, version, html = render_agreement(row)
    return {
        "title": template.title,
        "version": version.version,
        "html": html,
        "countersigned": bool(template.countersign_role),
        "full_name": frappe.db.get_value("Person", row.person, "full_name"),
    }


@frappe.whitelist(methods=["POST"])
def sign_agreement(requirement, signer_name, consent=0, signature=None):
    row = _own_row(requirement, kind="Agreement")
    if row.status != "Pending":
        frappe.throw(_("This agreement has already been signed."))
    if not cint(consent):
        frappe.throw(_("Tick the box to confirm you agree before signing."))
    signer_name = _clean_name(signer_name)
    _check_signature(signature)
    sa = sign(row, signer_name, signature)
    return {"signed_agreement": sa.name, "status": recompute(row.name)}


@frappe.whitelist(methods=["POST"])
def upload_document(requirement, file_url):
    row = _own_row(requirement, kind="Document")
    if row.status not in ("Pending",):
        frappe.throw(_("This document has already been sent."))
    f = frappe.db.get_value(
        "File",
        {"file_url": file_url, "owner": frappe.session.user},
        ["name", "file_name", "attached_to_name", "is_private"],
        as_dict=True,
        order_by="creation desc",
    )
    if not f or f.attached_to_name:
        _deny(_("Upload the file again, then send it."), "requirements.upload_document")
    if not cint(f.is_private):
        frappe.db.set_value("File", f.name, "is_private", 1)
    check_extension(row.document_type, f.file_name)
    create_person_document(row.person, row.document_type, file_url)
    return {"status": recompute(row.name)}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=300, seconds=3600, ip_based=True)
def application_documents(program):
    """The documents the public application form asks for, for one program."""
    if not program or not frappe.db.exists("Program", program):
        return []
    rows = frappe.get_all(
        "Requirement Rule",
        filters={
            "parent": program,
            "parenttype": "Program",
            "parentfield": "enrollment_requirements",
            "kind": "Document",
            "ask_on_application": 1,
        },
        fields=["document_type", "instructions"],
        order_by="idx asc",
    )
    out = []
    for r in rows:
        dt = frappe.db.get_value(
            "Document Type", r.document_type, ["is_active", "description"], as_dict=True
        )
        if dt and dt.is_active:
            out.append(
                {
                    "document_type": r.document_type,
                    "description": r.instructions or dt.description or "",
                    "allowed_extensions": allowed_extensions(r.document_type),
                }
            )
    return out


def adopt_applicant_documents(applicant):
    """ADR 091 §10: each file on the application becomes a Person Document."""
    if not applicant.person:
        return
    for row in applicant.get("documents") or []:
        if not row.file or row.person_document or not row.document_type:
            continue
        doc = create_person_document(applicant.person, row.document_type, row.file)
        row.db_set("person_document", doc.name, update_modified=False)


def accepted_valid_until(document_type, on=None):
    months = cint(frappe.db.get_value("Document Type", document_type, "valid_months"))
    return add_months(getdate(on or today()), months) if months else None
