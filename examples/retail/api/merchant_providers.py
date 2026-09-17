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
