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

**This module currently encodes the spine as it is, not as ADR 068 leaves it.**
Phase 1 is deliberately behaviour-neutral: every role binding is `LOCAL`, and
`gender` is still `FILL_ONLY`. The flips — `LOCAL` to `MIRROR`/`SNAPSHOT`, and
`gender`/address to `AUTHORED` — land in phases 4 and 7, where the JSON changes
alongside them and the agreement test moves in lockstep.
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
            STUDENT: Binding("first_name", propagate=True),
            APPLICANT: Binding("first_name", propagate=True),
        },
    ),
    Spec(
        "middle_name",
        arg="middle_name",
        mode=AUTHORED,
        push_blank=True,
        roles={
            STUDENT: Binding("middle_name", propagate=True),
            APPLICANT: Binding("middle_name", propagate=True),
        },
    ),
    Spec(
        "last_name",
        arg="last_name",
        mode=AUTHORED,
        push_blank=True,
        roles={
            STUDENT: Binding("last_name", propagate=True),
            APPLICANT: Binding("last_name", propagate=True),
        },
    ),
    Spec(
        # Computed on Person (`set_full_name`), so not settable from a role.
        "full_name",
        push_blank=True,
        roles={
            STUDENT: Binding("student_name", propagate=True),
            APPLICANT: Binding("title", propagate=True),
            ALUMNI: Binding("full_name", propagate=True),
            # Instructor.instructor_name is deliberately absent: it is the
            # docname today (`format:{instructor_name}`), so pushing it would
            # desync name from docname. ADR 068 section 5 makes the key opaque
            # and this binding appears then.
        },
    ),
    Spec(
        "primary_email",
        # `email` is a positional on ensure_person and handled separately in
        # `_apply` (it is the match heuristic as well as a value), so it is not
        # settable through the generic values dict.
        roles={
            STUDENT: Binding("student_email_id", propagate=True),
            APPLICANT: Binding("student_email_id", propagate=True),
            INSTRUCTOR: Binding("prof_email", propagate=True),
            # Alumni Profile.email is the docname today; see full_name above.
        },
    ),
    Spec(
        "primary_mobile",
        arg="mobile",
        mode=AUTHORED,
        roles={
            STUDENT: Binding("student_mobile_number", propagate=True),
            APPLICANT: Binding("student_mobile_number", propagate=True),
            INSTRUCTOR: Binding("phone_message", propagate=True),
        },
    ),
    Spec("language", arg="language", mode=FILL_ONLY),
    Spec("country", arg="country", mode=FILL_ONLY),
    Spec(
        "image",
        arg="image",
        mode=FILL_ONLY,
        roles={
            # Not propagated today: Student.image and Instructor.profileimage
            # are independently writable. Phase 4 makes them mirrors.
            STUDENT: Binding("image"),
            INSTRUCTOR: Binding("profileimage"),
            # A mirror of a mirror: the alumnus's photo comes from their
            # Student record rather than from the spine, so an alumnus who was
            # never a student here has no photo at all.
            ALUMNI: Binding("image", kind=FOREIGN, source="student.image"),
        },
    ),
    Spec(
        "gender",
        arg="gender",
        # FILL_ONLY today, which is why `update_person(overwrite=True)` cannot
        # correct a gender. Phase 4 promotes it to AUTHORED.
        mode=FILL_ONLY,
        roles={
            STUDENT: Binding("gender"),
            APPLICANT: Binding("gender"),
            # Sourced from erpnext's Employee, which is not in `required_apps`
            # — so on a bench without erpnext the link dangles and the field is
            # simply dead. Gender is identity, not payroll; phase 4 repoints it
            # at Person.
            INSTRUCTOR: Binding("gender", kind=FOREIGN, source="employee.gender"),
        },
    ),
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
