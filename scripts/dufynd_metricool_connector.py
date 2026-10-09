"""Connected Metricool tool entry point. Public dispatch always uses SQL GO gates.

The host supplies its authenticated connected-tool callable; no paid API token.
Other hosts can still invoke Metricool directly: this is not a global MCP ACL.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from scripts.dufynd_publish_orchestrator import (
    PublishBlocked,
    PublishOrchestrator,
    audit_media,
)

TOOL = "mcp__codex_apps__metricool_createscheduledpost"


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
) -> dict:
    """Bind the real named connector behind prepare/hash/reserve/GO/receipt.

    call_tool must complete synchronously once; the host must not retry it.
    Unknown outcomes are durably held by PublishOrchestrator.
    """

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
