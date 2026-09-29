from __future__ import annotations

from scripts.sync_dufynd_jarvis_repo_state import sync_repo_state


class FakeBridge:
    def __init__(self) -> None:
        self.synced: dict | None = None

    def sync_repo_control_plane(
        self,
        *,
        repo_status: dict,
        repo_head_sha: str | None = None,
        source_branch: str = "scentai-mvp",
    ) -> None:
        self.synced = {
            "repo_status": repo_status,
            "repo_head_sha": repo_head_sha,
            "source_branch": source_branch,
        }

    def load_context(self) -> dict:
        assert self.synced is not None
        repo_status = self.synced["repo_status"]
        generated_at = repo_status["generated_at"]
        return {
            "master_status": [
                {
                    "key": "jarvis.repo_control_plane",
                    "value": {
                        "source_fingerprint_sha256": repo_status["source_fingerprint_sha256"],
                    },
                    "last_verified_at": generated_at,
                    "updated_at": generated_at,
                }
            ]
        }


def test_sync_repo_state_writes_then_verifies_exact_fingerprint() -> None:
    bridge = FakeBridge()
    repo_status = {
        "generated_at": "2026-09-29T15:47:18+00:00",
        "source_fingerprint_sha256": "fingerprint-123",
        "overall_state": "work_available",
    }

    report = sync_repo_state(
        bridge,
        repo_status,
        repo_head_sha="abc123",
        source_branch="scentai-mvp",
    )

    assert bridge.synced == {
        "repo_status": repo_status,
        "repo_head_sha": "abc123",
        "source_branch": "scentai-mvp",
    }
    assert report["stale"] is False
    assert report["safe_to_use_autonomy_queue"] is True
    assert report["repo_source_fingerprint_sha256"] == "fingerprint-123"
