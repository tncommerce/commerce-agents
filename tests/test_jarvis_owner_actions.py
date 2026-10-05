from __future__ import annotations

import httpx
import pytest

from retail.api.jarvis_owner_actions import (
    OwnerActionConflict,
    OwnerActionWriter,
)


def test_manual_owner_confirmation_closes_owner_action_immediately():
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path, request.url.params))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "first-money:instagram-profile-attribution:20261005",
                        "action_type": "instagram_profile_link_update",
                        "status": "pending",
                        "decision_token": "MANUAL-INSTAGRAM-PROFILE-ATTRIBUTION-20261005",
                        "context": {
                            "manual_action_required": True,
                            "approval_alone_enables_execution": False,
                        },
                        "decision": None,
                    }
                ],
            )
        if request.method == "PATCH":
            body = request.read().decode()
            assert '"owner_confirmed_manual_action":true' in body
            assert '"owner_action_completed":true' in body
            assert '"verification_basis":"owner_confirmation"' in body
            assert '"status":"completed"' in body
            assert '"completed_at":' in body
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "first-money:instagram-profile-attribution:20261005",
                        "status": "completed",
                    }
                ],
            )
        raise AssertionError(request.method)

    writer = OwnerActionWriter(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    result = writer.resolve(
        decision_id="first-money:instagram-profile-attribution:20261005",
        action_token="MANUAL-INSTAGRAM-PROFILE-ATTRIBUTION-20261005",
        action="confirm_manual",
    )
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["verification_required"] is False
    assert [call[0] for call in calls] == ["GET", "PATCH"]


def test_direct_approval_is_allowed_only_when_gate_explicitly_enables_it():
    def transport(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "gate:direct",
                        "action_type": "safe_internal_approval",
                        "status": "pending",
                        "decision_token": "GO-SAFE-DIRECT",
                        "context": {
                            "manual_action_required": False,
                            "approval_alone_enables_execution": True,
                        },
                        "decision": None,
                    }
                ],
            )
        if request.method == "PATCH":
            assert '"status":"approved"' in request.read().decode()
            return httpx.Response(
                200,
                json=[{"decision_id": "gate:direct", "status": "approved"}],
            )
        raise AssertionError(request.method)

    writer = OwnerActionWriter(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    result = writer.resolve(
        decision_id="gate:direct",
        action_token="GO-SAFE-DIRECT",
        action="approve",
    )
    assert result["status"] == "approved"
    assert result["verification_required"] is False


def test_review_only_content_candidate_can_be_approved_without_execution_flag():
    def transport(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "decision_id": "content-review:asset:abc",
                        "action_type": "content_candidate_review",
                        "status": "pending",
                        "decision_token": "GO-CONTENT-REVIEW-ABC",
                        "context": {
                            "manual_action_required": False,
                            "approval_alone_enables_execution": False,
                        },
                        "decision": None,
                    }
                ],
            )
        if request.method == "PATCH":
            body = request.read().decode()
            assert '"status":"approved"' in body
            assert '"review_only":true' in body
            return httpx.Response(
                200,
                json=[{"decision_id": "content-review:asset:abc", "status": "approved"}],
            )
        raise AssertionError(request.method)

    writer = OwnerActionWriter(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    result = writer.resolve(
        decision_id="content-review:asset:abc",
        action_token="GO-CONTENT-REVIEW-ABC",
        action="approve_review",
    )
    assert result["status"] == "approved"
    assert result["verification_required"] is False


def test_owner_action_token_and_gate_mode_fail_closed():
    def transport(request):
        return httpx.Response(
            200,
            json=[
                {
                    "decision_id": "gate:manual",
                    "action_type": "manual",
                    "status": "pending",
                    "decision_token": "MANUAL-EXACT-TOKEN",
                    "context": {
                        "manual_action_required": True,
                        "approval_alone_enables_execution": False,
                    },
                    "decision": None,
                }
            ],
        )

    writer = OwnerActionWriter(
        secret_key="server-secret",
        transport=httpx.MockTransport(transport),
    )
    with pytest.raises(OwnerActionConflict):
        writer.resolve(
            decision_id="gate:manual",
            action_token="MANUAL-WRONG-TOKEN",
            action="confirm_manual",
        )
    with pytest.raises(OwnerActionConflict):
        writer.resolve(
            decision_id="gate:manual",
            action_token="MANUAL-EXACT-TOKEN",
            action="approve",
        )
