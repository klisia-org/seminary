"""p006 Phase 0 curl-matrix runner against potestas.localhost:8006.

Each check: (jar, method, params, expect) where expect is an HTTP status or a
callable(resp) -> (ok: bool, note: str). Prints PASS/FAIL per row and a summary.
"""

import json
import sys

import requests

H = "http://localhost:8006"
PW = "P0test!2026"
USERS = {
    "guest": None,
    "stuA": "demo.jedwards@seminary.edu",
    "stuB": "demo.jcalvin@seminary.edu",
    "instr": "demo.mluther@seminary.edu",  # Instructor + Program Chair
    "instr2": "gwetherby@example.net",  # Instructor, no sections
    "reg": "enascimento@example.com",  # Student + Registrar
    "chair": "tcholmondeley@example.net",  # Program Chair
    "admin": "Administrator",
}

SESSIONS = {}


def jar(name):
    if name in SESSIONS:
        return SESSIONS[name]
    s = requests.Session()
    s.headers["Host"] = "potestas.localhost"
    if USERS[name]:
        r = s.post(f"{H}/api/method/login", data={"usr": USERS[name], "pwd": PW})
        assert (
            r.status_code == 200
        ), f"login failed for {name}: {r.status_code} {r.text[:200]}"
        page = s.get(f"{H}/seminary/courses")
        import re as _re

        m = _re.search(r'csrf_token"?\]?\s*[:=]\s*"([^"]+)"', page.text)
        if m:
            s.headers["X-Frappe-CSRF-Token"] = m.group(1)
    SESSIONS[name] = s
    return s


def call(who, method, params=None, http="POST", as_json=False):
    s = jar(who)
    url = f"{H}/api/method/{method}"
    if http == "GET":
        return s.get(url, params=params or {})
    if as_json:
        return s.post(url, json=params or {})
    return s.post(
        url,
        data={
            k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
            for k, v in (params or {}).items()
        },
    )


RESULTS = []


def check(
    label, who, method, params=None, expect=200, http="POST", as_json=False, after=None
):
    try:
        r = call(who, method, params, http=http, as_json=as_json)
    except AssertionError as e:
        RESULTS.append((label, False, str(e)))
        print(f"FAIL  {label}: {e}")
        return None
    if callable(expect):
        ok, note = expect(r)
    else:
        ok, note = (r.status_code == expect), f"got {r.status_code}"
        if not ok:
            note += " " + r.text[:160].replace("\n", " ")
    if ok and after:
        ok2, note2 = after()
        ok, note = ok and ok2, f"{note}; {note2}"
    RESULTS.append((label, ok, note))
    print(("PASS " if ok else "FAIL ") + f" {label}: {note}")
    return r


def summary():
    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
    for label, _, note in fails:
        print(f"  FAIL {label}: {note}")
    return 1 if fails else 0


if __name__ == "__main__":
    print("skeleton only; import and add checks")
    sys.exit(0)
