/* Copyright (c) 2026, Klisia / SeminaryERP and contributors
 * For license information, please see license.txt
 *
 * The SCORM runtime, running on the DELIVERY origin (privatedocs p009 §2.8).
 *
 * It lives here, inside the launcher document, because the launcher is
 * same-origin with the SCO it frames -- which is what lets a package's standard
 *
 *     while (win.parent) { if (win.API) return win.API; win = win.parent; }
 *
 * discovery find it with **zero bytes of the package rewritten**. No HTML
 * parsing of hostile input, no injection, no per-package state to invalidate.
 *
 * ## Synchronous API, asynchronous transport
 *
 * `LMSGetValue` must return a string *now*; `postMessage` cannot. So the model
 * is held here: seeded from the launch payload, answered locally, and flushed
 * to the parent in debounced batches (plus immediately on Commit, Finish,
 * Terminate and pagehide). That is how every SCORM shim works, and it is why
 * the server treats everything it receives as a claim.
 *
 * ## What crosses the origin boundary
 *
 * Only the elements the server persists. The package may read and write the
 * whole data model here -- spec compliance is a client-side property, and a
 * package that asks for `cmi.interactions.0.id` should get an answer rather
 * than an error -- but nothing outside the persisted set is ever sent. The
 * server has its own copy of that list and drops anything else; this one exists
 * so a chatty package does not generate traffic.
 *
 * Written rather than taken from `scorm-again`: the data-model pedantry is
 * tedious but small, and p010 H11 has just spent effort bounding this app's
 * supply chain. See p009 §8 item 1.
 */

(function (global) {
  "use strict";

  var NO_ERROR = "0";
  var ERR_GENERAL = "101";
  var ERR_NOT_INITIALIZED = "301";
  var ERR_ARGUMENT = "201";
  var ERR_READ_ONLY = "403";
  var ERR_UNDEFINED_ELEMENT = "401";
  // 2004 spells the lifecycle errors out; 1.2 folds them into 301.
  var ERR_2004 = {
    alreadyInitialized: "103",
    terminatedBefore: "112",
    terminatedAfter: "113",
    getBeforeInit: "122",
    getAfterTerm: "123",
    setBeforeInit: "132",
    setAfterTerm: "133",
    commitBeforeInit: "142",
    commitAfterTerm: "143",
    readOnly: "404",
    undefinedElement: "401"
  };

  /* Elements forwarded to the LMS. Deliberately the same list the server keeps
   * in `seminary/scorm/cmi.py`; the server's copy is the one that decides. */
  var PERSISTED = [
    "cmi.core.lesson_status",
    "cmi.core.lesson_location",
    "cmi.core.score.raw",
    "cmi.core.score.min",
    "cmi.core.score.max",
    "cmi.core.session_time",
    "cmi.core.total_time",
    "cmi.completion_status",
    "cmi.success_status",
    "cmi.score.raw",
    "cmi.score.min",
    "cmi.score.max",
    "cmi.score.scaled",
    "cmi.location",
    "cmi.session_time",
    "cmi.total_time",
    "cmi.suspend_data"
  ];

  var READ_ONLY = [
    "cmi.core.student_id",
    "cmi.core.student_name",
    "cmi.core.credit",
    "cmi.core.entry",
    "cmi.core.lesson_mode",
    "cmi.core.total_time",
    "cmi.learner_id",
    "cmi.learner_name",
    "cmi.credit",
    "cmi.entry",
    "cmi.mode",
    "cmi.total_time",
    "cmi.launch_data",
    "cmi.comments_from_lms",
    "cmi.max_time_allowed",
    "cmi.completion_threshold",
    "cmi.student_data.mastery_score"
  ];

  var CHILDREN = {
    "cmi.core._children":
      "student_id,student_name,lesson_location,credit,lesson_status,entry,score,total_time,lesson_mode,exit,session_time",
    "cmi.core.score._children": "raw,min,max",
    "cmi.score._children": "raw,min,max,scaled",
    "cmi.objectives._children": "id,score,status",
    "cmi.interactions._children":
      "id,objectives,time,type,correct_responses,weighting,student_response,result,latency",
    "cmi.student_data._children": "mastery_score,max_time_allowed,time_limit_action"
  };

  function has(list, value) {
    for (var i = 0; i < list.length; i++) {
      if (list[i] === value) return true;
    }
    return false;
  }

  /* hundredths -> the duration format the declared version uses. A package that
   * never sets session_time still gets one, which is what an LMS is expected to
   * record; the server validates whatever arrives either way. */
  function duration(ms, is2004) {
    var total = Math.max(0, Math.floor(ms / 10)); // hundredths
    var hundredths = total % 100;
    var seconds = Math.floor(total / 100) % 60;
    var minutes = Math.floor(total / 6000) % 60;
    var hours = Math.floor(total / 360000);
    function pad(n, width) {
      var s = String(n);
      while (s.length < width) s = "0" + s;
      return s;
    }
    if (is2004) {
      return (
        "PT" + hours + "H" + minutes + "M" + seconds + "." + pad(hundredths, 2) + "S"
      );
    }
    return (
      pad(hours, 4) + ":" + pad(minutes, 2) + ":" + pad(seconds, 2) + "." + pad(hundredths, 2)
    );
  }

  /** @param config {version, sco, appOrigin, cmi}  @param transport {send, now} */
  function createRuntime(config, transport) {
    var is2004 = String(config.version) === "2004";
    var cmi = config.cmi || {};
    var model = {};
    var dirty = {};
    var state = "not-initialized";
    var lastError = NO_ERROR;
    var startedAt = null;
    var flushTimer = null;

    function seed(key, value) {
      if (value === undefined || value === null) return;
      model[key] = String(value);
    }

    // The launch payload speaks the internal shape; both versions read it.
    seed(is2004 ? "cmi.learner_id" : "cmi.core.student_id", cmi.learner_id);
    seed(is2004 ? "cmi.learner_name" : "cmi.core.student_name", cmi.learner_name);
    seed(is2004 ? "cmi.mode" : "cmi.core.lesson_mode", cmi.mode || "normal");
    seed(is2004 ? "cmi.credit" : "cmi.core.credit", cmi.credit || "credit");
    seed(is2004 ? "cmi.entry" : "cmi.core.entry", cmi.entry || "ab-initio");
    seed(is2004 ? "cmi.location" : "cmi.core.lesson_location", cmi.location);
    seed(is2004 ? "cmi.total_time" : "cmi.core.total_time", cmi.total_time || (is2004 ? "PT0H0M0S" : "0000:00:00.00"));
    seed("cmi.suspend_data", cmi.suspend_data);

    if (is2004) {
      seed("cmi.completion_status", cmi.completion_status || "unknown");
      seed("cmi.success_status", cmi.success_status || "unknown");
      seed("cmi.score.raw", cmi.score_raw);
      seed("cmi.score.min", cmi.score_min);
      seed("cmi.score.max", cmi.score_max);
      seed("cmi.score.scaled", cmi.score_scaled);
    } else {
      // 1.2 folds completion and success into one vocabulary.
      var status = "not attempted";
      if (cmi.success_status === "passed") status = "passed";
      else if (cmi.success_status === "failed") status = "failed";
      else if (cmi.completion_status === "completed") status = "completed";
      else if (cmi.completion_status === "incomplete") status = "incomplete";
      seed("cmi.core.lesson_status", status);
      seed("cmi.core.score.raw", cmi.score_raw);
      seed("cmi.core.score.min", cmi.score_min);
      seed("cmi.core.score.max", cmi.score_max);
    }

    function fail(code) {
      lastError = code;
      return "false";
    }

    function ok() {
      lastError = NO_ERROR;
      return "true";
    }

    function collect() {
      var payload = {};
      var any = false;
      for (var key in dirty) {
        if (Object.prototype.hasOwnProperty.call(dirty, key)) {
          payload[key] = model[key];
          any = true;
        }
      }
      return any ? payload : null;
    }

    function flush(reason) {
      if (flushTimer) {
        transport.clearTimeout(flushTimer);
        flushTimer = null;
      }
      var payload = collect();
      if (!payload) return false;
      dirty = {};
      transport.send({
        type: "scorm:commit",
        sco: config.sco,
        reason: reason || "commit",
        data: payload
      });
      return true;
    }

    function scheduleFlush() {
      if (flushTimer) return;
      flushTimer = transport.setTimeout(function () {
        flushTimer = null;
        flush("auto");
      }, transport.flushDelay || 3000);
    }

    function initialize() {
      if (state === "running") {
        return fail(is2004 ? ERR_2004.alreadyInitialized : ERR_GENERAL);
      }
      if (state === "terminated") {
        return fail(is2004 ? ERR_2004.alreadyInitialized : ERR_GENERAL);
      }
      state = "running";
      startedAt = transport.now();
      transport.send({ type: "scorm:ready", sco: config.sco });
      return ok();
    }

    function terminate() {
      if (state === "not-initialized") {
        return fail(is2004 ? ERR_2004.terminatedBefore : ERR_NOT_INITIALIZED);
      }
      if (state === "terminated") {
        return fail(is2004 ? ERR_2004.terminatedAfter : ERR_NOT_INITIALIZED);
      }
      // A package that never reported its session time still gets one.
      var timeKey = is2004 ? "cmi.session_time" : "cmi.core.session_time";
      if (!model[timeKey] && startedAt !== null) {
        model[timeKey] = duration(transport.now() - startedAt, is2004);
        dirty[timeKey] = true;
      }
      state = "terminated";
      flush("terminate");
      transport.send({ type: "scorm:terminate", sco: config.sco });
      return ok();
    }

    function getValue(element) {
      if (state !== "running") {
        return (
          fail(is2004 ? (state === "terminated" ? ERR_2004.getAfterTerm : ERR_2004.getBeforeInit) : ERR_NOT_INITIALIZED),
          ""
        );
      }
      if (!element) {
        return (fail(ERR_ARGUMENT), "");
      }
      if (CHILDREN[element] !== undefined) {
        lastError = NO_ERROR;
        return CHILDREN[element];
      }
      if (/\._count$/.test(element)) {
        lastError = NO_ERROR;
        return "0";
      }
      if (Object.prototype.hasOwnProperty.call(model, element)) {
        lastError = NO_ERROR;
        return model[element];
      }
      // Unknown but well-formed: answer empty rather than error. A package
      // probing an element we do not track should keep working.
      if (/^cmi\./.test(element)) {
        lastError = NO_ERROR;
        return "";
      }
      lastError = is2004 ? ERR_2004.undefinedElement : ERR_UNDEFINED_ELEMENT;
      return "";
    }

    function setValue(element, value) {
      if (state !== "running") {
        return fail(
          is2004
            ? state === "terminated"
              ? ERR_2004.setAfterTerm
              : ERR_2004.setBeforeInit
            : ERR_NOT_INITIALIZED
        );
      }
      if (!element || !/^cmi\./.test(element)) {
        return fail(ERR_ARGUMENT);
      }
      if (has(READ_ONLY, element) || CHILDREN[element] !== undefined) {
        return fail(is2004 ? ERR_2004.readOnly : ERR_READ_ONLY);
      }

      model[element] = value === undefined || value === null ? "" : String(value);

      // Only the persisted set crosses the origin. Everything else is answered
      // locally and goes no further -- interactions and objectives included.
      if (has(PERSISTED, element)) {
        dirty[element] = true;
        scheduleFlush();
      }
      return ok();
    }

    function commit() {
      if (state !== "running") {
        return fail(
          is2004
            ? state === "terminated"
              ? ERR_2004.commitAfterTerm
              : ERR_2004.commitBeforeInit
            : ERR_NOT_INITIALIZED
        );
      }
      flush("commit");
      return ok();
    }

    function getLastError() {
      return lastError;
    }

    function getErrorString(code) {
      var strings = {
        "0": "No error",
        "101": "General exception",
        "103": "Already initialized",
        "112": "Termination before initialization",
        "113": "Termination after termination",
        "122": "Retrieve data before initialization",
        "123": "Retrieve data after termination",
        "132": "Store data before initialization",
        "133": "Store data after termination",
        "142": "Commit before initialization",
        "143": "Commit after termination",
        "201": "Invalid argument error",
        "301": "Not initialized",
        "401": "Undefined data model element",
        "403": "Element is read only",
        "404": "Data model element is read only",
        "406": "Data model element type mismatch",
        "407": "Data model element value out of range"
      };
      return strings[String(code)] || "";
    }

    var api12 = {
      LMSInitialize: initialize,
      LMSFinish: terminate,
      LMSGetValue: getValue,
      LMSSetValue: setValue,
      LMSCommit: commit,
      LMSGetLastError: getLastError,
      LMSGetErrorString: getErrorString,
      LMSGetDiagnostic: getErrorString
    };

    var api2004 = {
      Initialize: initialize,
      Terminate: terminate,
      GetValue: getValue,
      SetValue: setValue,
      Commit: commit,
      GetLastError: getLastError,
      GetErrorString: getErrorString,
      GetDiagnostic: getErrorString
    };

    return {
      api12: api12,
      api2004: api2004,
      is2004: is2004,
      flush: flush,
      /* For the page: what to hang on `window`. Advertising both would confuse
       * a package that probes for one and finds the other (p009 §2.8). */
      install: function (win) {
        if (is2004) win.API_1484_11 = api2004;
        else win.API = api12;
      },
      _model: model
    };
  }

  global.SeminaryScormRuntime = { createRuntime: createRuntime, duration: duration };
})(typeof globalThis !== "undefined" ? globalThis : this);
