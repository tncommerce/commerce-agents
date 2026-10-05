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
  const statusHelp = (status) => {
    const help = {
      AKTUELL: "Diese Quelle wurde innerhalb des erwarteten Zeitfensters erfolgreich geprüft.",
      ÜBERWACHT: "Die Quelle meldet sich gesund und wird regelmäßig beobachtet; das ist keine aktive Worker-Ausführung.",
      "NACHWEIS ÄLTER": "Der letzte bestätigte Nachweis ist älter. Das bedeutet nicht automatisch einen Ausfall.",
      "WAITING EXTERNAL": "Jarvis kann erst weiterarbeiten, wenn eine externe Antwort oder ein externes Ereignis eintritt.",
      BLOCKED: "Eine konkrete Voraussetzung fehlt. Der nächste Lösungsschritt wird darunter angezeigt.",
      "OWNER GATE": "Nur hier ist eine Entscheidung von Tuan erforderlich. Ein GO allein führt keine externe Aktion aus.",
      "VERBINDUNG / SYSTEM PRÜFEN": "Eine Quelle meldet einen konkreten Fehler oder eine gesperrte Verbindung.",
      "VERBINDUNG EINGESCHRÄNKT": "Ein nichtkritischer Kanal ist eingeschränkt. Production und Owner Gates werden separat bewertet.",
    }[status];
    if (!help) return null;
    const details = node("details", undefined, "status-help");
    const summary = node("summary", "ⓘ");
    summary.title = help;
    summary.setAttribute("aria-label", "Erklärung: " + status);
    details.append(summary, node("p", help));
    return details;
  };
  const badge = (status) => {
    const tone =
      {
        AKTUELL: "good",
        ÜBERWACHT: "info",
        "NACHWEIS ÄLTER": "warn",
        "VERBINDUNG / SYSTEM PRÜFEN": "action",
        "VERBINDUNG EINGESCHRÄNKT": "warn",
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
      STALE: "Nachweis älter",
      ACTIVE: "Aktiv",
      "WAITING HUMAN": "Owner Gate",
      UNKNOWN: "Unbekannt",
      WAITING: "Wartet",
      WORKING: "Arbeitet",
      READY: "Bereit",
    };
    const result = node("span", labels[status] || status, "pill " + tone);
    const help = statusHelp(status === "WAITING HUMAN" ? "OWNER GATE" : status === "STALE" ? "NACHWEIS ÄLTER" : status);
    if (help) result.append(help);
    return result;
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
        line(card, "Warum", taskWait(m));
        line(card, "Danach", m.explanation?.next_step || detailText(m.next_checkpoint));
        line(card, "Owner", m.explanation?.owner_action || "Freigabestatus unter Entscheidungen prüfen.");
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
    (code ? "Schritt noch nicht in Klartext dokumentiert" : "Nicht dokumentiert");
  const taskWait = (task) => {
    if (!task) return "Keine konkrete Aufgabe zugeordnet";
    if (task.explanation?.reason) return task.explanation.reason;
    if (task.blocker) return detailText(task.blocker);
    if (task.human_gate) return "Eine echte Owner-Entscheidung ist offen";
    if (task.dependencies?.length)
      return task.dependencies.map(detailText).join(" · ");
    if (task.status === "waiting_external")
      return "Externe Antwort oder Nachweis fehlt; genauer Auslöser noch nicht dokumentiert.";
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
      STALE: "NACHWEIS ÄLTER",
      MONITORED: "ÜBERWACHT",
      DEGRADED: "Quelle meldet Einschränkung",
      BLOCKED: "Blockiert",
      UNKNOWN: "Nicht bestätigt",
      BLOCKED_CONFIGURATION: "Konfiguration blockiert",
      INITIALIZING_STUCK: "Initialisierung überfällig",
      INITIALIZING: "Initialisierung läuft",
      FAILED: "Lesen fehlgeschlagen",
    })[health] ||
    health ||
    "Nicht bestätigt";
  const age = (stampValue) => {
    if (!stampValue || !Number.isFinite(Date.parse(stampValue))) return "Zeitpunkt nicht dokumentiert";
    const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(stampValue)) / 1000));
    if (seconds < 60) return "vor " + seconds + " Sek.";
    if (seconds < 3600) return "vor " + Math.floor(seconds / 60) + " Min";
    return "vor " + Math.floor(seconds / 3600) + "h " + Math.floor(seconds % 3600 / 60) + "min";
  };
  function taskDetail(task) {
    const item = node("article", undefined, "dependency-task");
    item.dataset.taskId = task.task_id || "";
    item.append(node("strong", taskTitle(task)));
    line(item, "Status", detailText(task.status));
    line(item, "Grund / Voraussetzung", taskWait(task));
    line(item, "Seit", age(task.explanation?.since || task.updated_at) + " · " + stamp(task.explanation?.since || task.updated_at));
    line(item, "Zeitbasis", task.explanation?.since_basis || "Letzte Aufgabenaktualisierung; Statusbeginn nicht dokumentiert");
    line(item, "Was passiert danach", task.explanation?.next_step || detailText(task.next_checkpoint));
    line(item, "Wer kann es lösen", task.explanation?.resolver || "Zuständigkeit noch nicht dokumentiert");
    line(item, "Owner", task.explanation?.owner_action || "Freigabestatus unter Entscheidungen prüfen.");
    const source = node("details", undefined, "task-source");
    source.append(node("summary", "Original & Aufgabenkennung"));
    line(source, "Original", task.title || task.task_id);
    line(source, "Aufgabe", task.task_id);
    line(source, "Technischer Blocker", task.blocker);
    line(source, "Technischer Checkpoint", task.next_checkpoint);
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
    item.append(node("small", (w.display_name || "Identität nicht dokumentiert").toUpperCase() + (w.identity_tag ? " · " + w.identity_tag : "")), node("small", w.role || "Worker"), heading);
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
        node("strong", w.description?.next_step || detailText(w.next_checkpoint)),
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
          "Technische Identität & Nachweise",
        ),
      );
      line(metadata, "worker_id", w.worker_id);
      line(metadata, "execution_id", w.execution_id);
      line(metadata, "Aufgabe", w.task_id);
      line(metadata, "Original", w.task_title || w.task_id);
      line(metadata, "Gestartet", stamp(w.started_at));
      line(metadata, "Lebenszeichen", stamp(w.heartbeat_at));
      line(metadata, "Lease gültig bis", stamp(w.lease_expires_at));
      item.append(metadata);
      return item;
    }
    line(item, w.status === "ACTIVE" ? "Aktuell" : "Wartet auf", w.status === "ACTIVE" ? taskTitle(w) + " · " + detailText(w.execution_status) : w.description?.reason || detailText(w.wait_reason));
    line(item, "Danach", w.description?.next_step || detailText(w.next_checkpoint));
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
      node("small", w.role || "Worker"),
      node("h3", (w.display_name || "Identität nicht dokumentiert").toUpperCase() + (w.identity_tag ? " · " + w.identity_tag : "")),
      node("p", w.task_title || w.task_id || "Task"),
    );
    line(card, "Startzeit", shortTime(w.started_at));
    line(card, "Laufzeit", w.duration_seconds == null ? "Nicht dokumentiert" : Math.floor(w.duration_seconds / 60) + " Min");
    line(card, "Heartbeat", age(w.heartbeat_at));
    const identity = node("details", undefined, "worker-identity");
    identity.append(node("summary", "Technische Identität"));
    line(identity, "worker_id", w.worker_id);
    line(identity, "execution_id", w.execution_id);
    line(identity, "Handler", w.handler_id);
    line(identity, "Lease", stamp(w.lease_expires_at));
    card.append(identity);
    card.append(workerEvidence(w));
    return card;
  }

  function healthTone(health) {
    if (health && typeof health === "object") return health.display_tone || healthTone(health.health);
    const v = String(health || "").toUpperCase();
    if (["HEALTHY", "READY", "SUCCESS", "LIVE"].includes(v)) return "green";
    if (["ACTIVE", "WORKING", "MONITORED"].includes(v)) return "blue";
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
    if (publication.replacementScheduled) {
      tone = "blue";
      title = "Ersatz geplant · Owner GO vorhanden";
      copy = "Der ursprüngliche Post bleibt entfernt/gestoppt historisiert. Die freigegebene Ersatzrevision ist separat für Instagram geplant.";
      nextMilestone = publication.replacement?.scheduled_at
        ? "Instagram-Veröffentlichung · " + stamp(publication.replacement.scheduled_at)
        : "Geplante Ersatzveröffentlichung beobachten";
    } else if (publication.stopped) {
      tone = "amber";
      title = "Launch gestoppt · Ersatz wartet auf Owner GO";
      copy = "Instagram wurde entfernt, TikTok vor Veröffentlichung gestoppt. Historische Messsignale bleiben erhalten; der alte Plan ist kein aktiver Launch.";
      nextMilestone = "Content-Chat: neue Revision prüfen und explizites Owner GO abwarten";
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
      publication.live ? "LIVE" : publication.replacementScheduled || publication.scheduled ? "PLAN" : "OFFEN",
    );
    const ring = $("pipeline-ring");
    if (ring) ring.dataset.state = publication.live ? "live" : "pending";

    return { reached, firstMissing };
  }

  function renderRiskAndCrew(s) {
    const risk = s.global_risk;
    const riskRoot = $("global-risk");
    const crew = s.crew;
    const openIds = new Set([...document.querySelectorAll("#risk-panel details[open], #crew-grid details[open]")].map(el => el.id));
    const focusId = document.activeElement?.id;
    if (riskRoot) {
      setTone("global-risk", risk?.tone || "amber");
      put("risk-title", risk?.title || "LAGE NICHT BESTÄTIGT");
      put("risk-summary", risk?.summary || "Aktuelle Risikoprojektion fehlt; keine Entwarnung bestätigt.");
      put("risk-owner-action", risk?.owner_action || "Owner-Bedarf nicht bestätigt.");
      put("risk-observed", "Live-Daten · " + stamp(risk?.observed_at));
      $("risk-level").textContent = risk?.tone === "red" ? "HANDLUNG" : risk?.tone === "amber" ? "BEOBACHTEN" : risk?.tone === "green" ? "GESUND" : "UNBESTÄTIGT";
      $("risk-level").className = "pill " + ({green: "good", blue: "info", amber: "warn", red: "action"}[risk?.tone] || "warn");
      const panel = $("risk-panel");
      panel.replaceChildren();
      for (const item of risk?.panels || []) {
        const detail = node("details", undefined, "risk-item state-" + item.tone);
        detail.id = "risk-detail-" + item.id;
        detail.open = openIds.has(detail.id);
        const summary = node("summary");
        summary.id = "risk-summary-" + item.id;
        summary.append(node("small", item.name), node("span", {green:"●",blue:"●",amber:"●",red:"●"}[item.tone], "risk-dot " + item.tone), node("strong", item.title));
        detail.append(summary);
        line(detail, "Warum", item.reason);
        if (item.since) line(detail, "Nachweis", stamp(item.since) + " · " + age(item.since));
        line(detail, "Nächster Schritt", item.next_step);
        line(detail, "Owner", item.owner_action);
        panel.append(detail);
      }
    }
    if ($("crew-grid")) {
      put(
        "crew-count",
        crew
          ? crew.roles.length +
              " Rollen · " +
              crew.active_executions +
              " aktive Ausführungen"
          : "Rollenstatus nicht bestätigt",
      );
      put(
        "crew-supervisor-state",
        crew
          ? crew.supervisor_state +
              " · " +
              (s.command_center?.active_workers || 0) +
              " belegte aktive Ausführungen. Nächster Loop: " +
              shortTime(s.command_center?.next_loop_estimate)
          : "Aktuelle Loop-Evidence fehlt.",
      );
      setTone(
        "crew-supervisor",
        s.global_risk?.panels?.find((p) => p.id === "automation")?.tone || "amber",
      );
      $("crew-owner-link").hidden = !(s.decision_center?.length > 0);

      const liveBoard = $("crew-live-now");
      liveBoard.replaceChildren();
      const liveNow = crew?.live_now || [];
      put(
        "crew-live-count",
        liveNow.length
          ? liveNow.length + " wirklich aktiv"
          : "0 aktiv · Jarvis überwacht",
      );
      if (liveNow.length) {
        for (const live of liveNow) {
          const item = node("article", undefined, "crew-live-card");
          item.dataset.role = live.role_id;
          item.append(
            node("span", "LIVE", "crew-live-badge"),
            node("strong", live.role),
            node("small", live.alias.toUpperCase()),
            node("p", live.task || "Aktuelle Aufgabe nicht dokumentiert", "crew-live-task"),
          );
          const meta = node("div", undefined, "crew-live-meta");
          meta.append(
            node("span", "Seit " + age(live.started_at)),
            node("span", "Heartbeat " + age(live.heartbeat_at)),
            node("span", "Echter Fortschritt " + age(live.last_progress_at)),
          );
          item.append(meta);
          item.append(
            node("p", live.checkpoint?.verified === true
              ? "Letzter bestätigter Schritt · " + detailText(live.checkpoint.step) + " · " + stamp(live.checkpoint.verified_at)
              : "Letzter bestätigter Schritt · Unbekannt", "crew-live-next"),
          );
          if (live.next_checkpoint)
            item.append(
              node("p", "Nächster Checkpoint · " + live.next_checkpoint, "crew-live-next"),
            );
          liveBoard.append(item);
        }
      } else {
        const empty = node("article", undefined, "crew-live-empty");
        empty.append(
          node("span", "MONITORING", "crew-monitor-badge"),
          node("strong", "Aktuell keine Worker-Ausführung"),
          node(
            "p",
            "Jarvis überwacht weiter. Neue Arbeit erscheint hier erst, wenn ein realer Task gestartet und durch Lease + Heartbeat bestätigt ist.",
          ),
        );
        liveBoard.append(empty);
      }

      const grid = $("crew-grid");
      grid.replaceChildren();
      const clusterMap = new Map(
        (crew?.clusters || []).map((cluster) => [cluster.id, cluster]),
      );
      for (const cluster of ["BUILD", "MONEY", "GROWTH", "OPERATIONS"]) {
        const info = clusterMap.get(cluster) || {
          id: cluster,
          label: cluster,
          purpose: "",
          active_count: 0,
          waiting_count: 0,
          blocked_count: 0,
          state: "BEREIT",
        };
        const group = node("section", undefined, "crew-cluster crew-cluster-" + cluster.toLowerCase());
        group.dataset.cluster = cluster;

        const groupHead = node("header", undefined, "crew-cluster-head");
        const copy = node("div");
        copy.append(
          node("span", info.label.toUpperCase(), "crew-cluster-label"),
          node("p", info.purpose || "", "crew-cluster-purpose"),
        );
        const clusterState = node("div", undefined, "crew-cluster-state");
        clusterState.append(
          node("strong", info.state),
          node(
            "span",
            info.active_count +
              " aktiv · " +
              info.waiting_count +
              " wartet · " +
              info.blocked_count +
              " prüfen",
          ),
        );
        groupHead.append(copy, clusterState);
        group.append(groupHead);

        const lane = node("div", undefined, "crew-lane-workers");
        for (const member of (crew?.roles || []).filter((c) => c.cluster === cluster)) {
          const card = node(
            "article",
            undefined,
            "crew-node state-" + member.tone,
          );
          card.dataset.role = member.role_id;
          card.dataset.state = member.state;
          card.dataset.active = String(
            member.state === "AKTIV" &&
              member.active_count > 0 &&
              crew.complete === true,
          );

          const head = node("div", undefined, "crew-node-top");
          const identity = node("div", undefined, "crew-node-identity");
          identity.append(
            node("h4", member.alias.toUpperCase()),
            node("small", member.role.toUpperCase(), "crew-role"),
          );
          head.append(
            identity,
            node(
              "span",
              member.state,
              "pill " +
                ({ green: "good", blue: "info", amber: "warn", red: "action" }[
                  member.tone
                ] || "warn"),
            ),
          );
          card.append(head);

          if (member.state === "AKTIV") {
            card.append(node("small", "JETZT", "crew-now-label"));
            card.append(
              node(
                "p",
                member.task || "Aktuelle Aufgabe nicht dokumentiert",
                "crew-focus crew-focus-live",
              ),
            );
            if (member.since) line(card, "Läuft seit", age(member.since));
          } else if (member.state === "WARTET EXTERN") {
            card.append(node("small", "WARTET AUF", "crew-now-label"));
            card.append(node("p", member.reason, "crew-focus"));
          } else if (["BLOCKIERT", "DEGRADED", "OWNER GATE"].includes(member.state)) {
            card.append(node("small", "WARUM", "crew-now-label"));
            card.append(node("p", member.reason, "crew-focus"));
          } else if (member.last_action) {
            card.append(node("small", "ZULETZT", "crew-now-label"));
            card.append(node("p", member.last_action, "crew-focus"));
            if (member.last_action_at)
              line(card, "Abgeschlossen", age(member.last_action_at));
          } else {
            card.append(node("small", "AKTUELL", "crew-now-label"));
            card.append(
              node(
                "p",
                member.state === "BEREIT"
                  ? "Bereit für zulässige Arbeit"
                  : "Überwacht den zugeordneten Bereich",
                "crew-focus",
              ),
            );
          }

          line(card, "Danach", member.next_step);
          if (member.connections.includes("active"))
            card.append(
              node(
                "p",
                "Jarvis → " +
                  member.alias +
                  " · " +
                  member.active_count +
                  " reale Ausführung(en)",
                "crew-live-path",
              ),
            );
          if (member.connections.includes("external"))
            card.append(
              node("p", member.alias + " → Externe Antwort", "crew-dependency"),
            );
          if (member.connections.includes("owner"))
            card.append(
              node("p", "Jarvis → Tuan · Freigabe prüfen", "crew-owner-path"),
            );

          const detail = node("details", undefined, "crew-details");
          detail.id = "crew-details-" + member.role_id;
          detail.open = openIds.has(detail.id);
          const summary = node(
            "summary",
            member.task_count + " Aufgaben · Details",
          );
          summary.id = "crew-summary-" + member.role_id;
          detail.append(summary);
          line(detail, "Owner", member.owner_action);
          line(detail, "Zeitbasis", member.since_basis || "Kein Aufgabenbeginn gespeichert");
          line(detail, "Rolle", member.capability_note);
          for (const execution of member.executions) {
            line(detail, "worker_id", execution.worker_id);
            line(
              detail,
              "execution_id",
              execution.execution_id || "Task-Lease ohne Execution-ID",
            );
            line(detail, "Handler", execution.handler_id || "Nicht dokumentiert");
            line(detail, "Gestartet", stamp(execution.started_at));
            line(
              detail,
              "Laufzeit",
              execution.duration_seconds == null
                ? "Nicht dokumentiert"
                : Math.floor(execution.duration_seconds / 60) + " Min",
            );
            line(
              detail,
              "Checkpoint",
              execution.next_checkpoint || "Nicht dokumentiert",
            );
            line(
              detail,
              "Heartbeat",
              stamp(execution.heartbeat_at) + " · " + age(execution.heartbeat_at),
            );
            line(detail, "Lease bis", stamp(execution.lease_expires_at));
            line(
              detail,
              "Evidence",
              execution.checkpoint?.verified === true
                ? "Checkpoint verifiziert"
                : "Kein verifizierter Checkpoint",
            );
          }
          for (const task of member.tasks) {
            detail.append(node("p", task.title, "crew-focus"));
            line(
              detail,
              "Abhängigkeit",
              task.explanation?.reason || "Nicht dokumentiert",
            );
            line(
              detail,
              "Danach",
              task.explanation?.next_step || "Nicht dokumentiert",
            );
            if (task.blocker) line(detail, "Blocker-Code", task.blocker);
            line(detail, "task_id", task.task_id);
          }
          card.append(detail);
          lane.append(card);
        }
        group.append(lane);
        grid.append(group);
      }

      const activity = $("crew-activity");
      activity.replaceChildren();
      const recent = crew?.recent_activity || [];
      if (recent.length) {
        for (const entry of recent.slice(0, 6)) {
          const row = node("article", undefined, "crew-activity-row");
          const time = node("time", shortTime(entry.completed_at));
          const body = node("div");
          body.append(
            node("strong", entry.alias.toUpperCase() + " · " + (entry.task || "Ausführung abgeschlossen")),
            node(
              "span",
              entry.checkpoint?.verified === true
                ? "Checkpoint verifiziert"
                : "Ausführung abgeschlossen",
            ),
          );
          row.append(time, body);
          activity.append(row);
        }
      } else {
        activity.append(
          node(
            "p",
            "Noch keine abgeschlossene Worker-Aktivität im aktuellen bounded Snapshot.",
            "muted",
          ),
        );
      }

      const unassigned = crew?.unassigned_executions || [];
      $("crew-unassigned").hidden = !unassigned.length;
      $("crew-unassigned").textContent =
        unassigned.length +
        " reale Ausführung(en) ohne dokumentierte Rollenzuordnung. Technische Ausführungen unter Details prüfen.";
    }
    if (focusId && $(focusId) && document.activeElement?.id !== focusId) $(focusId).focus({preventScroll:true});
  }

  function render(s) {
    snapshot = s;
    renderRiskAndCrew(s);
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
      ["STALE", "DEGRADED", "BLOCKED", "UNKNOWN"].includes(h.health) || h.confirmed_failure === true || ["amber", "red"].includes(h.display_tone),
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
      stopped: revenue.publication_stopped === true,
      replacementScheduled: revenue.replacement_scheduled === true,
      replacement: revenue.replacement || null,
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
          : "Publikationsnachweis älter; kein Fehler bestätigt.";
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
    if (publication.replacementScheduled) {
      moneyTone = "blue";
      moneyMain = "Geplant";
      moneyDetail = publication.replacement?.scheduled_at
        ? "Ersatz · Instagram · " + stamp(publication.replacement.scheduled_at)
        : "Freigegebene Ersatzrevision ist geplant.";
    } else if (publication.stopped) {
      moneyTone = "amber";
      moneyMain = "Gestoppt";
      moneyDetail = "Instagram entfernt · TikTok gestoppt · Ersatz im Content-Chat; Owner GO fehlt.";
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
            healthTone(h) === "red" ? 0 : healthTone(h) === "amber" ? 1 : healthTone(h) === "blue" ? 2 : 3;
          return a.name === "Jarvis free loop"
            ? -1
            : b.name === "Jarvis free loop"
              ? 1
              : score(a) - score(b);
        })
        .slice(0, 8);
      for (const h of ranked) {
        const tone = healthTone(h);
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
          left.append(node("small", "Zuletzt erfolgreich geprüft: " + stamp(h.last_success_at) + " · " + age(h.last_success_at)));
        if (h.name === "Production Smoke" && h.test_passed) left.append(node("small", "LETZTER TEST BESTANDEN · " + value(h.passed) + " / " + value(h.total)));
        left.append(node("small", h.evidence_note || "Nachweisstatus prüfen."));
        row.append(left, badge(h.display_status || sourceHealthLabel(h.health)));
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
        summary.append(node("strong", h.name), badge(h.display_status || sourceHealthLabel(h.health)));
        item.append(summary);
        if (h.last_success_at)
          line(item, "Zuletzt erfolgreich geprüft", stamp(h.last_success_at));
        line(item, "Einordnung", h.evidence_note || "Nicht dokumentiert");
        for (const o of h.observers || []) {
          line(item, o.observer_id, sourceHealthLabel((o.observer_state || o.health).toUpperCase()));
          line(item, "Letzte erfolgreiche Beobachtung", stamp(o.last_success_at));
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
    const duration = current?.duration_seconds;
    const executionDetails = $("execution-detail-list");
    const focusedEvidence = document.activeElement?.matches(
      ".execution-metadata > summary",
    )
      ? document.activeElement.parentElement.parentElement.dataset.executionKey
      : null;
    const sourceStatus = $("execution-source-status");
    sourceStatus.hidden = s.freshness?.operational_complete === true;
    sourceStatus.textContent =
      "Operative Daten unvollständig. Angezeigte Nachweise sind kein vollständiger Live-Überblick.";
    const openEvidence = new Set(
      [...executionDetails.querySelectorAll(".execution-metadata[open]")].map(
        (el) => el.parentElement.dataset.executionKey,
      ),
    );
    executionDetails.replaceChildren();
    const liveWorkers = workers.filter(
      (w) =>
        !w.completed_at &&
        !["completed", "failed_terminal"].includes(w.execution_status),
    );
    liveWorkers.sort(
      (a, b) =>
        (a.status === "ACTIVE" ? 0 : 1) - (b.status === "ACTIVE" ? 0 : 1),
    );
    const operatingMode = liveWorkers.some((w) => w.status === "ACTIVE")
      ? "working"
      : liveWorkers.length
        ? "waiting"
        : s.freshness?.operational_complete === true
          ? "monitoring"
          : "unknown";
    document.body.dataset.executionMode = operatingMode;
    $("work").classList.toggle("has-execution", liveWorkers.length > 0);
    const currentSignals = new Set();
    liveWorkers.slice(0, 3).forEach((w, index) => {
      const key = w.execution_id || w.worker_id || w.task_id || String(index);
      currentSignals.add(key);
      const signal = JSON.stringify([
        w.status,
        w.execution_status,
        w.next_checkpoint,
        w.last_progress_at,
        w.checkpoint?.verified === true ? w.checkpoint : null,
      ]);
      const item = workerEvidence(w, true);
      item.dataset.executionKey = key;
      item.querySelector("details").open = openEvidence.has(key);
      if (
        executionObserved &&
        executionSignals.has(key) &&
        executionSignals.get(key) !== signal
      )
        item.classList.add("evidence-changed");
      else if (executionObserved && !executionSignals.has(key))
        item.classList.add("evidence-changed");
      executionSignals.set(key, signal);
      executionDetails.append(item);
      if (focusedEvidence === key)
        item.querySelector("summary").focus({ preventScroll: true });
    });
    for (const key of executionSignals.keys())
      if (!currentSignals.has(key)) executionSignals.delete(key);
    executionObserved = true;
    if (liveWorkers.length > 3)
      executionDetails.append(
        node(
          "small",
          liveWorkers.length -
            3 +
            " weitere Ausführungen in den technischen Details",
        ),
      );
    if (!liveWorkers.length && s.freshness?.operational_complete === true) {
      const focus = (s.workstreams || [])
        .filter((w) => w.focus_task)
        .sort(
          (a, b) =>
            (a.focus_task.blocker ? 0 : 1) - (b.focus_task.blocker ? 0 : 1),
        );
      const reason =
        focus.find((w) => w.focus_task.blocker) ||
        focus.find((w) => w.focus_task.dependencies?.length);
      if (reason) {
        const wait = node("div", undefined, "standby-reason");
        wait.append(
          node(
            "small",
            (reason.focus_task.blocker
              ? "EIN OFFENER BLOCKER · "
              : "BEOBACHTETE ABHÄNGIGKEIT · ") + reason.name,
          ),
          node("strong", taskWait(reason.focus_task)),
          node(
            "a",
            "Alle Aufgaben und Voraussetzungen ansehen →",
            "detail-link",
          ),
        );
        wait.lastChild.href = "#workstreams";
        executionDetails.append(wait);
      }
    }

    put(
      "execution-context",
      current
        ? [
            duration == null
              ? "Ausführungsdauer nicht dokumentiert"
              : "Seit " + Math.floor(duration / 60) + " Min in Ausführung",
            "Kein belastbarer Prozentfortschritt dokumentiert",
          ].join(" · ")
        : c.status === "WAITING"
          ? c.system_explanation || "Der freie Loop prüft die Queue. Externe Antworten und neue Messsignale können die nächste Arbeit auslösen."
          : "Keine aktive Ausführung verifiziert. Systemstatus und Quellen prüfen.",
    );
    put(
      "next-wake",
      "Nächster Loop · " + stamp(c.next_loop_estimate) + " (Schätzung)",
    );
    const streams = $("workstream-list");
    const streamSignature = JSON.stringify(s.workstreams || []);
    if (streams.dataset.signature !== streamSignature) {
      const openSources = new Set(
        [...streams.querySelectorAll(".task-source[open]")].map(
          (el) => el.parentElement.dataset.taskId,
        ),
      );
      const focused = document.activeElement;
      const focusedTask = focused?.closest(".dependency-task")?.dataset.taskId;
      const focusedStream = focused?.closest(".workstream-details")?.dataset
        .stream;
      const expanded = new Set(
        [...streams.querySelectorAll("details[open]")].map(
          (el) => el.dataset.stream,
        ),
      );
      streams.replaceChildren();
      for (const w of s.workstreams || []) {
        const card = node("article", undefined, "workstream-card");
        card.dataset.state = w.status;
        const focus = w.focus_task || w.next_task;
        card.append(node("h3", w.name), badge(w.status));
        const working = w.status === "WORKING";
        const main = working
          ? taskTitle(focus)
          : focus
            ? taskWait(focus)
            : w.evidence_note ||
              (w.status === "MONITORING"
                ? "Überwacht Queue, Quellenfrische und neue externe Signale."
                : "Keine offene Aufgabe aus dieser Quelle.");
                card.append(node("p", focus ? taskTitle(focus) : main, "workstream-purpose"));
        if (focus) {
          line(card, "Warum", taskWait(focus));
          line(card, "Nächster Schritt", focus.explanation?.next_step || detailText(focus.next_checkpoint));
          line(card, "Owner", focus.explanation?.owner_action || "Freigabestatus unter Entscheidungen prüfen.");
        }
        const details = node("details", undefined, "workstream-details");
        details.dataset.stream = w.name;
        details.open = expanded.has(w.name);
        details.append(
          node(
            "summary",
            w.tasks ? w.tasks + " Aufgaben · Details" : "Nachweise ansehen",
          ),
        );
        const grid = node("div", undefined, "task-evidence-grid");
        for (const worker of w.active_workers || [])
          grid.append(workerEvidence(worker));
        for (const task of w.tasks_preview || (focus ? [focus] : [])) {
          const detail = taskDetail(task);
          detail.querySelector(".task-source").open = openSources.has(
            task.task_id,
          );
          grid.append(detail);
        }
        if (!grid.children.length) {
          grid.append(
            node(
              "p",
              w.evidence_note ||
                (w.status === "MONITORING"
                  ? "Der freie Loop ist aktiv. Kein Worker wird als arbeitend dargestellt, solange keine aktive Ausführung verifiziert ist."
                  : "Kein konkreter Task zugeordnet."),
              "muted",
            ),
          );
        }
        if (w.tasks_preview_complete === false)
          grid.append(
            node(
              "p",
              "Aufgabenliste begrenzt oder Quelle unvollständig. Fehlende Aufgaben werden nicht als null gewertet.",
              "muted",
            ),
          );
        details.append(grid);
        card.append(details);
        streams.append(card);
      }
      streams.dataset.signature = streamSignature;
      if (focused?.tagName === "SUMMARY") {
        const candidates = [...streams.querySelectorAll("summary")];
        const replacement = candidates.find((el) =>
          focusedTask
            ? el.closest(".dependency-task")?.dataset.taskId === focusedTask
            : focusedStream &&
              el.parentElement.dataset.stream === focusedStream,
        );
        replacement?.focus({ preventScroll: true });
      }
    }
    const next = $("next-task-list");
    next.replaceChildren();
    (s.next_tasks || []).forEach((t, i) => {
      const item = node("article", undefined, "next-task");
      item.append(
        node("span", String(i + 1).padStart(2, "0"), "task-index"),
        node("p", taskTitle(t)),
      );
      next.append(item);
    });
    if (!next.children.length)
      next.append(
        node(
          "p",
          c.status === "ERROR"
            ? "Nächste Arbeit derzeit nicht verlässlich bestimmbar."
            : "Keine Ready-Aufgabe beobachtet. Nächste Auswahl beim Supervisor-Wake.",
          "muted",
        ),
      );
    else
      next.append(
        node(
          "small",
          "Nach Task-Priorität · Handler-Freigabe erfolgt erst im Loop",
        ),
      );
    const trigger = $("next-observed-trigger");
    trigger.replaceChildren();
    if (!(s.next_tasks || []).length) {
      const planned = (s.first_money?.posts || [])
        .filter(
          (p) =>
            ["PENDING", "SCHEDULED"].includes(String(p.state).toUpperCase()) &&
            Date.parse(p.scheduled_at) > Date.now(),
        )
        .sort(
          (a, b) => Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at),
        )[0];
      if (planned) {
        trigger.append(
          node("small", "NÄCHSTER BEOBACHTETER TERMIN"),
          node(
            "strong",
            String(planned.platform).toUpperCase() +
              " · " +
              stamp(planned.scheduled_at),
          ),
          node(
            "p",
            s.first_money.publication_stale
              ? "Letzter Veröffentlichungsplan; Nachweis veraltet. Keine Worker-Zuweisung."
              : "Geplanter Veröffentlichungszeitpunkt. Keine Worker-Zuweisung.",
          ),
        );
      }
    }
    const waiting = s.waiting || {};
    const counts = $("waiting-counts");
    counts.replaceChildren();
    for (const [key, label] of [
      ["owner", "Deine Entscheidung"],
      ["external", "Externer Trigger"],
      ["technical", "Technischer Blocker"],
      ["budget", "Budget"],
    ]) {
      const cell = node(
        "div",
        undefined,
        "waiting-row" +
          (key === "owner" && waiting[key] > 0 ? " owner-required" : ""),
      );
      cell.append(node("span", label), node("strong", waiting[key]));
      counts.append(cell);
    }
    const list = $("waiting-list");
    list.replaceChildren();
    for (const t of waiting.rows || []) list.append(taskDetail(t));
    const safety = s.runtime_safety || {};
    const n = numeric(safety.today_new_cost_usd);
    put("cost-total", n == null ? "UNKNOWN" : "$" + n.toFixed(4));
    put(
      "cost-basis",
      "Abgerechnete Provider-Kosten heute. Ungeklärte Kosten bleiben separat sichtbar.",
    );
    const cost = $("cost-context");
    cost.replaceChildren();
    line(cost, "Offene Reservations", safety.open_reservations);
    line(
      cost,
      "Ungeklärte Provider-Kosten",
      safety.provider_cost_unknown == null
        ? "UNKNOWN"
        : safety.provider_cost_unknown
          ? "Ja · prüfen"
          : "Keine",
    );
    line(
      cost,
      "Budgetfenster",
      s.budget?.status || "Kein bestätigtes Budgetfenster",
    );
  }
  function clock() {
    put(
      "clock",
      new Date().toLocaleString("de-DE", {
        weekday: "short",
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Europe/Berlin",
      }),
    );
  }
  clock();
  setInterval(clock, 30000);

  async function refresh() {
    clearTimeout(timer);
    if (busy || document.hidden) return;
    busy = true;
    const refreshButton = $("refresh");
    if (refreshButton) refreshButton.disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch("/internal/jarvis/snapshot", {
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403) {
        location.assign("/internal/login");
        return;
      }
      if (!response.ok) throw new Error("Unavailable");
      const s = await response.json();
      if (
        s.version !== 1 ||
        s.read_only !== true ||
        !s.command_center ||
        !s.freshness ||
        !s.mission_board ||
        !Array.isArray(s.worker_deck) ||
        !Array.isArray(s.system_health)
      )
        throw new Error("Invalid snapshot");
      render(s);
    } catch {
      const connection = $("connection-alert");
      if (connection) {
        connection.hidden = false;
        connection.textContent = snapshot
          ? "LIVE READ UNAVAILABLE · Letzte Beobachtung bleibt sichtbar, ist aber nicht mehr als aktuell bestätigt."
          : "LIVE READ UNAVAILABLE · Kein Systemzustand bestätigt. Erneute Prüfung folgt.";
      }
      put("sync-label", "Verbindung unterbrochen");
      setTone("global-risk", "amber");
      put("risk-title", "LIVE-LAGE NICHT BESTÄTIGT");
      put("risk-summary", "Verbindung unterbrochen. Letzte Nachweise sind keine aktuelle Entwarnung.");
      put("risk-owner-action", "Owner-Bedarf aktuell nicht bestätigt.");
      put("risk-level", "UNBESTÄTIGT");
      if ($("risk-level")) $("risk-level").className = "pill warn";
      if ($("risk-panel")) $("risk-panel").replaceChildren();
      if ($("crew-grid")) {
        $("crew-grid").querySelectorAll(".crew-node").forEach(card => {
          card.dataset.active = "false";
          card.dataset.state = "DEGRADED";
          card.className = "crew-node state-amber";
          const state = card.querySelector(".pill");
          if (state) { state.textContent = "LETZTER STAND"; state.className = "pill warn"; }
          card.querySelectorAll(".crew-live-path").forEach(el => el.remove());
        });
      }
      put("crew-supervisor-state", "Verbindung unterbrochen · kein aktueller Ausführungsnachweis.");
      put("crew-count", "Letzter Rollenstand · aktive Ausführungen unbestätigt");
      setPulse(
        "pulse-jarvis",
        "amber",
        "Verbindung prüfen",
        "Live-Daten konnten nicht geladen werden.",
      );
      setPulse(
        "pulse-action",
        "amber",
        "Unklar",
        "Freigabestatus kann aktuell nicht bestätigt werden.",
      );
      setPulse(
        "pulse-money",
        "amber",
        "Unklar",
        "Publication-State kann aktuell nicht bestätigt werden.",
      );
      setPulse(
        "pulse-cost",
        "amber",
        "Unklar",
        "Kostenstatus kann aktuell nicht bestätigt werden.",
      );
      setTone("jarvis-core", "amber");
      document.body.dataset.executionMode = "unknown";
      $("jarvis-core").dataset.mode = "unknown";
      const sourceStatus = $("execution-source-status");
      sourceStatus.hidden = false;
      sourceStatus.textContent =
        "Verbindung unterbrochen. Angezeigte Arbeit ist der letzte bekannte Stand, nicht aktuell bestätigt.";
      document
        .querySelectorAll(".execution-evidence .execution-state")
        .forEach((el) => {
          el.textContent =
            "Zuletzt · " + el.textContent.replace(/^Zuletzt · /, "");
        });
      const approval = $("approval-alert");
      if (approval) approval.hidden = true;
      const jarvisState = $("jarvis-state");
      if (jarvisState)
        jarvisState.replaceWith(
          Object.assign(badge("ERROR"), { id: "jarvis-state" }),
        );
    } finally {
      clearTimeout(timeout);
      busy = false;
      if (refreshButton) refreshButton.disabled = false;
      timer = setTimeout(refresh, 10000);
    }
  }

  $("refresh")?.addEventListener("click", refresh);
  $("toggle-details")?.addEventListener("click", () => {
    const open = document.body.classList.toggle("show-advanced");
    $("toggle-details").setAttribute("aria-expanded", String(open));
    $("toggle-details").textContent = open
      ? "Technische Details ausblenden"
      : "Technische Details anzeigen";
  });
  $("domain-filter")?.addEventListener("change", missions);
  $("show-done")?.addEventListener("change", missions);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh();
    else clearTimeout(timer);
  });
  $("logout")?.addEventListener("click", async () => {
    const button = $("logout");
    button.disabled = true;
    try {
      const response = await fetch("/internal/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRF-Token": document.querySelector('meta[name="owner-csrf"]')
            .content,
        },
      });
      if (response.ok || response.status === 503 || response.status === 401) {
        location.assign("/internal/login");
      } else {
        throw new Error("Logout failed");
      }
    } catch {
      const connection = $("connection-alert");
      if (connection) {
        connection.hidden = false;
        connection.textContent =
          "Abmelden nicht bestätigt. Bitte erneut versuchen.";
      }
      button.disabled = false;
    }
  });
  document.querySelectorAll("nav a").forEach((a) =>
    a.addEventListener("click", () => {
      document
        .querySelectorAll("nav a")
        .forEach((n) => n.classList.remove("selected"));
      a.classList.add("selected");
    }),
  );

  refresh();
})();
