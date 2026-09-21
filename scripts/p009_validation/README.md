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

## Against real packages

Synthetic packages are structurally honest and nothing like what an authoring
tool emits, so `main()` takes a path:

```python
m["main"]("/path/to/export.zip", title="ZZT p009 golf")
```

**ADL Golf sample, SCORM 2004 3rd Edition** (`SequencingPostTestRollup`), run
2026-09-20 against live R2 — 78 entries in, 69 inventoried (9 directory entries
skipped), version detected as 2004, five SCOs became five lessons, and every
member served: HTML/JS/CSS proxied with the recorded type, JPG/PNG/XSD
redirected to a presigned URL. Two things it proved that no synthetic package
had:

* **The manifest's hrefs carry query strings** (`shared/launchpage.html?content=playing`,
  the same file five times). The lookup splits on `?` and keeps the suffix for
  the launch URL, which is exactly what `manifest.SCO.suffix` is for.
* **Its API discovery is `ScanForAPI(win.parent)`**, walking while
  `win.API_1484_11 == null`. It finds the launcher on the first hop, which is
  the property the whole same-origin launcher design exists to give it.

**Not a SCORM package:** an Articulate `.story` file zipped up is the authoring
*source*, not a published export, and is refused with "This SCORM package has no
imsmanifest.xml." The export comes from *Publish → LMS → SCORM 1.2 / 2004*.

**ADL `SequencingRandomTest`, SCORM 2004 3rd Edition**, run 2026-09-20 — 69 members, **eight**
SCOs became eight lessons (four content modules plus `test_1`..`test_4`). It is the package that
shows what "sequencing is out of scope" costs: it asks for `randomizationControls
randomizationTiming="onEachNewAttempt" reorderChildren="true"` over the four test items and
carries rollup rules across children, and under p009 those four appear in manifest order, the
same order every time, with chapter completion counted as "all eight lessons complete". Every
byte plays; the assessment design does not. See p009 §2.5.
