"""Static contract for the actionable DUFYND Owner Action Center."""


def room_text(filename):
    with open(
        "examples/retail/api/control_room/" + filename,
        encoding="utf-8",
    ) as handle:
        return handle.read()


def test_owner_action_center_explains_and_executes_only_guarded_actions():
    js = room_text("room.js")
    assert '"Was ist zu tun?"' in js
    assert '"Warum"' in js
    assert '"Nutzen"' in js
    assert '"Risiko"' in js
    assert '"Kosten USD"' in js
    assert '"Aktuell"' in js
    assert '"Soll"' in js
    assert '"Ziel-URL kopieren"' in js
    assert '"Instagram-Profil bearbeiten"' in js
    assert '"Erledigt"' in js
    assert "owner_confirmed_manual_action !== true" in js
    assert '"Jetzt freigeben"' in js
    assert '"Kandidat freigeben"' in js
    assert 'fetch("/internal/jarvis/owner-action"' in js
    assert '"X-CSRF-Token": csrf' in js
    assert "d.approval_alone_enables_execution" in js
    assert "d.manual_action_required" in js


def test_owner_action_center_uses_amber_for_routine_human_gate():
    css = room_text("room.css")
    assert ".owner-action-buttons" in css
    assert ".owner-action.primary" in css
    assert "#f0b65d" in css


def test_crew_uses_business_display_state_instead_of_raw_degraded_label():
    js = room_text("room.js")
    assert "member.display_state || member.state" in js
    assert 'DEGRADED: "Prüfung nötig"' in js
