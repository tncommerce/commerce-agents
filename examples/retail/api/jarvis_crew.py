"""Pure owner projections from the sanitized DTO. Roles never dispatch or imply execution."""

from __future__ import annotations

from .jarvis_clarity import AFFILIATE_TASKS, CONTENT_RIGHTS, ROSTER

CLUSTERS = {
    "BUILD": ("tech", "infrastructure", "qa"),
    "MONEY": ("revenue", "attribution", "affiliate"),
    "GROWTH": ("content", "research", "outreach"),
    "OPERATIONS": ("operations",),
}
HANDLERS = {
    "ci_pr_verifier": "tech",
    "first_money_evidence_audit": "revenue",
    "analytics_funnel_audit": "revenue",
    "content_candidate_preflight": "content",
    "supervisor_state_audit": "qa",
    "purchase_destination_freshness_audit": "affiliate",
    "queue_priority_reconciler": "operations",
}


def task_role(task: dict) -> str | None:
    tid = task.get("task_id") or ""
    if tid in CONTENT_RIGHTS or tid.startswith("notino_original_asset"):
        return "research"
    if tid in AFFILIATE_TASKS:
        return "affiliate"
    return {
        "tech": "tech",
        "platform": "tech",
        "infrastructure": "infrastructure",
        "qa": "qa",
        "research": "research",
        "rights": "research",
        "content": "content",
        "revenue": "revenue",
        "analytics": "revenue",
        "finance": "revenue",
        "attribution": "attribution",
        "cro": "attribution",
        "diagnostics": "attribution",
        "jarvis": "operations",
        "supervisor": "operations",
        "automation": "operations",
        "affiliate": "affiliate",
        "commerce": "affiliate",
        "outreach": "outreach",
        "product": "content",
        "growth": "content",
        "business": "content",
    }.get(task.get("domain"))


def project_crew(snapshot: dict) -> dict:
    complete = snapshot["freshness"]["operational_complete"]
    command = snapshot["command_center"]
    systems = {s["name"]: s for s in snapshot["system_health"]}
    missions = [
        m
        for lane, rows in snapshot["mission_board"].items()
        if lane not in {"DONE", "CANCELLED"}
        for m in rows
    ]
    live = [
        w
        for w in snapshot["worker_deck"]
        if not w.get("completed_at") and w.get("status") != "IDLE"
    ]

    # Prefer documented handler/function over a generic executor's historical display alias.
    def execution_role(worker):
        return HANDLERS.get(worker.get("handler_id")) or worker.get("role_key")

    crew = []
    decisions = snapshot["decision_center"]
    for cluster, keys in CLUSTERS.items():
        for key in keys:
            alias, role = ROSTER[key]
            executions = [w for w in live if execution_role(w) == key]
            tasks = sorted(
                [m for m in missions if task_role(m) == key],
                key=lambda m: (-(m.get("priority") or 0), m.get("task_id") or ""),
            )
            active = [w for w in executions if w["status"] == "ACTIVE"] if complete else []
            linked_gates = [
                g
                for g in decisions
                if (g.get("task_id") and g.get("task_id") in {m["task_id"] for m in tasks})
                or (key == "content" and g.get("content_candidate"))
                or (key == "outreach" and g.get("provider") == "gmail")
            ]
            gates = [m for m in tasks if m.get("human_gate")]
            if linked_gates and not gates:
                gates = [
                    {
                        "title": linked_gates[0].get("title"),
                        "explanation": {
                            "reason": linked_gates[0].get("reason")
                            or "Eine konkrete Owner-Entscheidung ist offen.",
                            "next_step": "Freigabeumfang im Owner Gate prüfen; kein automatisches Publishing.",
                            "owner_action": "Konkrete Freigabe prüfen.",
                        },
                    }
                ]
            blocked = [m for m in tasks if m.get("blocker") or m.get("status") == "blocked"]
            waiting = [m for m in tasks if m.get("status") == "waiting_external"]
            ready = [m for m in tasks if m.get("status") in {"ready", "queued"}]
            monitor = systems.get(
                {
                    "operations": "Jarvis free loop",
                    "qa": "Production Smoke",
                    "infrastructure": "Render",
                    "outreach": "Gmail",
                }.get(key)
            )
            if (
                key == "revenue"
                and snapshot["first_money"]["analytics_provenance"]
                == "launch_attributed_excludes_prelaunch"
            ):
                monitor = {"health": "HEALTHY"}
            degraded = any(w["status"] in {"STALE", "FAILED"} for w in executions)
            if not complete:
                state, focus = "DEGRADED", None
            elif active:
                state, focus = "AKTIV", active[0].get("task_context")
            elif gates:
                state, focus = "OWNER GATE", gates[0]
            elif degraded:
                state, focus = "DEGRADED", executions[0].get("task_context")
            elif blocked:
                state, focus = "BLOCKIERT", blocked[0]
            elif waiting:
                state, focus = "WARTET EXTERN", waiting[0]
            elif executions:
                state, focus = "ÜBERWACHT", executions[0].get("task_context")
            elif (
                monitor
                and not monitor.get("confirmed_failure")
                and monitor.get("health") in {"HEALTHY", "MONITORED"}
            ):
                state, focus = "ÜBERWACHT", ready[0] if ready else None
            elif monitor and (
                monitor.get("confirmed_failure")
                or monitor.get("health") in {"STALE", "DEGRADED", "BLOCKED", "UNKNOWN"}
            ):
                state, focus = "DEGRADED", ready[0] if ready else None
            else:
                state, focus = "BEREIT", ready[0] if ready else None
            explanation = (focus or {}).get("explanation") or {}
            current = active[0] if active else None
            title = (focus or {}).get("title") or (current or {}).get("task_title")
            next_step = explanation.get("next_step") or (
                "Aktuelle Ausführung und nächsten verifizierten Checkpoint prüfen."
                if current
                else "Datenquelle erneut prüfen; keine aktuelle Arbeit bestätigt."
                if state == "DEGRADED"
                else "Belegte Signale und zulässige kostenlose Aufgaben abwarten."
            )
            if current:
                next_step = {
                    "ci_pr_verifier": "Aktuellen HEAD und CI-Nachweis abgleichen.",
                    "analytics_funnel_audit": "Attribuierten Funnel prüfen und nächste Evidence ableiten.",
                    "first_money_evidence_audit": "First-Money-Evidence prüfen und nächsten Messschritt bestimmen.",
                    "supervisor_state_audit": "Runtime-Gesundheit und Ausführungsnachweise read-only prüfen.",
                    "purchase_destination_freshness_audit": "Stock-, Preis- und Affiliate-Nachweise abgleichen.",
                    "content_candidate_preflight": "Creative, Attribution und Freigabereife prüfen.",
                    "queue_priority_reconciler": "Aufgabenpriorität und Abhängigkeiten read-only abgleichen.",
                }.get(
                    current.get("handler_id"),
                    "Nächsten dokumentierten Prüfcheckpoint abgleichen; Original in den Details.",
                )
            crew.append(
                {
                    "role_id": key,
                    "alias": alias,
                    "role": role,
                    "cluster": cluster,
                    "state": state,
                    "tone": "red"
                    if state == "OWNER GATE"
                    else "blue"
                    if state in {"AKTIV", "ÜBERWACHT"}
                    else "green"
                    if state == "BEREIT"
                    else "amber",
                    "task": title,
                    "reason": explanation.get("reason")
                    or (
                        "Reale Ausführung durch Lease und Heartbeat bestätigt."
                        if current
                        else "Datenquelle oder Ausführungsnachweis eingeschränkt."
                        if state == "DEGRADED"
                        else "Keine laufende Ausführung; dauerhafte Rolle im Organisationsmodell."
                    ),
                    "next_step": next_step,
                    "since": (current or {}).get("started_at") or explanation.get("since"),
                    "since_basis": "Ausführungsbeginn"
                    if current
                    else explanation.get("since_basis"),
                    "owner_action": explanation.get("owner_action")
                    or "Keine Aktion von dir erforderlich.",
                    "task_count": len(tasks),
                    "active_count": len(active),
                    "tasks": tasks,
                    "owner_gates": linked_gates,
                    "executions": executions,
                    "connections": (["active"] if active else [])
                    + (["owner"] if gates else [])
                    + (["external"] if waiting else []),
                    "capability_note": "Organisationsrolle; kein Nachweis eines zertifizierten Dispatch-Handlers.",
                }
            )
    return {
        "roles": crew,
        "active_executions": sum(c["active_count"] for c in crew),
        "unassigned_executions": [w for w in live if execution_role(w) not in ROSTER],
        "complete": complete,
        "supervisor_state": command["ceo_status"],
        "observed_at": snapshot["generated_at"],
    }


def project_risk(snapshot: dict) -> dict:
    systems = {s["name"]: s for s in snapshot["system_health"]}
    command, safety = snapshot["command_center"], snapshot["runtime_safety"]
    risks = []
    panels = []

    def panel(key, name, tone, title, reason, next_step, since=None, owner=False):
        row = {
            "id": key,
            "name": name,
            "tone": tone,
            "title": title,
            "reason": reason,
            "next_step": next_step,
            "since": since,
            "since_basis": "Zeit des zugrunde liegenden Nachweises",
            "owner_required": owner,
            "owner_action": "Konkrete Freigabe prüfen."
            if owner
            else "Keine Aktion von dir erforderlich.",
        }
        panels.append(row)
        if tone in {"red", "amber"}:
            risks.append(row)
        return row

    smoke = systems.get("Production Smoke", {})
    production_failed = smoke.get("confirmed_failure") is True
    panel(
        "production",
        "PRODUCTION",
        "red"
        if production_failed
        else "green"
        if smoke.get("health") == "HEALTHY" and smoke.get("test_passed")
        else "amber",
        "Production prüfen"
        if production_failed
        else "Live · Smoke bestanden"
        if smoke.get("test_passed") and smoke.get("health") == "HEALTHY"
        else "Letzter Test bestanden"
        if smoke.get("test_passed")
        else "Production nicht aktuell bestätigt",
        smoke.get("evidence_note") or "Aktueller Production-Nachweis fehlt.",
        "Production-Fehler read-only eingrenzen."
        if production_failed
        else "Beim nächsten relevanten Deployment erneut prüfen.",
        smoke.get("last_success_at"),
    )
    ci, github = systems.get("CI · scentai-mvp", {}), systems.get("GitHub", {})
    ci_failed = ci.get("confirmed_failure") and ci.get("sha") == command.get("observed_head_sha")
    panel(
        "github",
        "GITHUB / CI",
        "red"
        if ci_failed
        else "green"
        if ci.get("health") == "HEALTHY" and github.get("health") in {"HEALTHY", "MONITORED"}
        else "amber",
        "Aktueller HEAD · CI fehlgeschlagen"
        if ci_failed
        else "Aktueller HEAD · CI grün"
        if ci.get("health") == "HEALTHY"
        else "CI-Nachweis prüfen",
        "CI und Branch-Identität werden gemeinsam geprüft; frühere HEADs bestätigen keinen aktuellen Release.",
        "Fehlgeschlagenen Check eingrenzen."
        if ci_failed
        else "Aktuellen HEAD und CI weiter beobachten.",
        ci.get("last_success_at"),
    )
    render = systems.get("Render", {})
    panel(
        "render",
        "RENDER",
        "amber" if render.get("health") not in {"HEALTHY", "MONITORED"} else "green",
        "Nachweis älter"
        if render.get("health") == "STALE"
        else "Verbindung prüfen"
        if render.get("confirmed_failure")
        else "Deployment beobachtet"
        if render.get("health") in {"HEALTHY", "MONITORED"}
        else "Deployment nicht bestätigt",
        render.get("evidence_note") or "Render-Nachweis fehlt; kein Ausfall daraus ableitbar.",
        "Read-only Deploy-Nachweis aktualisieren; Production-Smoke separat bewerten.",
        render.get("last_success_at"),
    )
    leases = safety.get("stale_leases")
    risky_workers = [
        w
        for w in snapshot["worker_deck"]
        if not w.get("completed_at")
        and w.get("status") == "STALE"
        and w.get("execution_status") not in {"completed", "cancelled"}
    ]
    stale_risk = bool(leases and leases > 0) or bool(risky_workers)
    automation_current = all(
        systems.get(n, {}).get("health") == "HEALTHY" for n in ("Supervisor", "Jarvis free loop")
    )
    panel(
        "automation",
        "AUTOMATION",
        "red" if stale_risk else "blue" if automation_current else "amber",
        "Lease-Risiko prüfen"
        if stale_risk
        else "Jarvis überwacht"
        if automation_current
        else "Loop-Nachweis prüfen",
        "Aktive Ausführungen: "
        + str(command["active_workers"])
        + ". Ein freier Loop ist keine laufende Worker-Ausführung.",
        "Verwaiste Ausführung fail-closed abgleichen."
        if stale_risk
        else "Nächsten Loop und eingehende Signale prüfen.",
        command.get("last_loop_at"),
    )
    budget = snapshot["budget"]
    unknown = (
        safety.get("provider_cost_unknown") is True
        or budget.get("provider_cost_unknown") is True
        or budget.get("unknown_provider_cost_task_count", 0) > 0
    )
    reservation_counts = [safety.get("open_reservations"), safety.get("ledger_open_reservations")]
    reservations = max((n for n in reservation_counts if isinstance(n, int)), default=None)
    cost_tone = (
        "red"
        if unknown
        else "amber"
        if reservations is None or reservations > 0 or safety.get("provider_cost_unknown") is None
        else "green"
    )
    panel(
        "cost",
        "COST CONTROL",
        cost_tone,
        "Kosten ungeklärt"
        if unknown
        else "Offene Reservierung prüfen"
        if reservations
        else "Keine unbekannten Kosten"
        if cost_tone == "green"
        else "Kostennachweis fehlt",
        "Unbekannte Kosten werden nie als null dargestellt; offene Reservierungen werden separat geprüft.",
        "Settlements und Kostenledger read-only abgleichen."
        if cost_tone != "green"
        else "Bestehende Kosten-Gates weiter überwachen.",
        command.get("last_loop_at"),
    )
    gmail = systems.get("Gmail", {})
    credentials = gmail.get("credentials", [])
    owner_credential = any(c.get("owner_reauthorization_required") for c in credentials)
    sources_ok = gmail.get("health") in {"HEALTHY", "MONITORED"} and not gmail.get(
        "confirmed_failure"
    )
    panel(
        "sources",
        "SYSTEM SOURCES",
        "red" if owner_credential else "green" if sources_ok else "amber",
        "Gmail eingeschränkt" if not sources_ok else "Antwortkanäle beobachtet",
        "Gmail-Zugang abgelaufen oder Kanalnachweis eingeschränkt; automatische Antwortprüfung nicht bestätigt."
        if not sources_ok
        else "Gmail-Observer zuletzt erfolgreich geprüft.",
        "Owner-Reautorisierung prüfen."
        if owner_credential
        else "Privaten Observer-Zugang read-only prüfen; keine Anfrage erneut senden.",
        gmail.get("last_success_at"),
        owner_credential,
    )
    blocked = snapshot["mission_board"]["BLOCKED"]
    affiliate = [m for m in blocked if m.get("workstream") == "Affiliate"]
    coverage = next(
        (m for m in affiliate if m.get("blocker") == "deterministic_merchant_coverage_required"),
        None,
    )
    panel(
        "affiliate",
        "AFFILIATE",
        "amber" if affiliate else "green",
        "Händlerabdeckung unvollständig"
        if coverage
        else "Kaufziel-Prüfung blockiert"
        if affiliate
        else "Kein Kaufziel-Blocker erkannt",
        (coverage or (affiliate[0] if affiliate else {})).get("explanation", {}).get("reason")
        or "Keine blockierte Affiliate-Aufgabe im aktuellen vollständigen Aufgabenread.",
        (coverage or (affiliate[0] if affiliate else {})).get("explanation", {}).get("next_step")
        or "Kaufziel-Nachweise weiter beobachten.",
        (coverage or {}).get("updated_at"),
    )
    other_blocked = [m for m in blocked if m not in affiliate and not m.get("human_gate")]
    if other_blocked:
        panel(
            "dependencies",
            "VORAUSSETZUNGEN",
            "amber",
            str(len(other_blocked)) + " Aufgaben blockiert",
            other_blocked[0].get("explanation", {}).get("reason")
            or "Konkrete Voraussetzung fehlt.",
            other_blocked[0].get("explanation", {}).get("next_step")
            or "Aufgabenquelle read-only prüfen.",
            other_blocked[0].get("updated_at"),
        )
    money = snapshot["first_money"]
    runtime = money.get("runtime", {})
    tracking = (
        money.get("analytics_provenance") == "launch_attributed_excludes_prelaunch"
        and money.get("analytics_complete") is True
    )
    panel(
        "money",
        "FIRST MONEY",
        "blue" if tracking else "amber",
        "Launch · Monitoring" if tracking else "Tracking-Nachweis prüfen",
        "Launch-Funnel aus attribuierten Signalen. Clickout ist kein Sale; Revenue nur mit Affiliate-Network-Nachweis."
        if tracking
        else "Aktueller, eindeutig attribuierter Runtime-Nachweis fehlt; keine Conversion ableiten.",
        "Auf erstes Signal warten."
        if runtime.get("phase") == "prelaunch"
        else "Nächstes Funnel-Signal und externen Sale-Nachweis beobachten.",
        runtime.get("observed_at"),
    )
    if runtime.get("purchase_decision") in {"blocked", "failed", "no_go", "stop", "expired"}:
        panel(
            "purchase",
            "KAUFZIEL",
            "amber",
            "Kaufziel-Nachweis prüfen",
            "Runtime meldet eine fehlende Kaufziel-Voraussetzung.",
            "Aktuelle Stock-/Preis-/Affiliate-Evidence read-only prüfen.",
            runtime.get("purchase_verified_at"),
        )
    gates = snapshot["decision_center"]
    gate_complete = command.get("gates_complete") is True
    panel(
        "owner",
        "OWNER",
        "red" if gates else "green" if gate_complete else "amber",
        str(len(gates)) + " Entscheidung(en) offen"
        if gates
        else "Keine Freigabe offen"
        if gate_complete
        else "Freigabestatus unklar",
        (gates[0].get("title") or "Konkrete Entscheidung im Freigabebereich prüfen.")
        if gates
        else "Keine aktuelle Owner-Entscheidung erforderlich."
        if gate_complete
        else "Entscheidungsquelle nicht vollständig bestätigt.",
        "Konkrete Entscheidung und Freigabeumfang prüfen; kein automatisches Publishing."
        if gates
        else "Neue Owner Gates weiter beobachten.",
        owner=bool(gates),
    )
    if not snapshot["freshness"]["operational_complete"]:
        panel(
            "evidence",
            "LIVE-DATEN",
            "amber",
            "Nachweise unvollständig",
            "Der bounded Read ist unvollständig; keine vollständige Entwarnung möglich.",
            "Vollständigen Live-Read erneut prüfen.",
        )
    critical = sum(r["tone"] == "red" for r in risks)
    warning = sum(r["tone"] == "amber" for r in risks)
    tone = "red" if critical else "amber" if warning else "green"
    essential_known = (
        snapshot["freshness"]["operational_complete"]
        and bool(smoke.get("test_passed"))
        and automation_current
    )
    return {
        "tone": tone,
        "title": "HANDLUNG ERFORDERLICH"
        if critical
        else "LAGE NICHT VOLLSTÄNDIG BESTÄTIGT"
        if not essential_known
        else "BETRIEB STABIL"
        if warning
        else "ALLES IM GRÜNEN",
        "summary": str(critical) + " kritische Punkte prüfen."
        if critical
        else str(warning) + " Punkte beobachten. Kein kritischer Fehler erkannt."
        if warning
        else "Keine kritischen Risiken erkannt.",
        "owner_required": any(r["owner_required"] for r in panels),
        "owner_action": "Konkrete Freigabe prüfen."
        if any(r["owner_required"] for r in panels)
        else "Keine Aktion von dir erforderlich."
        if gate_complete
        else "Owner-Bedarf nicht vollständig bestätigt.",
        "critical_count": critical,
        "warning_count": warning,
        "risks": risks,
        "panels": panels,
        "observed_at": snapshot["generated_at"],
        "basis": "Sanitized live sources; evidence age is not an outage; roles are not executions.",
    }
