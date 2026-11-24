"""LTI 1.3 and LTI Advantage, with seminary as the platform (decisions/110).

- ``keys``: this site's signing keys and the tool-key checks.
- ``launch``: the OIDC launch and Deep Linking.
- ``services``: the token endpoint, Assignment and Grade Services, Names and Roles.
- ``grades``: when a posted score reaches the gradebook.
- ``registration``: Dynamic Registration.
- ``renderer``: the ``/lti/...`` routes.
"""

#: Every route this package serves lives under ``/lti/``.
PREFIX = "lti"

LTI_VERSION = "1.3.0"
CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"
DL_CLAIM = "https://purl.imsglobal.org/spec/lti-dl/claim/"
AGS_CLAIM = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
NRPS_CLAIM = "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice"

SCOPE_LINEITEM_READ = "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly"
SCOPE_RESULT_READ = "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly"
SCOPE_SCORE = "https://purl.imsglobal.org/spec/lti-ags/scope/score"
SCOPE_NRPS = "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly"
AGS_SCOPES = (SCOPE_LINEITEM_READ, SCOPE_RESULT_READ, SCOPE_SCORE)

ROLE_LEARNER = "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
ROLE_INSTRUCTOR = "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"
ROLE_TA = "http://purl.imsglobal.org/vocab/lis/v2/membership/Instructor#TeachingAssistant"
CONTEXT_SECTION = "http://purl.imsglobal.org/vocab/lis/v2/course#CourseSection"


def url(*parts: str) -> str:
	"""An absolute URL on this site under ``/lti/``."""
	import frappe

	return frappe.utils.get_url("/" + "/".join((PREFIX, *parts)))


def issuer() -> str:
	"""The platform's issuer: this site's own URL, with no trailing slash."""
	import frappe

	return frappe.utils.get_url().rstrip("/")
