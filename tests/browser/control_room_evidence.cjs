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
    // Clarity fixtures are isolated replay only: never create real workers or gates.
    s.system_health = [
      {name: "GitHub", health: "HEALTHY", display_status: "AKTUELL", display_tone: "green", last_success_at: s.generated_at, evidence_note: "Kein Ausfall bestätigt."},
      {name: "Production Smoke", health: "STALE", display_status: "NACHWEIS ÄLTER", display_tone: "amber", test_passed: true, passed: 18, total: 18,
        last_success_at: new Date(Date.parse(s.generated_at) - 12 * 3600000).toISOString(), evidence_note: "Letzter Test bestanden; kein Ausfall bestätigt."},
    ];
    s.worker_deck[0].display_name = "Zoro";
    s.worker_deck[0].role = "Tech Worker";
    s.worker_deck[0].identity_tag = "ABC123";
    s.worker_deck.push({...s.worker_deck[0], execution_id: "qa-second", worker_id: "qa-revenue", display_name: "Nami", role: "Revenue / Analytics Worker", identity_tag: "DEF456"});
    s.command_center.active_workers = 2;
    const task = {task_id: "qa-dior", title: "Dior Bildrechte", status: "waiting_external", updated_at: s.generated_at,
      explanation: {reason: "Wartet auf Antwort von Dior. Anfrage bereits versendet; nicht erneut senden.", since: s.generated_at,
        since_basis: "Letzte Aufgabenaktualisierung", next_step: "Nach Antwort: Rechte prüfen.", resolver: "Extern, danach Jarvis", owner_action: "Keine Aktion von dir erforderlich."}};
    const blocker = {task_id: "qa-coverage", title: "Automatischer Händler-Freshness-Check", status: "blocked", blocker: "deterministic_merchant_coverage_required",
      explanation: {reason: "Automatischer Händler-Check kann noch nicht vollständig laufen.", next_step: "Read-only Händlerabdeckung vervollständigen.", resolver: "TECH / Jarvis-Prüfung", owner_action: "Keine Aktion von dir erforderlich."}};
    s.workstreams = [{name: "Content", status: "WAITING EXTERNAL", tasks: 1, focus_task: task, tasks_preview: [task]},
      {name: "Affiliate", status: "BLOCKED", tasks: 1, focus_task: blocker, tasks_preview: [blocker]}];
    s.waiting = {owner: 0, external: 1, technical: 1, budget: 0, rows: [task, blocker]};
    await refresh();
    const healthText = await p.locator("#overview-system-health").innerText();
    assert.ok(healthText.includes("AKTUELL") && healthText.includes("LETZTER TEST BESTANDEN") && healthText.includes("18 / 18") && healthText.includes("NACHWEIS ÄLTER"));
    assert.equal(await p.locator("#overview-system-health .health-red").count(), 0);
    const help = p.locator("#overview-system-health .status-help summary[aria-label=\"Erklärung: NACHWEIS ÄLTER\"]");
    await help.click();
    assert.ok((await p.locator("#overview-system-health").innerText()).includes("nicht automatisch einen Ausfall"));
    const aliases = await p.locator("#worker-deck .worker-card h3").allTextContents();
    assert.ok(aliases.includes("ZORO · ABC123") && aliases.includes("NAMI · DEF456"));
    await refresh();
    assert.deepEqual(await p.locator("#worker-deck .worker-card h3").allTextContents(), aliases);
    const streamText = await p.locator("#workstream-list").innerText();
    for (const text of ["Dior", "Read-only Händlerabdeckung", "Keine Aktion von dir erforderlich."]) assert.ok(streamText.includes(text));
    assert.equal(await p.locator("#pulse-action.state-red").count(), 0);
    assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    s.system_health[0] = {...s.system_health[0], health: "BLOCKED", display_status: "VERBINDUNG / SYSTEM PRÜFEN", display_tone: "red", evidence_note: "Bestätigten Verbindungsfehler prüfen."};
    await refresh();
    assert.equal(await p.locator("#overview-system-health .health-red").count(), 1);
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
    assert.equal(await p.locator("#pulse-action.state-amber").count(), 1);
    assert.match(await p.locator("#pulse-action").innerText(), /Aktion nötig/);
    assert.equal(await p.locator("#pulse-action.state-red").count(), 0);
    const decisionText = await p.locator("#decision-list").innerText();
    for (const text of ["Delina EDP 75 ml", "qa_delina_asset", "A complete safe caption", "qa_delina_fixture", "qa_gate", "9.6", "Review-Gate erkannt. Keine automatische Aktion ohne explizit freigegebenen Handler."])
      assert.ok(decisionText.includes(text), text);
    assert.equal(await p.locator("#decision-list button").count(), 0);
    s.decision_center = [];
    s.command_center.human_approval_count = 0;
    await refresh();
    assert.equal(await p.locator("#approval-alert").isVisible(), false);
    assert.equal(await p.locator("#decisions").isVisible(), false);
    assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    // Server-built Crew/Risk scenarios. Fixed roles never manufacture executions.
    const applyScenario = async (name) => { Object.assign(s, structuredClone(base._qa_scenarios[name])); await refresh(); };
    await applyScenario("healthy");
    assert.equal(await p.locator("#global-risk.state-green").count(), 1);
    assert.equal(await p.locator(".crew-node").count(), 10);
    assert.equal(await p.locator(".crew-cluster").count(), 4);
    assert.equal(await p.locator('.crew-node[data-active="true"]').count(), 0);
    assert.equal(await p.locator("#crew").isVisible(), true);
    assert.match(await p.locator("#crew-live-now").innerText(), /keine Worker-Ausführung/i);
    const rosterBefore = await p.locator(".crew-node h4").allTextContents();
    assert.equal(new Set(rosterBefore).size, 10);
    await applyScenario("warning");
    assert.equal(await p.locator("#global-risk.state-amber").count(), 1);
    assert.match(await p.locator("#risk-summary").innerText(), /2 Punkte/);
    assert.equal(await p.locator("#risk-panel .state-red").count(), 0);
    assert.match(await p.locator("#source-summary").innerText(), /Quellenhinweise/);
    assert.ok((await p.locator("#crew-summary-research").boundingBox()).height >= 32);
    assert.equal(await p.locator("#pulse-action.state-red").count(), 0);
    assert.match(await p.locator('[data-role="research"]').innerText(), /Dior/);
    assert.match(await p.locator('[data-role="affiliate"]').innerText(), /Read-only/);
    await p.locator("#risk-summary-sources").click();
    assert.match(await p.locator("#risk-detail-sources").innerText(), /Gmail-Zugang abgelaufen/);
    await p.locator("#crew-summary-research").click();
    await p.locator("#crew-summary-research").focus();
    const crewAutomatic = p.waitForResponse(r => r.url().endsWith("/snapshot"));
    await p.evaluate(() => document.querySelector("#refresh").click());
    await crewAutomatic;
    await p.evaluate(() => new Promise(requestAnimationFrame));
    assert.equal(await p.locator("#crew-details-research").getAttribute("open"), "");
    assert.equal(await p.locator("#crew-summary-research").evaluate(el => el === document.activeElement), true);
    assert.deepEqual(await p.locator(".crew-node h4").allTextContents(), rosterBefore);
    await applyScenario("active");
    assert.equal(await p.locator('.crew-node[data-active="true"]').count(), 2);
    assert.equal(await p.locator("#crew-live-now .crew-live-card").count(), 2);
    assert.match(await p.locator("#crew-live-now").innerText(), /ZORO|NAMI/);
    assert.equal(await p.locator('[data-role="tech"]').getAttribute("data-state"), "AKTIV");
    assert.equal(await p.locator('[data-role="revenue"]').getAttribute("data-state"), "AKTIV");
    assert.match(await p.locator('[data-role="revenue"]').innerText(), /Launch-Funnel/);
    if (width < 701) {
      const activeNode = await p.locator('[data-role="tech"]').boundingBox();
      const readyNode = await p.locator('[data-role="outreach"]').boundingBox();
      assert.ok(activeNode.y < readyNode.y);
    }
    await p.emulateMedia({reducedMotion:"reduce"});
    assert.equal(await p.locator('[data-role="tech"]').evaluate(el => getComputedStyle(el, "::before").animationName), "none");
    await p.emulateMedia({reducedMotion:"no-preference"});
    assert.equal(await p.locator('[data-role="tech"]').evaluate(el => getComputedStyle(el, "::before").animationName), "crew-handoff");
    fail = true;
    await refresh();
    assert.match(await p.locator("#risk-title").innerText(), /NICHT BESTÄTIGT/);
    assert.equal(await p.locator('.crew-node[data-active="true"]').count(), 0);
    fail = false;
    await applyScenario("critical");
    assert.equal(await p.locator("#global-risk.state-red").count(), 1);
    assert.equal(await p.locator("#risk-detail-production.state-red").count(), 1);
    await applyScenario("old");
    assert.equal(await p.locator("#global-risk.state-amber").count(), 1);
    assert.match(await p.locator("#risk-detail-production").innerText(), /Letzter Test bestanden/);
    await applyScenario("gate");
    assert.equal(await p.locator("#global-risk.state-red").count(), 1);
    assert.equal(await p.locator('[data-role="content"]').getAttribute("data-state"), "OWNER GATE");
    assert.equal(await p.locator("#crew-owner-link").isVisible(), true);
    await applyScenario("warning");
    assert.equal(await p.locator("#crew-owner-link").isVisible(), false);
    assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const riskBox = await p.locator("#global-risk").boundingBox();
    const commandBox = await p.locator("#command").boundingBox();
    assert.ok(riskBox.y < commandBox.y);
    const out = path.resolve(__dirname, "../../examples/retail/storefront-web/.visual-qa");
    fs.mkdirSync(out, {recursive: true});
    await p.screenshot({path: path.join(out, "control-room-crew-risk-" + width + ".png"), fullPage: true});
    await p.close();
    console.log(
      width +
        "px hierarchy, truthful motion, failure/recovery and evidence-state PASS",
    );
  }
  assert.deepEqual(errors, []);
  await b.close();
})();
