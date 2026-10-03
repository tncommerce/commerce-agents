from __future__ import annotations

from pathlib import Path
from subprocess import run


SCRIPT = Path("scripts/deploy_dufynd_private_broker.sh")


def test_private_broker_owner_deploy_helper_has_valid_bash_syntax():
    result = run(
        ["bash", "-n", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_private_broker_owner_deploy_helper_preserves_security_boundary():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '[[ "$SHA" =~ ^[a-f0-9]{40}$ ]]' in source
    assert 'git -C "$WORKDIR/repo" checkout --quiet --detach FETCH_HEAD' in source
    assert 'if [[ "$ACTUAL_SHA" != "$SHA" ]]' in source
    assert "gcloud artifacts docker images describe" in source
    assert 'PINNED_IMAGE="${IMAGE_REPO}@${DIGEST}"' in source
    assert '--image="$PINNED_IMAGE"' in source
    assert 'if [[ "$READY_DIGEST" != "$DIGEST" ]]' in source
    assert 'if [[ "$LATEST_TRAFFIC" != "100" ]]' in source

    forbidden = (
        "--set-env-vars",
        "--update-env-vars",
        "--set-secrets",
        "--update-secrets",
        "--allow-unauthenticated",
        "add-iam-policy-binding",
        "set-iam-policy",
        "gcloud secrets versions access",
    )
    for fragment in forbidden:
        assert fragment not in source
