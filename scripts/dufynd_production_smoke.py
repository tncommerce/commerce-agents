from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote

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


def _check_storefront_route(
    client: httpx.Client,
    storefront_url: str,
    *,
    path: str,
    name: str,
) -> SmokeCheck:
    url = f"{storefront_url}{path}"
    try:
        response = client.get(url, follow_redirects=True)
        status_ok = response.status_code < 400
        brand_ok = "dufynd" in response.text.casefold()
        ok = status_ok and brand_ok
        if not status_ok:
            detail = f"{path} returned HTTP {response.status_code}."
        elif not brand_ok:
            detail = f"{path} did not contain the DUFYND brand marker."
        else:
            detail = f"{path} is reachable and branded as DUFYND."
        return SmokeCheck(
            name=name,
            ok=ok,
            status_code=response.status_code,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name=name,
            ok=False,
            status_code=None,
            detail=f"{path} request failed: {exc.__class__.__name__}",
        )


def _check_robots_policy(
    client: httpx.Client,
    storefront_url: str,
    *,
    expected_indexing: str,
) -> SmokeCheck:
    url = f"{storefront_url}/robots.txt"
    try:
        response = client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return SmokeCheck(
                name="robots_policy",
                ok=False,
                status_code=response.status_code,
                detail=f"robots.txt returned HTTP {response.status_code}.",
            )

        lines = [
            line.strip().casefold()
            for line in response.text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        has_user_agent = any(line.startswith("user-agent:") for line in lines)
        disallow_all = "disallow: /" in lines
        allow_all = "allow: /" in lines
        has_sitemap = any(line.startswith("sitemap:") for line in lines)

        if has_user_agent and disallow_all:
            detected = "disabled"
        elif has_user_agent and allow_all and has_sitemap:
            detected = "enabled"
        else:
            detected = "unknown"

        expected_ok = expected_indexing == "any" or detected == expected_indexing
        ok = detected != "unknown" and expected_ok

        if detected == "unknown":
            detail = "robots.txt does not match DUFYND's supported launch policies."
        elif not expected_ok:
            detail = (
                f"robots.txt reports indexing {detected}, but {expected_indexing} was expected."
            )
        else:
            detail = f"robots.txt is valid; search indexing is {detected}."

        return SmokeCheck(
            name="robots_policy",
            ok=ok,
            status_code=response.status_code,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="robots_policy",
            ok=False,
            status_code=None,
            detail=f"robots.txt request failed: {exc.__class__.__name__}",
        )


def _check_sitemap(
    client: httpx.Client,
    storefront_url: str,
) -> SmokeCheck:
    url = f"{storefront_url}/sitemap.xml"
    try:
        response = client.get(url, follow_redirects=True)
        status_ok = response.status_code < 400
        body = response.text.casefold()
        xml_ok = "<urlset" in body
        canonical_ok = storefront_url.casefold() in body
        ok = status_ok and xml_ok and canonical_ok

        if not status_ok:
            detail = f"sitemap.xml returned HTTP {response.status_code}."
        elif not xml_ok:
            detail = "sitemap.xml is missing the urlset root."
        elif not canonical_ok:
            detail = "sitemap.xml does not contain the canonical DUFYND site URL."
        else:
            detail = "sitemap.xml is reachable and uses the canonical DUFYND site URL."

        return SmokeCheck(
            name="sitemap",
            ok=ok,
            status_code=response.status_code,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="sitemap",
            ok=False,
            status_code=None,
            detail=f"sitemap.xml request failed: {exc.__class__.__name__}",
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

        store = payload.get("store")
        products = payload.get("products")
        skills = payload.get("skills")
        model = payload.get("model")
        ok = (
            payload.get("ok") is True
            and store == "DUFYND"
            and isinstance(products, int)
            and products > 0
            and isinstance(skills, list)
            and isinstance(model, str)
            and bool(model)
        )
        return SmokeCheck(
            name="api_health",
            ok=ok,
            status_code=response.status_code,
            detail=(
                f"DUFYND API health contract is valid ({products} products)."
                if ok
                else (
                    "API health contract is stale or misbranded: "
                    f"store={store!r}, products={products!r}."
                )
            ),
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="api_health",
            ok=False,
            status_code=None,
            detail=f"API health request failed: {exc.__class__.__name__}",
        )


def _check_product_catalog(
    client: httpx.Client,
    api_url: str,
) -> tuple[SmokeCheck, str | None]:
    url = f"{api_url}/api/products"
    try:
        response = client.get(
            url,
            params={"category": "fragrance", "limit": 1},
            follow_redirects=True,
        )
        if response.status_code >= 400:
            return (
                SmokeCheck(
                    name="product_catalog",
                    ok=False,
                    status_code=response.status_code,
                    detail=f"Product catalog returned HTTP {response.status_code}.",
                ),
                None,
            )

        try:
            payload = response.json()
        except ValueError:
            return (
                SmokeCheck(
                    name="product_catalog",
                    ok=False,
                    status_code=response.status_code,
                    detail="Product catalog did not return JSON.",
                ),
                None,
            )

        products = payload.get("products")
        first = products[0] if isinstance(products, list) and products else None
        product_id = first.get("product_id") if isinstance(first, dict) else None
        ok = isinstance(product_id, str) and product_id.startswith("SC-")
        return (
            SmokeCheck(
                name="product_catalog",
                ok=ok,
                status_code=response.status_code,
                detail=(
                    f"Fragrance catalog contract is valid; sample={product_id}."
                    if ok
                    else "Fragrance catalog did not return a DUFYND fragrance product."
                ),
            ),
            product_id if ok else None,
        )
    except httpx.HTTPError as exc:
        return (
            SmokeCheck(
                name="product_catalog",
                ok=False,
                status_code=None,
                detail=f"Product catalog request failed: {exc.__class__.__name__}",
            ),
            None,
        )


def _check_product_detail(
    client: httpx.Client,
    api_url: str,
    product_id: str | None,
) -> SmokeCheck:
    if not product_id:
        return SmokeCheck(
            name="product_detail",
            ok=False,
            status_code=None,
            detail="Product detail was not checked because no valid catalog product was available.",
        )

    encoded_product_id = quote(product_id, safe="")
    url = f"{api_url}/api/products/{encoded_product_id}"
    try:
        response = client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            return SmokeCheck(
                name="product_detail",
                ok=False,
                status_code=response.status_code,
                detail=f"Product detail returned HTTP {response.status_code}.",
            )

        try:
            payload = response.json()
        except ValueError:
            return SmokeCheck(
                name="product_detail",
                ok=False,
                status_code=response.status_code,
                detail="Product detail did not return JSON.",
            )

        ok = payload.get("product_id") == product_id
        return SmokeCheck(
            name="product_detail",
            ok=ok,
            status_code=response.status_code,
            detail=(
                f"Product detail contract is valid for {product_id}."
                if ok
                else (
                    "Product detail identity mismatch: "
                    f"expected={product_id!r}, received={payload.get('product_id')!r}."
                )
            ),
        )
    except httpx.HTTPError as exc:
        return SmokeCheck(
            name="product_detail",
            ok=False,
            status_code=None,
            detail=f"Product detail request failed: {exc.__class__.__name__}",
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
    expected_indexing: str = "any",
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
    if expected_indexing not in {"any", "enabled", "disabled"}:
        raise ValueError("expected_indexing must be any, enabled or disabled")

    with httpx.Client(
        timeout=timeout_seconds,
        transport=transport,
    ) as client:
        product_catalog_check, sample_product_id = _check_product_catalog(client, api)
        checks = [
            _check_storefront(client, storefront),
            _check_storefront_route(
                client,
                storefront,
                path="/duftfinder",
                name="storefront_duftfinder",
            ),
            _check_storefront_route(
                client,
                storefront,
                path="/vergleich",
                name="storefront_vergleich",
            ),
            _check_storefront_route(
                client,
                storefront,
                path="/parfum-alternativen",
                name="storefront_alternatives",
            ),
            _check_storefront_route(
                client,
                storefront,
                path="/impressum",
                name="storefront_impressum",
            ),
            _check_storefront_route(
                client,
                storefront,
                path="/datenschutz",
                name="storefront_datenschutz",
            ),
            _check_storefront_route(
                client,
                storefront,
                path="/transparenz",
                name="storefront_transparenz",
            ),
            _check_robots_policy(
                client,
                storefront,
                expected_indexing=expected_indexing,
            ),
            _check_sitemap(client, storefront),
            _check_api_health(client, api),
            product_catalog_check,
            _check_product_detail(client, api, sample_product_id),
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
        "--expected-indexing",
        choices=("any", "enabled", "disabled"),
        default="any",
        help=(
            "Optionally assert the live robots.txt indexing policy. "
            "The default only validates that the policy is internally recognized."
        ),
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
            expected_indexing=args.expected_indexing,
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
