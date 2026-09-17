from __future__ import annotations

from typing import Protocol


class MerchantFeedAdapter(Protocol):
    provider_name: str

    def adapt_row(self, payload: dict) -> dict:
        ...


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
            f"Unsupported merchant feed provider: {provider}. "
            f"Supported providers: {supported}"
        ) from exc


def adapt_provider_rows(
    provider: str,
    payloads: list[dict],
) -> list[dict]:
    adapter = get_provider_adapter(provider)
    return [
        adapter.adapt_row(payload)
        for payload in payloads
    ]


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
            for canonical_field, source_field
            in self.field_map.items()
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
        raise ValueError(
            "Merchant feed provider name cannot be empty"
        )

    if key in _ADAPTERS and not replace:
        raise ValueError(
            f"Merchant feed provider already registered: {key}"
        )

    _ADAPTERS[key] = adapter
