# NVDA journeys

The test suite walks the journeys in `docs/accessibility/journeys.yaml` with a virtual screen
reader. This folder runs the same journeys with NVDA, the screen reader most people use on
Windows, and records what it said. It asserts nothing: read the report and use it for the manual
rows in `docs/accessibility/manual.yaml`. It also covers what the virtual reader can't hear,
such as toasts and other alerts added to the page.

Run it on a Windows machine that can open the site, e.g. the Windows side of a WSL2 bench, where
`http://<site>.localhost:<port>` is forwarded to Windows.

## Once

On Windows, with Node 18 or later (a current LTS is better) and Google Chrome. If PowerShell
refuses to run `npx`/`npm` ("running scripts is disabled"), use `npx.cmd`/`npm.cmd`, or run the
same commands from Command Prompt:

```powershell
# Copy this folder somewhere on the Windows disk first: npm is unreliable on \\wsl$ paths.
cd C:\screen-reader
npm install
npx @guidepup/setup
```

`@guidepup/setup` installs a copy of NVDA that Guidepup can drive and sets Windows up for it.
Close any other running NVDA before a run.

That copy opens NVDA's Speech Viewer when it starts, and the viewer takes the focus from
Chrome. It doesn't save settings changed while it runs, so turn the viewer off in its settings
file instead: in `%LOCALAPPDATA%\guidepup\nvda\all\<version>\extracted\userConfig\nvda.ini`,
under `[speechViewer]`, set `showSpeechViewerAtStartup = False`. Guidepup reads NVDA's speech
through NVDA Remote, not the viewer. Do it again after running `@guidepup/setup` again.

## Each run

1. **In WSL**, export the journeys with sessions to sign in with. The sessions last an hour.

   ```bash
   bench --site <site> execute seminary.seminary.accessibility.export_journeys \
     --kwargs "{'out': '/mnt/c/screen-reader/journeys.json'}"
   ```

   Another app's journeys: add `'target': '<app>.accessibility.target'` to the kwargs.

2. **On Windows**, within the hour, run them from a terminal window, and close other windows
   first. Chrome opens, then NVDA starts and speaks. NVDA reads whichever window is in front,
   and Windows won't put Chrome back in front once another window has taken it: don't use the
   keyboard or mouse until Chrome closes. If the report says the page didn't have the keyboard focus,
   something took the focus; run it again.

   ```powershell
   node nvda.mjs journeys.json report.md
   ```

   If Chrome isn't in its usual place, set `CHROME_PATH` first.

3. **In WSL**, end the sessions:

   ```bash
   bench --site <site> execute seminary.seminary.accessibility.end_exported_sessions \
     --kwargs "{'path': '/mnt/c/screen-reader/journeys.json'}"
   ```

4. Read `report.md`. For each check, the question is whether NVDA gave the same information as
   the virtual reader, not whether it used the same words. Then delete `journeys.json`: it holds
   sign-ins until the sessions end.
