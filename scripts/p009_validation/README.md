# p009 validation

`p3fixtures.py` builds a real two-SCO SCORM package, unpacks it against the
site's **live object storage**, and prints a delivery base URL. The automated
suites (`test_p009_*`) run against a fake backend in a dict; this is the only
check that the unpack and serve paths work against the real store.

```bash
# unpack and print the URL (needs apotheke installed and r2_* in site_config)
bench --site potestas.localhost console
>>> import runpy; runpy.run_path("/home/drmrmelo/lms/apps/seminary/scripts/p009_validation/p3fixtures.py")["main"]()

# then, from a shell -- the Host header is what selects the delivery origin
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: <HOST>' 'http://127.0.0.1:8006<BASE>'

# clean up, objects included
>>> ...["teardown"]()
```

Locally the second hostname is a symlink in `sites/` pointing at the site, which
is how `bench setup add-domain` does it; `scorm_delivery_host` in the site's
`site_config.json` names it. What local testing **cannot** cover is the part
that needs a real second registrable domain over TLS: third-party cookie
behaviour, the sandboxed cross-origin iframe, and `postMessage` between two real
origins. That belongs on the canary.
