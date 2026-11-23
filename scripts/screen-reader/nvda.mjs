// The accessibility journeys with NVDA, on Windows (decision 102a §4).
//
// Usage: node nvda.mjs <journeys.json> <report.md>
//
// journeys.json comes from the bench (see README.md): the URLs, the sessions to sign in with,
// and each journey's moves. NVDA words things differently from the virtual reader the test
// suite uses, so nothing is asserted: the report shows what NVDA said at each check, and what
// the virtual reader is expected to hear there, for a person to read.
import { readFileSync, writeFileSync } from "node:fs";

import { nvda } from "@guidepup/guidepup";
import puppeteer from "puppeteer-core";

const [jobPath, outPath] = process.argv.slice(2);
if (!jobPath || !outPath) {
  console.error("Usage: node nvda.mjs <journeys.json> <report.md>");
  process.exit(2);
}
const job = JSON.parse(readFileSync(jobPath, "utf8"));
const chrome =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function runSteps(page, steps) {
  for (const step of steps || []) {
    if (step.click) await page.click(step.click);
    else if (step.type) await page.type(step.type[0], step.type[1]);
    if (step.wait) await pause(step.wait);
  }
}

// What NVDA says inside its own windows, not the page.
const OUTSIDE_CHROME = [/speech viewer/i, /read only, multi line/i];

async function journey(page, row) {
  const checks = [];
  let said = [];
  const listen = async () => {
    said = said.concat(await nvda.spokenPhraseLog());
    await nvda.clearSpokenPhraseLog();
  };
  await page.goto(row.url, { waitUntil: "networkidle2", timeout: 60000 });
  await pause(1500);
  // A session that has ended (they last an hour) lands on the login page, where NVDA's
  // moves would type into the form instead of reading the page.
  if (row.cookies?.length && new URL(page.url()).pathname.startsWith("/login"))
    throw new Error(
      "The site asked to sign in: the exported sessions have ended. Export the journeys again."
    );
  // The page must have the keyboard focus: in a window that isn't in front NVDA ignores focus
  // changes, and in the address bar (where Chrome may leave it after loading a page) NVDA's
  // keys would type the address. F6 moves Chrome's focus from the address bar to the page.
  const inPage = () => page.evaluate(() => document.hasFocus());
  let focused = await inPage();
  for (let i = 0; i < 3 && !focused; i++) {
    await nvda.press("F6");
    await pause(500);
    focused = await inPage();
  }
  await runSteps(page, row.steps);
  // Which window NVDA is reading: its title, said by NVDA, should name the page.
  await nvda.clearSpokenPhraseLog();
  await nvda.perform(nvda.keyboardCommands.reportTitle);
  await pause(800);
  const window = (await nvda.spokenPhraseLog()).join(" ");
  // Browse mode starts where NVDA last was: begin every journey at the top of the page.
  // Control+Home reads the first item, which the virtual reader reaches with its first
  // "next", so that move presses once less.
  await nvda.clearSpokenPhraseLog();
  await nvda.press("Control+Home");
  await pause(800);
  let atTop = true;
  for (const move of row.moves) {
    const fromTop = atTop;
    atTop = false;
    if (move.next)
      for (let i = fromTop ? 1 : 0; i < move.next; i++) await nvda.next();
    else if (move.landmark)
      for (let i = 0; i < move.landmark; i++)
        await nvda.perform(nvda.keyboardCommands.moveToNextLandmark);
    else if (move.focus) await page.focus(move.focus);
    // A real key press, as a person would make, so that NVDA sees it.
    else if (move.press) await nvda.press(move.press);
    else if (move.click) await page.click(move.click);
    else if (move.clear) {
      await listen();
      said = [];
    }
    // NVDA speaks after the browser has moved: give it a moment.
    await pause(move.wait || 800);
    // NVDA may not announce a focus change the page made itself (the virtual reader does), so
    // it is asked what has the focus. If that names something outside the page, NVDA wasn't
    // following Chrome.
    if (move.focus || move.press || move.click) {
      await nvda.perform(nvda.keyboardCommands.reportCurrentFocus);
      await pause(800);
    }
    if (move.hear || move.not_hear) {
      await listen();
      checks.push({
        hear: move.hear || [],
        not_hear: move.not_hear || [],
        said: [...said],
      });
    }
  }
  await listen();
  return { checks, said, focused, window };
}

const lines = [
  "# NVDA journeys",
  "",
  `Site: ${job.base}. Run: ${new Date().toISOString()}.`,
  "",
  "What NVDA said at each check, beside what the virtual reader must hear there. NVDA's",
  "wording differs, so read each check rather than matching text: the question is whether NVDA",
  "gave the same information.",
  "",
];
// Chrome first: started from the terminal you are using, Windows puts it in front, and nothing
// the script does afterwards asks for the front again (Windows would refuse and only flash
// Chrome's taskbar button). NVDA reads the window in front, so its own Speech Viewer must stay
// off (see README.md).
const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: false,
  defaultViewport: null,
  // On the main monitor (it starts at 0,0), maximised.
  args: [
    "--window-position=0,0",
    "--start-maximized",
    "--force-renderer-accessibility",
  ],
});
await nvda.start();
await pause(3000);
try {
  // One tab for every journey: each new tab is a chance for the focus to go elsewhere.
  const page = (await browser.pages())[0] || (await browser.newPage());
  for (const row of job.journeys) {
    if (row.cookies?.length) await browser.setCookie(...row.cookies);
    lines.push(`## ${row.key}`, "", row.url, "");
    try {
      const { checks, said, focused, window } = await journey(page, row);
      lines.push(`NVDA was reading: ${window || "(it didn't say)"}`, "");
      if (!focused)
        lines.push(
          "**The page didn't have the keyboard focus during this journey** (Chrome's window wasn't in front, or the focus stayed in the address bar), so NVDA may have read something else. Close other windows, start the run, and don't touch the keyboard or mouse until Chrome closes.",
          ""
        );
      else if (!said.length && checks.every((c) => !c.said.length))
        lines.push("**NVDA said nothing during this journey.**", "");
      if (
        said.some((p) => OUTSIDE_CHROME.some((re) => re.test(p))) ||
        checks.some((c) =>
          c.said.some((p) => OUTSIDE_CHROME.some((re) => re.test(p)))
        )
      )
        lines.push(
          "**NVDA left Chrome during this journey** (it read one of its own windows). Close NVDA's Speech Viewer and run again.",
          ""
        );
      checks.forEach((c, i) => {
        lines.push(`### Check ${i + 1}`, "");
        if (c.hear.length)
          lines.push(
            `- Virtual reader must hear: ${c.hear
              .map((t) => `"${t}"`)
              .join(", ")}`
          );
        if (c.not_hear.length)
          lines.push(
            `- Virtual reader must not hear: ${c.not_hear
              .map((t) => `"${t}"`)
              .join(", ")}`
          );
        lines.push("- NVDA said:", "", ...c.said.map((p) => `  - ${p}`), "");
      });
    } catch (err) {
      lines.push(`Not run: ${String(err).slice(0, 300)}`, "");
    } finally {
      const cookies = await browser.cookies();
      if (cookies.length) await browser.deleteCookie(...cookies);
    }
  }
} finally {
  await nvda.stop();
  await browser.close();
}
for (const m of job.not_run || [])
  lines.push(`- Not run: ${m.journey}: ${m.why}`);
writeFileSync(outPath, lines.join("\n") + "\n");
console.log("Wrote", outPath);
