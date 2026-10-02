"""Private encrypted state. Firestore CAS is the production adapter; no control-plane key."""

from __future__ import annotations

import base64
import json
import re
import secrets
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from threading import local

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from scripts.dufynd_observer_credentials import (
    BrokerError,
    CredentialMetadata,
    PrivateCredential,
    metadata,
)


class FirestoreCAS:
    def __init__(self, project: str, client: httpx.Client):
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
            raise BrokerError("missing_configuration")
        self.base = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/broker"
        self.client = client

    def request(self, method, url, **kwargs):
        try:
            identity = self.client.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
                timeout=2,
                follow_redirects=False,
            )
            identity.raise_for_status()
            response = self.client.request(
                method,
                url,
                headers={"Authorization": "Bearer " + identity.json()["access_token"]},
                timeout=5,
                follow_redirects=False,
                **kwargs,
            )
            if response.status_code in {404, 409, 412}:
                return response
            response.raise_for_status()
            return response
        except Exception:
            raise BrokerError("provider_outage") from None

    def get(self, key):
        self.check_key(key)
        response = self.request("GET", self.base + "/" + key)
        if response.status_code == 404:
            return None, None
        try:
            body = response.json()
            return body["fields"]["ciphertext"]["stringValue"], body["updateTime"]
        except Exception:
            raise BrokerError("invalid_response") from None

    def cas(self, key, version, value):
        self.check_key(key)
        condition = (
            {"currentDocument.updateTime": version}
            if version
            else {"currentDocument.exists": "false"}
        )
        response = self.request(
            "PATCH",
            self.base + "/" + key,
            params=condition,
            json={"fields": {"ciphertext": {"stringValue": value}}},
        )
        return response.status_code == 200

    @staticmethod
    def check_key(key):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", key):
            raise BrokerError("invalid_response")


class EncryptedVault:
    def __init__(self, backend, key: bytes, clock=time.time):
        if len(key) != 32:
            raise BrokerError("missing_configuration")
        self.backend, self.cipher, self.clock = backend, AESGCM(key), clock
        self.held = local()

    def get(self, key):
        raw, version = self.backend.get(key)
        if raw is None:
            return {}, version
        try:
            encoded = base64.b64decode(raw, validate=True)
            return json.loads(
                self.cipher.decrypt(encoded[:12], encoded[12:], key.encode())
            ), version
        except Exception:
            raise BrokerError("invalid_response") from None

    def cas(self, key, version, value):
        nonce = secrets.token_bytes(12)
        raw = json.dumps(value, separators=(",", ":")).encode()
        encoded = base64.b64encode(nonce + self.cipher.encrypt(nonce, raw, key.encode())).decode()
        return self.backend.cas(key, version, encoded)

    @contextmanager
    def lock(self, cid):
        owner = secrets.token_hex(16)
        row, version = self.get(cid)
        if row.get("lease_until", 0) > self.clock():
            raise BrokerError("refresh_race")
        row.update(lease_owner=owner, lease_until=self.clock() + 90)
        if not self.cas(cid, version, row):
            raise BrokerError("refresh_race")
        self.held.owner = owner
        try:
            yield
        finally:
            row, version = self.get(cid)
            if row.get("lease_owner") == owner:
                row.update(lease_owner="", lease_until=0)
                self.cas(cid, version, row)
            self.held.owner = None

    def read(self, cid):
        row, _ = self.get(cid)
        provider = "gmail" if cid == "gmail_known_threads" else "render"
        health = metadata(provider)
        if row.get("health"):
            values = row["health"]
            for name in (
                "expires_at",
                "refreshed_at",
                "revoked_at",
                "last_health_check",
                "rotation_due_at",
            ):
                if values.get(name):
                    values[name] = datetime.fromisoformat(values[name])
            for name in ("allowed_operations", "allowed_resources", "oauth_scopes"):
                values[name] = tuple(values[name])
            health = CredentialMetadata(**values)
            health.validate()
        return health, PrivateCredential(**row["secret"]) if row.get("secret") else None

    def update(self, cid, generation, health, secret, *, replace_secret=True):
        row, version = self.get(cid)
        if (
            row.get("lease_owner") != getattr(self.held, "owner", None)
            or row.get("lease_until", 0) <= self.clock()
            or row.get("generation", 0) != generation
        ):
            return False
        row["health"] = health.public()
        if replace_secret:
            row["secret"] = asdict(secret) if secret else None
            row["generation"] = generation + 1
        return self.cas(cid, version, row)

    def rotate(self, cid, generation, secret, health):
        if secret.generation != generation + 1:
            return False
        return self.update(cid, generation, health, secret)

    def mark(self, cid, generation, health):
        return self.update(cid, generation, health, None, replace_secret=False)

    def revoke(self, cid, generation, health):
        return self.update(cid, generation, health, None)

    def thread_state(self, thread_id):
        row, _ = self.get("gmail_known_threads")
        return row.get("threads", {}).get(thread_id, {})

    def commit_thread(self, thread_id, generation, state):
        row, version = self.get("gmail_known_threads")
        if (
            row.get("lease_owner") != getattr(self.held, "owner", None)
            or row.get("lease_until", 0) <= self.clock()
            or row.get("generation", 0) != generation
        ):
            return False
        row.setdefault("threads", {})[thread_id] = state
        return self.cas("gmail_known_threads", version, row)
