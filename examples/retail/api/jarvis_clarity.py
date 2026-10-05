"""Deterministic presentation only: no worker creation, dispatch or permissions."""

from __future__ import annotations

from hashlib import sha256

ROSTER = {
    "tech": ("Zoro", "Tech Worker"),
    "revenue": ("Nami", "Revenue / Analytics Worker"),
    "research": ("Robin", "Research / Rights Worker"),
    "infrastructure": ("Franky", "Infrastructure Worker"),
    "content": ("Sanji", "Content Worker"),
    "qa": ("Chopper", "QA / Health Worker"),
    "attribution": ("Law", "Attribution / Diagnostics Worker"),
    "operations": ("Jinbe", "Queue / Operations Worker"),
    "affiliate": ("Brook", "Affiliate / Network Worker"),
    "outreach": ("Usopp", "External Response Worker"),
}

# Verified task purposes; historical executor/domain labels are deliberately not authoritative.
CONTENT_RIGHTS = {
    "tech_model3d_outreach_20260929",
    "tech_widian_3d_contact_form_20260930",
    "jarvis_dior_hypnotic_image_rights_outreach_20261001",
    "repo_current_commerce",
    "release02_brand_image_rights_outreach_20261001",
    "release03_brand_image_rights_outreach_20261001",
    "release04_brand_image_rights_outreach_20261001",
    "release05_brand_image_rights_outreach_20261001",
    "release06_armani_si_image_rights_outreach_20261001",
}
AFFILIATE_TASKS = {
    "perfumetrader_feed_response",
    "perfumetrader_product_coverage",
    "notino_original_asset_rights_path_20261001",
    "notino_original_asset_visual_review_queue_20261001",
    "jarvis_purchase_freshness_watchlist_20261001",
}


def workstream(task: dict) -> str:
    tid = task.get("task_id")
    if tid in CONTENT_RIGHTS:
        return "Content"
    if tid in AFFILIATE_TASKS:
        return "Affiliate"
    return {
        "content": "Content",
        "research": "Content",
        "rights": "Content",
        "tech": "Tech / Workmode",
        "platform": "Tech / Workmode",
        "infrastructure": "Tech / Workmode",
        "qa": "Tech / Workmode",
        "jarvis": "Jarvis",
        "supervisor": "Jarvis",
        "automation": "Jarvis",
        "business": "Business / Growth",
        "growth": "Business / Growth",
        "product": "Business / Growth",
        "revenue": "Business / Growth",
        "analytics": "Business / Growth",
        "finance": "Business / Growth",
        "affiliate": "Affiliate",
        "commerce": "Affiliate",
    }.get(task.get("domain"), "Nicht zugeordnet")


def worker_identity(worker: dict) -> dict:
    identity = worker.get("worker_id") or worker.get("execution_id") or worker.get("task_id")
    if not identity:
        return {
            "display_name": "Identität nicht dokumentiert",
            "role": "Worker",
            "identity_tag": None,
        }
    engine = str(worker.get("worker_id") or worker.get("worker_type") or "").lower()
    family = next((key for key, (name, _) in ROSTER.items() if name.lower() in engine), None)
    if family is None and not worker.get("worker_id"):
        family = {
            "supervisor_state_audit": "qa",
            "purchase_destination_freshness_audit": "affiliate",
            "ci_pr_verifier": "tech",
        }.get(worker.get("handler_id"))
    if family is None:
        family = next(
            (
                key
                for key, words in (
                    ("attribution", ("attribution", "diagnostic", "cro")),
                    ("infrastructure", ("render", "deploy", "infrastructure")),
                    ("research", ("research", "rights", "evidence")),
                    ("revenue", ("revenue", "analytics", "finance")),
                    ("outreach", ("outreach", "response")),
                    ("content", ("content", "creative")),
                    ("affiliate", ("affiliate", "feed", "network")),
                    ("qa", ("qa", "health", "smoke")),
                    ("operations", ("queue", "supervisor", "reconcile")),
                    ("tech", ("tech", "code", "github")),
                )
                if any(word in engine for word in words)
            ),
            None,
        )
    inferred = family is not None
    if family is None:
        # Fixed fallback roster, independent of task titles, row order and refresh time.
        family = tuple(ROSTER)[
            int(sha256(str(identity).encode()).hexdigest()[:8], 16) % len(ROSTER)
        ]
    name, role = ROSTER[family]
    if not inferred:
        role = "Worker · Rolle nicht dokumentiert"
    instance = str(identity) + ":" + str(worker.get("execution_id") or worker.get("task_id") or "")
    return {
        "display_name": name,
        "role": role,
        "role_key": family if inferred else None,
        "identity_tag": sha256(instance.encode()).hexdigest()[:6].upper(),
    }


def task_explanation(task: dict, waits: list[dict], observers: list[dict]) -> dict:
    tid = task.get("task_id")
    status = task.get("status")
    blocker = task.get("blocker")
    observer_ids = {
        w.get("observer_id")
        for w in waits
        if w.get("task_id") == tid and w.get("satisfied") is False
    }
    attached = [
        o for o in observers if o.get("observer_id") in observer_ids and o.get("enabled") is True
    ]
    automatic = bool(attached) and all(
        o.get("health") in {"HEALTHY", "MONITORED"} for o in attached
    )
    reason = "Die genaue Voraussetzung ist noch nicht dokumentiert."
    next_step = "Jarvis muss den fehlenden Nachweis konkret zuordnen."
    resolver = "Jarvis"
    if blocker == "deterministic_merchant_coverage_required":
        reason = "Automatischer Händler-Check kann noch nicht vollständig laufen. Für einen Teil der Kaufziele fehlt verlässlich automatisierbare Händler-/Produktabdeckung."
        resolver = "TECH / Jarvis-Prüfung"
        next_step = (
            "Read-only Händlerabdeckung vervollständigen; danach den Freshness-Check erneut prüfen."
        )
    elif task.get("human_gate"):
        reason = "Eine dokumentierte Owner-Entscheidung ist offen."
        next_step = "Konkrete Entscheidung im Bereich Freigaben prüfen. Ein GO allein führt keine externe Aktion aus."
        resolver = "Owner"
    elif status == "waiting_external":
        resolver = "Extern, danach Jarvis"
        if tid == "jarvis_dior_hypnotic_image_rights_outreach_20261001":
            reason = "Wartet auf Antwort von Dior zu den Bildrechten. Die Anfrage wurde bereits versendet; nicht erneut senden."
            next_step = "Nach der Antwort: Nutzungsrechte und genaue Produktidentität prüfen."
        elif tid in {
            "notino_original_asset_rights_path_20261001",
            "notino_original_asset_visual_review_queue_20261001",
        }:
            reason = "Wartet auf Bestätigung der Publisher-Bildrechte von VIVNetworks / Notino. Bis dahin keine Bildnutzung freigegeben."
            next_step = "Nach der Antwort: Lizenzbedingungen prüfen, danach die betroffenen Assets bewerten."
        elif tid in {"perfumetrader_feed_response", "perfumetrader_product_coverage"}:
            reason = "Wartet auf Produktdaten-/Merchant-Antwort von Perfumetrader. Follow-up bereits gesendet; kein erneuter Outreach ohne Grund."
            next_step = "Nach der Antwort: Datenzugang und genaue Produkt-/Händlerabdeckung read-only prüfen."
        elif tid in CONTENT_RIGHTS:
            reason = "Wartet auf Marken-/Rechteinhaber-Rückmeldung zu Bildern oder 3D-Assets."
            next_step = "Nach Eingang: Rechteumfang und Asset-Identität prüfen; keine automatische Freigabe."
        elif tid == "catalog_release_01_readiness":
            reason = "Wartet auf freigegebene Bilder, aktuelle Kaufziele und eindeutig belegte Produktvarianten."
            next_step = "Fehlende Release-Nachweise zusammenführen und Freigabereife prüfen."
            resolver = "Extern und Jarvis"
        else:
            reason = "Wartet auf eine externe Antwort oder einen externen Nachweis; der genaue Auslöser fehlt in der Aufgabenquelle."
        next_step += " " + (
            "Jarvis beobachtet den zugeordneten Antwortkanal automatisch."
            if automatic
            else "Eine automatische Prüfung dieses konkreten Antwortkanals ist derzeit nicht bestätigt."
        )
    elif blocker:
        reason = "Eine interne Voraussetzung fehlt; der gespeicherte Blocker muss konkret geprüft werden."
        next_step = "Jarvis muss den Blocker read-only prüfen und den Lösungspfad vervollständigen."
    elif status in {"ready", "queued"}:
        reason = "Bereit; wartet auf Auswahl eines zulässigen kostenlosen Handlers."
        next_step = "Beim nächsten Loop Voraussetzungen prüfen und geeignete Arbeit auswählen."
    elif status in {"done", "cancelled"}:
        reason = "Aufgabe ist abgeschlossen oder beendet."
        next_step = "Kein weiterer Arbeitsschritt aus dieser Aufgabe."
    return {
        "reason": reason,
        "next_step": next_step,
        "resolver": resolver,
        "owner_action": "Konkrete Freigabe prüfen."
        if task.get("human_gate")
        else "Keine Aktion von dir erforderlich.",
        "jarvis_can_resolve_alone": False,
        "automatic_monitoring_confirmed": automatic,
        "since": task.get("updated_at"),
        "since_basis": "Letzte Aufgabenaktualisierung; exakter Statusbeginn nicht gespeichert",
    }
