"""Private broker preparation, never a task tool or public API.

Storage/lock adapters are deliberately owner-selected: no default secret file,
new service, exported connector credential or deployed callback is introduced.
Only a trusted broker may hold this object; task packets receive health metadata.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

RENDER_SERVICE = "srv-dakpfrnf3r2c73dr3f20"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
KNOWN_THREADS = frozenset({"1a0f385ed98c6af8", "1a0f69c169fb928f", "1a0f6a90772a743d"})
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
STATES = frozenset(
    {
        "missing_configuration",
        "healthy",
        "expiring",
        "expired",
        "revoked",
        "refresh_failed",
        "scope_mismatch",
        "account_mismatch",
    }
)
REASONS = STATES | frozenset(
    {
        "rate_limited",
        "provider_outage",
        "rotation_secret_missing",
        "refresh_race",
        "invalid_grant",
        "invalid_response",
        "broker_activation_required",
    }
)


class BrokerError(RuntimeError):
    def __init__(self, reason: str):
        # Never propagate provider exception text, responses or arbitrary fields.
        super().__init__(reason if reason in REASONS else "invalid_response")
        self.reason = str(self)


@dataclass(frozen=True)
class CredentialMetadata:
    credential_id: str
    provider: str
    account_alias: str
    allowed_operations: tuple[str, ...]
    allowed_resources: tuple[str, ...]
    oauth_scopes: tuple[str, ...]
    secret_reference: str
    status: str = "missing_configuration"
    expires_at: datetime | None = None
    refreshed_at: datetime | None = None
    revoked_at: datetime | None = None
    last_health_check: datetime | None = None
    health_reason: str = "missing_configuration"
    rotation_due_at: datetime | None = None

    def validate(self) -> None:
        expected = {
            "render": (
                "render_deploy_broker",
                "tncommerce_render",
                ("deployment.read",),
                (RENDER_SERVICE,),
                (),
                "dufynd_observer_render_read_token",
            ),
            "gmail": (
                "gmail_known_threads",
                "dufynd_owner_mailbox",
                ("thread.metadata", "history.read"),
                tuple(sorted(KNOWN_THREADS)),
                (GMAIL_SCOPE,),
                "dufynd_observer_gmail_read_access_token",
            ),
        }.get(self.provider)
        actual = (
            self.credential_id,
            self.account_alias,
            self.allowed_operations,
            self.allowed_resources,
            self.oauth_scopes,
            self.secret_reference,
        )
        if expected is None or actual != expected:
            raise BrokerError("scope_mismatch")
        if self.status not in STATES or self.health_reason not in REASONS:
            raise BrokerError("invalid_response")
        for value in (
            self.expires_at,
            self.refreshed_at,
            self.revoked_at,
            self.last_health_check,
            self.rotation_due_at,
        ):
            if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
                raise BrokerError("invalid_response")

    def health(self, now: datetime, *, secret_present: bool) -> str:
        self.validate()
        if self.revoked_at is not None or self.status == "revoked":
            return "revoked"
        if self.status in {
            "scope_mismatch",
            "account_mismatch",
            "refresh_failed",
            "missing_configuration",
        }:
            return self.status
        if not secret_present:
            return "missing_configuration"
        if self.provider == "gmail" and self.expires_at is None:
            return "missing_configuration"
        if self.expires_at is not None and self.expires_at <= now:
            return "expired"
        if self.expires_at is not None and self.expires_at <= now + timedelta(minutes=5):
            return "expiring"
        return "healthy"

    def public(self) -> dict[str, Any]:
        self.validate()
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else list(value)
                if isinstance(value, tuple)
                else value
            )
            for name, value in vars(self).items()
        }


def metadata(provider: str) -> CredentialMetadata:
    if provider == "render":
        return CredentialMetadata(
            "render_deploy_broker",
            provider,
            "tncommerce_render",
            ("deployment.read",),
            (RENDER_SERVICE,),
            (),
            "dufynd_observer_render_read_token",
        )
    if provider == "gmail":
        return CredentialMetadata(
            "gmail_known_threads",
            provider,
            "dufynd_owner_mailbox",
            ("thread.metadata", "history.read"),
            tuple(sorted(KNOWN_THREADS)),
            (GMAIL_SCOPE,),
            "dufynd_observer_gmail_read_access_token",
        )
    raise BrokerError("scope_mismatch")


@dataclass(frozen=True, repr=False)
class PrivateCredential:
    """All values live only in the private broker's selected Vault adapter."""

    access_token: str = field(repr=False)
    refresh_token: str = field(default="", repr=False)
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    expected_account: str = field(default="", repr=False)
    generation: int = 0


class PrivateVault(Protocol):
    def lock(self, credential_id: str) -> AbstractContextManager[None]: ...
    def read(self, credential_id: str) -> tuple[CredentialMetadata, PrivateCredential | None]: ...
    def rotate(
        self,
        credential_id: str,
        generation: int,
        secret: PrivateCredential,
        health: CredentialMetadata,
    ) -> bool: ...
    def mark(self, credential_id: str, generation: int, health: CredentialMetadata) -> bool: ...
    def revoke(self, credential_id: str, generation: int, health: CredentialMetadata) -> bool: ...

    # lock + CAS must be durable/distributed; token and health commit together.
    # revoke invalidates generations and removes token/refresh/client secrets.


class FixedTransport:
    """Bounded upstream transport; never accepts arbitrary URLs from a task."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def request(self, method: str, url: str, **kwargs: Any) -> Mapping[str, Any] | list[Any]:
        allowed = (
            method == "GET"
            and url == f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys"
            or method == "POST"
            and url in {TOKEN_ENDPOINT, REVOKE_ENDPOINT}
            or method == "GET"
            and url
            in {
                f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{t}" for t in KNOWN_THREADS
            }
            or method == "GET"
            and url
            in {
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                "https://gmail.googleapis.com/gmail/v1/users/me/history",
            }
        )
        if not allowed:
            raise BrokerError("scope_mismatch")
        try:
            with self.client.stream(
                method, url, follow_redirects=False, timeout=5, **kwargs
            ) as response:
                if response.status_code == 429:
                    raise BrokerError("rate_limited")
                if response.status_code >= 500:
                    raise BrokerError("provider_outage")
                if 300 <= response.status_code < 400:
                    raise BrokerError("invalid_response")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise BrokerError("invalid_response")
                if url == REVOKE_ENDPOINT and response.status_code == 200:
                    return {}
                import json

                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise BrokerError("invalid_response") from None
                if response.status_code != 200:
                    if (
                        url == TOKEN_ENDPOINT
                        and isinstance(body, dict)
                        and body.get("error") == "invalid_grant"
                    ):
                        raise BrokerError("invalid_grant")
                    raise BrokerError("refresh_failed")
                if not isinstance(body, (dict, list)):
                    raise BrokerError("invalid_response")
                return body
        except BrokerError:
            raise
        except Exception:
            raise BrokerError("provider_outage") from None


class GmailRefreshBroker:
    def __init__(
        self,
        vault: PrivateVault,
        transport: FixedTransport,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.vault, self.transport, self.clock = vault, transport, clock

    def refresh(self) -> dict[str, Any]:
        cid = "gmail_known_threads"
        with self.vault.lock(cid):
            health, secret = self.vault.read(cid)
            now = self.clock()
            state = health.health(now, secret_present=secret is not None)
            if (
                state in {"revoked", "account_mismatch", "scope_mismatch", "missing_configuration"}
                or secret is None
            ):
                raise BrokerError(state)
            if state == "healthy":
                return health.public()
            if not all(
                (
                    secret.refresh_token,
                    secret.client_id,
                    secret.client_secret,
                    secret.expected_account,
                )
            ):
                raise BrokerError("missing_configuration")
            try:
                # Exactly two attempts for transport/429/5xx; invalid_grant never retried.
                for attempt in range(2):
                    try:
                        result = self.transport.request(
                            "POST",
                            TOKEN_ENDPOINT,
                            data={
                                "grant_type": "refresh_token",
                                "refresh_token": secret.refresh_token,
                                "client_id": secret.client_id,
                                "client_secret": secret.client_secret,
                            },
                        )
                        break
                    except BrokerError as exc:
                        if attempt or exc.reason not in {"rate_limited", "provider_outage"}:
                            raise
                if (
                    not isinstance(result, dict)
                    or result.get("token_type", "").lower() != "bearer"
                    or not isinstance(result.get("access_token"), str)
                    or not result["access_token"]
                ):
                    raise BrokerError("invalid_response")
                # Missing scope cannot prove the refresh kept the narrow grant.
                if set(str(result.get("scope", "")).split()) != {GMAIL_SCOPE}:
                    raise BrokerError("scope_mismatch")
                expiry = result.get("expires_in")
                if type(expiry) is not int or not 60 <= expiry <= 86400:
                    raise BrokerError("invalid_response")
                profile = self.transport.request(
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={"Authorization": "Bearer " + result["access_token"]},
                )
                if (
                    not isinstance(profile, dict)
                    or profile.get("emailAddress", "").casefold()
                    != secret.expected_account.casefold()
                ):
                    raise BrokerError("account_mismatch")
                updated = replace(
                    health,
                    status="healthy",
                    health_reason="healthy",
                    expires_at=now + timedelta(seconds=expiry),
                    refreshed_at=now,
                    last_health_check=now,
                    rotation_due_at=now + timedelta(seconds=expiry - 60),
                )
                if "refresh_token" in result and (
                    not isinstance(result["refresh_token"], str) or not result["refresh_token"]
                ):
                    raise BrokerError("invalid_response")
                rotated = replace(
                    secret,
                    access_token=result["access_token"],
                    refresh_token=result.get("refresh_token", secret.refresh_token),
                    generation=secret.generation + 1,
                )
                if not self.vault.rotate(cid, secret.generation, rotated, updated):
                    raise BrokerError("refresh_race")
                return updated.public()
            except BrokerError as exc:
                state = (
                    exc.reason
                    if exc.reason in {"scope_mismatch", "account_mismatch"}
                    else "revoked"
                    if exc.reason == "invalid_grant"
                    else "refresh_failed"
                )
                updated = replace(
                    health,
                    status=state,
                    health_reason=exc.reason,
                    last_health_check=now,
                    revoked_at=now if state == "revoked" else health.revoked_at,
                )
                if state == "revoked":
                    self.vault.revoke(cid, secret.generation, updated)
                else:
                    self.vault.mark(cid, secret.generation, updated)
                raise BrokerError(exc.reason) from None

    def revoke(self) -> dict[str, Any]:
        cid = "gmail_known_threads"
        with self.vault.lock(cid):
            health, secret = self.vault.read(cid)
            health = replace(
                health, status="revoked", revoked_at=self.clock(), health_reason="revoked"
            )
            if secret is not None:
                # Local revoke is fail-closed even if provider is down.
                if not self.vault.revoke(cid, secret.generation, health):
                    raise BrokerError("refresh_race")
                self.transport.request(
                    "POST", REVOKE_ENDPOINT, data={"token": secret.refresh_token}
                )
            return health.public()


class RenderReadBroker:
    def __init__(self, transport: FixedTransport, upstream: PrivateCredential):
        self.transport, self.upstream = transport, upstream

    def read(
        self, *, service_id: str, method: str = "GET", path: str = "deploys"
    ) -> list[dict[str, Any]]:
        if (service_id, method, path) != (RENDER_SERVICE, "GET", "deploys"):
            raise BrokerError("scope_mismatch")
        if not self.upstream.access_token:
            raise BrokerError("missing_configuration")
        response = self.transport.request(
            "GET",
            f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys",
            params={"limit": 20},
            headers={"Authorization": "Bearer " + self.upstream.access_token},
        )
        if not isinstance(response, list) or len(response) > 20:
            raise BrokerError("invalid_response")
        import re

        result = []
        for item in response:
            if not isinstance(item, dict):
                raise BrokerError("invalid_response")
            deploy = item.get("deploy", item)
            if not isinstance(deploy, dict) or not re.fullmatch(
                r"dep-[a-z0-9]+", str(deploy.get("id", ""))
            ):
                raise BrokerError("invalid_response")
            if deploy.get("serviceId", RENDER_SERVICE) != RENDER_SERVICE:
                raise BrokerError("scope_mismatch")
            commit = deploy.get("commit", {})
            sha = commit.get("id") if isinstance(commit, dict) else None
            if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise BrokerError("invalid_response")
            status = deploy.get("status")
            if status not in {
                "live",
                "created",
                "queued",
                "build_in_progress",
                "update_in_progress",
                "pre_deploy_in_progress",
                "build_failed",
                "update_failed",
                "pre_deploy_failed",
                "canceled",
                "deactivated",
            }:
                raise BrokerError("invalid_response")
            times = {}
            for name in ("createdAt", "updatedAt", "startedAt", "finishedAt"):
                value = deploy.get(name)
                if value is not None:
                    if not isinstance(value, str) or len(value) > 40:
                        raise BrokerError("invalid_response")
                    try:
                        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        raise BrokerError("invalid_response") from None
                    if parsed.utcoffset() is None:
                        raise BrokerError("invalid_response")
                times[name] = value
            result.append(
                {
                    "deployment_id": deploy["id"],
                    "service_id": RENDER_SERVICE,
                    "commit_sha": sha,
                    "status": status,
                    "timestamps": times,
                }
            )
        return result


class GmailKnownThreadBroker:
    def __init__(
        self,
        transport: FixedTransport,
        credential: PrivateCredential,
        health: CredentialMetadata,
        now: datetime,
    ):
        if (
            health.provider != "gmail"
            or health.health(now, secret_present=bool(credential.access_token)) != "healthy"
        ):
            raise BrokerError("expired")
        self.transport, self.credential = transport, credential

    def read(self, thread_id: str, history_id: str | None = None) -> dict[str, Any]:
        import re

        if thread_id not in KNOWN_THREADS:
            raise BrokerError("scope_mismatch")
        headers = {"Authorization": "Bearer " + self.credential.access_token}
        if history_id is not None:
            if not re.fullmatch(r"[0-9]{1,30}", history_id):
                raise BrokerError("invalid_response")
            matched = False
            page_token = None
            seen_pages = set()
            for _ in range(4):
                params = {
                    "startHistoryId": history_id,
                    "historyTypes": "messageAdded",
                    "maxResults": 100,
                }
                if page_token:
                    params["pageToken"] = page_token
                raw = self.transport.request(
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/history",
                    params=params,
                    headers=headers,
                )
                if not isinstance(raw, dict) or not re.fullmatch(
                    r"[0-9]{1,30}", str(raw.get("historyId", ""))
                ):
                    raise BrokerError("invalid_response")
                records = raw.get("history", [])
                if not isinstance(records, list) or len(records) > 100:
                    raise BrokerError("invalid_response")
                # Foreign IDs are discarded locally, before any durable evidence.
                for event in records:
                    if not isinstance(event, dict) or not isinstance(
                        event.get("messagesAdded", []), list
                    ):
                        raise BrokerError("invalid_response")
                    for entry in event.get("messagesAdded", []):
                        if not isinstance(entry, dict) or not isinstance(
                            entry.get("message"), dict
                        ):
                            raise BrokerError("invalid_response")
                        message = entry["message"]
                        if message.get("threadId") == thread_id and not set(
                            message.get("labelIds", [])
                        ) & {"SENT", "DRAFT"}:
                            matched = True
                page_token = raw.get("nextPageToken")
                if not page_token:
                    if matched:
                        # Read known-thread metadata; never persist raw history IDs.
                        return self.read(thread_id)
                    return {"thread_id": thread_id, "history_id": raw["historyId"], "messages": []}
                if (
                    not isinstance(page_token, str)
                    or len(page_token) > 512
                    or page_token in seen_pages
                ):
                    raise BrokerError("invalid_response")
                seen_pages.add(page_token)
            # No partial-page cursor is ever persisted as completion.
            raise BrokerError("invalid_response")
        raw = self.transport.request(
            "GET",
            f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
            params={"format": "metadata", "metadataHeaders": ["From", "Content-Type"]},
            headers=headers,
        )
        if (
            not isinstance(raw, dict)
            or raw.get("id") != thread_id
            or not re.fullmatch(r"[0-9]{1,30}", str(raw.get("historyId", "")))
        ):
            raise BrokerError("invalid_response")
        messages = raw.get("messages")
        if not isinstance(messages, list) or len(messages) > 100:
            raise BrokerError("invalid_response")
        result = []
        for message in messages:
            if not isinstance(message, dict) or message.get("threadId") != thread_id:
                raise BrokerError("invalid_response")
            if set(message.get("labelIds", [])) & {"SENT", "DRAFT"}:
                continue
            if not re.fullmatch(r"[a-f0-9]{1,32}", str(message.get("id", ""))) or not re.fullmatch(
                r"[0-9]{1,16}", str(message.get("internalDate", ""))
            ):
                raise BrokerError("invalid_response")
            from email.utils import parseaddr

            sender, content_type = "", ""
            for h in message.get("payload", {}).get("headers", []):
                if h.get("name", "").lower() == "from":
                    candidate = parseaddr(str(h.get("value", ""))[:320])[1].lower()
                    if re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", candidate):
                        sender = candidate
                if h.get("name", "").lower() == "content-type":
                    content_type = str(h.get("value", ""))[:160]
            bounce = (
                any(part in sender.lower() for part in ("mailer-daemon", "postmaster"))
                or "delivery-status" in content_type.lower()
            )
            result.append(
                {
                    "message_id": message["id"],
                    "thread_id": thread_id,
                    "internal_date": message["internalDate"],
                    "sender": sender,
                    "content_type": content_type.split(";", 1)[0].strip().lower()
                    if re.fullmatch(r"[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+(?:;[^\r\n]*)?", content_type)
                    else "",
                    "delivery_failure": bounce,
                }
            )
        return {"thread_id": thread_id, "history_id": raw["historyId"], "messages": result}
