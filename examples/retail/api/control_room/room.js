'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const value = v => v === null || v === undefined || v === '' ? 'Unknown' : String(v);
  const stamp = v => v && Number.isFinite(Date.parse(v)) ? new Date(v).toLocaleString('de-DE', {timeZone:'Europe/Berlin'}) : 'Unknown';
  const put = (id, v) => { $(id).textContent = value(v); };
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = value(text); if (cls) n.className = cls; return n; };
  const badge = status => node('span', status, 'pill ' + ({WORKING:'good','OWNER GATE':'warn',ERROR:'bad',ACTIVE:'good',HEALTHY:'good',READY:'good',OFF:'good',BLOCKED:'bad',FAILED:'bad',DEGRADED:'warn',STALE:'warn','WAITING HUMAN':'warn',WAITING:'warn'}[status] || 'neutral'));
  const line = (parent, label, text) => { const p = node('p'); p.append(node('small', label + ' · '), node('span', text)); parent.append(p); };
  let snapshot = null, busy = false, timer = null;
  const decisionPanel = document.querySelector('.decision-panel');
  if (decisionPanel && $('command')) $('command').after(decisionPanel);
  function missions() {
    if (!snapshot) return;
    const board = $('mission-board'); board.replaceChildren();
    const domain = $('domain-filter').value;
    for (const [lane, rows] of Object.entries(snapshot.mission_board)) {
      if (lane === 'DONE' && !$('show-done').checked) continue;
      const filtered = rows.filter(r => !domain || r.domain === domain);
      const column = node('div', undefined, 'mission-lane');
      column.tabIndex = 0; column.setAttribute('aria-label', lane + ' Missions');
      column.append(node('h3', lane + ' · ' + filtered.length));
      for (const m of (lane === 'DONE' ? filtered.slice(0, 12) : filtered)) {
        const card = node('article', undefined, 'mission-card');
        card.append(node('small', value(m.domain) + ' · P' + value(m.priority)), node('h4', m.title));
        line(card, 'Owner', m.owner);
        if (m.blocker) line(card, 'Blocker', m.blocker);
        if (m.next_checkpoint) line(card, 'Next checkpoint', m.next_checkpoint);
        if (m.human_gate) card.append(badge('WAITING HUMAN'));
        column.append(card);
      }
      if (!filtered.length) column.append(node('p', 'Keine beobachteten Tasks', 'muted'));
      board.append(column);
    }
  }
  function workerCard(w) {
    const card = node('article', undefined, 'worker-card' + (w.status === 'ACTIVE' ? ' active' : ''));
    const top = node('div', undefined, 'worker-top'); top.append(node('span', '⌘', 'station-icon'), badge(w.status)); card.append(top);
    card.append(node('small', w.worker_type || 'Worker'), node('h3', w.worker_id || w.execution_id), node('p', w.task_title || w.task_id));
    line(card, 'Execution', w.execution_status);
    line(card, 'Heartbeat', stamp(w.heartbeat_at));
    line(card, 'Lease', stamp(w.lease_expires_at));
    line(card, 'Handler', w.handler_id);
    if (w.next_checkpoint) line(card, 'Checkpoint', w.next_checkpoint);
    return card;
  }
  function render(s) {
    snapshot = s;
    const c = s.command_center, f = s.freshness;
    const complete = f.operational_complete === true;
    const gates = Array.isArray(s.decision_center) ? s.decision_center : [];
    const gateCount = Number(c.human_approval_count || gates.length || 0);
    const needsApproval = gateCount > 0 || c.status === 'OWNER GATE';
    const ownerBox = document.querySelector('.owner-now');
    if (ownerBox) ownerBox.classList.toggle('needs-approval', needsApproval);
    put('owner-now', needsApproval ? 'Freigabe erforderlich' : (complete ? 'Keine Aktion erforderlich' : 'Status wird geprüft'));
    put('owner-detail', needsApproval ? (gates[0]?.title || 'Eine Owner-Entscheidung wartet. Öffne Freigaben für Details.') : (c.owner_action || 'Jarvis benötigt aktuell keine Entscheidung von dir.'));
    const approval = $('approval-alert');
    approval.hidden = !needsApproval;
    if (needsApproval) {
      put('approval-summary', gates.length === 1 ? gates[0].title : (gateCount + ' Freigaben warten auf dich'));
      put('approval-detail', gates[0]?.reason || 'Öffne Freigaben für Grund, Risiko, Kosten, Nutzen und den exakten GO-Token.');
    }
    put('current-task', c.current_task || 'Keine aktive Ausführung beobachtet');
    put('allowed-task', c.next_allowed_task);
    put('stop-reason', c.stop_reason);
    put('lease-count', s.runtime_safety?.active_leases);
    put('loop-time', 'Loop · ' + stamp(c.last_loop_at) + ' · nächster Wake (Schätzung) ' + stamp(c.next_loop_estimate));
    put('priority', c.current_task || (c.status === 'WAITING' ? 'Jarvis wartet auf zulässige Arbeit oder externe Nachweise.' : 'Aktueller Status aus dem letzten verifizierten Loop.'));
    $('jarvis-state').replaceWith(Object.assign(badge(c.status), {id:'jarvis-state'}));
    put('head', c.observed_head_sha ? c.observed_head_sha.slice(0, 10) : null);
    put('head-age', 'Branch-Beobachtung · ' + stamp(c.head_observed_at));
    put('active-workers', (complete ? '' : '≥ ') + c.active_workers);
    put('working-count', (complete ? '' : '≥ ') + c.working_tasks);
    put('decision-count', (complete ? '' : '≥ ') + c.human_approval_count);
    put('decision-nav', c.human_approval_count);
    put('worker-summary', c.active_workers ? 'Aktive Ausführungen beobachtet' : 'Keine aktiven Worker beobachtet');
    put('wake-time', c.last_supervisor_wake ? new Date(c.last_supervisor_wake).toLocaleTimeString('de-DE') : null);
    put('next-wake', 'Wake-Schätzung · ' + stamp(c.next_supervisor_wake_estimate));
    put('last-action', c.last_completed_action);
    put('next-action', (c.checkpoint_stale ? 'STALE PLAN · ' : '') + value(c.next_safe_action));
    put('checkpoint-age', (c.checkpoint_stale ? 'STALE · ' : '') + 'Checkpoint · ' + stamp(c.checkpoint_observed_at));
    const decisions = $('decision-list'); decisions.replaceChildren();
    for (const d of gates) {
      const n = node('article', undefined, 'decision-item'); n.append(badge('WAITING HUMAN'), node('h3', d.title)); line(n, 'Gate', d.type); line(n, 'Grund', d.reason); line(n, 'Risiko', d.risk); line(n, 'Kosten USD', d.cost_usd); line(n, 'Nutzen', d.benefit); line(n, 'Exakter GO-Token', d.go_token); if (d.provider) line(n, 'Provider', d.provider); decisions.append(n);
    }
    if (!gates.length) decisions.append(node('p', complete ? 'Keine Freigabe erforderlich. Du musst aktuell nichts entscheiden.' : 'Freigabestatus derzeit nicht vollständig prüfbar.', 'muted'));
    for (const key of ['cap','spend','remaining']) { const v = s.budget[{cap:'cap_usd',spend:'spent_usd',remaining:'remaining_usd'}[key]]; put('budget-' + key, v === null || v === undefined ? null : '$' + Number(v).toFixed(2)); }
    $('paid-state').replaceWith(Object.assign(badge(s.budget.paid_model_execution), {id:'paid-state'}));
    put('budget-details', 'Paid execution beobachtet · ' + stamp(s.budget.paid_model_execution_observed_at) + ' · Runs ' + value(s.budget.runs) + '/' + value(s.budget.max_runs) + ' · Budgetstatus ' + value(s.budget.status));
    const deck = $('worker-deck'); deck.replaceChildren();
    const current = s.worker_deck.filter(w => !['completed','failed_terminal'].includes(w.execution_status) && !w.completed_at);
    for (const w of current) deck.append(workerCard(w));
    if (!current.length) { const empty = node('div', undefined, 'empty-station'); empty.append(node('span', '⌘', 'station-icon'), node('p', complete ? 'Keine laufenden Worker-Ausführungen. Jarvis wartet auf ausführbare Arbeit.' : 'Keine laufenden Ausführungen in der unvollständigen Beobachtung.')); deck.append(empty); }
    const history = s.worker_deck.filter(w => !current.includes(w));
    if (history.length) { const details = node('details', undefined, 'worker-history'); details.append(node('summary', 'Letzte abgeschlossene Ausführungen · ' + history.length)); const grid = node('div', undefined, 'worker-grid'); history.forEach(w => grid.append(workerCard(w))); details.append(grid); deck.append(details); }
    put('worker-count', current.length + ' laufende Ausführungen · ' + history.length + ' recent history');
    const select = $('domain-filter'), selected = select.value;
    const domains = [...new Set(Object.values(s.mission_board).flat().map(r => r.domain).filter(Boolean))].sort();
    select.replaceChildren(new Option('All domains', '')); domains.forEach(d => select.add(new Option(d, d))); select.value = selected;
    put('completeness', complete ? 'Operative Quellen vollständig innerhalb der Read-Grenzen. History begrenzt; Snapshot nicht atomar.' : 'Unvollständige Quellen: ' + f.incomplete_sources.join(', ') + '. Zähler sind beobachtete Untergrenzen.');
    missions();
    const revenue = s.first_money || {}, products = s.money_products || {}, safety = s.runtime_safety || {};
    const publications = $('publication-list'); publications.replaceChildren();
    for (const p of revenue.posts || []) line(publications, p.platform, stamp(p.scheduled_at) + ' · ' + value(p.state));
    line(publications, 'Publication-Nachweis', (revenue.publication_stale ? 'STALE · ' : '') + stamp(revenue.publication_observed_at) + ' · gespeicherte Plattform-Beobachtung');
    put('content-identifiers', 'content_id: ' + value(revenue.content_id) + ' · experiment_id: ' + value(revenue.experiment_id));
    const funnel = $('funnel'); funnel.replaceChildren();
    for (const [label,key] of [['Sessions','sessions'],['Product Views','product_views'],['Offer Views','offer_views'],['Merchant Clickouts','merchant_clickouts'],['Transactions','transactions'],['Commission EUR','commission_eur']]) {
      const cell = node('div'); cell.append(node('small', label), node('strong', (key !== 'transactions' && key !== 'commission_eur' && !revenue.analytics_complete ? '≥ ' : '') + value(revenue[key]))); funnel.append(cell);
    }
    put('funnel-basis', 'Beobachtete Events inkl. möglicher technischer Tests. Nur diese content_id / 1 Million. ' + (revenue.analytics_complete ? '' : 'Begrenzte Daten: Untergrenzen. ') + 'Transactions und Commission: Unknown bis Affiliate-Netzwerk-Nachweis. Clickouts sind keine Verkäufe.');
    const productList = $('money-products'); productList.replaceChildren();
    for (const p of products.rows || []) { const cell = node('div'); cell.append(node('h4', p.product), node('p', p.state)); productList.append(cell); }
    put('product-evidence', (products.stale ? 'STALE · ' : '') + 'Business-Checkpoint · ' + stamp(products.observed_at));
    const queue = $('queue-counts'); queue.replaceChildren();
    for (const key of ['done','active','waiting_external','blocked','cancelled']) { const cell = node('div'); cell.append(node('small', key), node('strong', s.queue?.[key])); queue.append(cell); }
    put('queue-time', 'Loop-Beobachtung · ' + stamp(s.queue?.observed_at));
    put('runtime-safety', 'Neue Jarvis-Kosten heute: ' + (safety.today_new_cost_usd === null || safety.today_new_cost_usd === undefined ? 'Unknown' : '$' + Number(safety.today_new_cost_usd).toFixed(4)) + ' · Stale leases: ' + value(safety.stale_leases) + ' · Open reservations: ' + value(safety.open_reservations) + ' · provider_cost_unknown: ' + value(safety.provider_cost_unknown) + ' · Tag: Europe/Berlin; offene/unklare Kosten bleiben Unknown.');
    const activity = $('activity-list'); activity.replaceChildren();
    for (const e of s.worker_deck.filter(w => w.completed_at && w.checkpoint?.verified === true).slice(0, 8)) { const n = node('article', undefined, 'activity-item'); n.append(node('time', stamp(e.completed_at)), node('strong', e.task_title || e.task_id)); line(n, 'Verified checkpoint', e.checkpoint.step); activity.append(n); }
    if (!s.live_activity.length) activity.append(node('p', 'Keine Events in der Beobachtung.', 'muted'));
    const systems = $('system-list'); systems.replaceChildren();
    for (const h of s.system_health) {
      const n = node('details', undefined, 'system-row'); const summary = node('summary'); summary.append(node('strong', h.name), badge(h.health)); n.append(summary);
      if (h.last_success_at) line(n, 'Last success', stamp(h.last_success_at));
      for (const o of h.observers || []) { line(n, o.observer_id, o.health); line(n, 'Last success', stamp(o.last_success_at)); line(n, 'Next retry', stamp(o.next_retry_at)); }
      for (const cr of h.credentials || []) { line(n, 'Credential status', cr.effective_status); line(n, 'Expires', stamp(cr.expires_at)); if (cr.owner_reauthorization_required) line(n, 'Owner action', 'Reauthorization required'); }
      systems.append(n);
    }
    put('map-state', c.status); put('map-workers', current.length + ' laufende Ausführungen');
    const tools = $('map-tools'); tools.replaceChildren();
    for (const name of s.system_map.systems) { const n = node('span'); n.append(node('strong', name), node('small', name === 'Supabase' ? 'Read-Layer erreichbar' : s.system_health.find(h => h.name === name)?.health || 'UNKNOWN')); tools.append(n); }
    put('snapshot-time', 'Snapshot · ' + stamp(s.generated_at));
    put('sync-label', 'Live read · ' + new Date().toLocaleTimeString('de-DE'));
    const alert = $('connection-alert'); alert.hidden = complete; alert.textContent = 'Live-Abfrage erfolgreich; operative Daten unvollständig. Details unter Mission board.';
  }
  async function refresh() {
    clearTimeout(timer);
    if (busy || document.hidden) return;
    busy = true; $('refresh').disabled = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const r = await fetch('/internal/jarvis/snapshot', {credentials:'same-origin', cache:'no-store', signal:controller.signal});
      if (r.status === 401 || r.status === 403) { location.assign('/internal/login'); return; }
      if (!r.ok) throw new Error('Unavailable');
      const s = await r.json();
      if (s.version !== 1 || s.read_only !== true || !s.command_center || !s.freshness || !s.mission_board || !Array.isArray(s.worker_deck) || !Array.isArray(s.system_health)) throw new Error('Invalid snapshot');
      render(s);
    } catch {
      $('connection-alert').hidden = false;
      put('connection-alert', snapshot ? 'LIVE READ UNAVAILABLE · Letzte Beobachtung bleibt sichtbar und ist nicht mehr als aktuell bestätigt.' : 'LIVE READ UNAVAILABLE · Kein Systemzustand bestätigt. Erneute Prüfung folgt.');
      put('sync-label', 'Verbindung unterbrochen');
      put('owner-now', 'Status derzeit nicht verfügbar');
      put('owner-detail', 'Live-Daten konnten nicht geladen werden. Bitte erneut prüfen.');
      $('approval-alert').hidden = true;
      $('jarvis-state').replaceWith(Object.assign(badge('ERROR'), {id:'jarvis-state'}));
    } finally { clearTimeout(timeout); busy = false; $('refresh').disabled = false; timer = setTimeout(refresh, 10000); }
  }
  $('refresh').addEventListener('click', refresh);
  $('toggle-details').addEventListener('click', () => {
    const open = document.body.classList.toggle('show-advanced');
    $('toggle-details').setAttribute('aria-expanded', String(open));
    $('toggle-details').textContent = open ? 'Technische Details ausblenden' : 'Technische Details anzeigen';
  });
  $('domain-filter').addEventListener('change', missions);
  $('show-done').addEventListener('change', missions);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); else clearTimeout(timer); });
  $('logout').addEventListener('click', async () => {
    $('logout').disabled = true;
    try { const r = await fetch('/internal/logout', {method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':document.querySelector('meta[name="owner-csrf"]').content}}); if (r.ok || r.status === 503 || r.status === 401) location.assign('/internal/login'); else throw new Error(); }
    catch { put('connection-alert', 'Abmelden nicht bestätigt. Bitte erneut versuchen.'); $('connection-alert').hidden = false; $('logout').disabled = false; }
  });
  document.querySelectorAll('nav a').forEach(a => a.addEventListener('click', () => { document.querySelectorAll('nav a').forEach(n => n.classList.remove('selected')); a.classList.add('selected'); }));
  refresh();
})();