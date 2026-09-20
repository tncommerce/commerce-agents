from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass
class SmokeCheck:
    name: str
    ok: bool
    status_code: int | None
    detail: str


@dataclass
class SmokeReport:
    storefront_url: str
    api_url: str
    checks: list[SmokeCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "storefront_url": self.storefront_url,
            "api_url": self.api_url,
            "checks": [asdict(check) for check in self.checks],
        }


def _normalize_base_url(value: str, *, field: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = httpx.URL(normalized)
    if parsed.scheme not in {"https", "http"} or not parsed.host:
        raise ValueError(f"{field} must be an absolute http(s) URL")
    return normalized


def _check_storefront(
    client: httpx.Client,
    storefront_url: str,
) -> SmokeCheck:
    try:
        response = client.get(storefront_url, follow_redirects=True)
        status_ok = response.status_code < 400
        brand_ok = "dufynd" in response.text.casefold()
        ok = status_ok and brand_ok
        if not status_ok:
            detail = f"Storefront returned HTTP {response.status_code}."
        elif not brand_ok:
            detail = "Storefront response did not contain the DUFYND brand marker."
        else:
            detail = "Storefront responded successfully with the DUFYND brand marker."
        return SmokeCheck(
            name="storefront",
            ok=ok,
            status_code=response.status_code,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="storefront",
            ok=False,
            status_code=None,
            detail=f"Storefront request failed: {exc.__class__.__name__}",
        )


def _check_api_health(
    client: httpx.Client,
    api_url: str,
) -> SmokeCheck:
    url = f"{api_url}/api/health"
    try:
        response = client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return SmokeCheck(
                name="api_health",
                ok=False,
                status_code=response.status_code,
                detail=f"API health returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError:
            return SmokeCheck(
                name="api_health",
                ok=False,
                status_code=response.status_code,
                detail="API health did not return JSON.",
            )

        ok = payload == {
            "ok": True,
            "service": "dufynd-api",
        }
        return SmokeCheck(
            name="api_health",
            ok=ok,
            status_code=response.status_code,
            detail=(
                "DUFYND API health payload is valid."
                if ok
                else "API health payload does not identify the DUFYND API."
            ),
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="api_health",
            ok=False,
            status_code=None,
            detail=f"API health request failed: {exc.__class__.__name__}",
        )


def _check_merchant_partners(
    client: httpx.Client,
    api_url: str,
) -> SmokeCheck:
    url = f"{api_url}/api/merchant-partners"
    try:
        response = client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return SmokeCheck(
                name="merchant_partners",
                ok=False,
                status_code=response.status_code,
                detail=f"Merchant partners returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError:
            return SmokeCheck(
                name="merchant_partners",
                ok=False,
                status_code=response.status_code,
                detail="Merchant partners did not return JSON.",
            )

        partners = payload.get("partners")
        disclosure = payload.get("affiliate_disclosure")
        ok = isinstance(partners, list) and isinstance(disclosure, str)
        return SmokeCheck(
            name="merchant_partners",
            ok=ok,
            status_code=response.status_code,
            detail=(
                f"Merchant partner contract is valid ({len(partners)} rows)."
                if ok
                else "Merchant partner payload is missing its expected contract."
            ),
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="merchant_partners",
            ok=False,
            status_code=None,
            detail=f"Merchant partner request failed: {exc.__class__.__name__}",
        )


def run_smoke(
    *,
    storefront_url: str,
    api_url: str,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 12.0,
) -> SmokeReport:
    storefront = _normalize_base_url(
        storefront_url,
        field="storefront_url",
    )
    api = _normalize_base_url(
        api_url,
        field="api_url",
    )

    with httpx.Client(
        timeout=timeout_seconds,
        transport=transport,
    ) as client:
        checks = [
            _check_storefront(client, storefront),
            _check_api_health(client, api),
            _check_merchant_partners(client, api),
        ]

    return SmokeReport(
        storefront_url=storefront,
        api_url=api,
        checks=checks,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only smoke test against the live DUFYND storefront and API."
    )
    parser.add_argument(
        "--storefront-url",
        default="https://dufynd.de",
    )
    parser.add_argument(
        "--api-url",
        default="https://scentai-api-kxhe.onrender.com",
        help="Public DUFYND API base URL, without a trailing slash.",
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        report = run_smoke(
            storefront_url=args.storefront_url,
            api_url=args.api_url,
        )
    except ValueError as exc:
        parser.error(str(exc))

    payload = report.to_dict()
    if args.machine_readable:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            "DUFYND production smoke | "
            f"ok={payload['ok']} | "
            f"checks={sum(check.ok for check in report.checks)}/"
            f"{len(report.checks)}"
        )
        for check in report.checks:
            marker = "PASS" if check.ok else "FAIL"
            print(f"  {marker} {check.name}: {check.detail}")

    return 0 if report.ok else 20


if __name__ == "__main__":
    raise SystemExit(main())
