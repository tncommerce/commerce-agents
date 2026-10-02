"""Provider-neutral HTTPS entry point. Owner administration uses a separate private key."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from scripts.dufynd_observer_credentials import (
    GMAIL_SCOPE,
    KNOWN_THREADS,
    TOKEN_ENDPOINT,
    BrokerError,
    FixedTransport,
    GmailKnownThreadBroker,
    GmailRefreshBroker,
    PrivateCredential,
    RenderReadBroker,
    metadata,
)

from private_broker.store import EncryptedVault, FirestoreCAS

ISSUER = "https://token.actions.githubusercontent.com"
WORKFLOW = "tncommerce/commerce-agents/.github/workflows/dufynd-private-observer.yml@refs/heads/scentai-mvp"


@dataclass(frozen=True, repr=False)
class Config:
    origin: str
    mailbox: str
    client_id: str
    client_secret: str
    owner_key: str
    render_key: str = ""
    repository_id: str = ""
    callback_logging_ready: bool = False

    def validate(self):
        url = urlsplit(self.origin)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.path
            or url.query
            or url.fragment
            or url.username
            or url.port not in {None, 443}
        ):
            raise BrokerError("missing_configuration")
        if (
            not re.fullmatch(r"[^\s@]+@[^\s@]+", self.mailbox)
            or len(self.owner_key) < 32
            or not self.repository_id.isdigit()
        ):
            raise BrokerError("missing_configuration")

    @property
    def callback(self):
        return self.origin + "/oauth/gmail/callback"


class WorkloadAuth:
    def __init__(self, config, keys):
        self.config, self.keys = config, keys

    def verify(self, token):
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or any(k in header for k in ("jku", "jwk", "x5u")):
                raise ValueError
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.config.origin,
                issuer=ISSUER,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "nbf",
                        "sub",
                        "repository",
                        "repository_id",
                        "ref",
                        "workflow_ref",
                        "event_name",
                    ]
                },
            )
            expected = {
                "repository": "tncommerce/commerce-agents",
                "repository_id": self.config.repository_id,
                "ref": "refs/heads/scentai-mvp",
                "workflow_ref": WORKFLOW,
                "sub": "repo:tncommerce/commerce-agents:ref:refs/heads/scentai-mvp",
            }
            if (
                any(claims.get(k) != v for k, v in expected.items())
                or claims["event_name"] not in {"workflow_dispatch", "schedule"}
                or claims["exp"] - claims["iat"] > 600
                or time.time() - claims["iat"] > 600
            ):
                raise ValueError
        except Exception:
            raise BrokerError("broker_activation_required") from None


class OAuth:
    def __init__(self, config, vault, transport):
        self.config, self.vault, self.transport = config, vault, transport

    def start(self):
        if not self.config.callback_logging_ready:
            raise BrokerError("broker_activation_required")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        key = "oauth_" + hashlib.sha256(state.encode()).hexdigest()
        row, _ = self.vault.get("gmail_known_threads")
        if not self.vault.cas(
            key,
            None,
            {
                "verifier": verifier,
                "expires": time.time() + 600,
                "generation": row.get("generation", 0),
            },
        ):
            raise BrokerError("refresh_race")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        return {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?"
            + urlencode(
                {
                    "client_id": self.config.client_id,
                    "redirect_uri": self.config.callback,
                    "response_type": "code",
                    "scope": GMAIL_SCOPE,
                    "access_type": "offline",
                    "include_granted_scopes": "false",
                    "prompt": "consent select_account",
                    "login_hint": self.config.mailbox,
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        }

    def callback(self, state, code):
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", state) or not code or len(code) > 4096:
            raise BrokerError("invalid_response")
        key = "oauth_" + hashlib.sha256(state.encode()).hexdigest()
        record, version = self.vault.get(key)
        if (
            not record.get("verifier")
            or record.get("expires", 0) < time.time()
            or not self.vault.cas(key, version, {"used": True})
        ):
            raise BrokerError("invalid_response")
        # Consume before any exchange, including unsuccessful exchanges and account mismatch.
        with self.vault.lock("gmail_known_threads"):
            row, _ = self.vault.get("gmail_known_threads")
            generation = row.get("generation", 0)
            if generation != record["generation"]:
                raise BrokerError("refresh_race")
            result = self.transport.request(
                "POST",
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "redirect_uri": self.config.callback,
                    "code_verifier": record["verifier"],
                },
            )
            if not isinstance(result, dict) or set(str(result.get("scope", "")).split()) != {
                GMAIL_SCOPE
            }:
                raise BrokerError("scope_mismatch")
            if (
                result.get("token_type", "").lower() != "bearer"
                or not all(
                    isinstance(result.get(k), str) and result[k]
                    for k in ("access_token", "refresh_token")
                )
                or type(result.get("expires_in")) is not int
                or not 60 <= result["expires_in"] <= 86400
            ):
                raise BrokerError("invalid_response")
            profile = self.transport.request(
                "GET",
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": "Bearer " + result["access_token"]},
            )
            if (
                not isinstance(profile, dict)
                or profile.get("emailAddress", "").casefold() != self.config.mailbox.casefold()
            ):
                raise BrokerError("account_mismatch")
            now = datetime.now(UTC)
            health = replace(
                metadata("gmail"),
                status="healthy",
                health_reason="healthy",
                expires_at=now + timedelta(seconds=result["expires_in"]),
                refreshed_at=now,
                last_health_check=now,
            )
            secret = PrivateCredential(
                result["access_token"],
                result["refresh_token"],
                self.config.client_id,
                self.config.client_secret,
                self.config.mailbox,
                generation + 1,
            )
            if not self.vault.rotate("gmail_known_threads", generation, secret, health):
                raise BrokerError("refresh_race")
            return {"status": "authorized"}


def create_app(config: Config, vault: EncryptedVault, transport: FixedTransport, auth):
    config.validate()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    oauth = OAuth(config, vault, transport)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            if len(request.url.query) > 8192:
                raise BrokerError("invalid_response")
            if request.url.path.startswith("/owner/"):
                supplied = request.headers.get("authorization", "")
                if not hmac.compare_digest(supplied, "Bearer " + config.owner_key):
                    raise BrokerError("broker_activation_required")
            elif request.url.path != "/oauth/gmail/callback":
                token = request.headers.get("authorization", "")
                if not token.startswith("Bearer ") or len(token) > 16000:
                    raise BrokerError("broker_activation_required")
                auth.verify(token[7:])
            response = await call_next(request)
        except BrokerError as exc:
            response = JSONResponse({"error": exc.reason}, status_code=403)
        except Exception:
            response = JSONResponse({"error": "invalid_response"}, status_code=503)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            }
        )
        return response

    @app.get("/v1/render/services/{service_id}/deployments")
    def render(service_id: str, request: Request):
        if request.query_params:
            raise BrokerError("scope_mismatch")
        if service_id != "srv-dakpfrnf3r2c73dr3f20":
            raise BrokerError("scope_mismatch")
        with vault.lock("render_deploy_broker"):
            try:
                result = RenderReadBroker(transport, PrivateCredential(config.render_key)).read(
                    service_id=service_id
                )
                state, reason = "healthy", "healthy"
            except BrokerError as exc:
                state, reason = (
                    "missing_configuration" if not config.render_key else "refresh_failed",
                    exc.reason,
                )
                checked = replace(
                    metadata("render"),
                    status=state,
                    health_reason=reason,
                    last_health_check=datetime.now(UTC),
                )
                if not vault.mark("render_deploy_broker", 0, checked):
                    raise BrokerError("refresh_race") from None
                raise
            checked = replace(
                metadata("render"),
                status=state,
                health_reason=reason,
                last_health_check=datetime.now(UTC),
            )
            if not vault.mark("render_deploy_broker", 0, checked):
                raise BrokerError("refresh_race")
            return result

    @app.get("/v1/health")
    def health():
        now = datetime.now(UTC)
        gmail, secret = vault.read("gmail_known_threads")
        return {
            "gmail": replace(
                gmail,
                status=gmail.health(now, secret_present=secret is not None),
                last_health_check=now,
            ).public(),
            "render": vault.read("render_deploy_broker")[0].public(),
        }

    @app.get("/v1/gmail/threads/{thread_id}/metadata")
    def gmail(thread_id: str, request: Request):
        if thread_id not in KNOWN_THREADS or request.query_params:
            raise BrokerError("scope_mismatch")
        GmailRefreshBroker(vault, transport).refresh()
        # Credential lease also fences snapshot/ack against rotation or revoke.
        with vault.lock("gmail_known_threads"):
            health, secret = vault.read("gmail_known_threads")
            if secret is None:
                raise BrokerError("missing_configuration")
            state = vault.thread_state(thread_id)
            cursor = state.get("cursor", {})
            outstanding = state.get("pending", {})
            if (
                outstanding.get("generation") == secret.generation
                and outstanding.get("digest") != cursor.get("digest")
                and outstanding.get("result")
            ):
                return {"observation_id": outstanding["digest"], "evidence": outstanding["result"]}
            result = GmailKnownThreadBroker(transport, secret, health, datetime.now(UTC)).read(
                thread_id, cursor.get("history_id")
            )
            digest = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            # At-least-once delivery: advance ONLY on authenticated matching acknowledgment.
            pending = {
                "history_id": result["history_id"],
                "digest": digest,
                "result": result,
                "generation": secret.generation,
            }
            if not vault.commit_thread(
                thread_id, secret.generation, {"cursor": cursor, "pending": pending}
            ):
                raise BrokerError("refresh_race")
            return {"observation_id": digest, "evidence": result}

    @app.post("/v1/gmail/threads/{thread_id}/ack/{digest}")
    def ack(thread_id: str, digest: str):
        if thread_id not in KNOWN_THREADS or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise BrokerError("scope_mismatch")
        with vault.lock("gmail_known_threads"):
            row, _ = vault.get("gmail_known_threads")
            state = vault.thread_state(thread_id)
            pending = state.get("pending", {})
            if pending.get("digest") != digest or pending.get("generation") != row.get(
                "generation"
            ):
                raise BrokerError("refresh_race")
            current = state.get("cursor", {})
            if current.get("digest") == digest:
                return {"status": "duplicate"}
            if not vault.commit_thread(
                thread_id,
                row.get("generation"),
                {
                    "cursor": {"history_id": pending["history_id"], "digest": digest},
                    "pending": pending,
                },
            ):
                raise BrokerError("refresh_race")
            return {"status": "acknowledged"}

    @app.post("/owner/oauth/gmail/start")
    def start():
        return oauth.start()

    @app.get("/oauth/gmail/callback")
    def callback(request: Request):
        if (
            set(request.query_params)
            - {"state", "code", "scope", "authuser", "prompt", "error", "error_description"}
            or len(request.query_params.getlist("state")) != 1
            or len(request.query_params.getlist("code")) != 1
        ):
            raise BrokerError("invalid_response")
        return oauth.callback(request.query_params["state"], request.query_params["code"])

    @app.post("/owner/gmail/revoke")
    def revoke():
        _, existing = vault.read("gmail_known_threads")
        if existing is not None:
            return GmailRefreshBroker(vault, transport).revoke()
        with vault.lock("gmail_known_threads"):
            row, _ = vault.get("gmail_known_threads")
            health = replace(
                metadata("gmail"),
                status="revoked",
                health_reason="revoked",
                revoked_at=datetime.now(UTC),
            )
            if not vault.revoke("gmail_known_threads", row.get("generation", 0), health):
                raise BrokerError("refresh_race")
            return health.public()

    return app


def production_app():
    logging.disable(logging.CRITICAL)
    # Only mounted Secret Manager files. No normal DUFYND credentials accepted.
    if any(
        os.environ.get(k)
        for k in (
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SECRET_KEY",
            "ANTHROPIC_API_KEY",
            "GITHUB_TOKEN",
        )
    ):
        raise BrokerError("missing_configuration")

    def secret(name):
        with open("/run/secrets/" + name + "-dir/value", encoding="utf-8") as source:
            return source.read().strip()

    config = Config(
        os.environ["BROKER_ORIGIN"],
        os.environ["BROKER_MAILBOX"],
        os.environ["GOOGLE_CLIENT_ID"],
        secret("google-client-secret"),
        secret("owner-key"),
        secret("render-key"),
        os.environ["BROKER_REPOSITORY_ID"],
        os.environ.get("BROKER_CALLBACK_LOGGING_READY") == "1",
    )
    client = httpx.Client(trust_env=False)
    vault = EncryptedVault(
        FirestoreCAS(os.environ["BROKER_PROJECT"], client),
        base64.b64decode(secret("encryption-key"), validate=True),
    )
    keys = jwt.PyJWKClient(ISSUER + "/.well-known/jwks", cache_keys=False, lifespan=300, timeout=5)
    return create_app(config, vault, FixedTransport(client), WorkloadAuth(config, keys))
