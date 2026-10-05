"""Supabase owner authentication for the internal read-only Control Room.

No signup, email invitation, provider OAuth, refresh-token storage or auth bypass.
Every read validates the user AND the live Supabase session; browser cookies
contain authenticated ciphertext only, never readable Supabase/provider tokens.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from .jarvis_dashboard import PROJECT_ORIGIN, DashboardReader, create_dashboard_router
from .jarvis_owner_actions import OwnerActionConflict, OwnerActionUnavailable, OwnerActionWriter
from .jarvis_safe_actions import (
    JarvisSafeActionConflict,
    JarvisSafeActionRunner,
    JarvisSafeActionUnavailable,
)
from .jarvis_voice import JarvisVoiceGateway, VoiceUnavailable

ORIGIN = "https://scentai-api-kxhe.onrender.com"
SESSION_COOKIE = "__Host-dufynd_owner"
LOGIN_COOKIE = "__Host-dufynd_login"
ASSET_DIR = Path(__file__).with_name("control_room")
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Vary": "Cookie, Authorization",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'",
}


class OwnerDenied(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class OwnerConfig:
    owner_id: str
    auth_key: str
    session_key: str
    read_key: str
    budget_id: str | None = None

    @classmethod
    def from_env(cls) -> OwnerConfig | None:
        if os.getenv("DUFYND_CONTROL_ROOM_ENABLED") != "1":
            return None
        config = cls(
            owner_id=os.getenv("DUFYND_CONTROL_ROOM_OWNER_ID", ""),
            auth_key=os.getenv("DUFYND_CONTROL_ROOM_AUTH_KEY", ""),
            session_key=os.getenv("DUFYND_CONTROL_ROOM_SESSION_KEY", ""),
            read_key=os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            budget_id=os.getenv("DUFYND_JARVIS_BUDGET_ID") or None,
        )
        try:
            if (
                str(UUID(config.owner_id)) != config.owner_id
                or not config.auth_key
                or not config.read_key
            ):
                return None
            if not config.auth_key.startswith("sb_publishable_"):
                claims = jwt.decode(config.auth_key, options={"verify_signature": False})
                if claims.get("role") != "anon":
                    return None
            Fernet(config.session_key.encode())
        except (ValueError, TypeError, jwt.PyJWTError):
            return None
        return config


class OwnerAuth:
    def __init__(self, config: OwnerConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.cipher = Fernet(config.session_key.encode())
        self.transport = transport
        self._attempts: list[float] = []
        self._lock = threading.Lock()

    def _get(self, path: str, token: str, params: dict[str, str] | None = None) -> Any:
        with httpx.Client(transport=self.transport, timeout=5, follow_redirects=False) as client:
            r = client.get(
                PROJECT_ORIGIN + path,
                headers={"apikey": self.config.auth_key, "Authorization": "Bearer " + token},
                params=params,
            )
        if r.status_code != 200 or len(r.content) > 100_000:
            raise OwnerDenied()
        return r.json()

    def verify_token(self, token: object) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 16000:
            raise OwnerDenied()
        try:
            # This network call validates the exact signed token and fetches the
            # current user. Never authorize using locally decoded claims alone.
            user = self._get("/auth/v1/user", token)
            if (
                not isinstance(user, dict)
                or user.get("id") != self.config.owner_id
                or user.get("is_anonymous") is not False
                or not user.get("email_confirmed_at")
            ):
                raise OwnerDenied()
            claims = jwt.decode(token, options={"verify_signature": False})
            session_id = str(UUID(claims["session_id"]))
            expires = claims.get("exp")
            if (
                claims.get("sub") != self.config.owner_id
                or claims.get("role") != "authenticated"
                or claims.get("iss") != PROJECT_ORIGIN + "/auth/v1"
                or claims.get("aud") != "authenticated"
                or type(expires) is not int
                or expires <= time.time()
            ):
                raise OwnerDenied()
            # Fixed read-only RPC checks auth.uid, JWT session_id and auth.sessions.
            # It exposes only a boolean and grants no table access to the browser.
            if (
                self._get(
                    "/rest/v1/rpc/dufynd_dashboard_owner_session",
                    token,
                    {"p_session_id": session_id},
                )
                is not True
            ):
                raise OwnerDenied()
            return {"expires": expires}
        except (httpx.HTTPError, jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise OwnerDenied() from None

    def seal(self, data: dict[str, Any]) -> str:
        return self.cipher.encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()

    def open(self, value: str, *, ttl: int) -> dict[str, Any]:
        try:
            if len(value) > 24000:
                raise OwnerDenied()
            data = json.loads(self.cipher.decrypt(value.encode(), ttl=ttl))
            if not isinstance(data, dict):
                raise OwnerDenied()
            return data
        except (InvalidToken, ValueError, TypeError):
            raise OwnerDenied() from None

    def require_owner(self, request: Request) -> dict[str, Any]:
        try:
            data = self.open(request.cookies.get(SESSION_COOKIE, ""), ttl=3600)
            self.verify_token(data.get("access_token"))
            if not isinstance(data.get("csrf"), str) or len(data["csrf"]) != 43:
                raise OwnerDenied()
            return data
        except OwnerDenied:
            raise HTTPException(401, "Owner session required", headers=PRIVATE_HEADERS) from None

    def require_origin(self, request: Request) -> None:
        if request.headers.get("origin") != ORIGIN or request.headers.get(
            "sec-fetch-site", "same-origin"
        ) not in {"same-origin", "none"}:
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS)

    def check_attempt(self) -> None:
        # Single existing API instance. Bound memory globally and keep Supabase's
        # own auth rate limits; never trust a client-supplied forwarding header.
        with self._lock:
            now = time.monotonic()
            self._attempts = [value for value in self._attempts if now - value < 60]
            if len(self._attempts) >= 5:
                raise HTTPException(
                    429, "Try again later", headers={**PRIVATE_HEADERS, "Retry-After": "60"}
                )
            self._attempts.append(now)

    def login(self, email: object, password: object) -> tuple[str, int]:
        if (
            not isinstance(email, str)
            or not isinstance(password, str)
            or len(email) > 254
            or not 1 <= len(password) <= 1024
        ):
            raise OwnerDenied()
        try:
            with httpx.Client(
                transport=self.transport, timeout=8, follow_redirects=False
            ) as client:
                r = client.post(
                    PROJECT_ORIGIN + "/auth/v1/token",
                    params={"grant_type": "password"},
                    headers={"apikey": self.config.auth_key},
                    json={"email": email, "password": password},
                )
            if r.status_code != 200 or len(r.content) > 100_000:
                raise OwnerDenied()
            token = r.json().get("access_token")
            verified = self.verify_token(token)
            ttl = min(3600, verified["expires"] - int(time.time()))
            if ttl < 1:
                raise OwnerDenied()
            # Discard refresh_token and any provider tokens; no automatic renewal.
            cookie = self.seal({"access_token": token, "csrf": secrets.token_urlsafe(32)})
            if len(cookie) > 3800:
                raise OwnerDenied()
            return cookie, ttl
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise OwnerDenied() from None

    def logout(self, data: dict[str, Any]) -> bool:
        try:
            with httpx.Client(
                transport=self.transport, timeout=5, follow_redirects=False
            ) as client:
                r = client.post(
                    PROJECT_ORIGIN + "/auth/v1/logout",
                    params={"scope": "local"},
                    headers={
                        "apikey": self.config.auth_key,
                        "Authorization": "Bearer " + data["access_token"],
                    },
                )
            return r.status_code in {200, 204}
        except (httpx.HTTPError, KeyError):
            return False


def _cookie(response: Response, name: str, value: str, ttl: int) -> None:
    response.set_cookie(
        name, value, max_age=ttl, secure=True, httponly=True, samesite="strict", path="/"
    )


def _delete_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, secure=True, httponly=True, samesite="strict", path="/")


def create_control_room_router(
    config: OwnerConfig | None = None,
    *,
    auth: OwnerAuth | None = None,
    reader: DashboardReader | None = None,
    voice_gateway: JarvisVoiceGateway | None = None,
    action_writer: OwnerActionWriter | None = None,
    safe_action_runner: JarvisSafeActionRunner | None = None,
) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    config = config or OwnerConfig.from_env()
    auth = auth or (OwnerAuth(config) if config else None)
    if voice_gateway is None and config and auth:
        voice_gateway = JarvisVoiceGateway.from_env(config.owner_id)
    if action_writer is None and config and auth:
        action_writer = OwnerActionWriter(secret_key=config.read_key)
    if safe_action_runner is None and config and auth:
        safe_action_runner = JarvisSafeActionRunner(secret_key=config.read_key)

    def owner(request: Request) -> dict[str, Any]:
        if auth is None:
            raise HTTPException(503, "Owner access not configured", headers=PRIVATE_HEADERS)
        return auth.require_owner(request)

    @router.get("/internal/login")
    def login_page() -> HTMLResponse:
        nonce = secrets.token_urlsafe(32) if auth else ""
        template = (ASSET_DIR / "login.html").read_text()
        response = HTMLResponse(
            template.replace("LOGIN_CSRF", nonce)
            .replace("LOGIN_DISABLED", "" if auth else "disabled")
            .replace(
                "LOGIN_NOTICE",
                "Dein privater DUFYND-Zugang." if auth else "Der Owner-Zugang wird eingerichtet.",
            ),
            headers=PRIVATE_HEADERS,
        )
        if auth:
            _cookie(response, LOGIN_COOKIE, auth.seal({"nonce": nonce}), 600)
        return response

    @router.post("/internal/login")
    async def login(request: Request) -> JSONResponse:
        if auth is None:
            raise HTTPException(503, "Owner access not configured", headers=PRIVATE_HEADERS)
        auth.require_origin(request)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(400, "Invalid request", headers=PRIVATE_HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise HTTPException(400, "Invalid request", headers=PRIVATE_HEADERS)
        try:
            payload = json.loads(body)
            nonce = auth.open(request.cookies.get(LOGIN_COOKIE, ""), ttl=600).get("nonce")
            if (
                not isinstance(payload, dict)
                or set(payload) != {"email", "password", "csrf"}
                or not isinstance(nonce, str)
                or not isinstance(payload.get("csrf"), str)
                or not hmac.compare_digest(nonce, payload["csrf"])
            ):
                raise OwnerDenied()
        except (ValueError, TypeError, OwnerDenied):
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS) from None
        auth.check_attempt()
        # Blocking auth IO runs off the event loop.
        try:
            cookie, ttl = await run_in_threadpool(auth.login, payload["email"], payload["password"])
        except OwnerDenied:
            return JSONResponse(
                {"error": "Anmeldung nicht möglich. Zugang prüfen."},
                status_code=401,
                headers=PRIVATE_HEADERS,
            )
        response = JSONResponse(
            {"ok": True, "destination": "/internal/jarvis"}, headers=PRIVATE_HEADERS
        )
        _cookie(response, SESSION_COOKIE, cookie, ttl)
        _delete_cookie(response, LOGIN_COOKIE)
        return response

    @router.get("/internal/jarvis")
    def room(request: Request) -> Response:
        try:
            data = owner(request)
        except HTTPException:
            return RedirectResponse("/internal/login", status_code=303, headers=PRIVATE_HEADERS)
        voice_enabled = bool(voice_gateway and voice_gateway.enabled)
        return HTMLResponse(
            (ASSET_DIR / "index.html")
            .read_text()
            .replace("OWNER_CSRF", data["csrf"])
            .replace("VOICE_ENABLED", "true" if voice_enabled else "false"),
            headers=PRIVATE_HEADERS,
        )

    @router.get("/internal/assets/{asset}")
    def asset(asset: str) -> Response:
        # Public assets contain presentation logic only, never live data or keys.
        if asset not in {"room.css", "room.js", "login.js"}:
            raise HTTPException(404, "Not found", headers=PRIVATE_HEADERS)
        return Response(
            (ASSET_DIR / asset).read_text(),
            headers=PRIVATE_HEADERS,
            media_type="text/css" if asset.endswith(".css") else "text/javascript",
        )

    @router.post("/internal/jarvis/voice/session")
    async def voice_session(request: Request) -> Response:
        data = owner(request)
        assert auth is not None
        auth.require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, data["csrf"]):
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS)
        if request.headers.get("content-type", "").split(";")[0] != "application/sdp":
            raise HTTPException(400, "Invalid voice request", headers=PRIVATE_HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise HTTPException(413, "Voice offer too large", headers=PRIVATE_HEADERS)
        try:
            sdp = body.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Invalid voice request", headers=PRIVATE_HEADERS) from None
        if voice_gateway is None or not voice_gateway.enabled:
            raise HTTPException(
                503,
                "Voice provider not configured",
                headers=PRIVATE_HEADERS,
            )
        try:
            answer = await run_in_threadpool(voice_gateway.connect, sdp)
        except ValueError:
            raise HTTPException(400, "Invalid voice request", headers=PRIVATE_HEADERS) from None
        except VoiceUnavailable:
            raise HTTPException(
                502,
                "Voice provider unavailable",
                headers=PRIVATE_HEADERS,
            ) from None
        return Response(
            answer,
            headers=PRIVATE_HEADERS,
            media_type="application/sdp",
            status_code=201,
        )

    @router.post("/internal/jarvis/safe-action")
    async def safe_action(request: Request) -> JSONResponse:
        data = owner(request)
        assert auth is not None
        auth.require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, data["csrf"]):
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(400, "Invalid safe action", headers=PRIVATE_HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024:
                raise HTTPException(413, "Safe action too large", headers=PRIVATE_HEADERS)
        try:
            payload = json.loads(body)
            if payload != {"action": "advance_next_safe_work"}:
                raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            raise HTTPException(400, "Invalid safe action", headers=PRIVATE_HEADERS) from None
        if safe_action_runner is None:
            raise HTTPException(503, "Safe action unavailable", headers=PRIVATE_HEADERS)
        try:
            result = await run_in_threadpool(safe_action_runner.advance_next_safe_work)
        except JarvisSafeActionConflict as error:
            raise HTTPException(409, str(error), headers=PRIVATE_HEADERS) from None
        except JarvisSafeActionUnavailable:
            raise HTTPException(503, "Safe action unavailable", headers=PRIVATE_HEADERS) from None
        return JSONResponse(result, headers=PRIVATE_HEADERS)

    @router.post("/internal/jarvis/owner-action")
    async def owner_action(request: Request) -> JSONResponse:
        data = owner(request)
        assert auth is not None
        auth.require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, data["csrf"]):
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(400, "Invalid owner action", headers=PRIVATE_HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise HTTPException(413, "Owner action too large", headers=PRIVATE_HEADERS)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or set(payload) != {
                "decision_id",
                "action_token",
                "action",
            }:
                raise ValueError
        except (ValueError, TypeError, json.JSONDecodeError):
            raise HTTPException(400, "Invalid owner action", headers=PRIVATE_HEADERS) from None
        if action_writer is None:
            raise HTTPException(503, "Owner actions unavailable", headers=PRIVATE_HEADERS)
        try:
            result = await run_in_threadpool(
                action_writer.resolve,
                decision_id=payload["decision_id"],
                action_token=payload["action_token"],
                action=payload["action"],
            )
        except ValueError:
            raise HTTPException(400, "Invalid owner action", headers=PRIVATE_HEADERS) from None
        except OwnerActionConflict:
            raise HTTPException(
                409,
                "Owner action no longer matches the live gate",
                headers=PRIVATE_HEADERS,
            ) from None
        except OwnerActionUnavailable:
            raise HTTPException(503, "Owner action unavailable", headers=PRIVATE_HEADERS) from None
        return JSONResponse(result, headers=PRIVATE_HEADERS)

    @router.post("/internal/logout")
    def logout(request: Request) -> JSONResponse:
        data = owner(request)
        assert auth is not None
        auth.require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(csrf, data["csrf"]):
            raise HTTPException(403, "Forbidden", headers=PRIVATE_HEADERS)
        confirmed = auth.logout(data)
        response = JSONResponse(
            {"ok": confirmed, "destination": "/internal/login"},
            status_code=200 if confirmed else 503,
            headers=PRIVATE_HEADERS,
        )
        _delete_cookie(response, SESSION_COOKIE)
        return response

    if config and auth:
        reader = reader or DashboardReader(secret_key=config.read_key, budget_id=config.budget_id)
        router.include_router(create_dashboard_router(reader, authorize_owner=owner))
    else:

        @router.get("/internal/jarvis/snapshot")
        def unavailable() -> None:
            raise HTTPException(503, "Owner access not configured", headers=PRIVATE_HEADERS)

    return router
