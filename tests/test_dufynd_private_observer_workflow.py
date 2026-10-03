from pathlib import Path


def test_private_observer_workflow_uses_package_module_invocation():
    workflow = Path(".github/workflows/dufynd-private-observer.yml").read_text(encoding="utf-8")
    assert "run: python -m private_broker.observer_read" in workflow
    assert "run: python private_broker/observer_read.py" not in workflow
