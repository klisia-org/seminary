"""The shared-attribute registry (ADR 068).

One declared list of what a *shared human attribute* is, and where each one
lives on the role doctypes. Before this module the answer was implicit in four
places that disagreed: `ensure_person`'s signature, `_apply`'s branching,
`Person.propagate_to_roles`' target dict, and the `read_only_depends_on` flags
in the doctype JSONs. The protected set and the propagated set were the same
arbitrary subset, and every field outside it was an unmanaged second home.

Everything derives from `SPEC` below: the spine module's function signatures,
its write semantics, the propagation targets, and the JSON flags (asserted by
`test_person.py`, not generated at runtime — a doctype JSON stays the source of
truth for Frappe, this just refuses to let it drift).

Adding an attribute means adding one `Spec`. Forgetting a doctype then fails
the suite instead of becoming the next hole.

A `LOCAL` binding left here is a deliberate statement, not a leftover: the
Student Applicant bindings are `LOCAL` because that doctype captures data
*before* a Person exists (ADR 068 §1, §9), so it cannot mirror one. Everywhere
else a role binding is a `MIRROR` or a `SNAPSHOT`, and the agreement test in
`test_person.py` fails if a JSON quietly changes kind underneath the registry.
"""

# --------------------------------------------------------------- write modes

#: Last-write-wins when the caller is authoritative (`overwrite=True`), but
#: never blanking: a cleared intake field is an omission, not a correction.
AUTHORED = "authored"

#: Only ever fills a blank. An existing Person's value is never replaced.
FILL_ONLY = "fill_only"


# ------------------------------------------------------------- binding kinds

#: A writable local column on the role doctype, kept in step by an explicit
#: push from `Person.on_update`. The pre-068 shape, and the thing 068 retires.
LOCAL = "local"

#: `fetch_from person.*` + `read_only`. Always current. Answers "who is this
#: person now" — identity fields, a gradebook row, a faculty picker.
MIRROR = "mirror"

#: No `fetch_from`. Written once by the controller at a named capture moment
#: and never re-fetched. Answers "what was recorded at the time" — a program
#: enrollment's name is the one that reaches the diploma, and a rename after
#: the degree is complete must not rewrite it (ADR 068 section 3).
SNAPSHOT = "snapshot"

#: `fetch_from` pointing at something that is *not* the spine. Not a design,
#: an artefact: the field mirrors whichever doctype its author had in hand.
#: Declared so the wrong source is visible in the registry and pinned by a
#: test, rather than reading as a plain local column. Phase 4 repoints these
#: at Person and they become MIRROR.
FOREIGN = "foreign"


class Binding:
    """How one Person attribute surfaces on one role doctype."""

    def __init__(self, fieldname, kind=LOCAL, propagate=False, source=None):
        self.fieldname = fieldname
        self.kind = kind
        #: Whether `Person.propagate_to_roles` pushes this field. A MIRROR is
        #: still pushed: `fetch_from` only fires when the *role* doc is saved,
        #: and Frappe has no reverse hook.
        self.propagate = propagate
        #: FOREIGN only: the `fetch_from` the JSON actually declares today.
        self.source = source

    def __repr__(self):
        return "Binding(%r, %s, propagate=%s)" % (
            self.fieldname,
            self.kind,
            self.propagate,
        )


class Spec:
    """One shared human attribute."""

    def __init__(
        self,
        person_field,
        arg=None,
        mode=None,
        roles=None,
        never_blank=False,
        push_blank=False,
        sensitive=False,
        derived=False,
    ):
        self.person_field = person_field
        #: Keyword name on `ensure_person`/`update_person`. None means the
        #: attribute is not settable through the spine's entry points.
        self.arg = arg
        self.mode = mode
        self.roles = roles or {}
        #: `first_name` is reqd on Person, so an authoritative caller may
        #: change it but never clear it.
        self.never_blank = never_blank
        #: Push an empty string when the spine value is blank, rather than
        #: skipping the push. False for unique/required mirrors, where an empty
        #: spine would otherwise wipe a role's email.
        self.push_blank = push_blank
        #: Held at permlevel 1 on Person.
        self.sensitive = sensitive
        #: Resolved by the system, never typed (coordinates). "Mandatory" for a
        #: derived attribute can only mean *resolvable*.
        self.derived = derived

    @property
    def settable(self):
        return self.arg is not None

    def __repr__(self):
        return "Spec(%r)" % self.person_field


# --------------------------------------------------------------------- specs

STUDENT = "Student"
APPLICANT = "Student Applicant"
INSTRUCTOR = "Instructor"
ALUMNI = "Alumni Profile"

SPEC = (
    Spec(
        "first_name",
        arg="first_name",
        mode=AUTHORED,
        never_blank=True,
        push_blank=True,
        roles={
            STUDENT: Binding("first_name", MIRROR, propagate=True),
            APPLICANT: Binding("first_name", propagate=True),
        },
    ),
    Spec(
        "middle_name",
        arg="middle_name",
        mode=AUTHORED,
        push_blank=True,
        roles={
            STUDENT: Binding("middle_name", MIRROR, propagate=True),
            APPLICANT: Binding("middle_name", propagate=True),
        },
    ),
    Spec(
        "last_name",
        arg="last_name",
        mode=AUTHORED,
        push_blank=True,
        roles={
            STUDENT: Binding("last_name", MIRROR, propagate=True),
            APPLICANT: Binding("last_name", propagate=True),
        },
    ),
    Spec(
        # Computed on Person (`set_full_name`), so not settable from a role.
        "full_name",
        push_blank=True,
        roles={
            STUDENT: Binding("student_name", MIRROR, propagate=True),
            APPLICANT: Binding("title", propagate=True),
            ALUMNI: Binding("full_name", MIRROR, propagate=True),
            # Excluded until ADR 068 phase 3 made the key opaque: while the
            # docname *was* `format:{instructor_name}`, pushing a corrected
            # name would have desynced name from docname, so `person.py` had a
            # hard-coded `targets["Instructor"] = {}` and every instructor's
            # displayed name stayed stale forever.
            INSTRUCTOR: Binding("instructor_name", MIRROR, propagate=True),
        },
    ),
    Spec(
        "primary_email",
        # `email` is a positional on ensure_person and handled separately in
        # `_apply` (it is the match heuristic as well as a value), so it is not
        # settable through the generic values dict.
        roles={
            STUDENT: Binding("student_email_id", MIRROR, propagate=True),
            APPLICANT: Binding("student_email_id", propagate=True),
            INSTRUCTOR: Binding("prof_email", MIRROR, propagate=True),
            # Was the docname (`field:email`) until phase 3 — in the app whose
            # own ADR says email is data and never a key.
            ALUMNI: Binding("email", MIRROR, propagate=True),
        },
    ),
    Spec(
        "primary_mobile",
        arg="mobile",
        mode=AUTHORED,
        roles={
            STUDENT: Binding("student_mobile_number", MIRROR, propagate=True),
            APPLICANT: Binding("student_mobile_number", propagate=True),
            INSTRUCTOR: Binding("phone_message", MIRROR, propagate=True),
        },
    ),
    Spec("language", arg="language", mode=FILL_ONLY),
    # Messaging provider routing (ADR 043), *not* the postal country — that is
    # `mailing_country` below. They were conflated until ADR 068 phase 2, which
    # is how a student's self-service address edit could reach the SMS provider
    # selector.
    #
    # The applicant's single `country` column feeds both, and that is declared
    # rather than accidental: it is the only country an intake form asks for,
    # so it is the best first guess at which provider can reach them. FILL_ONLY
    # keeps it a *seed* — once a Person exists, a later postal move updates
    # `mailing_country` and leaves the routing field where an admin put it.
    Spec(
        "country", arg="country", mode=FILL_ONLY, roles={APPLICANT: Binding("country")}
    ),
    Spec(
        "date_of_birth",
        arg="date_of_birth",
        mode=AUTHORED,
        roles={
            APPLICANT: Binding("date_of_birth"),
        },
    ),
    Spec(
        "nationality",
        arg="nationality",
        mode=AUTHORED,
        roles={
            APPLICANT: Binding("nationality"),
        },
    ),
    Spec(
        "phonetic_name",
        arg="phonetic_name",
        mode=AUTHORED,
        roles={},
    ),
    Spec(
        "mailing_country",
        arg="mailing_country",
        mode=AUTHORED,
        roles={APPLICANT: Binding("country")},
    ),
    # The postal address. It has lived on Person since ADR 046, but
    # `ensure_person` accepted no address arguments at all, so the
    # "registrar-intake snapshot seeds the Person" that 046 describes has never
    # actually happened — only the importer and the portal preferences page
    # ever wrote one.
    Spec(
        "address_line_1",
        arg="address_line_1",
        mode=AUTHORED,
        roles={
            APPLICANT: Binding("address_line_1"),
        },
    ),
    Spec(
        "address_line_2",
        arg="address_line_2",
        mode=AUTHORED,
        roles={
            APPLICANT: Binding("address_line_2"),
        },
    ),
    Spec(
        "city",
        arg="city",
        mode=AUTHORED,
        roles={APPLICANT: Binding("city")},
    ),
    Spec(
        "state",
        arg="state",
        mode=AUTHORED,
        roles={APPLICANT: Binding("state")},
    ),
    Spec(
        "pincode",
        arg="pincode",
        mode=AUTHORED,
        roles={
            # Was `zipcode` on the applicant (labelled "ZIP cide") until ADR
            # 068 phase 7 renamed it. One spelling per attribute is the point:
            # a second name is what let `enroll_student`'s same-name mapper
            # drop the postal code at admission without anyone noticing.
            APPLICANT: Binding("pincode"),
        },
    ),
    # Resolved from the address by `integrations.geocoding`, never typed — so
    # they are not settable through the spine's entry points, and "mandatory"
    # for them can only mean *resolvable*, which a readiness pre-flight checks
    # rather than a `reqd` flag on a form (ADR 068 §7).
    Spec("latitude", derived=True, sensitive=True),
    Spec("longitude", derived=True, sensitive=True),
    Spec(
        "blood_group",
        arg="blood_group",
        mode=AUTHORED,
        sensitive=True,
        roles={
            APPLICANT: Binding("blood_group"),
        },
    ),
    Spec(
        "marital_status",
        arg="marital_status",
        mode=AUTHORED,
        sensitive=True,
        roles={APPLICANT: Binding("marital")},
    ),
    Spec(
        "ethnicity",
        arg="ethnicity",
        mode=AUTHORED,
        sensitive=True,
        roles={APPLICANT: Binding("ethnic")},
    ),
    Spec(
        "image",
        arg="image",
        mode=FILL_ONLY,
        roles={
            # Not propagated today: Student.image and Instructor.profileimage
            # are independently writable. Phase 4 makes them mirrors.
            STUDENT: Binding("image", MIRROR, propagate=True),
            INSTRUCTOR: Binding("profileimage", MIRROR, propagate=True),
            # Capture only, like the rest of the applicant's personal block.
            APPLICANT: Binding("image"),
            # A mirror of a mirror: the alumnus's photo comes from their
            # Student record rather than from the spine, so an alumnus who was
            # never a student here has no photo at all.
            ALUMNI: Binding("image", MIRROR, propagate=True),
        },
    ),
    Spec(
        "gender",
        arg="gender",
        # AUTHORED since phase 4. It was fill-only, which meant
        # `update_person(overwrite=True)` could not correct a gender at all —
        # the gap ADR 067 stalled on.
        mode=AUTHORED,
        roles={
            STUDENT: Binding("gender", MIRROR, propagate=True),
            APPLICANT: Binding("gender"),
            # Sourced from erpnext's Employee, which is not in `required_apps`
            # — so on a bench without erpnext the link dangles and the field is
            # simply dead. Gender is identity, not payroll; phase 4 repoints it
            # at Person.
            INSTRUCTOR: Binding("gender", MIRROR, propagate=True),
        },
    ),
)

# ----------------------------------------------------------------- snapshots


class Snapshot:
    """A person's attribute recorded on a document *about* them.

    Not a role binding: the document does not represent the human, it records
    something that happened to them. So the value answers "what was recorded at
    the time", and it must not move when the person is later renamed —
    `Program Enrollment.student_name` is the name that reaches the diploma.

    Captured once from the spine, then left alone. A `fetch_from` here would
    re-derive it on every save, including `on_update_after_submit`, so the
    agreement test asserts these fields declare none.
    """

    def __init__(
        self, doctype, fieldname, person_field, link_field="student", resync_while=None
    ):
        self.doctype = doctype
        self.fieldname = fieldname
        self.person_field = person_field
        #: Link to the Student this document is about.
        self.link_field = link_field
        #: Filters describing a record still open to correction. While a
        #: document matches them, a spine edit re-takes the snapshot; once it
        #: stops matching, the value is final. `None` means final on capture.
        #:
        #: This is the difference between protecting a legal record and
        #: punishing a typo: a name misspelt at enrollment would otherwise
        #: follow the student through a four-year program with no way to fix
        #: it, because the field is read-only and the document is submitted.
        self.resync_while = resync_while

    def __repr__(self):
        return "Snapshot(%r, %r)" % (self.doctype, self.fieldname)


SNAPSHOTS = (
    # The diploma chain. `Diploma.legal_name` was already a true snapshot; the
    # two hops feeding it were not.
    Snapshot(
        "Program Enrollment",
        "student_name",
        "full_name",
        # Corrigible while the enrollment is still running, frozen the moment
        # it concludes. `Graduated` is the one that reaches the diploma;
        # `Withdrawn`, `Dismissed` and `Transferred` are equally records of a
        # decision taken on a date, so they freeze too. A cancelled enrollment
        # (docstatus 2) is not corrected, it is void.
        resync_while={
            "status": ["in", ("Active", "Leave of Absence")],
            "docstatus": ["<", 2],
        },
    ),
    Snapshot("Graduation Request", "phonetic_name_snapshot", "phonetic_name"),
    # Records of a decision or an event on a date. Renaming the person does not
    # change what the register said when it was written.
    Snapshot("Withdrawal Request", "student_name", "full_name"),
    Snapshot("Student Leave Application", "student_name", "full_name"),
    Snapshot("Student Log", "student_name", "full_name"),
)

SNAPSHOTS_BY_DOCTYPE = {}
for _snap in SNAPSHOTS:
    SNAPSHOTS_BY_DOCTYPE.setdefault(_snap.doctype, []).append(_snap)
del _snap


def capture_snapshots(doc, method=None):
    """Fill any declared snapshot on `doc` that is still empty.

    Only ever fills a blank, so re-saving a record — or amending a submitted
    one — never re-derives a value that has already been recorded. That is the
    whole point: a student who changes their name after a degree is complete
    must not have the change reach the completed enrollment.
    """
    import frappe

    for snap in SNAPSHOTS_BY_DOCTYPE.get(doc.doctype, ()):
        if doc.get(snap.fieldname):
            continue
        student = doc.get(snap.link_field)
        if not student:
            continue
        person = frappe.db.get_value("Student", student, "person")
        if not person:
            continue
        value = frappe.db.get_value("Person", person, snap.person_field)
        if value:
            doc.set(snap.fieldname, value)


def resync_open_snapshots(person_name):
    """Re-take every snapshot on a document still open to correction.

    A snapshot is not a mirror: it records what was true when the document was
    written, and `capture_snapshots` only ever fills a blank. That is right for
    a concluded enrollment — the name on a completed degree must not move — and
    wrong for a running one, where a misspelling entered at enrollment would
    otherwise be uncorrectable for the length of the program. The field is
    `Read Only` with no `allow_on_submit`, so nobody could fix it by hand
    either.

    Which documents are still open is declared per snapshot (`resync_while`),
    so the rule lives next to the field it governs rather than in a controller
    that the next reader has to find.

    `db.set_value` for the same reason `propagate_to_roles` uses it: these
    documents are submitted, the field is read-only, and running hooks here
    would recurse back into the spine.
    """
    import frappe

    students = frappe.get_all("Student", filters={"person": person_name}, pluck="name")
    if not students:
        return 0

    resynced = 0
    for snap in SNAPSHOTS:
        if not snap.resync_while:
            continue
        value = frappe.db.get_value("Person", person_name, snap.person_field)
        if not value:
            # An empty spine never overwrites a recorded name.
            continue
        filters = dict(snap.resync_while)
        filters[snap.link_field] = ["in", students]
        for name in frappe.get_all(snap.doctype, filters=filters, pluck="name"):
            if frappe.db.get_value(snap.doctype, name, snap.fieldname) == value:
                continue
            frappe.db.set_value(
                snap.doctype, name, snap.fieldname, value, update_modified=False
            )
            resynced += 1
    return resynced


def mirror_values(doctype, person_name):
    """The mirror values a role record should be showing, as a dict.

    Frappe fetches a `fetch_from` field in `_validate_links()`, which runs
    *before* `validate()` — so a controller that resolves `person` inside
    `validate()` (every role doctype until ADR 068 phase 5 makes the link reqd
    and set up-front) misses the fetch and would save with empty mirrors on the
    very first insert. This fills them for that one case. Once the link is
    required and set before insert, Frappe does it and this can go.
    """
    import frappe

    fields = [
        (spec.person_field, binding.fieldname)
        for spec, binding in bindings_for(doctype)
        if binding.kind == MIRROR
    ]
    if not fields or not person_name:
        return {}
    spine = frappe.db.get_value(
        "Person", person_name, [f for f, _ in fields], as_dict=True
    )
    if not spine:
        return {}
    return {target: spine.get(source) for source, target in fields}


def role_doctypes_for_person():
    """Role records whose existence obliges the spine to stay reachable."""
    return (STUDENT, INSTRUCTOR, ALUMNI)


def assert_reachable(person):
    """A Person holding a role must keep a primary email.

    The role mirrors (`Student.student_email_id`, `Instructor.prof_email`,
    `Alumni Profile.email`) are `fetch_from person.primary_email`, and Frappe
    *blanks* a mirror whose source is null. Those addresses provision the
    portal login and are unique-indexed, so clearing the spine's email would
    strand the login on the role's next save — long after the edit that caused
    it. Refuse at the source instead.
    """
    import frappe
    from frappe import _

    if person.primary_email:
        return
    for doctype in role_doctypes_for_person():
        if frappe.db.exists(doctype, {"person": person.name}):
            frappe.throw(
                _(
                    "{0} holds a {1} record, so a primary email is required — "
                    "the role's email address is a mirror of this field."
                ).format(person.full_name or person.name, _(doctype))
            )


SPEC_BY_PERSON_FIELD = {spec.person_field: spec for spec in SPEC}
SPEC_BY_ARG = {spec.arg: spec for spec in SPEC if spec.settable}

#: Keyword names accepted by `ensure_person` / `update_person`.
SETTABLE_ARGS = tuple(spec.arg for spec in SPEC if spec.settable)

ROLE_DOCTYPES = (STUDENT, APPLICANT, INSTRUCTOR, ALUMNI)


def person_field_for(arg):
    """The Person fieldname a keyword argument writes to."""
    spec = SPEC_BY_ARG.get(arg)
    return spec.person_field if spec else None


def bindings_for(doctype):
    """Every (spec, binding) pair declared for one role doctype."""
    return [(spec, spec.roles[doctype]) for spec in SPEC if doctype in spec.roles]


def propagation_plan(person):
    """What `Person.on_update` should push, as {doctype: {fieldname: value}}.

    Blank values are pushed as "" only where `push_blank` says so: an empty
    spine must never wipe a unique or required mirror such as a role's email.
    """
    plan = {}
    for spec in SPEC:
        value = person.get(spec.person_field)
        for doctype, binding in spec.roles.items():
            if not binding.propagate:
                continue
            if not value and not spec.push_blank:
                continue
            plan.setdefault(doctype, {})[binding.fieldname] = value or ""
    return plan


# ------------------------------------------------------------------- capture


def spine_kwargs(doc, doctype=None):
    """The `ensure_person`/`update_person` keywords a role record carries.

    Derived from the registry rather than written out at the call site. The
    hand-written version is what lost the applicant's address and gender for
    the whole life of ADR 042: `_promote_to_person` passed seven arguments,
    the registry declares fourteen, and nothing anywhere compared the two.
    Adding a `Spec` with an APPLICANT binding now reaches the spine by itself.

    `primary_email` is absent by design — it is `ensure_person`'s positional
    match heuristic as well as a value, so the caller passes it separately.
    """
    doctype = doctype or doc.doctype
    return {
        spec.arg: doc.get(binding.fieldname)
        for spec, binding in bindings_for(doctype)
        if spec.settable
    }


def capture_fields(doctype):
    """Fieldnames on `doctype` that hold a shared attribute someone types.

    Excludes the bindings a role computes for itself: `Student Applicant.title`
    is `set_title()`'s output, not a captured datum, so freezing it after
    admission would only make the controller fight its own form.
    """
    return tuple(
        binding.fieldname
        for spec, binding in bindings_for(doctype)
        if spec.person_field != "full_name"
    )


#: The attributes an intake form must actually collect. Declared here so ADR
#: 067's per-program curation layer extends this list instead of starting a
#: second, parallel one — which is the failure this whole module exists to
#: prevent. Deliberately short: it names what breaks something downstream if
#: absent, not everything a registrar would like to have.
CAPTURE_REQUIRED = ("first_name", "primary_email", "gender")


def capture_required():
    """What an application must carry: the built-in floor, plus the school's own.

    `CAPTURE_REQUIRED` is what the app cannot work without. A school adds to it
    by ticking Required on a `Mandatory Personal Field` (ADR 067 section 9), and
    a matching rule cannot be used until its detail is ticked -- so the rules a
    school chooses and the questions its application asks stay in step by
    construction rather than by anybody remembering.

    Only fields that are actually *typed*: a derived one -- a map position --
    cannot be demanded on a form, so "required" for it means resolvable, which
    the planner reports and no save refuses.
    """
    import frappe

    fields = set(CAPTURE_REQUIRED)
    if not frappe.db.table_exists("Mandatory Personal Field"):
        return tuple(sorted(fields))
    from seminary.seminary.doctype.mandatory_personal_field import (
        mandatory_personal_field as mpf,
    )

    return tuple(sorted(fields | mpf.required_fields()))


def assert_capture_complete(doc, doctype=None):
    """Refuse a role record that skipped a required shared attribute.

    `Program.application_web_form` and
    `Seminary Settings.default_application_web_form` let an admin point intake
    at any Web Form built against Student Applicant. A form that simply omits
    a field cannot be caught on the client — the shared script prompts, but a
    prompt is not a guarantee — and the omission is invisible afterwards,
    because the applicant record looks complete and only the Person is empty.
    So the check lives on the document, where every form has to pass through it.
    """
    import frappe
    from frappe import _

    doctype = doctype or doc.doctype
    meta = frappe.get_meta(doctype)
    missing = []
    for person_field in capture_required():
        binding = SPEC_BY_PERSON_FIELD[person_field].roles.get(doctype)
        if not binding:
            continue
        if not doc.get(binding.fieldname):
            df = meta.get_field(binding.fieldname)
            missing.append(_(df.label) if df and df.label else binding.fieldname)
    if missing:
        frappe.throw(
            _(
                "{0} must be recorded on every application. If the form you used "
                "does not ask for it, the form itself is incomplete."
            ).format(", ".join(missing)),
            title=_("Missing required information"),
        )
