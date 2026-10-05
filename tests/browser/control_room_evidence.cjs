/* Isolated replay only. Usage: node tests/browser/control_room_evidence.cjs <allowlisted-snapshot.json>
 * Requires Playwright and Chromium; set CONTROL_ROOM_QA_CHROMIUM for a custom executable.
 * Every request is fulfilled locally. No credentials or live service calls are made. */
const fs = require("fs");
const path = require("path");
const assert = require("assert/strict");
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch({
    headless: true,
    ...(process.env.CONTROL_ROOM_QA_CHROMIUM
      ? { executablePath: process.env.CONTROL_ROOM_QA_CHROMIUM }
      : {}),
    args: [
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--disable-software-rasterizer",
    ],
  });
  const base = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const dir =
    path.resolve(__dirname, "../../examples/retail/api/control_room") + "/";
  const errors = [];
  for (const width of [390, 430, 768, 1440]) {
    const s = structuredClone(base);
    s.worker_deck = [
      {
        execution_id: "local-regression",
        task_id: "local-regression",
        task_title: "QA: Händlerabdeckung und Kaufziele prüfen",
        worker_id: "qa-worker",
        status: "ACTIVE",
        execution_status: "working",
        started_at: s.generated_at,
        last_progress_at: s.generated_at,
        heartbeat_at: s.generated_at,
        lease_expires_at: s.generated_at,
        next_checkpoint: "deterministic_verification",
        checkpoint: {
          verified: true,
          step: "coverage_verified",
          verified_at: s.generated_at,
        },
      },
    ];
    s.command_center.status = "WORKING";
    s.command_center.ceo_status = "JARVIS AKTIV";
    s.command_center.current_task = s.worker_deck[0].task_title;
    let fail = false;
    const p = await b.newPage({ viewport: { width, height: 1000 } });
    p.on("pageerror", (e) => errors.push(e.message));
    await p.route("**/*", (r) => {
      const path = new URL(r.request().url()).pathname;
      if (path.endsWith("/snapshot"))
        return fail
          ? r.fulfill({ status: 503, body: "Unavailable" })
          : r.fulfill({
              contentType: "application/json",
              body: JSON.stringify(s),
            });
      const file =
        path === "/internal/jarvis" ? "index.html" : path.split("/").pop();
      return r.fulfill({
        contentType: file.endsWith(".css")
          ? "text/css"
          : file.endsWith(".js")
            ? "application/javascript"
            : "text/html",
        body: fs.readFileSync(dir + file),
      });
    });
    await p.goto("https://dufynd-qa.local/internal/jarvis");
    await p.waitForFunction(
      () => document.body.dataset.executionMode === "working",
    );
    assert.equal(await p.locator("#work .work-flow").isVisible(), false);
    assert.equal(await p.locator(".evidence-changed").count(), 0);
    if (width === 1440) {
      const a = await p.locator("#work").boundingBox();
      const n = await p.locator(".next-panel").boundingBox();
      assert.ok(a.width > n.width * 1.7);
    }

    const summary = p.locator(".execution-metadata > summary");
    await summary.click();
    const refresh = async () => {
      const response = p.waitForResponse((r) => r.url().endsWith("/snapshot"));
      await p.locator("#refresh").click();
      await response;
      await p.evaluate(() => new Promise(requestAnimationFrame));
    };
    s.worker_deck[0].heartbeat_at = new Date(
      Date.parse(s.generated_at) + 1000,
    ).toISOString();
    await refresh();
    assert.equal(await p.locator(".evidence-changed").count(), 0);
    assert.equal(
      await p.locator(".execution-metadata").getAttribute("open"),
      "",
    );
    s.worker_deck[0].checkpoint.step = "purchase_verified";
    s.worker_deck[0].checkpoint.verified_at = new Date(
      Date.parse(s.generated_at) + 2000,
    ).toISOString();
    await refresh();
    assert.equal(await p.locator(".evidence-changed").count(), 1);
    await refresh();
    assert.equal(await p.locator(".evidence-changed").count(), 0);
    fail = true;
    await refresh();
    assert.equal(
      await p.locator("body").getAttribute("data-execution-mode"),
      "unknown",
    );
    assert.equal(await p.locator("#execution-source-status").isVisible(), true);
    assert.match(
      await p.locator("#execution-detail-list .execution-state").innerText(),
      /Zuletzt/,
    );
    fail = false;
    await refresh();
    assert.equal(
      await p.locator("#execution-source-status").isVisible(),
      false,
    );
    assert.equal(
      await p.locator("#execution-detail-list .execution-state").innerText(),
      "Arbeitet",
    );
    await summary.focus();
    const automatic = p.waitForResponse((r) => r.url().endsWith("/snapshot"));
    await p.evaluate(() => document.querySelector("#refresh").click());
    await automatic;
    await p.evaluate(() => new Promise(requestAnimationFrame));
    assert.equal(
      await summary.evaluate((el) => el === document.activeElement),
      true,
    );
    s.system_health = [];
    s.freshness.operational_complete = false;
    await refresh();
    assert.match(
      await p.locator("#source-summary").innerText(),
      /nicht vollständig bestätigt/,
    );
    assert.equal(await p.locator("#execution-source-status").isVisible(), true);
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    // A complete candidate is visible only as a pending Owner review; there is no write control.
    s.freshness.operational_complete = true;
    s.command_center.gates_complete = true;
    s.command_center.human_approval_count = 1;
    s.decision_center = [{title: "Delina · isolated review fixture", type: "content_candidate_review",
      reason: "Complete candidate", go_token: "GO-CONTENT-REVIEW-FIXTURE",
      content_candidate: {product: "Delina EDP 75 ml", asset_reference: "qa_delina_asset",
        revision_fingerprint: "a".repeat(64), hook: "Delina: passt sie zu dir?",
        caption: "A complete safe caption for Owner review.", platform: "instagram",
        requested_at: s.generated_at, content_id: "qa_delina_fixture", experiment_id: "qa_gate",
        internal_rating: "9.6", recommendation_reason: "Internally ready fixture"}}];
    await refresh();
    assert.equal(await p.locator("#approval-alert").isVisible(), true);
    const decisionText = await p.locator("#decision-list").innerText();
    for (const text of ["Delina EDP 75 ml", "qa_delina_asset", "A complete safe caption", "qa_delina_fixture", "qa_gate", "9.6", "Scheduling und Publishing nicht freigegeben"])
      assert.ok(decisionText.includes(text), text);
    assert.equal(await p.locator("#decision-list button").count(), 0);
    s.decision_center = [];
    s.command_center.human_approval_count = 0;
    await refresh();
    assert.equal(await p.locator("#approval-alert").isVisible(), false);
    assert.equal(await p.locator("#decisions").isVisible(), false);
    assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await p.close();
    console.log(
      width +
        "px hierarchy, truthful motion, failure/recovery and evidence-state PASS",
    );
  }
  assert.deepEqual(errors, []);
  await b.close();
})();
