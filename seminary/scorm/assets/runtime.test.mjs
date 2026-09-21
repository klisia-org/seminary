/* Copyright (c) 2026, Klisia / SeminaryERP and contributors
 *
 * The SCORM runtime, exercised in node (privatedocs p009 §9.x).
 *
 *     node --test seminary/scorm/assets/
 *
 * This runs the real `runtime.js` in a vm context with a fake transport, so the
 * data-model behaviour, the error codes and -- most importantly -- **what
 * crosses the origin boundary** are covered without a browser. What it cannot
 * cover is the part that needs two real origins: the `postMessage` hop itself,
 * the sandboxed iframe, and the `window.API` discovery walk. That is the tlink
 * pass, and these tests are what keeps it from being the first time anything is
 * checked.
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, "runtime.js"), "utf8");

function load() {
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(source, ctx);
  return ctx.SeminaryScormRuntime;
}

function harness(config = {}) {
  const sent = [];
  let clock = 0;
  const timers = new Map();
  let nextTimer = 1;

  const transport = {
    send: (m) => sent.push(m),
    now: () => clock,
    setTimeout: (fn, ms) => {
      const id = nextTimer++;
      timers.set(id, { fn, at: clock + ms });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    flushDelay: 3000,
  };

  const runtime = load().createRuntime(
    Object.assign({ version: "1.2", sco: "SCO1", appOrigin: "https://app.invalid" }, config),
    transport
  );
  return {
    runtime,
    sent,
    // Payloads are built inside the vm context, so their prototype is the vm's
    // `Object.prototype` and `deepStrictEqual` refuses them. Copy into a host
    // object before comparing.
    merged() {
      return Object.assign({}, ...sent.filter((m) => m.type === "scorm:commit").map((m) => ({ ...m.data })));
    },
    api: runtime.is2004 ? runtime.api2004 : runtime.api12,
    tick(ms) {
      clock += ms;
      for (const [id, t] of [...timers]) {
        if (t.at <= clock) {
          timers.delete(id);
          t.fn();
        }
      }
    },
    commits: () => sent.filter((m) => m.type === "scorm:commit"),
  };
}

test("the 1.2 API is installed, and only the 1.2 API", () => {
  const win = {};
  harness({ version: "1.2" }).runtime.install(win);
  assert.equal(typeof win.API.LMSInitialize, "function");
  assert.equal(win.API_1484_11, undefined, "advertising both confuses a package that probes");
});

test("the 2004 API is installed, and only the 2004 API", () => {
  const win = {};
  harness({ version: "2004" }).runtime.install(win);
  assert.equal(typeof win.API_1484_11.Initialize, "function");
  assert.equal(win.API, undefined);
});

test("nothing works before Initialize", () => {
  const h = harness();
  assert.equal(h.api.LMSGetValue("cmi.core.lesson_status"), "");
  assert.equal(h.api.LMSGetLastError(), "301");
  assert.equal(h.api.LMSSetValue("cmi.core.lesson_status", "completed"), "false");
  assert.equal(h.api.LMSCommit(), "false");
  assert.equal(h.commits().length, 0);
});

test("a second Initialize is refused", () => {
  const h = harness({ version: "2004" });
  assert.equal(h.api.Initialize(""), "true");
  assert.equal(h.api.Initialize(""), "false");
  assert.equal(h.api.GetLastError(), "103");
});

test("the launch snapshot seeds the model both ways", () => {
  const h = harness({
    version: "1.2",
    cmi: {
      learner_id: "opaque-id",
      learner_name: "A Student",
      location: "page-4",
      suspend_data: "{\"p\":4}",
      completion_status: "incomplete",
      score_raw: 42,
    },
  });
  h.api.LMSInitialize("");
  assert.equal(h.api.LMSGetValue("cmi.core.student_id"), "opaque-id");
  assert.equal(h.api.LMSGetValue("cmi.core.lesson_location"), "page-4");
  assert.equal(h.api.LMSGetValue("cmi.suspend_data"), '{"p":4}');
  assert.equal(h.api.LMSGetValue("cmi.core.lesson_status"), "incomplete");
  assert.equal(h.api.LMSGetValue("cmi.core.score.raw"), "42");
});

test("a 2004 snapshot keeps completion and success apart", () => {
  const h = harness({
    version: "2004",
    cmi: { completion_status: "completed", success_status: "failed", score_scaled: -0.5 },
  });
  h.api.Initialize("");
  assert.equal(h.api.GetValue("cmi.completion_status"), "completed");
  assert.equal(h.api.GetValue("cmi.success_status"), "failed");
  assert.equal(h.api.GetValue("cmi.score.scaled"), "-0.5");
});

test("read-only elements are refused", () => {
  const h = harness();
  h.api.LMSInitialize("");
  assert.equal(h.api.LMSSetValue("cmi.core.student_id", "someone-else"), "false");
  assert.equal(h.api.LMSGetLastError(), "403");
  assert.equal(h.api.LMSSetValue("cmi.core._children", "x"), "false");
});

test("_children and _count are answered", () => {
  const h = harness();
  h.api.LMSInitialize("");
  assert.match(h.api.LMSGetValue("cmi.core._children"), /lesson_status/);
  assert.equal(h.api.LMSGetValue("cmi.core.score._children"), "raw,min,max");
  assert.equal(h.api.LMSGetValue("cmi.interactions._count"), "0");
  assert.equal(h.api.LMSGetLastError(), "0");
});

test("an unknown cmi element answers empty rather than erroring", () => {
  // A package probing something we do not track must keep working.
  const h = harness();
  h.api.LMSInitialize("");
  assert.equal(h.api.LMSGetValue("cmi.student_preference.audio"), "");
  assert.equal(h.api.LMSGetLastError(), "0");
  assert.equal(h.api.LMSGetValue("not.a.cmi.element"), "");
  assert.equal(h.api.LMSGetLastError(), "401");
});

test("ONLY persisted elements cross the origin boundary", () => {
  const h = harness();
  h.api.LMSInitialize("");
  h.api.LMSSetValue("cmi.interactions.0.id", "q1");
  h.api.LMSSetValue("cmi.objectives.0.id", "obj1");
  h.api.LMSSetValue("cmi.core.lesson_location", "page-9");
  h.api.LMSCommit();

  const [commit] = h.commits();
  assert.deepEqual(Object.keys(commit.data), ["cmi.core.lesson_location"]);
  // ...and the package can still read back what it wrote locally.
  assert.equal(h.api.LMSGetValue("cmi.interactions.0.id"), "q1");
});

test("writes are batched, not one message per SetValue", () => {
  const h = harness();
  h.api.LMSInitialize("");
  h.api.LMSSetValue("cmi.core.lesson_location", "1");
  h.api.LMSSetValue("cmi.core.lesson_location", "2");
  h.api.LMSSetValue("cmi.suspend_data", "s");
  assert.equal(h.commits().length, 0, "a SetValue must not be a round trip");
  h.tick(3000);
  assert.equal(h.commits().length, 1);
  assert.deepEqual({ ...h.commits()[0].data }, {
    "cmi.core.lesson_location": "2",
    "cmi.suspend_data": "s",
  });
});

test("Commit with nothing dirty sends nothing", () => {
  const h = harness();
  h.api.LMSInitialize("");
  h.api.LMSCommit();
  assert.equal(h.commits().length, 0);
});

test("Finish flushes, reports a session time, and closes the API", () => {
  const h = harness();
  h.api.LMSInitialize("");
  h.api.LMSSetValue("cmi.core.lesson_status", "completed");
  h.tick(62_000);
  assert.equal(h.api.LMSFinish(""), "true");

  // 62s is past the auto-flush, so the status went in that batch and Finish
  // carries only what was still dirty. What matters is that everything reached
  // the LMS exactly once, not which message carried it.
  const all = h.merged();
  assert.equal(all["cmi.core.lesson_status"], "completed");
  assert.match(all["cmi.core.session_time"], /^\d{4}:\d{2}:\d{2}\.\d{2}$/);
  assert.ok(h.sent.some((m) => m.type === "scorm:terminate"));

  assert.equal(h.api.LMSSetValue("cmi.core.lesson_status", "failed"), "false");
  assert.equal(h.api.LMSGetLastError(), "301");
});

test("a session time the package set is not overwritten", () => {
  const h = harness();
  h.api.LMSInitialize("");
  h.api.LMSSetValue("cmi.core.session_time", "0000:07:00.00");
  h.tick(999_000);
  h.api.LMSFinish("");
  assert.equal(h.merged()["cmi.core.session_time"], "0000:07:00.00");
});

test("2004 lifecycle errors are the 2004 ones", () => {
  const h = harness({ version: "2004" });
  assert.equal(h.api.GetValue("cmi.location"), "");
  assert.equal(h.api.GetLastError(), "122");
  h.api.Initialize("");
  h.api.Terminate("");
  assert.equal(h.api.SetValue("cmi.location", "x"), "false");
  assert.equal(h.api.GetLastError(), "133");
  assert.equal(h.api.Commit(""), "false");
  assert.equal(h.api.GetLastError(), "143");
});

test("every message names its SCO", () => {
  const h = harness({ sco: "SCO-7" });
  h.api.LMSInitialize("");
  h.api.LMSSetValue("cmi.core.lesson_status", "completed");
  h.api.LMSCommit();
  h.api.LMSFinish("");
  assert.ok(h.sent.length > 0);
  for (const message of h.sent) assert.equal(message.sco, "SCO-7");
});
