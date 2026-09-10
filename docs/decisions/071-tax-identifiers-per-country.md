# 071 — Tax identifiers per country

**Date:** 2026-09-10
**Status:** Accepted

## Context

Bringing up the Asaas gateway for the Brazilian seminary surfaced a fact the schema had nowhere to
put: Asaas cannot create a charge without the payer's CPF, and a Person has no tax identifier.

The only box on the application form that would take one was
`Student Applicant.social_security_number` — a plain `Data` field, `reqd` on the public web form,
with no format validation of any kind. Outside the United States nobody typed a social security
number into it. Brazilian applicants typed a CPF, because it was the only place a CPF could go. It
was also absent from `person_fields.SPEC`, so whatever was typed stayed on the applicant record and
never reached the Person; a registrar re-keyed it, or nobody did. ADR 068 §9 had already flagged it
as *"a plaintext field on a public form"* awaiting a retention decision.

The obvious shortcut is a column per country — `cpf`, `ssn`, `nif`, `vat_number` — which is how a
doctype ends up with thirty identity fields of which any record uses one, and how the next country
becomes a schema migration.

Two things make the general version harder than it looks:

**Which country decides?** A Person carries three country-ish fields, deliberately (ADR 046,
ADR 068 §2): `country` routes messaging, `mailing_country` is postal, `nationality` is citizenship.
They disagree often — a Brazilian on exchange in Ohio, a Mozambican student enrolled from home.

**Check digits are not a pattern.** CPF and CNPJ carry mod-11 check digits, so a regex can say a
value is eleven digits and cannot say it is a real CPF. Anything that wants to catch a transposed
digit before the payer leaves the page has to run an algorithm — and this codebase has no way to
share code between Python and its two front ends. `STATUS_COLORS` living in both `person.js` and
`frontend/src/utils/statusTheme.js` is the standing example of what happens when you try.

## Decision

**One `tax_id` field per doctype, one Python file per country.**
`seminary/seminary/tax_ids.py` holds a `Rule` per country and a `Form` per document that country
issues (Brazil issues two: CPF for a person, CNPJ for an organization). Adding a country is adding
one `Rule`. Modelled on `person_fields.SPEC`, and asserted the same way: a test checks that every
rule is internally consistent, including that the specimen in its own error message would pass its
own validator.

**Citizenship decides, residence is the fallback.** `COUNTRY_FIELDS` declares the precedence per
doctype — `("nationality", "mailing_country")` on a Person, `("nationality", "country")` on a
Student Applicant, which has no Person yet and one country column, and `("country",)` on a Partner
Organization. A tax number is issued by the state that claims you; residence is the weaker signal
because it moves.

**An unconfigured country stores free text.** `RULES` is an allowlist of rules someone has actually
checked, not a claim about the world. A seminary admitting its first Angolan student is not blocked
because nobody has written the Angolan rule.

**The browser gets data, never rules.** `client_rule()` ships label, mask, shape regex and a
specimen; `checksum` is a `bool`. Client code — the Desk bundle and the Vue composable — applies
whatever it is handed and contains no country name. The check digits are confirmed by a whitelisted
`check_tax_id` on blur and again in `validate()` on save. So the shape check is instant and
offline, the arithmetic never crosses the wire, and a new country needs no JavaScript change at
all. A test (`test_the_client_contract_carries_no_algorithm`) holds that boundary shut.

**Values are stored normalised and displayed masked.** `11144477735` on disk, `111.444.777-35` on
screen. One canonical shape for exports, future duplicate checks and the Asaas bridge, which wants
digits anyway.

**Legacy values warn; new and edited ones are refused.** `assert_on` throws when the value is new
or has just been changed, and only `msgprint`s otherwise — the same reasoning as
`Person.warn_about_required_details`. A rule shipped this week must not make a record created three
years ago unsaveable while a registrar corrects an unrelated phone number, and some of these values
came from an unvalidated public form and always will be junk.

**`social_security_number` is renamed, not supplemented.** ADR 068 §7's rule — one spelling per
attribute — applied to `zipcode` → `pincode` for the same reason it applies here: a `tax_id`
alongside an `ssn` is two homes for one fact, and the unvalidated one stays wired to the public
form. `applicant_ssn_to_tax_id` renames the column pre-model-sync, so no populated orphan survives
to answer raw SQL.

**Sensitive, at permlevel 1.** A national identity number sits with `blood_group`, `marital_status`
and the coordinates. `Spec(sensitive=True)` and the JSON agree, and `test_person.py` asserts it.
Registrar and Seminary Manager already hold level 1, and every write path goes through the spine's
`ignore_permissions=True` save, so self-service still reaches it. This is the retention decision
ADR 068 §9 deferred.

**Requiredness stays curated, not hard-coded.** `Mandatory Personal Field` already means "refused
on an application form, warned on a person's record", and `seed_mandatory_personal_fields` creates
the Tax ID row from the registry with no extra code. A Brazilian seminary ticks it.

`nationality` becomes `reqd` on the application web form. Requiring a tax identifier while not
asking which country's is requiring an answer with no question behind it — the same objection
ADR 067 §9 raises about derived mandatory fields.

## Consequences

- Adding a country is one `Rule`; adding one that needs a new check-digit algorithm is one `Rule`
  plus one function, still in the same file, still invisible to both front ends.
- `Person.tax_id` is a validated, canonical value the Asaas bridge can use directly. The
  `asaas_checkout` page still asks the payer to type their CPF; prefilling it from the Person is a
  follow-up now that somewhere to read it from exists.
- `get_student_info` now merges the spine's personal details. It returned `Student.*`, and ADR 068
  phase 4 dropped the address, date of birth and nationality columns from Student — so the profile
  modal has been rendering empty boxes that students retype. Fixed here because the tax ID would
  otherwise have inherited the same emptiness.
- The mod-11 implementation exists twice: here and in
  `payments/payment_gateways/doctype/asaas_settings/asaas_settings.py`, which validates what the
  payer types on the checkout page. Acknowledged rather than shared — the payments app is a
  separate, Frappe-standard app that cannot import seminary. It goes away when the checkout reads
  the already-validated `Person.tax_id` instead of asking again.
- Country → **payment-gateway eligibility** is deliberately not decided here. A Mozambican student
  cannot pay through Asaas at all and needs Stripe or PayPal, which today is a single
  `Seminary Settings.payment_gateway` field with no notion of who is paying. `Rule.gateways` is
  declared and reserved so that work adds a key to this table rather than starting a second one; a
  test asserts it does not reach the browser until it means something. The matching half —
  making `Mandatory Personal Field.mandatory` country-conditional, so a CPF is required of
  Brazilians and not of everyone — belongs with it.
