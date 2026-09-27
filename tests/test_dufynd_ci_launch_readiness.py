"""Keep the DUFYND launch-readiness checker exercised by normal web CI."""

from pathlib import Path

CI = Path(".github/workflows/ci.yml")


def test_web_ci_runs_launch_readiness_smoke_check() -> None:
    source = CI.read_text(encoding="utf-8")

    assert "- name: Exercise DUFYND launch readiness checker" in source
    assert "npm run launch:check --workspace acme-retail-storefront-web" in source


def test_ci_launch_readiness_smoke_stays_non_strict() -> None:
    source = CI.read_text(encoding="utf-8")
    step = source.split(
        "- name: Exercise DUFYND launch readiness checker",
        1,
    )[1].split("\n\n", 1)[0]

    assert "launch:check:strict" not in step
    assert "--strict" not in step
