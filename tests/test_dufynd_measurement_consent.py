"""Execute the real endpoint function bodies without importing the live app host.

All stores, trackers and redirects are in-memory fixtures. No HTTP request is
sent to Supabase, an affiliate network, a merchant, or the deployed application.
This is not an ASGI/CORS or complete application-integration test.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "api/main.py" if (ROOT / "api/main.py").exists() else ROOT / "examples/retail/api/main.py"
BASE_SOURCE = ROOT / "baseline/main.py" if (ROOT / "baseline/main.py").exists() else ROOT / "tests/fixtures/privacy26-base-main.py"


class Redirect:
    def __init__(self, url: str, status_code: int, headers: dict | None = None):
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class Tasks:
    def __init__(self):
        self.items = []

    def add_task(self, function, **kwargs):
        self.items.append((function, kwargs))


def environment(path: Path):
    tree = ast.parse(path.read_text())
    functions = []
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name in {
            "merchant_partner_clickout", "merchant_clickout", "analytics_event"
        }:
            node.decorator_list = []
            functions.append(node)
    assert len(functions) == 3
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *functions],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    records = {"analytics": [], "clickouts": [], "target_calls": []}
    offer = SimpleNamespace(product_id="SC-RABANNE-1-MILLION-EDT-100", merchant_id="perfumetrader", offer_id="fixture-offer")
    partner = SimpleNamespace(merchant_id="perfumetrader", affiliate_url="https://affiliate.invalid/base?publisher=synthetic")

    async def analytics_record(**kwargs):
        records["analytics"].append(kwargs)
        return "fixture-event", "fixture-memory"

    def clickout_record(_offer, **kwargs):
        records["clickouts"].append(kwargs)
        return "fixture-click-id"

    def target(_offer, **kwargs):
        records["target_calls"].append(kwargs)
        return "https://affiliate.invalid/base?publisher=synthetic" + ("&synthetic_ref=measured" if kwargs else "")

    context = {
        "RedirectResponse": Redirect, "HTTPException": HTTPException, "uuid4": uuid4,
        "partner_store": SimpleNamespace(eligible=lambda key: partner if key == "perfumetrader" else None),
        "offer_store": SimpleNamespace(eligible_offer=lambda key: offer if key == "fixture-offer" else None),
        "_live_dufynd_offer_product": lambda _key: True,
        "offer_clickout_target": target,
        "partner_clickout_url": lambda _partner, **kw: partner.affiliate_url + "&synthetic_ref=measured",
        "sanitize_attribution_identifier": lambda value: value,
        "analytics_tracker": SimpleNamespace(record=analytics_record),
        "clickout_tracker": SimpleNamespace(record=clickout_record),
    }
    exec(compile(module, str(path), "exec"), context)
    return context, records


def request():
    return SimpleNamespace(
        analytics_session_id="synthetic_analytics_123456", event_id=None,
        event="page_view", internal_qa=True, product_id=None, source="fixture",
        acquisition_source="instagram", campaign_id="synthetic", content_id=None,
        search_term=None, result_count=None, surface="fixture", related_product_id=None,
        item_position=None,
    )


async def run():
    cases = 0
    for choice in [None, "denied", "denied-v1", "true", "granted", "GRANTED-V1", "granted-v0", ""]:
        for kind, key in [("merchant_partner_clickout", "perfumetrader"), ("merchant_clickout", "fixture-offer")]:
            ctx, records = environment(APP_SOURCE)
            tasks = Tasks()
            out = await ctx[kind](key, tasks, src="instagram", cmp="stale", sid="stale_identifier_123456", qa=True, measurement=choice)
            assert out.status_code == 302
            assert out.url == "https://affiliate.invalid/base?publisher=synthetic"
            assert out.headers == {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
            assert not records["analytics"] and not records["clickouts"] and not tasks.items
            cases += 1
        ctx, records = environment(APP_SOURCE)
        out = await ctx["analytics_event"](request(), SimpleNamespace(session_id="functional_session"), measurement=choice)
        assert out == {"ok": True, "recorded": False, "storage": "disabled"}
        assert not records["analytics"]
        cases += 1
    for kind, key in [("merchant_partner_clickout", "perfumetrader"), ("merchant_clickout", "fixture-offer")]:
        ctx, records = environment(APP_SOURCE)
        tasks = Tasks()
        out = await ctx[kind](key, tasks, src="instagram", cmp="synthetic", sid="synthetic_session", measurement="granted-v1")
        assert out.status_code == 302 and "synthetic_ref=measured" in out.url
        assert len(tasks.items) == 1
        assert tasks.items[0][1]["campaign_id"] == "synthetic"
        assert bool(records["clickouts"]) == (kind == "merchant_clickout")
        cases += 1
    ctx, records = environment(APP_SOURCE)
    out = await ctx["analytics_event"](request(), SimpleNamespace(session_id="functional_session"), measurement="granted-v1")
    assert out["ok"] and out["event_id"] == "fixture-event"
    assert len(records["analytics"]) == 1
    cases += 1
    for kind in ["merchant_partner_clickout", "merchant_clickout"]:
        for choice in [None, "granted-v1"]:
            ctx, records = environment(APP_SOURCE)
            try:
                await ctx[kind]("unavailable", Tasks(), measurement=choice)
                raise AssertionError("unavailable merchant/offer must not redirect")
            except HTTPException as error:
                assert error.status_code == 404
            assert not records["analytics"] and not records["clickouts"]
            cases += 1
    # Red control: actual parent records optional measurement with no consent signal.
    ctx, records = environment(BASE_SOURCE)
    tasks = Tasks()
    await ctx["merchant_clickout"]("fixture-offer", tasks, qa=True)
    assert len(records["clickouts"]) == 1 and len(tasks.items) == 1
    print(json.dumps({"status": "PASS", "cases": cases, "negative_control": "parent logs absent-consent clickout", "external_requests": 0, "scope": "actual extracted endpoint bodies; synthetic stores, no full app/ASGI"}, indent=2))


def test_measurement_gate_endpoint_bodies():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
