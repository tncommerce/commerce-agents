from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class MerchantFeedAdapter(Protocol):
    provider_name: str

    def adapt_row(self, payload: dict) -> dict: ...


class CanonicalMerchantFeedAdapter:
    provider_name = "canonical"

    def adapt_row(self, payload: dict) -> dict:
        return dict(payload)


_ADAPTERS: dict[str, MerchantFeedAdapter] = {
    "canonical": CanonicalMerchantFeedAdapter(),
}


def available_providers() -> list[str]:
    return sorted(_ADAPTERS)


def get_provider_adapter(provider: str) -> MerchantFeedAdapter:
    key = provider.strip().casefold()

    try:
        return _ADAPTERS[key]
    except KeyError as exc:
        supported = ", ".join(available_providers())
        raise ValueError(
            f"Unsupported merchant feed provider: {provider}. Supported providers: {supported}"
        ) from exc


def adapt_provider_rows(
    provider: str,
    payloads: list[dict],
) -> list[dict]:
    adapter = get_provider_adapter(provider)
    return [adapter.adapt_row(payload) for payload in payloads]


class MappedMerchantFeedAdapter:
    def __init__(
        self,
        *,
        provider_name: str,
        field_map: dict[str, str],
        constants: dict | None = None,
    ) -> None:
        self.provider_name = provider_name.strip().casefold()
        self.field_map = dict(field_map)
        self.constants = dict(constants or {})

    def adapt_row(self, payload: dict) -> dict:
        adapted = {
            canonical_field: payload[source_field]
            for canonical_field, source_field in self.field_map.items()
            if source_field in payload
        }

        adapted.update(self.constants)

        return adapted


def register_provider_adapter(
    adapter: MerchantFeedAdapter,
    *,
    replace: bool = False,
) -> None:
    key = adapter.provider_name.strip().casefold()

    if not key:
        raise ValueError("Merchant feed provider name cannot be empty")

    if key in _ADAPTERS and not replace:
        raise ValueError(f"Merchant feed provider already registered: {key}")

    _ADAPTERS[key] = adapter


def load_mapped_provider_adapter(path: Path) -> MappedMerchantFeedAdapter:
    """Load a provider field mapping from JSON without hard-coding network columns.

    This keeps SCENTAI independent from Awin/CJ export schemas until an approved,
    real feed sample is available. The config maps external feed column names to
    SCENTAI's canonical merchant contract.
    """

    raw = json.loads(path.read_text(encoding="utf-8-sig"))

    provider_name = str(raw.get("provider_name") or "").strip()
    field_map = raw.get("field_map")
    constants = raw.get("constants", {})

    if not provider_name:
        raise ValueError("Provider config requires provider_name")

    if not isinstance(field_map, dict) or not field_map:
        raise ValueError("Provider config requires a non-empty field_map")

    if not isinstance(constants, dict):
        raise ValueError("Provider config constants must be an object")

    invalid_fields = [
        key
        for key, value in field_map.items()
        if not isinstance(key, str)
        or not isinstance(value, str)
        or not key.strip()
        or not value.strip()
    ]
    if invalid_fields:
        raise ValueError("Provider config field_map must contain non-empty string keys and values")

    return MappedMerchantFeedAdapter(
        provider_name=provider_name,
        field_map=field_map,
        constants=constants,
    )
