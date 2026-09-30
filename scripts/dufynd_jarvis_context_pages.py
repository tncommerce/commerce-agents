"""Bound model-facing knowledge reads without dropping source evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PAGE_CHARS = 10000


def serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def context_overview(payload: dict[str, Any]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else key)
        else:
            sections.append(
                {
                    "section": path,
                    "type": type(value).__name__,
                    "items": len(value) if isinstance(value, list) else None,
                }
            )

    walk(payload, "")
    # Context keys are server-defined. Still bound the inventory itself if a
    # future RPC adds many nested sections; the root can always be paged.
    visible: list[dict[str, Any]] = []
    for section in sections:
        if len(serialized([*visible, section])) > PAGE_CHARS:
            break
        visible.append(section)
    return {
        "sections": visible,
        "section_count": len(sections),
        "inventory_complete": len(visible) == len(sections),
        "next_action": "Use load_context_page with context and section; empty section reads the root.",
    }


def context_page(
    payload: dict[str, Any], *, section: str = "", offset: int = 0
) -> tuple[dict[str, Any], str]:
    value: Any = payload
    for key in section.split(".") if section else []:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Unknown context section: {section}")
        value = value[key]
    document = serialized(value)
    if offset < 0 or offset > len(document):
        raise ValueError("Context offset is outside the selected section")
    end = min(offset + PAGE_CHARS, len(document))
    metadata = {
        "section": section,
        "offset": offset,
        "next_offset": end if end < len(document) else None,
        "total_chars": len(document),
        "sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        "format": "JSON text fragment; concatenate pages in offset order. Restart if sha256 changes.",
    }
    return metadata, document[offset:end]
