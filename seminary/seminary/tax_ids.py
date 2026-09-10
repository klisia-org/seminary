# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Per-country tax identifiers (ADR 071).

One `tax_id` field on Person and on Partner Organization, and one place — this
module — that knows what a tax identifier looks like in any given country.
Adding a country is adding one `Rule` to `RULES`. Nothing else in the app
learns anything about it: the Desk bundle, the public application form and the
Vue portal all render whatever `client_rule()` hands them.

The alternative was a column per country — `cpf`, `ssn`, `nif`, `vat_number` —
which is how a doctype ends up with thirty identity fields of which any one
record uses one.

### Why the browser gets data and never rules

A tax ID has two kinds of rule, and they behave differently:

* its **shape** (how long, which characters, where the punctuation falls) is a
  regex, so it ships to the browser inside the client contract and is checked
  as the user types, offline, with no round trip;
* its **check digits** are an algorithm, so they stay here. The contract says
  only `"checksum": true` — enough for the client to know there is more to
  verify and to ask `check_tax_id`, and not enough for anyone to reimplement
  it in JavaScript.

That split is the whole design. Porting each country's arithmetic into the
Desk bundle and again into the Vue app is what makes a per-country feature
stop scaling at the second country, and this codebase has no mechanism for
sharing code between Python and the two front ends.

### Countries we have not written a rule for

Store what was typed, unvalidated. `RULES` is an allowlist of countries whose
rules someone has actually checked, not a claim about the world — a seminary
admitting its first Angolan student must not be blocked because nobody has
written the Angolan rule yet.
"""

import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from seminary.seminary.utils import country_code

# ------------------------------------------------------------------ subjects

#: A human. Person, and Student Applicant before a Person exists.
PERSON = "person"

#: A legal entity. Partner Organization.
ORGANIZATION = "organization"

#: A form either may give. The default, because most countries issue one
#: number to everyone and the distinction only matters where it matters.
BOTH = "both"


# ------------------------------------------------------------------ cleaners

#: Kept as regex *source* rather than a compiled pattern: the same string is
#: handed to the browser and has to be valid in both `re` and `RegExp`.
DIGITS_ONLY = r"[^0-9]"
ALNUM_ONLY = r"[^0-9A-Za-z]"


class Form:
    """One document a country's tax-ID field accepts.

    Brazil is why this is a list and not a single pattern: the same field holds
    either a CPF (a person) or a CNPJ (an organization), with different lengths,
    different masks and different check digits. A country that issues one number
    declares one Form and never thinks about it again.
    """

    def __init__(
        self, name, pattern, mask=None, example=None, checksum=None, subject=BOTH
    ):
        #: What this country calls it — "CPF", "NIF", "EIN". It reaches the
        #: user in the error message, so it is the word they will go looking
        #: for on their own paperwork.
        self.name = name
        #: Anchored regex over the *cleaned* value. The only part of a rule the
        #: browser ever sees, so it has to be true standing alone: everything
        #: it accepts must be at least the right shape.
        self.pattern = pattern
        #: Display mask, one `#` per accepted character: "###.###.###-##".
        self.mask = mask
        #: A specimen for the error message and the placeholder. The suite
        #: asserts it against this very Form, so a new country cannot ship a
        #: message telling the user to type something invalid.
        self.example = example
        #: `callable(cleaned) -> bool`, run only once `pattern` has matched.
        #: None means the shape is the whole rule. Never sent to the browser.
        self.checksum = checksum
        #: PERSON, ORGANIZATION or BOTH — who may give this one.
        self.subject = subject

    def accepts(self, subject):
        return subject == BOTH or self.subject in (BOTH, subject)

    def __repr__(self):
        return "Form(%r, %s)" % (self.name, self.subject)


class Rule:
    """Everything one country's tax identifier is."""

    def __init__(
        self, country, label, forms, clean=DIGITS_ONLY, note=None, gateways=None
    ):
        #: ISO-3166 alpha-2, uppercase. Country records are named by their
        #: English name, which is renameable and displayed translated, so the
        #: code is the only stable key. Resolved by `utils.country_code`.
        self.country = country
        #: What the field is called here — "CPF / CNPJ". Replaces the docfield's
        #: generic "Tax ID" label once a country is known.
        self.label = label
        self.forms = tuple(forms)
        #: Characters stripped before matching, and therefore the stored form.
        self.clean = clean
        #: One sentence under the field saying where to find the number.
        self.note = note
        #: RESERVED — which payment gateways can bill in this country. Declared
        #: here so that work (a Mozambican student cannot pay through Asaas at
        #: all) adds a key to this table rather than starting a second one.
        #: `client_rule()` does not ship it, and a test holds that shut.
        self.gateways = tuple(gateways or ())

    def forms_for(self, subject):
        return tuple(form for form in self.forms if form.accepts(subject))

    def __repr__(self):
        return "Rule(%r, %d forms)" % (self.country, len(self.forms))


# --------------------------------------------------------------- checksums


def _mod11(digits, weights):
    """The check digit for `digits` under `weights`, Brazilian mod-11."""
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def _repeated(value):
    """`111.111.111-11` satisfies the arithmetic and is not a real document.
    Every Brazilian validator refuses the repeated-digit sequences by name."""
    return len(set(value)) == 1


def _is_valid_cpf(value):
    if _repeated(value):
        return False
    for weights in (list(range(10, 1, -1)), list(range(11, 1, -1))):
        if int(value[len(weights)]) != _mod11(value[: len(weights)], weights):
            return False
    return True


def _is_valid_cnpj(value):
    if _repeated(value):
        return False
    for weights in (
        [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    ):
        if int(value[len(weights)]) != _mod11(value[: len(weights)], weights):
            return False
    return True


# -------------------------------------------------------------- the registry


RULES = (
    Rule(
        country="BR",
        label="CPF / CNPJ",
        forms=(
            Form(
                "CPF",
                r"^\d{11}$",
                mask="###.###.###-##",
                example="111.444.777-35",
                checksum=_is_valid_cpf,
                subject=PERSON,
            ),
            Form(
                "CNPJ",
                r"^\d{14}$",
                mask="##.###.###/####-##",
                example="11.222.333/0001-81",
                checksum=_is_valid_cnpj,
                subject=ORGANIZATION,
            ),
        ),
    ),
)

RULES_BY_COUNTRY = {rule.country: rule for rule in RULES}


#: Which field decides the rule, per doctype, most authoritative first.
#:
#: Nationality before residence on a Person: a tax number is issued by the
#: state that claims you, and a Brazilian on exchange in Ohio still has a CPF
#: and no SSN. Residence is the fallback rather than the primary because it
#: moves and citizenship does not.
#:
#: A Student Applicant answers for itself — no Person exists yet at intake
#: (ADR 068 §1) — and has one `country` column rather than the routing/postal
#: split, so that column is its fallback.
COUNTRY_FIELDS = {
    "Person": ("nationality", "mailing_country"),
    "Student Applicant": ("nationality", "country"),
    "Partner Organization": ("country",),
}

#: Who each doctype's tax ID belongs to.
SUBJECTS = {
    "Person": PERSON,
    "Student Applicant": PERSON,
    "Partner Organization": ORGANIZATION,
}


# ------------------------------------------------------------------- lookups


def rule_for(country):
    """The rule for a Country docname or a raw alpha-2 code, or None."""
    return RULES_BY_COUNTRY.get(country_code(country))


def tax_country_for(doc):
    """The country whose rule governs `doc`, by the precedence in
    `COUNTRY_FIELDS`. None when the record says nothing about where it is
    from — in which case there is no rule to apply and no way to invent one."""
    for fieldname in COUNTRY_FIELDS.get(doc.doctype, ()):
        value = doc.get(fieldname)
        if value:
            return value
    return None


def strip(value, rule=None):
    """The stored form: `value` with the rule's punctuation removed."""
    value = (value or "").strip()
    if not value:
        return ""
    return re.sub(rule.clean if rule else DIGITS_ONLY, "", value)


def match(value, country, subject=BOTH):
    """Resolve `(rule, form, cleaned)` for a typed value.

    `form` is None when no form of the country's rule matches the shape, and
    `rule` is None when the country has no rule at all.
    """
    rule = rule_for(country)
    cleaned = strip(value, rule)
    if not (rule and cleaned):
        return rule, None, cleaned
    for form in rule.forms_for(subject):
        if re.match(form.pattern, cleaned):
            return rule, form, cleaned
    return rule, None, cleaned


def clean_tax_id(value, country, subject=BOTH):
    """The value as it should be stored — punctuation removed where a rule
    says so, untouched where no rule exists. Does not validate."""
    rule = rule_for(country)
    if not rule:
        return (value or "").strip() or None
    return strip(value, rule) or None


def format_tax_id(value, country, subject=BOTH):
    """The value as it should be shown: `12345678909` -> `123.456.789-09`."""
    rule, form, cleaned = match(value, country, subject)
    if not (form and form.mask):
        return cleaned or (value or "").strip()
    out = []
    digits = iter(cleaned)
    for char in form.mask:
        if char == "#":
            out.append(next(digits, ""))
        else:
            out.append(char)
    return "".join(out).rstrip(" .-/")


def problem_with(value, country, subject=BOTH):
    """Why `value` is not a valid tax ID for this country, or None if it is.

    Returns a ready-to-show sentence rather than a code: there is one caller
    shape (say what is wrong, name the document, show a specimen) and building
    the sentence in three places is how they drift apart.
    """
    rule, form, cleaned = match(value, country, subject)
    if not rule or not cleaned:
        return None

    accepted = rule.forms_for(subject)
    if not form:
        names = " / ".join(f.name for f in accepted)
        examples = " or ".join(f.example for f in accepted if f.example)
        return _("That does not look like a {0}. For example: {1}.").format(
            names, examples
        )

    if form.checksum and not form.checksum(cleaned):
        return _(
            "That is not a valid {0} — check the digits. For example: {1}."
        ).format(form.name, form.example)

    return None


def assert_tax_id(value, country, subject=BOTH):
    """Validate and return the stored form, or throw.

    An empty value is never refused: whether a tax ID is *required* is the
    school's call, curated on `Mandatory Personal Field`, not this module's.
    """
    problem = problem_with(value, country, subject)
    if problem:
        frappe.throw(problem, title=_("Check the tax ID"))
    return clean_tax_id(value, country, subject)


def assert_on(doc, fieldname="tax_id"):
    """Validate `doc.tax_id`, and normalise it in place.

    Refuses a value that is new or has just been edited, and only *warns*
    about one that was already on the record and was not touched. Same reason
    `Person.warn_about_required_details` warns rather than throws: a rule
    shipped this week must not make a record created three years ago
    unsaveable while a registrar is correcting an unrelated phone number.
    Some of these values came from a free-text box on a public form and always
    will be junk; refusing the save punishes whoever is trying to fix it.
    """
    value = doc.get(fieldname)
    if not value:
        doc.set(fieldname, None)
        return

    country = tax_country_for(doc)
    subject = SUBJECTS.get(doc.doctype, BOTH)
    problem = problem_with(value, country, subject)

    if not problem:
        doc.set(fieldname, clean_tax_id(value, country, subject))
        return

    before = None if doc.is_new() else doc.get_doc_before_save()
    if before is None or (before.get(fieldname) or "") != (value or ""):
        frappe.throw(problem, title=_("Check the tax ID"))

    frappe.msgprint(problem, indicator="orange", alert=True)


# ---------------------------------------------------- the browser's contract


def client_rule(country=None, subject=BOTH):
    """What a country's rule looks like to a front end.

    Shape, mask, label and specimen — everything a browser can act on offline.
    `checksum` is a bool and never the algorithm: see the module docstring.
    """
    rule = rule_for(country)
    if not rule:
        return {
            "country": country_code(country),
            "configured": False,
            "label": _("Tax ID"),
        }

    forms = rule.forms_for(subject)
    # Narrowing by subject narrows the label too: a Person form in Brazil asks
    # for a CPF, and offering "CPF / CNPJ" there invites the wrong one.
    label = (
        _(rule.label)
        if len(forms) == len(rule.forms)
        else " / ".join(form.name for form in forms)
    )
    return {
        "country": rule.country,
        "configured": True,
        "label": label or _("Tax ID"),
        "note": _(rule.note) if rule.note else None,
        "clean": rule.clean,
        "max_length": max((len(f.mask or "") for f in forms), default=0),
        "forms": [
            {
                "name": form.name,
                "pattern": form.pattern,
                "mask": form.mask,
                "example": form.example,
                "checksum": bool(form.checksum),
            }
            for form in forms
        ],
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60, ip_based=True)
def get_tax_id_rule(country=None, subject=BOTH):
    """The client contract for one country.

    Guest-callable because the public application form is a surface where a
    mistyped tax ID does real damage and the applicant is never logged in.
    Safe to open: this is static configuration, not anybody's data.
    """
    return client_rule(country, subject)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=60, ip_based=True)
def check_tax_id(value, country=None, subject=BOTH):
    """Run the check digits and answer. Never throws.

    A `frappe.throw` here would open a modal every time someone tabbed out of
    a half-typed number, so this returns a verdict and `validate()` is what
    refuses a save.

    It says nothing about whether the number is already on record. That would
    be an enumeration oracle over every tax ID the school holds, on an endpoint
    open to the internet.
    """
    problem = problem_with(value, country, subject)
    _rule, form, _cleaned = match(value, country, subject)
    return {
        "ok": not problem,
        "form": form.name if form else None,
        "formatted": format_tax_id(value, country, subject),
        "message": problem,
    }
