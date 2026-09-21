#!/usr/bin/env bash
# Set up the SCORM two-origin pass on a developer bench (p009 §7).
#
# Every bug p009 has had in a browser was a contradiction between two things we
# send that only a browser holds at once -- frame-ancestors against the frame
# the launcher creates, a CSP against the redirect we issue, a token's
# stability against the player's cleanup. None of them is visible from the
# server, and chasing them one deploy at a time against a canary is the slowest
# way to find them. This makes the pass local.
#
#   bash scripts/p009_validation/two_origin_local.sh potestas.localhost 8006
#
# What it does NOT reproduce: the nginx layer. `bench serve` has no nginx, so
# the `.html` rewrite and the `X-Frame-Options` header are deployment-only.
# `seminary.scorm.selftest.run` arm 4 is what covers those, on a real host.
set -euo pipefail

SITE="${1:-potestas.localhost}"
PORT="${2:-8006}"
DELIVERY="scormdev.localhost"
BENCH_SITES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/sites"

if [ ! -d "$BENCH_SITES/$SITE" ]; then
  echo "no such site: $BENCH_SITES/$SITE" >&2
  exit 1
fi

# The second origin is the *same site*, reached by another hostname. frappe
# resolves a site from the Host header by looking for sites/<host>, so a symlink
# is all it takes -- and because redis keys are prefixed with `db_name` rather
# than the site name, a launch token minted on one host resolves on the other.
if [ ! -e "$BENCH_SITES/$DELIVERY" ]; then
  ln -s "$SITE" "$BENCH_SITES/$DELIVERY"
  echo "linked sites/$DELIVERY -> $SITE"
else
  echo "sites/$DELIVERY already present"
fi

# `scormdev.localhost` and `<site>` are different registrable domains under the
# `.localhost` TLD, so the §2.2 cookie property holds here too -- the selftest's
# registrable-domain check passes rather than being waived.
bench --site "$SITE" set-config scorm_delivery_host "$DELIVERY"
bench --site "$SITE" set-config scorm_delivery_origin "http://$DELIVERY:$PORT"
bench --site "$SITE" set-config scorm_app_origin "http://$SITE:$PORT"
bench --site "$SITE" clear-cache

cat <<NOTE

Configured. Now:

  bench serve --port $PORT

  app       http://$SITE:$PORT
  delivery  http://$DELIVERY:$PORT

Both names resolve to 127.0.0.1 without touching /etc/hosts (browsers treat
*.localhost as loopback). Open a SCORM lesson in the app and watch the console.

Check the wiring first:

  bench --site $SITE execute seminary.scorm.selftest.run

Arms 1-3 should be green. Arm 4 will fail to resolve $DELIVERY unless
/etc/hosts names it -- **browsers** map *.localhost to loopback internally,
Python's resolver does not. The browser pass works without this; only arm 4
needs it:

  echo "127.0.0.1 $DELIVERY" | sudo tee -a /etc/hosts

Arm 1 accepts the plaintext origin *because* the host is loopback; on anything
else it refuses, so this cannot reach production.
NOTE
