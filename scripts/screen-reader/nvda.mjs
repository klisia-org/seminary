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

// NVDA reads the window that has the system focus. Another window (NVDA's own Speech Viewer,
// say) can take it between journeys, so Chrome's window is minimised and restored, which
// brings it to the front, before each one.
async function focusChrome(page) {
  const cdp = await page.createCDPSession();
  const { windowId } = await cdp.send("Browser.getWindowForTarget");
  await cdp.send("Browser.setWindowBounds", {
    windowId,
    bounds: { windowState: "minimized" },
  });
  await pause(300);
  await cdp.send("Browser.setWindowBounds", {
    windowId,
    bounds: { windowState: "maximized" },
  });
  await page.bringToFront();
  await pause(700);
  await cdp.detach();
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
  await focusChrome(page);
  await runSteps(page, row.steps);
  // Browse mode starts where NVDA last was: begin every journey at the top of the page.
  await nvda.press("Control+Home");
  await pause(800);
  await nvda.clearSpokenPhraseLog();
  for (const move of row.moves) {
    if (move.next) for (let i = 0; i < move.next; i++) await nvda.next();
    else if (move.landmark)
      for (let i = 0; i < move.landmark; i++)
        await nvda.perform(nvda.keyboardCommands.moveToNextLandmark);
    else if (move.focus) await page.focus(move.focus);
    else if (move.press) await page.keyboard.press(move.press);
    else if (move.click) await page.click(move.click);
    else if (move.clear) {
      await listen();
      said = [];
    }
    // NVDA speaks after the browser has moved: give it a moment.
    await pause(move.wait || 800);
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
  return { checks, said };
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
const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: false,
  defaultViewport: null,
  args: ["--start-maximized", "--force-renderer-accessibility"],
});
await nvda.start();
try {
  // One tab for every journey: each new tab is a chance for the focus to go elsewhere.
  const page = (await browser.pages())[0] || (await browser.newPage());
  for (const row of job.journeys) {
    if (row.cookies?.length) await browser.setCookie(...row.cookies);
    lines.push(`## ${row.key}`, "", row.url, "");
    try {
      const { checks, said } = await journey(page, row);
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
