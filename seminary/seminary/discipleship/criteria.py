# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# For license information, please see license.txt
"""Assignment rules for the cohort planner (ADR 067 section 8).

Two kinds, and the difference is the operand:

    Filter   a predicate over (student, mentor) -- may this mentor take this
             student? Filters are ANDed to produce the eligible pool.
    Ranking  an order over mentors, given a student. A ranking never fails; it
             sorts. ANDing one would be meaningless, which is why the kind is
             recorded in the catalog rather than inferred from the handler.

A rule that had to hold one student against *another student* would be neither,
and would need a third kind. None exists; ADR 067's "Deliberately not decided"
records the test for when one would be earned.

Handlers live here and nowhere else. The `Cohort Assignment Criterion` doctype
validates its `handler` against `registry()`, so a school can rename a rule and
retire it but cannot point one at arbitrary code.

Every handler reads from a pre-loaded row dict rather than the database. The
planner builds one row per person once; a handler that queried would turn one
proposal into (students x mentors) round trips.
"""

import math

import frappe
from frappe import _

FILTER = "Filter"
RANKING = "Ranking"

#: Sorts after every rankable mentor without needing a sentinel distance -- a
#: large number would still be a number, and would silently order two unrankable
#: mentors against each other.
UNRANKED = (1, 0.0)

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    """Great-circle distance in kilometres.

    Good enough by a wide margin: the question this answers is "is this mentor
    nearer than that one", over distances where the difference between a sphere
    and the real geoid is far below the precision of a rooftop geocode.
    """
    lat1, lon1, lat2, lon2 = (math.radians(v) for v in (a_lat, a_lon, b_lat, b_lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


class Criterion:
    """One rule, in the shape the planner consumes.

    `requires_field` names a `person_fields` attribute. It is what the readiness
    pre-flight counts, and what a school's mandatory-field curation will gate
    the rule on -- so it is a name from that registry, not a column name picked
    here.
    """

    kind = None
    handler = None
    requires_field = None
    label = None
    description = None

    def missing(self, row):
        """Is the datum this rule needs absent for this person?"""
        raise NotImplementedError

    def excludes(self, student, mentor):
        """Filter only: a reason this pairing is refused, or None to allow it.

        The reason is shown to a chair beside an unplaced student, so it says
        what is wrong in their words.
        """
        return None

    def rank(self, student, mentor):
        """Ranking only: a sort key, lowest first. `UNRANKED` sorts last."""
        return UNRANKED

    def note(self, student, mentor, alternatives):
        """A short decision hint for this student in this group, or None.

        `alternatives` is the student's ranked shortlist of *other* mentors, so
        a note can say what moving them would cost. A bare fact ("12 km") is not
        a decision aid; the comparison is.
        """
        return None


class GenderMatch(Criterion):
    kind = FILTER
    handler = "match_gender"
    requires_field = "gender"
    label = "Match student and mentor gender"
    description = (
        "Only offer a mentor of the same gender as the student. A person whose "
        "gender is not recorded cannot be matched by this rule at all."
    )

    def missing(self, row):
        return not row.get("gender")

    def excludes(self, student, mentor):
        if not student.get("gender"):
            return _("This student's gender is not recorded.")
        if not mentor.get("gender"):
            return _("{0} has no gender recorded.").format(mentor.get("full_name"))
        if student["gender"] != mentor["gender"]:
            return _("{0} is not the same gender as this student.").format(
                mentor.get("full_name")
            )
        return None

    def note(self, student, mentor, alternatives):
        # Worth saying only when it is the binding constraint: a chair about to
        # drag this student needs to know there is nowhere else to drag them.
        if not alternatives:
            return _("Only mentor in the pool matching this student's gender.")
        return None


class NearestMentor(Criterion):
    kind = RANKING
    handler = "nearest_mentor"
    requires_field = "latitude"
    label = "Mentor closest to the student"
    description = (
        "Prefer the nearest mentor. Only meaningful for a distributed program -- "
        "in a residential one every student is next to every mentor and this "
        "orders nothing. Requires both people to have a resolved address."
    )

    def missing(self, row):
        return not row.get("has_point")

    def _distance(self, student, mentor):
        if not (student.get("has_point") and mentor.get("has_point")):
            return None
        return haversine_km(
            student["latitude"],
            student["longitude"],
            mentor["latitude"],
            mentor["longitude"],
        )

    def rank(self, student, mentor):
        km = self._distance(student, mentor)
        # A mentor with no usable point is not "infinitely far": they are
        # unordered by this rule and fall to the back, where a later ranking or
        # the tie-break decides between them.
        return UNRANKED if km is None else (0, km)

    def note(self, student, mentor, alternatives):
        km = self._distance(student, mentor)
        if km is None:
            return None
        nearer = None
        for other in alternatives:
            other_km = self._distance(student, other)
            if other_km is not None:
                nearer = other_km
                break
        if nearer is None:
            return _("{0} away; no other mentor has a usable address.").format(
                format_distance(km)
            )
        return _("{0} away; next nearest mentor {1}.").format(
            format_distance(km), format_distance(nearer)
        )


#: Handler key -> instance. Instances are stateless, so one each is enough.
_REGISTRY = {c.handler: c for c in (GenderMatch(), NearestMentor())}


def registry():
    return dict(_REGISTRY)


def get(handler):
    return _REGISTRY.get(handler)


# ------------------------------------------------------------------- rendering

KM = "Kilometres"
MILES = "Miles"

_KM_PER_MILE = 1.609344


def using_unit(unit):
    """Set the school's unit for this request.

    On `frappe.local` rather than a module global: a module global outlives the
    request in a long-running worker, so one school's setting would render the
    next school's plan (the same reason `frappe.local.cbe_cache` lives there).
    """
    frappe.local.cohort_distance_unit = unit if unit in (KM, MILES) else KM


def format_distance(km):
    """Distances reach a person, never a coordinate -- the point itself is held
    at permlevel 1 and stays server-side (ADR 067 section 10)."""
    if getattr(frappe.local, "cohort_distance_unit", KM) == MILES:
        return _("{0} mi").format(round(km / _KM_PER_MILE, 1))
    return _("{0} km").format(round(km, 1))
