"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const value = (v) =>
    v === null || v === undefined || v === "" ? "Unknown" : String(v);
  const stamp = (v) =>
    v && Number.isFinite(Date.parse(v))
      ? new Date(v).toLocaleString("de-DE", { timeZone: "Europe/Berlin" })
      : "Unknown";
  const shortTime = (v) =>
    v && Number.isFinite(Date.parse(v))
      ? new Date(v).toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit",
          timeZone: "Europe/Berlin",
        })
      : "—";
  const numeric = (v) => {
    if (v === null || v === undefined || v === "" || typeof v === "boolean")
      return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const put = (id, v) => {
    const el = $(id);
    if (el && el.textContent !== value(v)) {
      el.textContent = value(v);
      if (
        el.animate &&
        !matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        el.animate(
          [
            { opacity: 0.65, transform: "translateY(2px)" },
            { opacity: 1, transform: "translateY(0)" },
          ],
          { duration: 240, easing: "ease-out" },
        );
      }
    }
  };
  const node = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = value(text);
    if (cls) n.className = cls;
    return n;
  };
  const line = (parent, label, text) => {
    const p = node("p");
    p.append(node("small", label + " · "), node("span", text));
    parent.append(p);
  };
  const badge = (status) => {
    const tone =
      {
        WORKING: "info",
        MONITORING: "info",
        "JARVIS ÜBERWACHT": "info",
        "JARVIS AKTIV": "info",
        "WARTET AUF DEINE FREIGABE": "action",
        PRÜFEN: "warn",
        BLOCKIERT: "warn",
        "WAITING EXTERNAL": "warn",
        ACTIVE: "info",
        HEALTHY: "good",
        READY: "good",
        SUCCESS: "good",
        LIVE: "good",
        "OWNER GATE": "action",
        "WAITING HUMAN": "action",
        WAITING: "warn",
        ERROR: "warn",
        BLOCKED: "warn",
        FAILED: "warn",
        DEGRADED: "warn",
        STALE: "warn",
        INITIALIZING: "warn",
        OFF: "neutral",
      }[String(status || "").toUpperCase()] || "neutral";
    const labels = {
      MONITORING: "Überwacht",
      "WAITING EXTERNAL": "Wartet extern",
      BLOCKED: "Blockiert",
      "NO DATA": "Keine Quelle",
      SCHEDULED: "Geplant",
      STALE: "Veraltet",
      UNKNOWN: "Unbekannt",
      WAITING: "Wartet",
      WORKING: "Arbeitet",
      READY: "Bereit",
    };
    return node("span", labels[status] || status, "pill " + tone);
  };
  const setTone = (id, tone) => {
    const el = $(id);
    if (!el) return;
    el.classList.remove(
      "state-green",
      "state-blue",
      "state-amber",
      "state-red",
      "state-neutral",
    );
    el.classList.add("state-" + tone);
  };
  const setPulse = (id, tone, main, detail) => {
    setTone(id, tone);
    put(id + "-value", main);
    put(id + "-detail", detail);
  };
  const friendlyProductState = (state) =>
    ({
      live_first_money_test_scheduled: "First-Money-Test geplant",
      live_visual_final_content_test_preparation:
        "Content-Test in Vorbereitung",
      next_after_delina_evidence: "Als Nächstes nach Delina-Daten",
      later: "Später priorisiert",
    })[state] || value(state).replaceAll("_", " ");

  let snapshot = null;
  let busy = false;
  let timer = null;

  function missions() {
    if (!snapshot) return;
    const board = $("mission-board");
    if (!board) return;
    board.replaceChildren();
    const domain = $("domain-filter")?.value || "";
    const showDone = $("show-done")?.checked === true;
    const lanes = snapshot.mission_board || {};

    for (const [lane, rowsRaw] of Object.entries(lanes)) {
      if (lane === "DONE" && !showDone) continue;
      const rows = Array.isArray(rowsRaw) ? rowsRaw : [];
      const filtered = rows.filter((r) => !domain || r.domain === domain);
      const column = node("div", undefined, "mission-lane");
      column.tabIndex = 0;
      column.setAttribute("aria-label", lane + " Missions");
      column.append(node("h3", lane + " · " + filtered.length));

      for (const m of lane === "DONE" ? filtered.slice(0, 12) : filtered) {
        const card = node("article", undefined, "mission-card");
        card.append(
          node("small", value(m.domain) + " · P" + value(m.priority)),
          node("h4", m.title),
        );
        line(card, "Owner", m.owner);
        if (m.blocker) line(card, "Blocker", m.blocker);
        if (m.next_checkpoint) line(card, "Next checkpoint", m.next_checkpoint);
        if (m.human_gate) card.append(badge("WAITING HUMAN"));
        column.append(card);
      }
      if (!filtered.length)
        column.append(node("p", "Keine beobachteten Tasks", "muted"));
      board.append(column);
    }
  }

  const detailLabels = {
    lease_missing: "Keine gültige Lease dokumentiert",
    lease_expired:
      "Lease ist abgelaufen; Ausführung nicht mehr als aktiv bestätigt",
    heartbeat_missing: "Lebenszeichen fehlt",
    heartbeat_not_current: "Lebenszeichen ist nicht aktuell",
    execution_marked_stale:
      "Ausführung ist in der Quelle als veraltet markiert",
    waiting_external: "Wartet auf externen Nachweis",
    waiting_human_input: "Wartet auf Owner-Entscheidung",
    ready: "Bereit zur Auswahl",
    queued: "Wartet auf Auswahl",
    blocked: "Blockiert",
    done: "Erledigt",
    cancelled: "Abgebrochen",
    vivnetworks_notino_image_rights_reply:
      "Bildrechte-Antwort von VIVnetworks / Notino",
    brand_or_rightsholder_reply: "Antwort von Marke oder Rechteinhaber",
    approved_product_images: "Freigegebene Produktbilder",
    current_purchase_destinations: "Aktuell geprüfte Kaufziele",
    exact_variant_identity: "Eindeutig belegte Produktvariante",
    human_fidelity_where_applicable:
      "Visuelle Produktfreigabe, soweit erforderlich",
    release_approved_images_incomplete:
      "Noch fehlende Bildfreigaben für den Release",
    release_promotion_gates_incomplete: "Noch fehlende Release-Nachweise",
    deterministic_merchant_coverage_required: "Geprüfte Händlerabdeckung fehlt",
    finish_read_only_purchase_freshness_crosscheck:
      "Kaufziele und Händlerabdeckung prüfen",
    external_dependency_resolution: "Externe Abhängigkeit auflösen",
    deterministic_verification: "Ergebnis anhand fester Kriterien prüfen",
    worker_result_or_deterministic_verification:
      "Worker-Ergebnis oder Prüfnachweis",
    typed_owner_decision: "Dokumentierte Owner-Entscheidung",
    next_safe_worker_or_budget_reopen:
      "Zulässiger Worker oder neues freigegebenes Budget",
    unknown_provider_cost: "Ungeklärte Provider-Kosten",
    budget_exhausted: "Freigegebenes Budget ausgeschöpft",
    lease_or_heartbeat_stale: "Lease oder Lebenszeichen ist veraltet",
    execution_failed: "Ausführung fehlgeschlagen; Ergebnis prüfen",
    no_recent_progress:
      "Seit mindestens zehn Minuten kein neuer Fortschrittsnachweis",
    dispatch_pending: "Ausführung noch nicht gestartet",
    retry_pending: "Ein erneuter Versuch ist noch nicht gestartet",
    owner_decision: "Ausführung wartet laut Quelle auf eine Owner-Entscheidung",
    external_dependency:
      "Externe Abhängigkeit; genauer Auslöser nicht dokumentiert",
    verifying: "Ergebnis wird geprüft",
    working: "Aufgabe wird bearbeitet",
    claimed: "Aufgabe übernommen",
    running: "Ausführung läuft",
    in_progress: "Ausführung läuft",
    dispatched: "Auftrag gestartet",
    completed: "Ausführung beendet",
    failed_terminal: "Ausführung beendet · fehlgeschlagen",
  };
  const detailText = (code) =>
    detailLabels[code] ||
    (code ? String(code).replaceAll("_", " ") : "Nicht dokumentiert");
  const taskWait = (task) => {
    if (!task) return "Keine konkrete Aufgabe zugeordnet";
    if (task.blocker) return detailText(task.blocker);
    if (task.human_gate) return "Eine echte Owner-Entscheidung ist offen";
    if (task.dependencies?.length)
      return task.dependencies.map(detailText).join(" · ");
    if (task.status === "waiting_external")
      return "Externe Abhängigkeit; genauer Auslöser nicht dokumentiert";
    if (["ready", "queued"].includes(task.status))
      return "Wartet auf Handler-Auswahl im nächsten Loop";
    return "Kein konkreter Wartegrund gespeichert";
  };
  // Presentation labels only: original titles and identifiers remain inspectable.
  const taskLabels = {
    tech_model3d_outreach_20260929:
      "Markenantworten zu fünf 3D-Modellen prüfen",
    tech_widian_3d_contact_form_20260930:
      "Widian-Anfrage für ein 3D-Modell vorbereiten",
    catalog_release_01_readiness: "Produktfreigabe für Release 01 vorbereiten",
    jarvis_dior_hypnotic_image_rights_outreach_20261001:
      "Bildrechte für Dior Hypnotic Poison 100 ml klären",
    notino_original_asset_rights_path_20261001:
      "Nutzungsrechte für Notino-Originalbilder klären",
    notino_original_asset_visual_review_queue_20261001:
      "Priorisierte Notino-Produktbilder prüfen",
    perfumetrader_product_coverage: "Perfumetrader-Händlerabdeckung erweitern",
    perfumetrader_feed_response: "Perfumetrader-Produktdatenantwort auswerten",
    jarvis_purchase_freshness_watchlist_20261001:
      "Aktualität der Kaufziele und Händlerabdeckung prüfen",
    repo_current_commerce:
      "Lizenzierte Bilder und visuelle Freigabe vorbereiten",
    release02_brand_image_rights_outreach_20261001:
      "Bildrechte für Release 02 klären",
    release03_brand_image_rights_outreach_20261001:
      "Bildrechte für Release 03 klären",
    release04_brand_image_rights_outreach_20261001:
      "Bildrechte für Release 04 klären",
    release05_brand_image_rights_outreach_20261001:
      "Bildrechte für Release 05 klären",
    release06_armani_si_image_rights_outreach_20261001:
      "Bildrechte für Armani Sì 100 ml klären",
  };
  const taskTitle = (task) =>
    taskLabels[task?.task_id] ||
    task?.title ||
    task?.task_title ||
    task?.task_id ||
    "Aufgabe nicht zugeordnet";
  const executionSignals = new Map();
  let executionObserved = false;
  const sourceHealthLabel = (health) =>
    ({
      HEALTHY: "Aktuell",
      STALE: "Beobachtung veraltet",
      DEGRADED: "Quelle meldet Einschränkung",
      BLOCKED: "Blockiert",
      UNKNOWN: "Nicht bestätigt",
    })[health] ||
    health ||
    "Nicht bestätigt";
  function taskDetail(task) {
    const item = node("article", undefined, "dependency-task");
    item.dataset.taskId = task.task_id || "";
    item.append(node("strong", taskTitle(task)));
    line(item, "Status", detailText(task.status));
    line(item, "Grund / Voraussetzung", taskWait(task));
    line(item, "Nächster Prüfschritt", detailText(task.next_checkpoint));
    line(item, "Aktualisiert", stamp(task.updated_at));
    const source = node("details", undefined, "task-source");
    source.append(node("summary", "Original & Aufgabenkennung"));
    line(source, "Original", task.title || task.task_id);
    line(source, "Aufgabe", task.task_id);
    item.append(source);
    return item;
  }
  function workerEvidence(w, compact = false) {
    const item = node(
      "article",
      undefined,
      compact ? "execution-evidence" : "worker-evidence",
    );
    item.dataset.state = w.status || "UNKNOWN";
    const state =
      w.status === "ACTIVE"
        ? "Arbeitet"
        : w.status === "WAITING"
          ? "Wartet"
          : w.status === "STALE"
            ? "Nachweis veraltet"
            : w.status === "FAILED"
              ? "Fehlgeschlagen"
              : "Inaktiv";
    const heading = node("div", undefined, "execution-heading");
    heading.append(
      node("strong", taskTitle(w)),
      node("span", state, "execution-state"),
    );
    item.append(heading);
    if (compact) {
      const path = node("div", undefined, "execution-path");
      const phase = node("div", undefined, "execution-step");
      phase.append(
        node(
          "small",
          w.status === "ACTIVE" ? "01 · AKTUELLER SCHRITT" : "01 · WARTEGRUND",
        ),
        node(
          "strong",
          w.status === "ACTIVE"
            ? detailText(w.execution_status)
            : w.wait_reason === "external_dependency" &&
                w.task_context?.dependencies?.length
              ? taskWait(w.task_context)
              : detailText(w.wait_reason),
        ),
      );
      const next = node("div", undefined, "execution-step");
      next.append(
        node("small", "02 · NÄCHSTER DOKUMENTIERTER PRÜFSCHRITT"),
        node("strong", detailText(w.next_checkpoint)),
      );
      path.append(phase, next);
      item.append(path);
      const proof = node("div", undefined, "execution-proof");
      proof.append(
        node("small", "LETZTER BESTÄTIGTER SCHRITT"),
        node(
          "span",
          w.checkpoint?.verified === true
            ? detailText(w.checkpoint.step) +
                " · " +
                stamp(w.checkpoint.verified_at)
            : "Noch kein verifizierter Checkpoint vorhanden",
        ),
      );
      item.append(proof);
      line(item, "Letzter Fortschritt", stamp(w.last_progress_at));
      const metadata = node("details", undefined, "execution-metadata");
      metadata.append(
        node(
          "summary",
          "Nachweise · " + (w.worker_id || w.worker_type || "Worker unbekannt"),
        ),
      );
      line(metadata, "Aufgabe", w.task_id);
      line(metadata, "Original", w.task_title || w.task_id);
      line(metadata, "Gestartet", stamp(w.started_at));
      line(metadata, "Lebenszeichen", stamp(w.heartbeat_at));
      line(metadata, "Lease gültig bis", stamp(w.lease_expires_at));
      item.append(metadata);
      return item;
    }
    line(
      item,
      "Worker",
      w.worker_id || w.worker_type || "Identität nicht dokumentiert",
    );
    line(
      item,
      w.status === "ACTIVE" ? "Phase" : "Wartegrund",
      w.status === "ACTIVE"
        ? detailText(w.execution_status)
        : detailText(w.wait_reason),
    );
    line(item, "Nächster Prüfschritt", detailText(w.next_checkpoint));
    if (w.checkpoint?.verified === true)
      line(
        item,
        "Letzter bestätigter Schritt",
        detailText(w.checkpoint.step) + " · " + stamp(w.checkpoint.verified_at),
      );
    else
      line(
        item,
        "Letzter bestätigter Schritt",
        "Kein verifizierter Checkpoint vorhanden",
      );
    if (compact && w.status !== "ACTIVE")
      line(item, "Letzter Fortschritt", stamp(w.last_progress_at));
    if (!compact) {
      line(item, "Gestartet", stamp(w.started_at));
      line(item, "Lebenszeichen", stamp(w.heartbeat_at));
      line(item, "Letzter Fortschritt", stamp(w.last_progress_at));
    }
    return item;
  }

  function workerCard(w) {
    const active = w.status === "ACTIVE";
    const card = node(
      "article",
      undefined,
      "worker-card" + (active ? " active" : ""),
    );
    const top = node("div", undefined, "worker-top");
    top.append(
      node("span", "⌘", "station-icon"),
      badge(active ? "ACTIVE" : w.status || w.execution_status),
    );
    card.append(top);
    card.append(
      node("small", w.worker_type || "Worker"),
      node("h3", w.worker_id || w.execution_id || "Worker"),
      node("p", w.task_title || w.task_id || "Task"),
    );
    line(card, "Execution", w.execution_status);
    line(card, "Heartbeat", stamp(w.heartbeat_at));
    line(card, "Lease", stamp(w.lease_expires_at));
    line(card, "Handler", w.handler_id);
    card.append(workerEvidence(w));
    return card;
  }

  function healthTone(health) {
    const v = String(health || "").toUpperCase();
    if (["HEALTHY", "READY", "SUCCESS", "LIVE"].includes(v)) return "green";
    if (["ACTIVE", "WORKING"].includes(v)) return "blue";
    return "amber";
  }

  function renderDecisionIntelligence(revenue, publication) {
    const sessions = numeric(revenue.sessions);
    const productViews = numeric(revenue.product_views);
    const offerViews = numeric(revenue.offer_views);
    const clickouts = numeric(revenue.merchant_clickouts);
    const transactions = numeric(revenue.transactions);
    const commission = numeric(revenue.commission_eur);

    const launchEvidence = revenue.analytics_provenance === "launch_attributed_excludes_prelaunch" && revenue.analytics_complete === true;
    // Attributed launch events are signals; they do not prove organic reach or sales.
    const reached = [
      publication.live,
      launchEvidence && (sessions || 0) > 0,
      launchEvidence && (productViews || 0) > 0,
      launchEvidence && ((offerViews || 0) + (numeric(revenue.offer_opens) || 0)) > 0,
      launchEvidence && (clickouts || 0) > 0,
      (transactions || 0) > 0,
      (commission || 0) > 0,
    ];

    const nextLabels = [
      "Content erfolgreich live",
      "Erste attributierte Launch-Session",
      "Erster Product View",
      "Erster Blick auf Kaufoptionen",
      "Erster Merchant Clickout",
      "Erste Affiliate-Transaktion",
      "Erste bestätigte Provision",
    ];
    const firstMissing = reached.findIndex((v) => !v);
    let nextMilestone =
      firstMissing === -1
        ? "Revenue Loop vollständig bewiesen"
        : nextLabels[firstMissing];

    let tone = "blue";
    let title = publication.scheduled
      ? "Test bereit"
      : "Noch kein Veröffentlichungsnachweis";
    let copy = publication.scheduled
      ? "Veröffentlichung ist geplant. Die ersten Messsignale können Vorbereitungstests enthalten."
      : "Publication-State und Messsignale werden geprüft.";

    if (publication.failed || publication.overdue || publication.stale) {
      tone = "amber";
      title = "Veröffentlichung prüfen";
      copy = publication.failed
        ? "Ein Plattformfehler wurde beobachtet. Erst den Publish-State klären."
        : publication.overdue
          ? "Ein geplanter Post ist überfällig, aber noch nicht als live bestätigt."
          : "Die letzte Plattform-Beobachtung ist veraltet.";
    } else if ((commission || 0) > 0) {
      tone = "green";
      title = "Revenue Loop bewiesen";
      copy =
        "Eine Provision ist bestätigt. Jetzt geht es um Wiederholbarkeit und Skalierung.";
    } else if ((transactions || 0) > 0) {
      tone = "green";
      title = "Sale bestätigt";
      copy =
        "Eine Affiliate-Transaktion ist nachgewiesen. Die Provisionsbestätigung ist der nächste Beweis.";
    } else if (
      [sessions, productViews, offerViews, clickouts].some(
        (n) => n !== null && n > 0,
      )
    ) {
      tone = "blue";
      title = publication.live
        ? "Messsignale beobachtet"
        : "Messung vor Veröffentlichung";
      copy =
        "Events sind vorhanden. Vorbereitungstests und organische Besuche sind in dieser Quelle nicht getrennt; daraus folgt noch kein Geschäftserfolg.";
    } else if (publication.live) {
      tone = "blue";
      title = "Test ist live";
      copy =
        "Der Content ist veröffentlicht. Die ersten qualifizierten Sessions sind der nächste Beweis.";
    }

    if (launchEvidence) {
      const states = {
        waiting_first_signal: ["Wartet auf erstes Signal", "Noch keine attributierte Launch-Session."],
        traffic_reached_dufynd: ["Traffic erreicht DUFYND", "Die erste attributierte Launch-Session ist angekommen."],
        product_interest: ["Produktinteresse", "Die Produktseite wird angesehen."],
        purchase_options_viewed: ["Kaufoptionen werden angesehen", "Offer View oder Offer Open wurde gemessen."],
        purchase_interest_reached: ["Kaufinteresse erreicht", "Merchant Clickout gemessen. Das ist kein Sale; Affiliate-Netzwerkbeleg fehlt."],
      };
      const state = states[revenue.runtime?.decision_state];
      if (state) { tone = "blue"; [title, copy] = state; }
      if (revenue.runtime?.phase === "prelaunch") {
        title = "PRELAUNCH · Test bereit";
        copy = "Launch-Zählung beginnt je Plattform zur geplanten Zeit. Vorbereitungsdaten sind ausgeschlossen.";
      }
      if (!publication.live) copy += " Veröffentlichung noch nicht frisch bestätigt.";
    }
    if (launchEvidence) {
      const next = {publication_evidence: "Veröffentlichungsnachweis", qualified_session: "Erste attributierte Launch-Session",
        product_view: "Erster Product View", offer_view: "Erster Blick auf Kaufoptionen",
        merchant_clickout: "Erster Merchant Clickout", affiliate_transaction_evidence: "Affiliate-Netzwerkbeleg für eine Transaktion"};
      nextMilestone = next[revenue.runtime?.next_evidence] || nextMilestone;
    }
    const signal = $("business-signal");
    if (signal) {
      signal.classList.remove(
        "signal-green",
        "signal-blue",
        "signal-amber",
        "signal-neutral",
      );
      signal.classList.add("signal-" + tone);
    }
    put("signal-title", title);
    put("signal-copy", copy);
    put("next-milestone", nextMilestone);
    put(
      "pipeline-stage",
      publication.live ? "LIVE" : publication.scheduled ? "PLAN" : "OFFEN",
    );
    const ring = $("pipeline-ring");
    if (ring) ring.dataset.state = publication.live ? "live" : "pending";

    return { reached, firstMissing };
  }

  function render(s) {
    snapshot = s;
    const c = s.command_center || {};
    const f = s.freshness || {};
    const complete = f.operational_complete === true;
    const gates = Array.isArray(s.decision_center) ? s.decision_center : [];
    const workers = Array.isArray(s.worker_deck) ? s.worker_deck : [];
    const primaryWorker = workers.find((w) => w.status === "ACTIVE");
    const primaryTitle = primaryWorker
      ? taskTitle(primaryWorker)
      : c.current_task;
    const systemsHealth = Array.isArray(s.system_health) ? s.system_health : [];
    const attention = systemsHealth.filter((h) =>
      ["STALE", "DEGRADED", "BLOCKED", "UNKNOWN"].includes(h.health),
    );
    put(
      "source-summary",
      attention.length
        ? attention.length + " Quellenhinweise · Details prüfen →"
        : systemsHealth.length && complete
          ? "Systemquellen aktuell →"
          : "Quellenstatus nicht vollständig bestätigt →",
    );
    $("source-summary").classList.toggle(
      "needs-check",
      attention.length > 0 || !systemsHealth.length || !complete,
    );
    const revenue = s.first_money || {};
    const products = s.money_products || {};
    const safety = s.runtime_safety || {};
    const budget = s.budget || {};
    const queueData = s.queue || {};
    const gatesCount = numeric(c.human_approval_count);
    const needsApproval = gates.length > 0 && gatesCount > 0;
    const gatesComplete = c.gates_complete === true;
    $("decisions").hidden = gatesComplete && !needsApproval;
    $("pulse-action").href =
      gatesComplete && !needsApproval ? "#command" : "#decisions";
    $("decision-nav").closest("a").href = $("pulse-action").href;

    const posts = Array.isArray(revenue.posts) ? revenue.posts : [];
    const now = Date.now();
    const normalizedStates = posts.map((p) =>
      String(p.state || "").toUpperCase(),
    );
    const publication = {
      failed: normalizedStates.some((x) =>
        ["ERROR", "FAILED", "REJECTED"].includes(x),
      ),
      live: normalizedStates.some((x) =>
        ["PUBLISHED", "POSTED", "LIVE", "SUCCESS"].includes(x),
      ),
      scheduled: normalizedStates.some((x) =>
        ["PENDING", "SCHEDULED"].includes(x),
      ),
      overdue: posts.some(
        (p) =>
          ["PENDING", "SCHEDULED"].includes(
            String(p.state || "").toUpperCase(),
          ) &&
          Number.isFinite(Date.parse(p.scheduled_at)) &&
          Date.parse(p.scheduled_at) + 20 * 60 * 1000 < now,
      ),
      stale: revenue.publication_stale === true,
    };
    const nextPost = posts
      .filter(
        (p) =>
          Number.isFinite(Date.parse(p.scheduled_at)) &&
          Date.parse(p.scheduled_at) >= now,
      )
      .sort(
        (a, b) => Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at),
      )[0];

    const jarvisTone = needsApproval
      ? "red"
      : c.ceo_status === "BLOCKIERT"
        ? "amber"
        : c.status === "WORKING"
          ? "blue"
          : c.status === "WAITING"
            ? "blue"
            : c.status === "ERROR"
              ? "amber"
              : complete
                ? "green"
                : "neutral";
    const jarvisMain = needsApproval
      ? "Freigabe offen"
      : c.ceo_status === "BLOCKIERT"
        ? "Blockiert"
        : c.status === "WORKING"
          ? "Arbeitet"
          : c.status === "WAITING"
            ? "Überwacht"
            : c.status === "ERROR"
              ? "Prüfen"
              : complete
                ? "Stabil"
                : "Unklar";
    const waitingExternal = Number(queueData.waiting_external || 0);
    const blockedTasks = Number(queueData.blocked || 0);
    const jarvisDetail =
      c.status === "WAITING"
        ? "Freier Loop aktiv · " +
          waitingExternal +
          " extern · " +
          blockedTasks +
          " blockiert."
        : primaryTitle || "Supervisor-State aktuell.";

    setPulse("pulse-jarvis", jarvisTone, jarvisMain, jarvisDetail);
    setPulse(
      "pulse-action",
      needsApproval ? "red" : gatesComplete ? "green" : "amber",
      needsApproval
        ? "Freigabe nötig"
        : gatesComplete
          ? "Nichts offen"
          : "Unklar",
      needsApproval
        ? gates[0]?.title || "Owner-Entscheidung erforderlich"
        : gatesComplete
          ? "Keine Owner-Entscheidung erforderlich."
          : "Freigabequellen sind unvollständig.",
    );
    setTone("jarvis-core", jarvisTone);
    $("jarvis-core").dataset.mode =
      c.status === "WORKING" ? "working" : "monitoring";

    let moneyTone = "neutral";
    let moneyMain = "Unklar";
    let moneyDetail = "Noch kein belastbarer Publication-State.";
    if (publication.failed || publication.overdue || publication.stale) {
      moneyTone = "amber";
      moneyMain = "Prüfen";
      moneyDetail = publication.failed
        ? "Publication-Fehler beobachtet."
        : publication.overdue
          ? "Geplanter Post überfällig."
          : "Publication-Beobachtung veraltet.";
    } else if (publication.live) {
      moneyTone = "green";
      moneyMain = "Live";
      moneyDetail = "First-Money-Content ist veröffentlicht.";
    } else if (publication.scheduled) {
      moneyTone = "blue";
      moneyMain = "Geplant";
      moneyDetail = nextPost
        ? (nextPost.platform || "Post") + " · " + stamp(nextPost.scheduled_at)
        : "Auto-Publish geplant.";
    }
    if (revenue.analytics_provenance === "launch_attributed_excludes_prelaunch" && revenue.analytics_complete === true) {
      moneyTone = "blue";
      moneyMain = revenue.runtime?.phase === "prelaunch" ? "PRELAUNCH" : "Messfenster";
      moneyDetail = revenue.runtime?.phase === "prelaunch"
        ? "Geplant: " + (nextPost ? stamp(nextPost.scheduled_at) : "Auto-Publish")
        : "Launch-Signale werden gemessen · Veröffentlichung separat bestätigen.";
      if (publication.failed) { moneyTone = "amber"; moneyDetail = "Publication-Fehler beobachtet · Messung separat prüfen."; }
    }
    setPulse("pulse-money", moneyTone, moneyMain, moneyDetail);

    const costUnknown =
      safety.provider_cost_unknown === true ||
      safety.today_new_cost_usd === null ||
      safety.today_new_cost_usd === undefined;
    const todayCost = numeric(safety.today_new_cost_usd) || 0;
    setPulse(
      "pulse-cost",
      costUnknown ? "amber" : todayCost === 0 ? "green" : "blue",
      costUnknown ? "Unbekannt" : "$" + todayCost.toFixed(4),
      costUnknown
        ? "Kostenstatus nicht vollständig bestätigt."
        : todayCost === 0
          ? "Keine neuen Jarvis-Kosten heute."
          : "Bekannte Jarvis-Kosten heute.",
    );

    const approval = $("approval-alert");
    if (approval) approval.hidden = !needsApproval;
    if (needsApproval) {
      put(
        "approval-summary",
        gates.length === 1
          ? gates[0].title
          : gatesCount + " Freigaben warten auf dich",
      );
      put(
        "approval-detail",
        gates[0]?.reason ||
          "Öffne die Freigabe für Grund, Risiko, Kosten, Nutzen und GO-Token.",
      );
    }

    const decisionPanel = $("decisions");
    if (decisionPanel) {
      decisionPanel.classList.toggle("has-decisions", needsApproval);
      decisionPanel.classList.toggle("no-decisions", !needsApproval);
    }
    const decisions = $("decision-list");
    if (decisions) {
      decisions.replaceChildren();
      for (const d of gates) {
        const item = node("article", undefined, "decision-item");
        item.append(badge("WAITING HUMAN"), node("h3", d.title));
        line(item, "Gate", d.type);
        line(item, "Grund", d.reason);
        line(item, "Risiko", d.risk);
        line(item, "Kosten USD", d.cost_usd);
        line(item, "Nutzen", d.benefit);
        if (d.content_candidate) {
          const candidate = d.content_candidate;
          for (const [label, key] of [["Produkt", "product"], ["Creative / Asset", "asset_reference"],
            ["Hook", "hook"], ["Caption", "caption"], ["Plattform", "platform"],
            ["content_id", "content_id"], ["experiment_id", "experiment_id"],
            ["Internes Rating / 10", "internal_rating"], ["Empfehlungsgrund", "recommendation_reason"],
            ["Asset-Revision", "revision_fingerprint"]]) line(item, label, candidate[key]);
          line(item, "Gewünschte Zeit", stamp(candidate.requested_at));
          line(item, "Status", "Wartet auf Owner · Scheduling und Publishing nicht freigegeben");
        }
        line(item, "Exakter GO-Token", d.go_token);
        if (d.provider) line(item, "Provider", d.provider);
        decisions.append(item);
      }
      if (!gates.length) {
        decisions.append(
          node(
            "p",
            gatesComplete
              ? "Keine Freigabe erforderlich. Du musst aktuell nichts entscheiden."
              : "Freigabestatus ist noch nicht vollständig bestätigt.",
            "muted",
          ),
        );
      }
    }

    put(
      "priority",
      primaryTitle ||
        (c.status === "WAITING"
          ? "Jarvis wartet auf den nächsten zulässigen oder externen Trigger."
          : "Aktueller Zustand aus dem letzten verifizierten Supervisor-Loop."),
    );
    put("current-task", primaryTitle || "Keine aktive Ausführung");
    put(
      "allowed-task",
      c.next_allowed_task || "Warten auf nächsten zulässigen Trigger",
    );
    put("stop-reason", c.stop_reason);
    put("lease-count", safety.active_leases);
    put("loop-time", "Loop · " + stamp(c.last_loop_at));
    const jarvisState = $("jarvis-state");
    if (jarvisState)
      jarvisState.replaceWith(
        Object.assign(badge(c.ceo_status || c.status), { id: "jarvis-state" }),
      );

    put(
      "head",
      c.observed_head_sha ? String(c.observed_head_sha).slice(0, 10) : null,
    );
    put("head-age", "Branch-Beobachtung · " + stamp(c.head_observed_at));
    put("active-workers", (complete ? "" : "≥ ") + value(c.active_workers));
    put("working-count", (complete ? "" : "≥ ") + value(c.working_tasks));
    put(
      "decision-count",
      (complete ? "" : "≥ ") + value(c.human_approval_count),
    );
    put("decision-nav", c.human_approval_count);
    put(
      "worker-summary",
      c.active_workers
        ? "Aktive Ausführungen beobachtet"
        : "Keine aktiven Worker beobachtet",
    );
    put(
      "wake-time",
      c.last_supervisor_wake ? shortTime(c.last_supervisor_wake) : null,
    );
    put(
      "next-wake",
      "Wake-Schätzung · " + stamp(c.next_supervisor_wake_estimate),
    );
    put("last-action", c.last_completed_action);
    put(
      "next-action",
      (c.checkpoint_stale ? "STALE PLAN · " : "") + value(c.next_safe_action),
    );
    put(
      "checkpoint-age",
      (c.checkpoint_stale ? "STALE · " : "") +
        "Checkpoint · " +
        stamp(c.checkpoint_observed_at),
    );

    const publications = $("publication-list");
    if (publications) {
      publications.replaceChildren();
      for (const p of posts)
        line(
          publications,
          p.platform,
          stamp(p.scheduled_at) + " · " + value(p.state),
        );
      line(
        publications,
        "Publication-Nachweis",
        (revenue.publication_stale ? "STALE · " : "") +
          stamp(revenue.publication_observed_at),
      );
    }
    put(
      "content-identifiers",
      "content_id: " +
        value(revenue.content_id) +
        " · experiment_id: " +
        value(revenue.experiment_id),
    );

    const intelligence = renderDecisionIntelligence(revenue, publication);
    const stageDefs = [
      ["Content", "publication", publication.live],
      ["Sessions", "sessions", (numeric(revenue.sessions) || 0) > 0],
      [
        "Product Views",
        "product_views",
        (numeric(revenue.product_views) || 0) > 0,
      ],
      ["Offer Views / Opens", "offer_views", ((numeric(revenue.offer_views) || 0) + (numeric(revenue.offer_opens) || 0)) > 0],
      [
        "Clickouts",
        "merchant_clickouts",
        (numeric(revenue.merchant_clickouts) || 0) > 0,
      ],
      [
        "Transactions",
        "transactions",
        (numeric(revenue.transactions) || 0) > 0,
      ],
      [
        "Commission €",
        "commission_eur",
        (numeric(revenue.commission_eur) || 0) > 0,
      ],
    ];
    const funnel = $("funnel");
    if (funnel) {
      funnel.replaceChildren();
      stageDefs.forEach(([label, key, reached], index) => {
        const cell = node("div");
        if (key !== "publication" && numeric(revenue[key]) === null)
          cell.classList.add("unknown");
        const firstMissing = intelligence.firstMissing;
        if (reached) cell.classList.add(index >= 5 ? "proven" : "reached");
        else if (index === firstMissing) cell.classList.add("current");
        let metric =
          key === "publication"
            ? publication.live
              ? "LIVE"
              : publication.scheduled
                ? "READY"
                : "—"
            : numeric(revenue[key]) === null
              ? "—"
              : value(revenue[key]);
        if (
          !revenue.analytics_complete &&
          [
            "sessions",
            "product_views",
            "offer_views",
            "merchant_clickouts",
          ].includes(key) &&
          numeric(revenue[key]) !== null
        ) {
          metric = "≥ " + metric;
        }
        if (key === "offer_views" && numeric(revenue.offer_opens) !== null) metric += " / " + value(revenue.offer_opens);
        const detail =
          key !== "publication" && numeric(revenue[key]) === null
            ? "Kein Nachweis"
            : reached
              ? key === "publication" || index >= 5
                ? "Belegt"
                : revenue.analytics_provenance === "launch_attributed_excludes_prelaunch" ? "Launch-Signal" : "Signal · unklassifiziert"
              : index === firstMissing
                ? "Nächster Beweis"
                : "Ausstehend";
        cell.append(
          node("small", label),
          node("strong", metric),
          node("span", detail),
        );
        funnel.append(cell);
      });
    }
    put(
      "funnel-basis",
      revenue.analytics_provenance === "launch_attributed_excludes_prelaunch"
        ? "Launch-Attribution nach Plattform-Zeitpunkt · Vorbereitung und fremder Traffic ausgeschlossen. Attribution beweist keine organische Reichweite. Clickouts sind keine Sales. Quelle: Analytics · " + stamp(revenue.runtime?.observed_at)
        : "Beobachtete Events für diesen Content und 1 Million; kann Vorbereitungstests enthalten. Clickouts sind keine Sales. Transaktionen und Provision benötigen Affiliate-Netzwerknachweise.",
    );
    put(
      "purchase-basis",
      revenue.runtime?.purchase_verified_at
        ? "Kaufziel geprüft · " +
            stamp(revenue.runtime.purchase_verified_at) +
            " · gültig bis " +
            stamp(revenue.runtime.purchase_expires_at)
        : "Kaufziel-Nachweis: UNKNOWN",
    );
    renderOperatingPanels(s);

    const productList = $("money-products");
    if (productList) {
      productList.replaceChildren();
      for (const p of products.rows || []) {
        const state = String(p.state || "");
        const cls = state.includes("live_first_money")
          ? "product-live"
          : state.includes("preparation")
            ? "product-active"
            : state.includes("next_after")
              ? "product-watch"
              : "product-later";
        const cell = node("div", undefined, cls);
        cell.append(
          node("h4", p.product),
          node("p", friendlyProductState(state)),
        );
        productList.append(cell);
      }
    }
    put(
      "product-evidence",
      (products.stale ? "STALE · " : "") +
        "Checkpoint · " +
        stamp(products.observed_at),
    );

    const queue = $("queue-counts");
    if (queue) {
      queue.replaceChildren();
      for (const key of [
        "done",
        "active",
        "waiting_external",
        "blocked",
        "cancelled",
      ]) {
        const cell = node("div");
        cell.append(node("small", key), node("strong", queueData[key]));
        queue.append(cell);
      }
    }
    put("queue-time", "Loop-Beobachtung · " + stamp(queueData.observed_at));
    put(
      "runtime-safety",
      "Neue Jarvis-Kosten heute: " +
        (costUnknown ? "Unknown" : "$" + todayCost.toFixed(4)) +
        " · Stale leases: " +
        value(safety.stale_leases) +
        " · Open reservations: " +
        value(safety.open_reservations) +
        " · provider_cost_unknown: " +
        value(safety.provider_cost_unknown),
    );

    for (const key of ["cap", "spend", "remaining"]) {
      const field = {
        cap: "cap_usd",
        spend: "spent_usd",
        remaining: "remaining_usd",
      }[key];
      const n = numeric(budget[field]);
      put("budget-" + key, n === null ? null : "$" + n.toFixed(2));
    }
    const paid = $("paid-state");
    if (paid)
      paid.replaceWith(
        Object.assign(badge(budget.paid_model_execution), { id: "paid-state" }),
      );
    put(
      "budget-details",
      "Paid execution · " +
        stamp(budget.paid_model_execution_observed_at) +
        " · Runs " +
        value(budget.runs) +
        "/" +
        value(budget.max_runs) +
        " · Status " +
        value(budget.status),
    );

    const deck = $("worker-deck");
    if (deck) {
      const historyOpen = deck.querySelector(".worker-history")?.open === true;
      deck.replaceChildren();
      const current = workers.filter(
        (w) =>
          !["completed", "failed_terminal"].includes(w.execution_status) &&
          !w.completed_at,
      );
      current.forEach((w) => deck.append(workerCard(w)));
      if (!current.length) {
        const empty = node("div", undefined, "empty-station");
        empty.append(
          node(
            "p",
            complete
              ? "Kein aktiver Worker zugeordnet. Konkrete Abhängigkeiten stehen unter Arbeit und Arbeitsbereichen."
              : "Keine laufenden Ausführungen in der aktuellen Beobachtung.",
          ),
        );
        deck.append(empty);
      }
      const history = workers.filter((w) => !current.includes(w)).slice(0, 6);
      if (history.length) {
        const details = node("details", undefined, "worker-history");
        details.open = historyOpen;
        details.append(
          node(
            "summary",
            "Letzte abgeschlossene Ausführungen · " + history.length,
          ),
        );
        const grid = node("div", undefined, "worker-grid");
        history.forEach((w) => grid.append(workerCard(w)));
        details.append(grid);
        deck.append(details);
      }
      put(
        "worker-count",
        current.length + " laufend · " + history.length + " recent",
      );
    }

    const select = $("domain-filter");
    if (select) {
      const selected = select.value;
      const domains = [
        ...new Set(
          Object.values(s.mission_board || {})
            .flat()
            .map((r) => r.domain)
            .filter(Boolean),
        ),
      ].sort();
      select.replaceChildren(new Option("All domains", ""));
      domains.forEach((d) => select.add(new Option(d, d)));
      select.value = selected;
    }
    put(
      "completeness",
      complete
        ? "Operative Quellen vollständig innerhalb der Read-Grenzen."
        : "Unvollständige Quellen: " +
            value((f.incomplete_sources || []).join(", ")) +
            ". Zähler sind beobachtete Untergrenzen.",
    );
    missions();

    const verifiedRecent = (s.live_feed || []).slice(0, 3);
    const overviewActivity = $("overview-activity-list");
    if (overviewActivity) {
      const signature = JSON.stringify(verifiedRecent);
      if (overviewActivity.dataset.signature !== signature) {
        overviewActivity.dataset.signature = signature;
        overviewActivity.replaceChildren();
        for (const e of verifiedRecent) {
          const item = node("article", undefined, "overview-feed-item");
          item.append(node("time", shortTime(e.observed_at)));
          const copy = node("div");
          copy.append(
            node("strong", taskLabels[e.task_id] || e.title),
            node("span", e.detail),
          );
          item.append(copy);
          overviewActivity.append(item);
        }
        if (!verifiedRecent.length)
          overviewActivity.append(
            node(
              "p",
              "Keine verifizierten Abschlüsse in der aktuellen Beobachtung. Der Supervisor wird separat überwacht.",
              "muted",
            ),
          );
      }
    }

    const activity = $("activity-list");
    if (activity) {
      activity.replaceChildren();
      for (const e of workers
        .filter(
          (w) =>
            w.completed_at &&
            w.execution_status === "completed" &&
            w.checkpoint?.verified === true,
        )
        .slice(0, 8)) {
        const item = node("article", undefined, "activity-item");
        item.append(
          node("time", stamp(e.completed_at)),
          node("strong", e.task_title || e.task_id),
        );
        line(item, "Verified checkpoint", e.checkpoint?.step);
        activity.append(item);
      }
      if (!activity.children.length)
        activity.append(
          node("p", "Keine verifizierten Events in der Beobachtung.", "muted"),
        );
    }

    const healthOverview = $("overview-system-health");
    if (healthOverview) {
      healthOverview.replaceChildren();
      const ranked = [...systemsHealth]
        .sort((a, b) => {
          const score = (h) =>
            healthTone(h) === "amber" ? 0 : healthTone(h) === "blue" ? 1 : 2;
          return a.name === "Jarvis free loop"
            ? -1
            : b.name === "Jarvis free loop"
              ? 1
              : score(a.health) - score(b.health);
        })
        .slice(0, 5);
      for (const h of ranked) {
        const tone = healthTone(h.health);
        const row = node("div", undefined, "health-chip health-" + tone);
        const left = node("span");
        left.append(
          node("i"),
          node(
            "span",
            h.name === "Supervisor"
              ? "Supervisor-Prüfung"
              : h.name === "Jarvis free loop"
                ? "Freier Jarvis-Loop"
                : h.name,
          ),
        );
        if (h.last_success_at)
          left.append(node("small", "Beobachtet " + stamp(h.last_success_at)));
        row.append(left, node("b", sourceHealthLabel(h.health)));
        healthOverview.append(row);
      }
      if (!ranked.length)
        healthOverview.append(
          node("p", "Keine Systemdaten im Snapshot.", "muted"),
        );
    }

    const systems = $("system-list");
    if (systems) {
      systems.replaceChildren();
      for (const h of systemsHealth) {
        const item = node("details", undefined, "system-row");
        const summary = node("summary");
        summary.append(node("strong", h.name), badge(h.health));
        item.append(summary);
        if (h.last_success_at)
          line(item, "Last success", stamp(h.last_success_at));
        for (const o of h.observers || []) {
          line(item, o.observer_id, o.health);
          line(item, "Last success", stamp(o.last_success_at));
          line(item, "Next retry", stamp(o.next_retry_at));
        }
        for (const cr of h.credentials || []) {
          line(item, "Credential status", cr.effective_status);
          line(item, "Expires", stamp(cr.expires_at));
          if (cr.owner_reauthorization_required)
            line(item, "Owner action", "Reauthorization required");
        }
        systems.append(item);
      }
    }

    put("map-state", c.status);
    const currentWorkerCount = workers.filter(
      (w) =>
        !["completed", "failed_terminal"].includes(w.execution_status) &&
        !w.completed_at,
    ).length;
    put("map-workers", currentWorkerCount + " laufende Ausführungen");
    const mapTools = $("map-tools");
    if (mapTools) {
      mapTools.replaceChildren();
      for (const name of s.system_map?.systems || []) {
        const item = node("span");
        item.append(
          node("strong", name),
          node(
            "small",
            name === "Supabase"
              ? "Read-Layer erreichbar"
              : systemsHealth.find((h) => h.name === name)?.health || "UNKNOWN",
          ),
        );
        mapTools.append(item);
      }
    }

    put("snapshot-time", "Snapshot · " + stamp(s.generated_at));
    put("sync-label", "Live · " + shortTime(new Date().toISOString()));
    const connection = $("connection-alert");
    if (connection) {
      connection.hidden = complete;
      connection.textContent =
        "Live-Abfrage erfolgreich; operative Daten sind unvollständig. Details unter Aufgaben-Details.";
    }
  }

  function renderOperatingPanels(s) {
    const c = s.command_center || {};
    const workers = s.worker_deck || [];
    const current = workers.find((w) => w.status === "ACTIVE");
    const duration =…19317 tokens truncated…    const path = new URL(r.request().url()).pathname;
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
