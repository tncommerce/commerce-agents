"""Strict Google-issued OIDC identity for one fixed Gmail refresh call.

This is intentionally separate from GitHub WorkloadAuth. No observer/read/ack,
owner-admin, or database route accepts Google scheduler identities.
Configured only after an owner-reviewed Cloud Run deployment and cost check.
"""

from __future__ import annotations

import re
import time

import jwt
from scripts.dufynd_observer_credentials import BrokerError

GOOGLE_SCHEDULER_ISSUER = "https://accounts.google.com"
GOOGLE_SCHEDULER_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
SCHEDULER_PATH = "/internal/gmail/refresh"

# Reject whitespace, wildcards, user mailbox identities or arbitrary issuers.
SERVICE_ACCOUNT_PATTERN = re.compile(
    r"[a-z][a-z0-9-]{4,29}@[a-z][a-z0-9-]{4,29}\.iam\.gserviceaccount\.com\Z"
)


class SchedulerOIDC:
    """Verify a Google-signed token for the exact refresh endpoint only."""

    def __init__(self, config, keys):
        self.config = config
        self.keys = keys

    def verify(self, token: str) -> None:
        if not self.config.scheduler_sa_email:
            raise BrokerError("broker_activation_required")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or any(
                item in header for item in ("jku", "jwk", "x5u", "x5c")
            ):
                raise ValueError("unsafe jwt header")

            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=GOOGLE_SCHEDULER_ISSUER,
                audience=self.config.origin + SCHEDULER_PATH,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email", "email_verified"]},
                leeway=15,
            )

            issued_at = claims["iat"]
            expires_at = claims["exp"]
            now = time.time()
            if (
                claims["email"] != self.config.scheduler_sa_email
                or claims["email_verified"] is not True
                or not isinstance(claims["sub"], str)
                or not claims["sub"]
                or not isinstance(issued_at, int)
                or not isinstance(expires_at, int)
                or expires_at - issued_at > 3600
                or issued_at > now + 15
                or issued_at < now - 600
            ):
                raise ValueError("scheduler identity mismatch")
        except Exception:
            # Never echo the token, identity claims, or cryptographic diagnostics.
            raise BrokerError("broker_activation_required") from None
