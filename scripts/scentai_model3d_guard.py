from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

MAX_GLB_BYTES = 15 * 1024 * 1024
MODEL_PREFIX = "/products/models/"


def normalize_model_url(value: object) -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith(MODEL_PREFIX) or candidate.startswith("//"):
        raise ValueError("model_url_must_be_local_products_model_glb")

    parsed = urlparse(candidate)
    decoded_path = unquote(parsed.path)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in decoded_path
        or ".." in PurePosixPath(decoded_path).parts
        or not decoded_path.lower().endswith(".glb")
    ):
        raise ValueError("model_url_must_be_local_products_model_glb")

    return decoded_path


def public_model_path(public_root: Path, model_url: str) -> Path:
    normalized = normalize_model_url(model_url)
    return public_root / normalized.removeprefix("/")


def validate_glb_bytes(payload: bytes) -> None:
    if len(payload) < 12:
        raise ValueError("glb_header_truncated")
    if len(payload) > MAX_GLB_BYTES:
        raise ValueError("glb_exceeds_launch_budget")
    if payload[:4] != b"glTF":
        raise ValueError("glb_magic_invalid")
    if int.from_bytes(payload[4:8], "little") != 2:
        raise ValueError("glb_version_unsupported")
    if int.from_bytes(payload[8:12], "little") != len(payload):
        raise ValueError("glb_declared_length_mismatch")


def validated_model_sha256(public_root: Path, model_url: str) -> str:
    path = public_model_path(public_root, model_url)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError("model_asset_missing") from exc
    validate_glb_bytes(payload)
    return hashlib.sha256(payload).hexdigest()
