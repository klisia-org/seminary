// WCAG 2.2 A and AA checks with axe-core in Chromium (decision 102 §3).
//
// Usage: node check.mjs <job.json> <out.json>
//
// The job is written by seminary.seminary.accessibility:
//   {"tags": [...], "remove": [selectors], "visits": [{"key", "url", "cookies": [{name, value, url}]}]}
// The report lists, for each visit, the rules that failed, passed, did not apply,
// or need a person, plus every rule's WCAG tags so the caller can map rules to
// success criteria without keeping its own copy of axe's mapping.
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

import puppeteer from "puppeteer-core";

const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const [jobPath, out] = process.argv.slice(2);
const job = JSON.parse(readFileSync(jobPath, "utf8"));
const tags = job.tags;

// The portal is a single-page app: wait until it has drawn something and its
// spinners are gone, rather than for the network, which a socket keeps busy.
async function settle(page) {
  await page
    .waitForFunction(
      () => {
        const app = document.querySelector("#app") || document.body;
        if (!app || !app.children.length) return false;
        return !document.querySelector(".animate-spin, [aria-busy='true']");
      },
      { timeout: 15000, polling: 250 }
    )
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 400));
}

const node = (n) => ({
  target: n.target.join(" "),
  html: n.html.slice(0, 300),
  why: (n.failureSummary || "").slice(0, 400),
});

const browser = await puppeteer.launch({
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
  args: ["--no-sandbox"],
});
const visits = [];
let rules = {};
try {
  for (const visit of job.visits) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.setBypassCSP(true);
    // A confirm() (the time-zone prompt, a leave-page guard) would stall the run.
    page.on("dialog", (d) => d.dismiss().catch(() => {}));
    await page.evaluateOnNewDocument(() => {
      try {
        sessionStorage.setItem("seminary_tz_reported", "1");
      } catch (e) {
        // No sessionStorage (a sandboxed page): the prompt is then dismissed below.
      }
    });
    if (visit.cookies?.length) await browser.setCookie(...visit.cookies);
    const row = { key: visit.key, url: visit.url };
    try {
      const res = await page.goto(visit.url, {
        waitUntil: "networkidle2",
        timeout: 60000,
      });
      row.status = res ? res.status() : null;
      await settle(page);
      row.final_url = page.url();
      row.title = await page.title();
      // A school's portal theme is checked when it is saved; the report measures
      // Seminary's own colours, so the theme's stylesheet is taken out first.
      if (job.remove?.length) {
        await page.evaluate((sels) => {
          for (const sel of sels)
            document.querySelectorAll(sel).forEach((el) => el.remove());
        }, job.remove);
        await new Promise((r) => setTimeout(r, 100));
      }
      await page.addScriptTag({ content: axeSource });
      const result = await page.evaluate(
        (tags) =>
          window.axe.run(document, {
            runOnly: { type: "tag", values: tags },
            resultTypes: ["violations", "incomplete"],
          }),
        tags
      );
      if (!Object.keys(rules).length) {
        rules = await page.evaluate(() =>
          Object.fromEntries(
            window.axe
              .getRules()
              .map((r) => [r.ruleId, { tags: r.tags, help: r.help }])
          )
        );
        row.axe_version = await page.evaluate(() => window.axe.version);
      }
      row.violations = result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        count: v.nodes.length,
        nodes: v.nodes.slice(0, 5).map(node),
      }));
      row.passes = result.passes.map((v) => v.id);
      row.inapplicable = result.inapplicable.map((v) => v.id);
      row.incomplete = result.incomplete.map((v) => v.id);
    } catch (err) {
      row.error = String(err).slice(0, 500);
    } finally {
      await page.close();
      const cookies = await browser.cookies();
      if (cookies.length) await browser.deleteCookie(...cookies);
    }
    visits.push(row);
  }
} finally {
  await browser.close();
}
writeFileSync(out, JSON.stringify({ tags, rules, visits }, null, 1));
