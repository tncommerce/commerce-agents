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


def test_observer_change_dispatch_preserves_existing_broker_event_boundary():
    workflow = workflow_source()
    bridge = workflow.split("  refresh-after-change:")[1].split("  read:")[0]
    assert "github.event_name == 'push'" in bridge
    assert "github.ref == 'refs/heads/scentai-mvp'" in bridge
    assert "--ref scentai-mvp" in bridge
    assert "id-token: write" not in bridge
    read = workflow.split("  read:")[1].split("  ingest:")[0]
    assert "github.event_name == 'workflow_dispatch'" in read
    assert "branches: [scentai-mvp]" in workflow


def test_private_observer_activity_fallback_covers_every_scentai_mvp_push():
    workflow = workflow_source()
    trigger = workflow.split("concurrency:")[0]
    assert "push:\n    branches: [scentai-mvp]" in trigger
    assert "\n    paths:" not in trigger
    bridge = workflow.split("  refresh-after-change:")[1].split("  read:")[0]
    assert "after scentai-mvp changes" in bridge
    assert "--ref scentai-mvp" in bridge


def test_observer_finalize_survives_unrelated_public_merchant_outage() -> None:
    """Never turn a fully accepted Gmail receipt into a false observer failure."""
    workflow = workflow_source()
    finalized = workflow.split("  finalize:")[1].split("  failure-receipt:")[0]
    assert "needs: ack" in finalized
    guarded = "python -m scripts.dufynd_private_observer_finalize"
    diagnostic = "if python -m scripts.dufynd_production_smoke --machine-readable; then"
    assert guarded in finalized
    assert diagnostic in finalized
    assert finalized.index(guarded) < finalized.index(diagnostic)
    assert "smoke_exit=$?" in finalized
    assert "::warning::DUFYND public smoke failed" in finalized
    assert 'echo "::error::' not in finalized
    assert "continue-on-error: true" not in finalized
    # Only commerce smoke is diagnostic here; finalizer remains unweakened.
    from pathlib import Path

    dedicated = Path(".github/workflows/dufynd-production-smoke.yml").read_text(encoding="utf-8")
    assert "python scripts/dufynd_production_smoke.py --expected-indexing enabled" in dedicated
    assert "if python scripts/dufynd_production_smoke.py" in dedicated

def test_private_observer_failure_receipt_has_pinned_python_dependencies() -> None:
    """A failed broker read must not lose the bounded failure receipt to missing Pydantic."""
    workflow = workflow_source()
    failure_receipt = workflow.split("  failure-receipt:", 1)[1]
    read_job = workflow.split("  read:", 1)[1].split("  ingest:", 1)[0]
    ack_job = workflow.split("  ack:", 1)[1].split("  finalize:", 1)[0]
    assert "pip install httpx==0.28.1 pydantic==2.13.4" in failure_receipt
    assert "pip install httpx==0.28.1 pydantic==2.13.4" not in read_job
    assert "pip install httpx==0.28.1 pydantic==2.13.4" not in ack_job
    assert "python -m scripts.dufynd_private_observer_failure" in failure_receipt
    assert "if: failure() && needs.read.result == 'failure'" in failure_receipt
    assert "GMAIL_REFRESH_TOKEN" not in failure_receipt
    assert 'gh run download "$GITHUB_RUN_ID"' in failure_receipt
