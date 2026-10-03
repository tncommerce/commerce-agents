from pathlib import Path


def workflow_source() -> str:
    return Path(".github/workflows/dufynd-private-observer.yml").read_text(encoding="utf-8")


def test_private_observer_workflow_uses_package_module_invocation():
    workflow = workflow_source()
    assert "run: python -m private_broker.observer_read" in workflow
    assert "run: python private_broker/observer_read.py" not in workflow


def test_private_observer_workflow_orders_capture_ack_and_activation():
    workflow = workflow_source()
    assert "needs: read" in workflow
    assert "needs: ingest" in workflow
    assert "needs: ack" in workflow
    assert "python -m scripts.dufynd_private_observer_ingest" in workflow
    assert "python -m private_broker.observer_ack" in workflow
    assert "python -m scripts.dufynd_private_observer_finalize" in workflow
    assert (
        workflow.index("needs: read")
        < workflow.index("needs: ingest")
        < workflow.index("needs: ack")
    )


def test_private_observer_workflow_keeps_provider_keys_out_of_actions():
    workflow = workflow_source()
    forbidden = (
        "RENDER_API_KEY",
        "RENDER_TOKEN",
        "GMAIL_ACCESS_TOKEN",
        "GMAIL_REFRESH_TOKEN",
        "GOOGLE_CLIENT_SECRET",
        "BROKER_OWNER_KEY",
    )
    for fragment in forbidden:
        assert fragment not in workflow
