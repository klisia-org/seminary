"""Generic, vendor-agnostic external plagiarism provider.

Posts the target text to a configurable HTTP endpoint and maps the JSON response
back into a PlagiarismReport via dotted paths in the Provider Account config — so
any web-plagiarism API can be wired up with one account row, no code change. No
vendor (Winston etc.) is hardcoded. External failures yield a Failed report;
they never block grading.
"""

import json

import frappe
from frappe import _

from .base import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    MatchedSource,
    PlagiarismAdapter,
    PlagiarismReport,
)


def _dig(data, path):
    """Resolve a dotted path (``result.score``) against nested dict/list JSON."""
    if not path:
        return None
    cur = data
    for key in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(key)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
        if cur is None:
            return None
    return cur


class ExternalHTTPPlagiarismAdapter(PlagiarismAdapter):
    provider_key = "external-http"
    requires_account = True

    def check(self, target: dict, corpus: list, config: dict) -> PlagiarismReport:
        report = PlagiarismReport()
        report.checked_chars = len(target.get("text") or "")
        report.engine_meta = {"provider": "external-http"}

        endpoint = config.get("endpoint")
        if not endpoint:
            report.status = STATUS_FAILED
            report.error = _("External provider has no endpoint configured.")
            return report

        text = target.get("text") or ""
        template = config.get("request_template")
        if template:
            try:
                body = json.loads(template.replace("{{text}}", json.dumps(text)[1:-1]))
            except ValueError:
                body = {"text": text}
        else:
            body = {"text": text}

        headers = {"Content-Type": "application/json"}
        api_key = config.get("api_key")
        if api_key:
            header = config.get("auth_header") or "Authorization"
            scheme = config.get("auth_scheme")
            headers[header] = f"{scheme} {api_key}" if scheme else api_key

        try:
            import requests

            request_timeout = int(config.get("timeout") or 60)
            resp = requests.post(
                endpoint,
                json=body,
                headers=headers,
                timeout=request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Plagiarism external provider")
            report.status = STATUS_FAILED
            report.error = str(e)[:500]
            return report

        score = _dig(data, config.get("response_score_path"))
        try:
            report.overall_score = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            report.overall_score = 0.0

        sources = _dig(data, config.get("response_sources_path"))
        if isinstance(sources, list):
            for s in sources[:25]:
                if not isinstance(s, dict):
                    continue
                report.matched_sources.append(
                    MatchedSource(
                        source_submission=str(
                            s.get("url") or s.get("title") or s.get("source") or ""
                        ),
                        similarity=float(s.get("score") or s.get("similarity") or 0.0),
                        source_student_name=s.get("title") or s.get("url"),
                    )
                )
        report.source_count = len(report.matched_sources)
        report.status = STATUS_COMPLETED
        return report
