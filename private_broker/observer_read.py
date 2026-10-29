"""Fixed OIDC read harness. Deliberately no task inputs, secrets or cursor ack."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from private_broker.observer_contract import (
    ProvenanceError,
    source_from_env,
    validate_render_recovery_evidence,
)

SAFE_REASONS = frozenset(
    {
        "invalid_grant",
        "revoked",
        "missing_configuration",
        "scope_mismatch",
        "account_mismatch",
        "refresh_failed",
        "rate_limited",
        "provider_outage",
        "refresh_race",
        "invalid_response",
        "broker_activation_required",
        "transport_error",
        "pending_redelivery_mismatch",
    }
)

RENDER_PATH = "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments"
HEALTH_PATH = "/v1/health"
RENDER_RECOVERY_FILE = "broker-render-observation.json"
RENDER_SUCCESS_FILE = "broker-render-observations.json"
MAX_ARTIFACT_BYTES = 262_144


class ReadFailure(Exception):
    """Non-secret, bounded diagnostic for a fixed observer stage."""

    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _json(response, stage: str, expected_type=dict):
    if not 200 <= response.status_code < 300:
        reason = f"http_{response.status_code}"
        # Only the broker's fixed error vocabulary may cross this boundary.
        try:
            body = response.json()
            if (
                stage != "oidc_identity"
                and isinstance(body, dict)
                and body.get("error") in SAFE_REASONS
            ):
                reason = body["error"]
        except Exception:
            pass
        raise ReadFailure(stage, reason)
    try:
        result = response.json()
    except Exception:
        raise ReadFailure(stage, "invalid_json") from None
    if not isinstance(result, expected_type):
        raise ReadFailure(stage, "invalid_json")
    return result


def _read(client, origin, path, headers, stage, expected_type=dict):
    try:
        response = client.get(origin + path, headers=headers)
    except httpx.TransportError:
        raise ReadFailure(stage, "transport_error") from None
    return _json(response, stage, expected_type)


def _preserve_failure(exc, source, results, client, origin, headers):
    """Keep the failed run failed, but retain an independent Render read.

    Only already activated Render credentials may later capture this evidence.
    No Gmail data, cursor, acknowledgement or activation proof enters this file.
    One health read after the Gmail failure also projects the actual revoked /
    expired state instead of keeping the last successful credential snapshot.
    """
    Path("broker-failure.json").write_text(
        json.dumps({"_meta": source, "stage": exc.stage, "reason": exc.reason}, sort_keys=True),
        encoding="utf-8",
    )
    if not exc.stage.startswith("gmail_") or RENDER_PATH not in results:
        return
    try:
        health = _read(client, origin, HEALTH_PATH, headers, "health")
        validate_render_recovery_evidence(health, results[RENDER_PATH])
    except Exception:
        # A second failure must not mask the original provider failure or
        # fabricate fresh credential health. The next run can recover Render.
        return
    recovery = {"_meta": source, RENDER_PATH: results[RENDER_PATH], HEALTH_PATH: health}
    encoded = json.dumps(recovery, sort_keys=True)
    if len(encoded.encode("utf-8")) <= 262_144:
        Path(RENDER_RECOVERY_FILE).write_text(encoded, encoding="utf-8")


def main():
    # A failed retry must never publish a previous invocation's success file.
    for filename in (
        "broker-observations.json",
        "broker-failure.json",
        RENDER_RECOVERY_FILE,
        RENDER_SUCCESS_FILE,
    ):
        Path(filename).unlink(missing_ok=True)
    # Inputless scheduled dispatches must never retry a paused Gmail recovery.
    # The established all-provider acceptance path requires an explicit choice.
    mode = os.getenv("DUFYND_OBSERVER_MODE", "render")
    if mode not in {"render", "all"}:
        raise SystemExit("invalid observer mode")
    origin = os.environ["BROKER_ORIGIN"]
    url = urlsplit(origin)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.path
        or url.query
        or url.fragment
        or url.username
    ):
        raise SystemExit("invalid broker origin")

    try:
        source = source_from_env()
        with httpx.Client(trust_env=False, timeout=30, follow_redirects=False) as client:
            identity = client.get(
                os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
                params={"audience": origin},
                headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
            )
            identity_payload = _json(identity, "oidc_identity")
            token = identity_payload.get("value")
            if not isinstance(token, str) or not token:
                raise ReadFailure("oidc_identity", "invalid_response")

            headers = {"Authorization": "Bearer " + token}
            if mode == "render":
                results = {"_meta": source}
                try:
                    results[RENDER_PATH] = _read(
                        client, origin, RENDER_PATH, headers, "render", list
                    )
                    results[HEALTH_PATH] = _read(client, origin, HEALTH_PATH, headers, "health")
                    validate_render_recovery_evidence(results[HEALTH_PATH], results[RENDER_PATH])
                    encoded = json.dumps(results, sort_keys=True)
                    if len(encoded.encode("utf-8")) > MAX_ARTIFACT_BYTES:
                        raise ReadFailure("render", "invalid_response")
                except ProvenanceError:
                    exc = ReadFailure("render", "invalid_response")
                    _preserve_failure(exc, source, results, client, origin, headers)
                    raise exc from None
                except ReadFailure as exc:
                    _preserve_failure(exc, source, results, client, origin, headers)
                    raise
                Path(RENDER_SUCCESS_FILE).write_text(encoded, encoding="utf-8")
                return

            reads = [
                ("render", RENDER_PATH),
                ("gmail_1", "/v1/gmail/threads/1a0f385ed98c6af8/metadata"),
                ("gmail_2", "/v1/gmail/threads/1a0f69c169fb928f/metadata"),
                ("gmail_3", "/v1/gmail/threads/1a0f6a90772a743d/metadata"),
                # Snapshot health last so provider reads/refreshes are reflected
                # in the projection artifact rather than stale pre-read state.
                ("health", HEALTH_PATH),
            ]
            results = {"_meta": source}
            gmail_reads = []
            for stage, path in reads:
                try:
                    result = _read(
                        client, origin, path, headers, stage, list if stage == "render" else dict
                    )
                except ReadFailure as exc:
                    _preserve_failure(exc, source, results, client, origin, headers)
                    raise
                results[path] = result
                if stage.startswith("gmail_"):
                    gmail_reads.append((stage, path, result))

            # Before any acknowledgment exists, the broker must redeliver the
            # exact same pending observation. This certifies the at-least-once
            # boundary without advancing any private cursor.
            for stage, path, first in gmail_reads:
                try:
                    repeated = _read(client, origin, path, headers, stage + "_repeat")
                    if (
                        not isinstance(first.get("observation_id"), str)
                        or not first["observation_id"]
                        or repeated.get("observation_id") != first["observation_id"]
                        or repeated.get("evidence") != first.get("evidence")
                    ):
                        raise ReadFailure(stage + "_repeat", "pending_redelivery_mismatch")
                except ReadFailure as exc:
                    _preserve_failure(exc, source, results, client, origin, headers)
                    raise

            Path("broker-observations.json").write_text(
                json.dumps(results, sort_keys=True), encoding="utf-8"
            )
    except ProvenanceError as exc:
        raise SystemExit(
            f"private observer read failed at provenance:{exc}; no cursor acknowledged"
        ) from None
    except ReadFailure as exc:
        raise SystemExit(
            f"private observer read failed at {exc.stage}:{exc.reason}; no cursor acknowledged"
        ) from None
    except Exception:
        raise SystemExit(
            "private observer read failed at internal; no cursor acknowledged"
        ) from None


if __name__ == "__main__":
    main()
