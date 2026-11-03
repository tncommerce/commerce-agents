"""Explicit opt-in OIDC reads of two fixed Render services; no Gmail or health read."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from private_broker.observer_contract import source_from_env
from private_broker.render_service_contract import (
    ARTIFACT_FILE,
    MAX_ARTIFACT_BYTES,
    MAX_RESPONSE_BYTES,
    SAFE_FAILURES,
    SERVICE_IDS,
    RenderServiceError,
    strict_json,
    validate_artifact,
    validate_observation,
    validate_provenance,
)


def _origin(value: str) -> str:
    try:
        url = urlsplit(value)
        if (
            not value
            or len(value) > 512
            or any(ord(char) <= 32 for char in value)
            or "\\" in value
            or url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path
            or url.query
            or url.fragment
            or url.port not in (None, 443)
        ):
            raise ValueError
    except ValueError:
        raise RenderServiceError("invalid_broker_origin") from None
    return value


def _service_read(client, origin: str, headers: dict, service_id: str):
    """Read once; one failure must not suppress the other fixed service's read."""
    try:
        with client.stream(
            "GET", f"{origin}/v2/render/services/{service_id}/deployments", headers=headers
        ) as response:
            if response.status_code != 200:
                reason = (
                    f"http_{response.status_code}"
                    if type(response.status_code) is int and 300 <= response.status_code <= 599
                    else "invalid_response"
                )
                try:
                    body = strict_json(_bounded_body(response), limit=MAX_RESPONSE_BYTES)
                    if isinstance(body, dict) and body.get("error") in SAFE_FAILURES:
                        reason = body["error"]
                except Exception:
                    pass
                return None, reason
            value = strict_json(_bounded_body(response), limit=MAX_RESPONSE_BYTES)
            return validate_observation(value, service_id=service_id), None
    except httpx.TransportError:
        return None, "transport_error"
    except Exception:
        return None, "invalid_response"


def _bounded_body(response: httpx.Response) -> bytes:
    """Stop and close the stream before buffering an oversized response body."""
    if response.headers.get("Content-Encoding", "identity").strip().lower() not in {"", "identity"}:
        # The request explicitly asks for identity encoding. Reject unexpected
        # compression before decoding so a small wire body cannot inflate past
        # the memory bound inside the HTTP client's automatic decompressor.
        raise RenderServiceError("invalid_response")
    body = bytearray()
    for chunk in response.iter_bytes():
        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
            raise RenderServiceError("invalid_response")
        body.extend(chunk)
    return bytes(body)


def main() -> None:
    artifact_path = Path(ARTIFACT_FILE)
    temporary_path = Path(ARTIFACT_FILE + ".tmp")
    artifact_path.unlink(missing_ok=True)
    temporary_path.unlink(missing_ok=True)
    # This is a new, explicitly granted scope. An unconfigured/default workflow
    # must keep using the existing v1 API-only path.
    if os.getenv("DUFYND_PRIVATE_RENDER_SERVICES_V2_ENABLED") != "1":
        raise SystemExit("render services v2 is disabled")
    try:
        origin = _origin(os.environ["BROKER_ORIGIN"])
        source = validate_provenance(source_from_env())
        request_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
        request_token = os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
        if not request_token:
            raise ValueError
    except Exception:
        raise SystemExit("render services v2 configuration or provenance invalid") from None

    artifact = {"_meta": source, "version": 2, "services": {}, "failures": {}}
    try:
        with httpx.Client(trust_env=False, timeout=30, follow_redirects=False) as client:
            with client.stream(
                "GET",
                request_url,
                params={"audience": origin},
                headers={"Authorization": "Bearer " + request_token, "Accept-Encoding": "identity"},
            ) as identity:
                if identity.status_code != 200:
                    raise ValueError
                identity_payload = strict_json(_bounded_body(identity), limit=MAX_RESPONSE_BYTES)
            token = identity_payload.get("value") if isinstance(identity_payload, dict) else None
            if not isinstance(token, str) or not token or len(token) > MAX_RESPONSE_BYTES:
                raise ValueError
            headers = {"Authorization": "Bearer " + token, "Accept-Encoding": "identity"}
            for service_id in SERVICE_IDS:
                observation, failure = _service_read(client, origin, headers, service_id)
                if failure is not None:
                    artifact["failures"][service_id] = failure
                else:
                    artifact["services"][service_id] = observation
    except Exception:
        raise SystemExit("render services v2 identity or transport failed") from None

    try:
        validate_artifact(artifact)
        encoded = json.dumps(artifact, sort_keys=True, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_ARTIFACT_BYTES:
            raise ValueError
        temporary_path.write_bytes(encoded)
        temporary_path.replace(artifact_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        artifact_path.unlink(missing_ok=True)
        raise SystemExit("render services v2 artifact rejected") from None
    if artifact["failures"]:
        # The workflow uploads the bounded partition even on failure. Its
        # separate ingest job may durably capture the independent valid peer.
        raise SystemExit("render services v2 read incomplete; sanitized artifact preserved")


if __name__ == "__main__":
    main()
