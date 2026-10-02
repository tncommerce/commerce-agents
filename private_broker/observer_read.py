"""Fixed OIDC read harness. Deliberately no task inputs, secrets or cursor ack."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx


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
        with httpx.Client(trust_env=False, timeout=30, follow_redirects=False) as client:
            identity = client.get(
                os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
                params={"audience": origin},
                headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
            )
            identity.raise_for_status()
            token = identity.json()["value"]
            headers = {"Authorization": "Bearer " + token}
            paths = ["/v1/health", "/v1/render/services/srv-dakpfrnf3r2c73dr3f20/deployments"] + [
                f"/v1/gmail/threads/{thread}/metadata"
                for thread in ("1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d")
            ]
            results = {}
            for path in paths:
                response = client.get(origin + path, headers=headers)
                response.raise_for_status()
                results[path] = response.json()
            Path("broker-observations.json").write_text(
                json.dumps(results, sort_keys=True), encoding="utf-8"
            )
    except Exception:
        raise SystemExit("private observer read failed; no cursor acknowledged") from None


if __name__ == "__main__":
    main()
