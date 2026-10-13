"""Connected Metricool tool entry point. Public dispatch always uses SQL GO gates.

The host supplies its authenticated connected-tool callable; no paid API token.
Other hosts can still invoke Metricool directly: this is not a global MCP ACL.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from scripts.dufynd_publish_orchestrator import (
    PublishBlocked,
    PublishOrchestrator,
    audit_media,
)

TOOL = "mcp__codex_apps__metricool_createscheduledpost"
MANUAL_MANIFEST_KEY = "content.manual_delivery_bindings_v1"
MANUAL_ADAPTER_VERSION = "manual-delivery/1"


def _private_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def sync_connected_manual_deliveries(bridge, *, call_tool, manifest_sha256, now=None):
    """Bounded readback -> existing SQL exclusions. Never writes to Metricool.

    The private manifest is a pinned handoff on existing master status, not a
    queue or publication GO. Missing identities, incomplete inventory or an
    uncertain DB response stop the caller. Repeating this observation is safe;
    it never means repeating a provider publication.
    """
    try:
        if not isinstance(manifest_sha256, str) or not re.fullmatch(
            r"[a-f0-9]{64}", manifest_sha256
        ):
            raise ValueError("pin missing")
        row = bridge.load_master_status_entry(MANUAL_MANIFEST_KEY)
        manifest = row["value"]
        if _private_digest(manifest) != manifest_sha256:
            raise ValueError("pin changed")
        if (
            type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
            or manifest["brand_id"] != "7182186"
            or set(manifest) != {"schema_version", "brand_id", "from_date", "to_date", "bindings"}
        ):
            raise ValueError("contract changed")
        start, end = (datetime.fromisoformat(manifest[k]) for k in ("from_date", "to_date"))
        current = now or datetime.now(UTC)
        if (
            start.utcoffset() is None
            or end.utcoffset() is None
            or not start <= current <= end
            or not 0 < (end - start).total_seconds() <= 604800
        ):
            raise ValueError("window invalid")
        entries = manifest["bindings"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
            raise ValueError("bounded nonempty manifest required")
        bindings, media, seen = [], [], set()
        for entry in entries:
            if set(entry) != {"source_key", "source_sha256", "binding"}:
                raise ValueError("source contract")
            if not re.fullmatch(r"content\.[A-Za-z0-9_.:-]{1,180}", entry["source_key"]):
                raise ValueError("private source key")
            source = bridge.load_master_status_entry(entry["source_key"])["value"]
            if _private_digest(source) != entry["source_sha256"]:
                raise ValueError("source changed")
            binding = entry["binding"]
            if set(binding) != {
                "content_id",
                "asset_sha256",
                "platform",
                "provider_post_id",
                "provider_uuid",
            }:
                raise ValueError("binding contract")
            # Never invent a content ID from caption, date, planner ID or hash.
            if source.get("content_id") != binding["content_id"]:
                raise ValueError("canonical content id unavailable")
            source_hash = (
                source.get("asset_sha256")
                or source.get("frozen_asset", {}).get("source_expected_sha256")
                or source.get("asset", {}).get("source_sha256")
            )
            if not source_hash or source_hash != binding["asset_sha256"]:
                raise ValueError("frozen hash unavailable")
            delivery = source.get("metricool_delivery", source.get("platform_schedule", {})).get(
                binding["platform"], {}
            )
            if str(delivery.get("id", delivery.get("metricool_id"))) != str(
                binding["provider_post_id"]
            ) or str(delivery.get("uuid")) != str(binding["provider_uuid"]):
                raise ValueError("provider source binding missing")
            uri = source.get("media_integrity", {}).get("metricool_media_url") or source.get(
                "asset", {}
            ).get("metricool_media")
            if not isinstance(uri, str) or not uri.startswith("https://"):
                raise ValueError("source media missing")
            for identity in ("content_id", "asset_sha256", "provider_post_id", "provider_uuid"):
                token = (binding["platform"], identity, str(binding[identity]))
                if token in seen:
                    raise ValueError("duplicate binding")
                seen.add(token)
            bindings.append(binding)
            media.append(uri)
        if bridge._rpc("dufynd_manual_guard_ready_v1", {}) is not True:
            raise ValueError("guard unavailable")
        response = unwrap_tool_result(
            call_tool(
                "mcp__codex_apps__metricool_getscheduledposts",
                {
                    "brandId": "7182186",
                    "fromDate": manifest["from_date"],
                    "toDate": manifest["to_date"],
                    "timezone": "Europe/Berlin",
                    "extendedRange": False,
                },
            )
        )
        if set(response) != {"data"}:
            raise ValueError("unrecognized pagination or response contract")
        data = response["data"]
        if not isinstance(data, list) or len(data) != len(bindings):
            raise ValueError("inventory incomplete or unbound")
        selected = []
        for binding, uri in zip(bindings, media, strict=True):
            matches = [
                p
                for p in data
                if isinstance(p, dict)
                and str(p.get("id")) == str(binding["provider_post_id"])
                and str(p.get("uuid")) == str(binding["provider_uuid"])
            ]
            if len(matches) != 1 or matches[0].get("media") != [uri]:
                raise ValueError("provider identity missing or ambiguous")
            selected.append(matches[0])
        runner = PublishOrchestrator(bridge, ffmpeg="unused")
        receipts = []
        for binding, post in zip(bindings, selected, strict=True):
            receipt = runner.record_manual_delivery(
                binding, post, evidence_ref="manifest:" + manifest_sha256
            )
            if (
                not isinstance(receipt, dict)
                or receipt.get("recorded") is not True
                or receipt.get("auto_publish_allowed") is not False
                or receipt.get("state")
                not in {"MANUAL_PENDING", "MANUAL_PUBLISHED", "MANUAL_UNKNOWN"}
                or receipt.get("existing_dispatch_requires_reconciliation") is not False
            ):
                raise ValueError("manual receipt uncertain or needs reconciliation")
            receipts.append(receipt)
        return {
            "adapter_version": MANUAL_ADAPTER_VERSION,
            "manifest_sha256": manifest_sha256,
            "exclusions_recorded": len(receipts),
            "provider_writes": 0,
        }
    except Exception:
        # No upstream exception text (tokens, source packets, URLs) reaches logs.
        # Previously committed exclusions intentionally survive a later failure.
        raise PublishBlocked("manual_delivery_preflight_hold") from None


def verify_hosted_bytes(
    uri: str, digest: str, *, review_only: bool = False, transport=None
) -> bool:
    url = urlsplit(uri)
    allowed = {"dufynd.de", "bqsdxaagklpkxioaqdqa.supabase.co"}
    if review_only:
        allowed.add("d2ol7oe51mr4n9.cloudfront.net")
    if (
        url.scheme != "https"
        or url.hostname not in allowed
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.query
        or url.fragment
        or not re.fullmatch(r"[a-f0-9]{64}", digest)
    ):
        return False
    hasher, size = hashlib.sha256(), 0
    with (
        httpx.Client(timeout=60, follow_redirects=False, transport=transport) as client,
        client.stream("GET", uri) as response,
    ):
        response.raise_for_status()
        if response.status_code != 200:
            return False
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > 300_000_000:
                return False
            hasher.update(chunk)
    return size > 0 and hasher.hexdigest() == digest


def unwrap_tool_result(result: dict) -> dict:
    if not isinstance(result, dict) or result.get("isError"):
        raise PublishBlocked("metricool_tool_error_no_retry")
    data = result.get("structuredContent")
    if isinstance(data, dict) and "data" in data:
        return data
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                data = json.loads(item["text"])
            except (ValueError, KeyError):
                continue
            if isinstance(data, dict) and "data" in data:
                return data
    raise PublishBlocked("metricool_receipt_missing_no_retry")


def dispatch_connected_metricool(
    bridge,
    *,
    call_tool: Callable[[str, dict], dict],
    ffmpeg: str,
    asset_id: str,
    path: Path,
    decision_id: str,
    verify_hosted_media: Callable[[str, str], bool],
    manual_manifest_sha256: str | None = None,
) -> dict:
    """Bind the real named connector behind prepare/hash/reserve/GO/receipt.

    call_tool must complete synchronously once; the host must not retry it.
    Unknown outcomes are durably held by PublishOrchestrator.
    """

    sync_connected_manual_deliveries(
        bridge, call_tool=call_tool, manifest_sha256=manual_manifest_sha256
    )

    def schedule(args):
        # mediaFiles is the desktop attachment uploader, not a URL list.
        # Metricool ingests the already hash-verified URL from info.media.
        args = {k: v for k, v in args.items() if k != "mediaFiles"}
        return unwrap_tool_result(call_tool(TOOL, args))

    return PublishOrchestrator(
        bridge,
        ffmpeg=ffmpeg,
        metricool_schedule=schedule,
    ).dispatch(
        asset_id,
        path,
        decision_id,
        verify_hosted_media=verify_hosted_media,
    )


def private_draft_arguments(
    *,
    path: Path,
    ffmpeg: str,
    uri: str,
    caption: str,
    date: str,
    verify_hosted_media: Callable[[str, str], bool],
) -> dict:
    """Review import only. No schedule, notification or owner GO fabrication."""
    report = audit_media(path, ffmpeg=ffmpeg)
    if (
        not uri.startswith("https://")
        or verify_hosted_media(uri, report["asset_sha256"]) is not True
    ):
        raise PublishBlocked("draft_hosted_bytes_unverified")
    info = {
        "text": caption,
        "providers": [{"network": "instagram"}],
        "media": [uri],
        "draft": True,
        "autoPublish": False,
        "saveExternalMediaFiles": True,
        "shortener": False,
        "publicationDate": {"dateTime": date[:19], "timezone": "Europe/Berlin"},
        "instagramData": {
            "type": "REEL",
            "autoPublish": False,
            "showReelOnFeed": True,
            "isAiGenerated": True,
        },
    }
    return {"blogId": "7182186", "date": date, "info": json.dumps(info, ensure_ascii=False)}


def verify_private_draft(result: dict) -> dict:
    data = unwrap_tool_result(result)["data"]
    if isinstance(data, list):
        if len(data) != 1:
            raise PublishBlocked("draft_receipt_ambiguous_no_retry")
        data = data[0]
    if not isinstance(data, dict) or not data.get("id"):
        raise PublishBlocked("draft_receipt_missing_no_retry")
    if data.get("draft") is not True or data.get("autoPublish") is not False:
        raise PublishBlocked("draft_flags_not_confirmed_reconcile_immediately")
    if data.get("instagramData", {}).get("autoPublish") is not False:
        raise PublishBlocked("draft_ig_flags_not_confirmed_reconcile_immediately")
    if any(
        p.get("publicUrl") or p.get("status") in {"PUBLISHED", "SENT"}
        for p in data.get("providers", [])
    ):
        raise PublishBlocked("draft_publication_state_unexpected")
    return {
        "id": data["id"],
        "uuid": data.get("uuid"),
        "media": data.get("media"),
        "draft": True,
        "publication_verified": False,
    }


def dispatch_connected_release(
    bridge,
    *,
    call_tool,
    ffmpeg,
    release_id,
    paths,
    decisions,
    verify_hosted_media,
    manual_manifest_sha256=None,
):
    """Production three-platform entry point; requires concrete SQL Owner GO."""
    from scripts.dufynd_publish_orchestrator import ReleaseOrchestrator

    sync_connected_manual_deliveries(
        bridge, call_tool=call_tool, manifest_sha256=manual_manifest_sha256
    )

    try:
        verify_release_connections(call_tool("mcp__codex_apps__metricool_getbrandsettings", {}))
    except Exception:
        bridge._rpc(
            "block_dufynd_release_preflight_v1",
            {
                "p_release_id": release_id,
                "p_errors": {
                    p: "metricool_brand_or_connection_unverified"
                    for p in ("youtube", "instagram", "tiktok")
                },
            },
        )
        raise PublishBlocked("all_three_metricool_connections_required") from None

    def schedule(args):
        args = {k: v for k, v in args.items() if k != "mediaFiles"}
        return unwrap_tool_result(call_tool(TOOL, args))

    return ReleaseOrchestrator(bridge, ffmpeg=ffmpeg, metricool_schedule=schedule).dispatch_release(
        release_id,
        paths,
        decisions,
        verify_hosted_media=verify_hosted_media,
    )


def record_release_verification(bridge, *, release_id, packet, provider, media, playback=None):
    """Persist PUBLISHED separately; AUDIO_VERIFIED needs independent listening."""
    from scripts.dufynd_publish_orchestrator import verify_platform_media, verify_publication

    evidence = verify_platform_media(packet, provider, media)
    args = {
        "p_release_id": release_id,
        "p_platform": packet["platform"],
        "p_state": "PUBLISHED",
        "p_evidence": evidence,
    }
    if bridge._rpc("record_dufynd_release_publication_v1", args) is not True:
        raise PublishBlocked("publication_evidence_not_saved")
    if playback is None:
        return {"state": "PUBLISHED", "audio_verified": False}
    verify_publication(packet, provider, playback)
    if playback.get("platform_output_sha256") != media["platform_output_sha256"]:
        raise PublishBlocked("audio_output_identity_changed")
    args.update(p_state="AUDIO_VERIFIED", p_evidence={**evidence, **playback})
    if bridge._rpc("record_dufynd_release_publication_v1", args) is not True:
        raise PublishBlocked("audio_evidence_not_saved")
    return {"state": "AUDIO_VERIFIED", "audio_verified": True}


def verify_release_connections(response):
    """Read current brand connections without creating or changing any post."""
    data = unwrap_tool_result(response).get("data")
    if not isinstance(data, list):
        raise PublishBlocked("metricool_brands_unverified")
    brand = next((b for b in data if str(b.get("id")) == "7182186"), {})
    connected = brand.get("networksData", {})
    expected = {
        "instagramData": "dufynd",
        "tiktokData": "dufynd",
        "youtubeData": "UCQooXN4sOeMsEG-43qaH0aA",
    }
    if brand.get("timezone") != "Europe/Berlin" or any(
        connected.get(k) != v for k, v in expected.items()
    ):
        raise PublishBlocked("metricool_connection_missing_or_target_changed")
    return True
