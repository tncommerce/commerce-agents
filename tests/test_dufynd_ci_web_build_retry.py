"""Keep the DUFYND CI web build resilient without hiding deterministic failures."""

from pathlib import Path

WORKFLOW = Path(".github/workflows/ci.yml")


def test_web_workspace_build_retries_once_after_a_failure() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    web_job = source.split("  web:", 1)[1].split("  dufynd-visual-qa:", 1)[0]
    build_step = web_job.split("      - name: Build every app", 1)[1]

    assert "first_status=$?" in build_step
    assert 'if [ "$first_status" -ne 0 ]; then' in build_step
    assert build_step.count("npm run build") == 2
    assert "retrying once" in build_step
