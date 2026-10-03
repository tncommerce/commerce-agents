"""Fixed OIDC read harness. Deliberately no task inputs, secrets or cursor ack."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from private_broker.observer_contract import ProvenanceError, source_from_env


class ReadFailure(Exception):
    """Non-secret, bounded diagnostic for a fixed observer stage."""

    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _json(response, stage: str, expected_type=dict):
    if not 200 <= response.status_code < 300:
        raise ReadFailure(stage, f"http_{response.status_code}")
    try:
        result = response.json()
    except Exception:
        raise ReadFailure(stage, "invalid_json") from None
    if not isinstance(result, expected_type):
        raise ReadFailure(stage, "invalid_json")
    return result


def main():
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
            reads = [
                ("render", "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments"),
                ("gmail_1", "/v1/gmail/threads/1a0f385ed98c6af8/metadata"),
                ("gmail_2", "/v1/gmail/threads/1a0f69c169fb928f/metadata"),
                ("gmail_3", "/v1/gmail/threads/1a0f6a90772a743d/metadata"),
                # Snapshot health last so provider reads/refreshes are reflected
                # in the projection artifact rather than stale pre-read state.
                ("health", "/v1/health"),
            ]
            results = {"_meta": source}
            gmail_reads = []
            for stage, path in reads:
                response = client.get(origin + path, headers=headers)
                result = _json(response, stage, list if stage == "render" else dict)
                results[path] = result
                if stage.startswith("gmail_"):
                    gmail_reads.append((stage, path, result))

            # Before any acknowledgment exists, the broker must redeliver the
            # exact same pending observation. This certifies the at-least-once
            # boundary without advancing any private cursor.
            for stage, path, first in gmail_reads:
                repeated = _json(client.get(origin + path, headers=headers), stage + "_repeat")
                if (
                    not isinstance(first.get("observation_id"), str)
                    or not first["observation_id"]
                    or repeated.get("observation_id") != first["observation_id"]
                    or repeated.get("evidence") != first.get("evidence")
                ):
                    raise ReadFailure(stage + "_repeat", "pending_redelivery_mismatch")

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
