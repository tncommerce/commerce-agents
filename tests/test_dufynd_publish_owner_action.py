import json

import httpx
import pytest

from retail.api.jarvis_owner_actions import OwnerActionConflict, OwnerActionWriter


@pytest.mark.parametrize("platform", ["instagram", "tiktok", "youtube"])
@pytest.mark.parametrize(
    "action,scope,expected",
    [
        ("approve", "schedule_and_publish", True),
        ("approve_review", "schedule_and_publish", False),
        ("approve", "review_only", False),
    ],
)
def test_specific_publish_go_uses_authenticated_writer_but_never_review_action(
    action, scope, expected, platform
):
    patches = []

    def transport(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "content-publish:fixture",
                        "action_type": "content_publish_go",
                        "status": "pending",
                        "decision_token": "GO-PUBLISH-FIXTURE",
                        "context": {
                            "approval_alone_enables_execution": True,
                            "scope": scope,
                            "candidate": {
                                "asset_sha256": "a" * 64,
                                "platform": platform,
                                "title": "Fixture Short",
                                "ai_generated": True,
                                "audio_source": "Fixture track",
                                "audio_rights_evidence_ref": "qa:licence",
                                "caption": "Fixture",
                                "uri": "https://dufynd.de/social/" + "a" * 64 + ".mp4",
                                "requested_at": "2099-01-01T00:00:00Z",
                            },
                        },
                    }
                ],
            )
        patches.append(json.loads(request.read()))
        return httpx.Response(
            200, json=[{"decision_id": "content-publish:fixture", "status": "approved"}]
        )

    writer = OwnerActionWriter(
        secret_key="fixture-secret", transport=httpx.MockTransport(transport)
    )
    if expected:
        assert (
            writer.resolve(
                decision_id="content-publish:fixture",
                action_token="GO-PUBLISH-FIXTURE",
                action=action,
            )["status"]
            == "approved"
        )
        assert patches[0]["decision"]["owner_confirmed"] is True
        assert patches[0]["decision"]["review_only"] is False
    else:
        with pytest.raises(OwnerActionConflict):
            writer.resolve(
                decision_id="content-publish:fixture",
                action_token="GO-PUBLISH-FIXTURE",
                action=action,
            )
        assert not patches
